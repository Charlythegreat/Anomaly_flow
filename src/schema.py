#!/usr/bin/env python3
"""
Schéma de validation des événements avec Pydantic.

Ce module définit la structure attendue des événements IoT reçus via Kafka.
Pydantic valide automatiquement les types et les contraintes lors de la
désérialisation, garantissant l'intégrité des données en entrée.

Exemple d'événement valide:
    {
        "sensor_id": "sensor-0",
        "ts": 1704186000.123,
        "value": 1.2345,
        "temperature": 24.5,
        "status": "OK"
    }
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
import time


class Event(BaseModel):
    """
    Modèle Pydantic représentant un événement de capteur IoT.
    
    Attributs:
        sensor_id: Identifiant unique du capteur (obligatoire, non vide)
        ts: Timestamp Unix en secondes (obligatoire)
        value: Valeur mesurée par le capteur (obligatoire)
        temperature: Température ambiante en °C (optionnel)
        status: État du capteur - OK, WARN, ou FAIL (optionnel, défaut: OK)
    
    Validations automatiques:
        - sensor_id doit avoir au moins 1 caractère
        - ts doit être dans une fenêtre de ±24h par rapport à maintenant
        - status doit être une valeur parmi {OK, WARN, FAIL}
    """
    
    # ═══════════════════════════════════════════════════════════════════
    # Champs obligatoires
    # ═══════════════════════════════════════════════════════════════════
    sensor_id: str = Field(
        min_length=1,
        description="Identifiant unique du capteur IoT"
    )
    ts: float = Field(
        description="Timestamp Unix en secondes (epoch)"
    )
    value: float = Field(
        description="Valeur principale mesurée par le capteur"
    )
    
    # ═══════════════════════════════════════════════════════════════════
    # Champs optionnels
    # ═══════════════════════════════════════════════════════════════════
    temperature: Optional[float] = Field(
        default=None,
        description="Température ambiante en degrés Celsius"
    )
    status: Optional[str] = Field(
        default="OK",
        description="État du capteur: OK, WARN, ou FAIL"
    )

    @field_validator("ts")
    @classmethod
    def ts_reasonable(cls, v: float) -> float:
        """
        Valide que le timestamp est raisonnable.
        
        Rejette les événements avec un timestamp trop ancien ou futur
        (±24 heures par rapport à l'heure actuelle).
        
        Note: Cette validation basique évite les erreurs grossières.
        Le contrôle de fraîcheur plus strict (5 min) est fait dans quality.py
        """
        now = time.time()
        one_day = 86400  # 24 heures en secondes
        
        if v < now - one_day:
            raise ValueError(f"Timestamp trop ancien (> 24h): {v}")
        if v > now + one_day:
            raise ValueError(f"Timestamp dans le futur (> 24h): {v}")
        
        return v

    @field_validator("status")
    @classmethod
    def status_ok(cls, v: str) -> str:
        """
        Valide que le status est une valeur autorisée.
        
        Valeurs acceptées: OK, WARN, FAIL
        Permet de tracker l'état de santé du capteur lui-même.
        """
        allowed = {"OK", "WARN", "FAIL"}
        
        if v is not None and v not in allowed:
            raise ValueError(f"Status invalide '{v}'. Valeurs acceptées: {allowed}")
        
        return v
