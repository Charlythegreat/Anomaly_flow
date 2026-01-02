#!/usr/bin/env python3
"""
Générateur d'événements IoT simulés.

Ce script simule des capteurs IoT en produisant des événements JSON
vers Kafka. Il génère environ 20 événements/seconde avec :
    - Des valeurs normales (majorité des cas)
    - Des anomalies injectées aléatoirement (~2%)
    - Des erreurs de qualité de données (~1.5%)

Utile pour tester le pipeline sans infrastructure IoT réelle.

Usage:
    KAFKA_BROKER=localhost:9092 python -m src.generator
"""

import json
import os
import random
import time
from typing import Dict

from kafka import KafkaProducer

# ═══════════════════════════════════════════════════════════════════════════
# Configuration via variables d'environnement
# ═══════════════════════════════════════════════════════════════════════════
BROKER = os.getenv("KAFKA_BROKER", "redpanda:9092")
TOPIC = os.getenv("TOPIC_EVENTS", "events")


def make_event(i: int) -> Dict:
    """
    Génère un événement IoT simulé.
    
    Args:
        i: Index de l'événement (utilisé pour répartir entre capteurs)
    
    Returns:
        Dictionnaire représentant l'événement avec les champs:
            - sensor_id: Identifiant du capteur (sensor-0 à sensor-4)
            - ts: Timestamp Unix
            - value: Valeur mesurée
            - temperature: Température ambiante
            - status: État du capteur
    
    Injections d'anomalies et erreurs:
        - 2%: Anomalie de valeur (offset de ±25 ou ±50)
        - 1%: Anomalie de température (offset de ±20 ou ±30)
        - 0.5%: Champ 'value' manquant (erreur DQ)
        - 0.5%: Valeur hors plage (9999)
        - 0.5%: Timestamp ancien (3 jours)
    """
    # ═══════════════════════════════════════════════════════════════════
    # Génération de la valeur de base avec un léger drift temporel
    # Le drift simule une variation naturelle au cours du temps
    # ═══════════════════════════════════════════════════════════════════
    base = random.uniform(-2.0, 2.0)
    drift = 0.02 * time.time() % 1.0  # Dérive lente
    value = base + drift

    # ═══════════════════════════════════════════════════════════════════
    # Injection d'anomalies sur la valeur (2% des cas)
    # Ces anomalies devraient être détectées par le modèle HST
    # ═══════════════════════════════════════════════════════════════════
    if random.random() < 0.02:
        value += random.choice([25, -25, 50, -50])

    # ═══════════════════════════════════════════════════════════════════
    # Génération de la température avec injection d'anomalies (1%)
    # Simule une température ambiante autour de 25°C
    # ═══════════════════════════════════════════════════════════════════
    temp = 25.0 + random.uniform(-1.5, 1.5)
    if random.random() < 0.01:
        temp += random.choice([20, -30])  # Température aberrante

    # ═══════════════════════════════════════════════════════════════════
    # Construction de l'événement de base
    # Le sensor_id alterne entre 5 capteurs virtuels
    # ═══════════════════════════════════════════════════════════════════
    evt = {
        "sensor_id": f"sensor-{i % 5}",
        "ts": time.time(),
        "value": round(value, 4),
        "temperature": round(temp, 2),
        "status": "OK",
    }

    # ═══════════════════════════════════════════════════════════════════
    # Injection d'erreurs Data Quality (~1.5% des cas)
    # Ces erreurs testent les contrôles DQ du processor
    # ═══════════════════════════════════════════════════════════════════
    r = random.random()
    if r < 0.005:
        # Champ obligatoire manquant → erreur DQ "required"
        evt.pop("value")
    elif r < 0.010:
        # Valeur hors plage → erreur DQ "range_value"
        evt["value"] = 9999
    elif r < 0.015:
        # Timestamp ancien (3 jours) → erreur DQ "freshness"
        evt["ts"] = time.time() - 3600 * 24 * 3

    return evt


def main():
    """
    Point d'entrée du générateur.
    
    Crée un producteur Kafka et envoie des événements en boucle infinie
    à raison d'environ 20 événements par seconde (sleep de 0.05s).
    """
    # ═══════════════════════════════════════════════════════════════════
    # Configuration du producteur Kafka
    # - linger_ms=5: Attend 5ms pour grouper les messages (optimisation)
    # ═══════════════════════════════════════════════════════════════════
    producer = KafkaProducer(
        bootstrap_servers=[BROKER],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda v: v.encode("utf-8"),
        linger_ms=5
    )
    
    i = 0
    print(f"Générateur connecté à {BROKER}, topic={TOPIC}")
    print("Envoi d'événements en cours... (Ctrl+C pour arrêter)")
    
    # ═══════════════════════════════════════════════════════════════════
    # Boucle principale de génération
    # ~20 événements/seconde
    # ═══════════════════════════════════════════════════════════════════
    while True:
        evt = make_event(i)
        key = evt.get("sensor_id", f"k-{i}")
        
        try:
            producer.send(TOPIC, key=key, value=evt)
        except Exception as e:
            print(f"Erreur d'envoi: {e}")
        
        i += 1
        time.sleep(0.05)  # ~20 événements/seconde


if __name__ == "__main__":
    main()
