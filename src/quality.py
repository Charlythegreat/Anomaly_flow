#!/usr/bin/env python3
"""
Contrôles de qualité des données (Data Quality - DQ).

Ce module implémente les vérifications DQ exécutées sur chaque événement
APRÈS la validation du schéma Pydantic. Ces contrôles détectent les
problèmes de données qui passent la validation de schéma mais sont
néanmoins incorrects ou suspects.

Contrôles implémentés:
    1. required    - Champs obligatoires présents (sensor_id, ts, value)
    2. range_value - Valeur dans la plage acceptable [-100, 100]
    3. range_temperature - Température dans la plage acceptable [-20°C, 80°C]
    4. freshness   - Événement pas trop ancien (< 5 minutes par défaut)

Chaque contrôle retourne un tuple (nom_du_contrôle, message_erreur).
"""

from typing import Dict, List, Tuple
import time
from .config import settings

# Type alias pour la lisibilité
# Un "Issue" est un tuple (nom_du_contrôle, description_du_problème)
Issue = Tuple[str, str]


def dq_checks(evt: Dict) -> List[Issue]:
    """
    Exécute tous les contrôles Data Quality sur un événement.
    
    Args:
        evt: Dictionnaire représentant l'événement à valider
             (déjà passé par la validation Pydantic)
    
    Returns:
        Liste des problèmes détectés. Liste vide si tout est OK.
        Chaque problème est un tuple (nom_contrôle, message).
    
    Exemple:
        >>> evt = {"sensor_id": "s1", "ts": old_timestamp, "value": 9999}
        >>> issues = dq_checks(evt)
        >>> print(issues)
        [("range_value", "value 9999 out of [-100,100]"),
         ("freshness", "lag 3600.0s exceeds 300.0s")]
    """
    issues: List[Issue] = []

    # ═══════════════════════════════════════════════════════════════════
    # Contrôle 1: Champs obligatoires
    # Vérifie que les champs essentiels sont présents et non-None
    # ═══════════════════════════════════════════════════════════════════
    required_fields = ["sensor_id", "ts", "value"]
    for field in required_fields:
        if evt.get(field) is None:
            issues.append(("required", f"Champ manquant: {field}"))

    # ═══════════════════════════════════════════════════════════════════
    # Contrôle 2: Plage de valeurs pour 'value'
    # Détecte les valeurs aberrantes (ex: 9999, -9999)
    # ═══════════════════════════════════════════════════════════════════
    value = evt.get("value")
    if value is not None:
        min_val, max_val = settings.value_range
        if not (min_val <= float(value) <= max_val):
            issues.append((
                "range_value",
                f"value {value} hors de la plage [{min_val}, {max_val}]"
            ))

    # ═══════════════════════════════════════════════════════════════════
    # Contrôle 3: Plage de valeurs pour 'temperature'
    # Détecte les températures physiquement impossibles
    # ═══════════════════════════════════════════════════════════════════
    temperature = evt.get("temperature")
    if temperature is not None:
        min_temp, max_temp = settings.temperature_range
        if not (min_temp <= float(temperature) <= max_temp):
            issues.append((
                "range_temperature",
                f"temperature {temperature}°C hors de la plage [{min_temp}, {max_temp}]"
            ))

    # ═══════════════════════════════════════════════════════════════════
    # Contrôle 4: Fraîcheur des données
    # Rejette les événements trop anciens (données périmées)
    # Utile pour détecter des problèmes de synchronisation ou de replay
    # ═══════════════════════════════════════════════════════════════════
    timestamp = evt.get("ts")
    if timestamp is not None:
        lag_seconds = time.time() - float(timestamp)
        max_lag = settings.freshness_max_lag_sec
        
        if lag_seconds > max_lag:
            issues.append((
                "freshness",
                f"Retard de {lag_seconds:.1f}s (max autorisé: {max_lag}s)"
            ))

    return issues
