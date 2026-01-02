#!/usr/bin/env python3
"""
Processeur principal du pipeline Anomaly Flow.

Ce module est le cœur du système. Il :
    1. Consomme les événements depuis Kafka (topic: events)
    2. Valide le schéma avec Pydantic
    3. Exécute les contrôles Data Quality
    4. Détecte les anomalies avec Half-Space Trees
    5. Expose les métriques pour Prometheus
    6. Publie les alertes sur Kafka (topic: alerts)

Usage:
    KAFKA_BROKER=localhost:9092 python -m src.processor

Métriques exposées sur :8000/metrics :
    - processed_records_total: Nombre total d'événements traités
    - dq_records_total: Compteur d'erreurs DQ par type
    - anomalies_total: Nombre d'anomalies détectées
    - last_anomaly_score: Dernier score d'anomalie calculé
    - anomaly_threshold: Seuil dynamique actuel
    - event_value: Histogramme de la distribution des valeurs
"""

import json
import time
import threading
from typing import Dict

import structlog
from kafka import KafkaConsumer, KafkaProducer
from prometheus_client import Counter, Gauge, Histogram, start_http_server

from .config import settings
from .schema import Event
from .quality import dq_checks
from .anomaly import StreamingAnomalyDetector

# ═══════════════════════════════════════════════════════════════════════════
# Configuration du logging structuré
# Les logs sont formatés en JSON pour faciliter l'analyse
# ═══════════════════════════════════════════════════════════════════════════
log = structlog.get_logger()

# ═══════════════════════════════════════════════════════════════════════════
# Métriques Prometheus
# Ces compteurs et jauges sont exposés sur :8000/metrics
# ═══════════════════════════════════════════════════════════════════════════

# Compteur du nombre total d'événements traités
processed_records_total = Counter(
    "processed_records_total",
    "Nombre total d'événements traités par le processor"
)

# Compteur des résultats Data Quality (par outcome et type de contrôle)
dq_records_total = Counter(
    "dq_records_total",
    "Résultats des contrôles Data Quality",
    labelnames=("outcome", "check")  # outcome: ok/invalid, check: schema/required/range/freshness
)

# Compteur du nombre total d'anomalies détectées
anomalies_total = Counter(
    "anomalies_total",
    "Nombre total d'anomalies détectées par le modèle HST"
)

# Jauge du dernier score d'anomalie calculé
last_anomaly_score = Gauge(
    "last_anomaly_score",
    "Dernier score d'anomalie calculé (streaming)"
)

# Jauge du seuil dynamique d'anomalie (quantile 99.5%)
threshold_gauge = Gauge(
    "anomaly_threshold",
    "Seuil dynamique d'anomalie (basé sur le quantile des scores)"
)

# Histogramme de la distribution des valeurs
# Permet de visualiser la répartition des mesures
value_hist = Histogram(
    "event_value",
    "Distribution des valeurs d'événements (event.value)",
    buckets=(-100, -50, -20, -10, -5, 0, 5, 10, 20, 50, 100)
)


def to_features(evt: Dict) -> Dict[str, float]:
    """
    Extrait les features numériques d'un événement pour le détecteur.
    
    Le modèle Half-Space Trees travaille sur des vecteurs numériques.
    Cette fonction sélectionne les champs pertinents pour la détection.
    
    Args:
        evt: Dictionnaire de l'événement validé
    
    Returns:
        Dictionnaire des features numériques:
            - value: Valeur principale (obligatoire)
            - temperature: Température (optionnel)
    """
    x = {
        "value": float(evt.get("value", 0.0)),
    }
    
    # Ajouter la température si présente
    if evt.get("temperature") is not None:
        x["temperature"] = float(evt["temperature"])
    
    return x


def run_processor():
    """
    Boucle principale du processor.
    
    Cette fonction:
        1. Démarre le serveur HTTP pour les métriques Prometheus
        2. Se connecte à Kafka (consumer + producer)
        3. Initialise le détecteur d'anomalies
        4. Traite chaque message en boucle infinie
    """
    # ═══════════════════════════════════════════════════════════════════
    # Démarrage du serveur de métriques Prometheus
    # Accessible sur http://localhost:8000/metrics
    # ═══════════════════════════════════════════════════════════════════
    start_http_server(8000)
    log.info("metrics_server_started", port=8000)

    # ═══════════════════════════════════════════════════════════════════
    # Configuration du consumer Kafka
    # - group_id: Permet le load balancing entre plusieurs processors
    # - auto_offset_reset: Lit depuis le début si pas d'offset sauvegardé
    # - enable_auto_commit: Commit automatique des offsets
    # ═══════════════════════════════════════════════════════════════════
    consumer = KafkaConsumer(
        settings.topic_events,
        bootstrap_servers=[settings.kafka_broker],
        group_id="processor",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        key_deserializer=lambda v: v.decode("utf-8") if v else None,
        max_poll_records=100,  # Limite le nombre de messages par poll
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # Configuration du producer Kafka pour les alertes
    # - linger_ms=10: Regroupe les messages pendant 10ms (optimisation)
    # ═══════════════════════════════════════════════════════════════════
    producer = KafkaProducer(
        bootstrap_servers=[settings.kafka_broker],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda v: v.encode("utf-8") if v else None,
        linger_ms=10
    )

    # ═══════════════════════════════════════════════════════════════════
    # Initialisation du détecteur d'anomalies Half-Space Trees
    # Les paramètres sont définis dans config.py
    # ═══════════════════════════════════════════════════════════════════
    det = StreamingAnomalyDetector(
        n_trees=settings.hst_n_trees,
        height=settings.hst_height,
        window_size=settings.hst_window_size,
        quantile_p=settings.quantile_p
    )

    log.info("processor_started", broker=settings.kafka_broker, topic=settings.topic_events)

    # ═══════════════════════════════════════════════════════════════════
    # Boucle principale de traitement
    # Traite chaque message Kafka un par un
    # ═══════════════════════════════════════════════════════════════════
    for msg in consumer:
        processed_records_total.inc()
        evt_raw = msg.value

        # ═══════════════════════════════════════════════════════════════
        # Étape 1: Validation du schéma avec Pydantic
        # Rejette les messages mal formés
        # ═══════════════════════════════════════════════════════════════
        try:
            evt = Event(**evt_raw).model_dump()
        except Exception as e:
            dq_records_total.labels("invalid", "schema").inc()
            log.warning("schema_invalid", error=str(e), raw_event=evt_raw)
            continue  # Passe au message suivant

        # ═══════════════════════════════════════════════════════════════
        # Étape 2: Contrôles Data Quality
        # Vérifie les règles métier (plages, fraîcheur, etc.)
        # ═══════════════════════════════════════════════════════════════
        issues = dq_checks(evt)
        if issues:
            # Incrémenter les compteurs pour chaque problème détecté
            for check, _ in issues:
                dq_records_total.labels("invalid", check).inc()
        else:
            dq_records_total.labels("ok", "all").inc()

        # ═══════════════════════════════════════════════════════════════
        # Étape 3: Enregistrer la valeur dans l'histogramme
        # Permet de visualiser la distribution dans Prometheus/Grafana
        # ═══════════════════════════════════════════════════════════════
        value_hist.observe(float(evt["value"]))

        # ═══════════════════════════════════════════════════════════════
        # Étape 4: Détection d'anomalies
        # Calcule le score et vérifie s'il dépasse le seuil dynamique
        # ═══════════════════════════════════════════════════════════════
        x = to_features(evt)
        score, thr, is_anom = det.score_and_update(x)
        
        # Mise à jour des métriques Prometheus
        last_anomaly_score.set(score)
        threshold_gauge.set(thr)

        # ═══════════════════════════════════════════════════════════════
        # Étape 5: Publication des alertes si anomalie détectée
        # Les alertes sont envoyées sur le topic 'alerts'
        # ═══════════════════════════════════════════════════════════════
        if is_anom:
            anomalies_total.inc()
            
            # Construction du payload de l'alerte
            alert_payload = {
                "type": "anomaly",
                "sensor_id": evt["sensor_id"],
                "ts": evt["ts"],
                "score": score,
                "threshold": thr,
                "features": x,
                "dq_issues": issues,
            }
            
            try:
                producer.send(
                    settings.topic_alerts,
                    key=evt["sensor_id"],
                    value=alert_payload
                )
            except Exception as pe:
                log.error("alert_send_failed", error=str(pe), alert=alert_payload)

        # ═══════════════════════════════════════════════════════════════
        # Étape 6: Logging de progression (tous les 100 événements)
        # Permet de suivre l'avancement du traitement
        # ═══════════════════════════════════════════════════════════════
        if processed_records_total._value.get() % 100 == 0:
            log.info(
                "progress",
                processed=int(processed_records_total._value.get()),
                anomalies=int(anomalies_total._value.get()),
                last_score=score,
                threshold=thr
            )


if __name__ == "__main__":
    # Point d'entrée du script
    # Lancer dans le thread principal pour permettre les interruptions
    run_processor()
