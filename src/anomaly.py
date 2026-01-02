#!/usr/bin/env python3
"""
Détection d'anomalies en streaming avec Half-Space Trees.

Ce module implémente un détecteur d'anomalies en ligne (online learning)
utilisant l'algorithme Half-Space Trees (HST) de la bibliothèque River.

Caractéristiques:
    - Apprentissage en continu : le modèle s'adapte aux nouvelles données
    - Pas besoin d'entraînement préalable (cold start possible)
    - Complexité O(1) par événement
    - Seuil dynamique basé sur le quantile des scores historiques
    - Non supervisé : pas besoin de données étiquetées

Principe de fonctionnement:
    1. Chaque arbre partitionne l'espace des features aléatoirement
    2. Les points "normaux" tombent dans des régions denses (beaucoup de voisins)
    3. Les anomalies tombent dans des régions peu peuplées (peu de voisins)
    4. Le score final = moyenne des scores de tous les arbres

Référence:
    Tan, S. C., Ting, K. M., & Liu, T. F. (2011).
    Fast anomaly detection for streaming data.
"""

from river import anomaly, stats
from typing import Dict, Tuple


class StreamingAnomalyDetector:
    """
    Détecteur d'anomalies streaming avec seuil dynamique.
    
    Utilise Half-Space Trees pour le scoring et un quantile
    streaming pour adapter automatiquement le seuil de détection.
    
    Attributs:
        model: Modèle Half-Space Trees de River
        threshold: Estimateur de quantile streaming pour le seuil
        last_score: Dernier score calculé (pour debugging)
    
    Exemple:
        >>> detector = StreamingAnomalyDetector(n_trees=25, height=15, 
        ...                                      window_size=250, quantile_p=0.995)
        >>> for event in events:
        ...     x = {"value": event["value"], "temperature": event["temp"]}
        ...     score, threshold, is_anomaly = detector.score_and_update(x)
        ...     if is_anomaly:
        ...         print(f"Anomalie détectée! Score: {score:.4f}")
    """
    
    def __init__(
        self,
        n_trees: int,
        height: int,
        window_size: int,
        quantile_p: float
    ):
        """
        Initialise le détecteur d'anomalies.
        
        Args:
            n_trees: Nombre d'arbres dans la forêt
                     Plus de trees = meilleure précision mais plus lent
                     Recommandé: 10-50
            
            height: Hauteur maximale de chaque arbre
                    Affecte la granularité des partitions
                    Recommandé: 8-15
            
            window_size: Taille de la fenêtre glissante
                        Nombre d'événements récents gardés en mémoire
                        Affecte la rapidité d'adaptation aux changements
                        Recommandé: 100-500
            
            quantile_p: Percentile pour le seuil dynamique
                       0.995 = seuls les 0.5% scores les plus élevés
                       sont considérés comme anomalies
                       Recommandé: 0.99-0.999
        """
        # ═══════════════════════════════════════════════════════════════
        # Modèle Half-Space Trees
        # seed=42 pour la reproductibilité des résultats
        # ═══════════════════════════════════════════════════════════════
        self.model = anomaly.HalfSpaceTrees(
            n_trees=n_trees,
            height=height,
            window_size=window_size,
            seed=42,
        )
        
        # ═══════════════════════════════════════════════════════════════
        # Estimateur de quantile streaming pour le seuil dynamique
        # Permet d'adapter automatiquement le seuil à la distribution
        # des scores observés
        # ═══════════════════════════════════════════════════════════════
        self.threshold = stats.Quantile(quantile_p)
        
        # Garde trace du dernier score pour le monitoring
        self.last_score: float = 0.0

    def score_and_update(self, x: Dict[str, float]) -> Tuple[float, float, bool]:
        """
        Calcule le score d'anomalie et met à jour le modèle.
        
        Cette méthode effectue 3 opérations:
            1. Calcule le score d'anomalie pour l'observation
            2. Met à jour le modèle avec la nouvelle observation
            3. Met à jour le seuil dynamique avec le nouveau score
        
        IMPORTANT: Le score est calculé AVANT l'apprentissage pour éviter
        le "data leakage" (fuite de données). Si on apprenait avant de
        scorer, le modèle connaîtrait déjà le point qu'il doit évaluer.
        
        Args:
            x: Dictionnaire des features numériques
               Ex: {"value": 1.23, "temperature": 24.5}
        
        Returns:
            Tuple contenant:
                - score: Score d'anomalie (plus élevé = plus anormal)
                - threshold: Seuil actuel (quantile des scores passés)
                - is_anomaly: True si score > seuil
        
        Note:
            Le seuil est initialisé à 0 et s'ajuste progressivement.
            Les premières détections peuvent être moins fiables.
        """
        # ═══════════════════════════════════════════════════════════════
        # Étape 1: Calculer le score AVANT d'apprendre
        # Évite le data leakage (le modèle ne doit pas connaître
        # le point qu'il évalue)
        # ═══════════════════════════════════════════════════════════════
        score = float(self.model.score_one(x))
        self.last_score = score
        
        # ═══════════════════════════════════════════════════════════════
        # Étape 2: Mettre à jour le modèle (apprentissage incrémental)
        # Le modèle apprend ce nouveau point pour les futures prédictions
        # ═══════════════════════════════════════════════════════════════
        self.model.learn_one(x)
        
        # ═══════════════════════════════════════════════════════════════
        # Étape 3: Mettre à jour le seuil dynamique
        # Le quantile s'adapte à la distribution observée des scores
        # ═══════════════════════════════════════════════════════════════
        current_threshold = float(self.threshold.get() or 0.0)
        self.threshold.update(score)
        new_threshold = float(self.threshold.get() or current_threshold)
        
        # Un score est anormal s'il dépasse le seuil
        # max(threshold, 1e-9) évite la division par zéro au démarrage
        is_anomaly = score > max(current_threshold, 1e-9)
        
        return score, new_threshold, is_anomaly
