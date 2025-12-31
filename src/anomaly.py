from river import anomaly, stats
from typing import Dict, Tuple

class StreamingAnomalyDetector:
    """
    Half-Space Trees online anomaly detection with dynamic threshold
    using streaming quantile of scores.
    """
    def __init__(self, n_trees: int, height: int, window_size: int, quantile_p: float):
        self.model = anomaly.HalfSpaceTrees(
            n_trees=n_trees,
            height=height,
            window_size=window_size,
            seed=42,
        )
        self.threshold = stats.Quantile(quantile_p)
        self.last_score: float = 0.0

    def score_and_update(self, x: Dict[str, float]) -> Tuple[float, float, bool]:
        # Score before learning to avoid leakage
        score = float(self.model.score_one(x))
        self.last_score = score
        # Update model
        self.model.learn_one(x)
        # Update quantile
        thr = float(self.threshold.get() or 0.0)
        self.threshold.update(score)
        is_anomaly = score > max(thr, 1e-9)
        new_thr = float(self.threshold.get() or thr)
        return score, new_thr, is_anomaly
