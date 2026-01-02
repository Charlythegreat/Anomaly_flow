#!/usr/bin/env python3
"""
Configuration centralisée du projet Anomaly Flow.

Ce module contient tous les paramètres configurables du système :
- Connexion Kafka (broker, topics)
- Seuils de qualité des données (plages de valeurs acceptables)
- Paramètres de détection d'anomalies (Half-Space Trees)

Les valeurs peuvent être surchargées via des variables d'environnement.
"""

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """
    Paramètres de configuration du système.
    
    Attributs:
        kafka_broker: Adresse du broker Kafka (ex: localhost:9092)
        topic_events: Topic Kafka pour les événements entrants
        topic_alerts: Topic Kafka pour les alertes d'anomalies
        value_range: Plage acceptable pour le champ 'value' (min, max)
        temperature_range: Plage acceptable pour la température (min, max)
        freshness_max_lag_sec: Délai max avant qu'un événement soit considéré périmé
        quantile_p: Percentile pour le seuil dynamique d'anomalie (0.995 = 99.5%)
        hst_n_trees: Nombre d'arbres dans la forêt Half-Space Trees
        hst_height: Hauteur maximale de chaque arbre
        hst_window_size: Taille de la fenêtre glissante pour l'apprentissage
    """
    
    # ═══════════════════════════════════════════════════════════════════
    # Configuration Kafka
    # ═══════════════════════════════════════════════════════════════════
    kafka_broker: str = os.getenv("KAFKA_BROKER", "redpanda:9092")
    topic_events: str = os.getenv("TOPIC_EVENTS", "events")
    topic_alerts: str = os.getenv("TOPIC_ALERTS", "alerts")

    # ═══════════════════════════════════════════════════════════════════
    # Seuils Data Quality (DQ)
    # Ces valeurs définissent les plages acceptables pour chaque champ
    # ═══════════════════════════════════════════════════════════════════
    value_range = (-100.0, 100.0)           # Plage valide pour 'value'
    temperature_range = (-20.0, 80.0)       # Plage valide pour 'temperature' (°C)
    freshness_max_lag_sec: float = 300.0    # 5 minutes max de retard

    # ═══════════════════════════════════════════════════════════════════
    # Paramètres de détection d'anomalies (Half-Space Trees)
    # 
    # L'algorithme HST est une forêt d'arbres aléatoires qui partitionne
    # l'espace des features. Les points dans des régions peu denses
    # (peu de voisins) sont considérés comme des anomalies.
    # ═══════════════════════════════════════════════════════════════════
    quantile_p: float = 0.995       # Seuil dynamique au 99.5ème percentile
    hst_n_trees: int = 25           # Nombre d'arbres (plus = plus précis mais plus lent)
    hst_height: int = 15            # Profondeur des arbres (affecte la granularité)
    hst_window_size: int = 250      # Fenêtre d'apprentissage (événements récents)


# Instance globale des paramètres
# Utilisée dans tout le projet via: from .config import settings
settings = Settings()
