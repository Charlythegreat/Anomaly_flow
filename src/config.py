import os
from dataclasses import dataclass

@dataclass
class Settings:
    kafka_broker: str = os.getenv("KAFKA_BROKER", "redpanda:9092")
    topic_events: str = os.getenv("TOPIC_EVENTS", "events")
    topic_alerts: str = os.getenv("TOPIC_ALERTS", "alerts")

    # Data Quality thresholds
    value_range = (-100.0, 100.0)
    temperature_range = (-20.0, 80.0)
    freshness_max_lag_sec: float = 300.0  # 5 minutes

    # Anomaly detection
    quantile_p: float = 0.995  # dynamic threshold at 99.5th percentile of scores
    hst_n_trees: int = 25
    hst_height: int = 15
    hst_window_size: int = 250

settings = Settings()
