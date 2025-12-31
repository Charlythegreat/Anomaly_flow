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

log = structlog.get_logger()

# Prometheus metrics
processed_records_total = Counter(
    "processed_records_total", "Total records processed"
)
dq_records_total = Counter(
    "dq_records_total", "Data Quality outcomes",
    labelnames=("outcome", "check")
)
anomalies_total = Counter(
    "anomalies_total", "Total anomalies detected"
)
last_anomaly_score = Gauge(
    "last_anomaly_score", "Last anomaly score (streaming)"
)
threshold_gauge = Gauge(
    "anomaly_threshold", "Dynamic anomaly threshold (quantile)"
)
value_hist = Histogram(
    "event_value", "Distribution of event.value",
    buckets=(-100, -50, -20, -10, -5, 0, 5, 10, 20, 50, 100)
)

def to_features(evt: Dict) -> Dict[str, float]:
    # Select numeric features for anomaly detector
    x = {
        "value": float(evt.get("value", 0.0)),
    }
    if evt.get("temperature") is not None:
        x["temperature"] = float(evt["temperature"])
    return x

def run_processor():
    # Start Prometheus metrics HTTP server
    start_http_server(8000)
    log.info("metrics_server_started", port=8000)

    consumer = KafkaConsumer(
        settings.topic_events,
        bootstrap_servers=[settings.kafka_broker],
        group_id="processor",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        key_deserializer=lambda v: v.decode("utf-8") if v else None,
        max_poll_records=100,
    )
    producer = KafkaProducer(
        bootstrap_servers=[settings.kafka_broker],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda v: v.encode("utf-8") if v else None,
        linger_ms=10
    )

    det = StreamingAnomalyDetector(
        n_trees=settings.hst_n_trees,
        height=settings.hst_height,
        window_size=settings.hst_window_size,
        quantile_p=settings.quantile_p
    )

    log.info("processor_started", broker=settings.kafka_broker, topic=settings.topic_events)

    for msg in consumer:
        processed_records_total.inc()
        evt_raw = msg.value

        # Schema validation
        try:
            evt = Event(**evt_raw).model_dump()
        except Exception as e:
            dq_records_total.labels("invalid", "schema").inc()
            log.warning("schema_invalid", error=str(e), event=evt_raw)
            continue

        # Data Quality checks
        issues = dq_checks(evt)
        if issues:
            for check, _ in issues:
                dq_records_total.labels("invalid", check).inc()
        else:
            dq_records_total.labels("ok", "all").inc()

        # Record value hist regardless
        value_hist.observe(float(evt["value"]))

        # Anomaly detection
        x = to_features(evt)
        score, thr, is_anom = det.score_and_update(x)
        last_anomaly_score.set(score)
        threshold_gauge.set(thr)

        if is_anom:
            anomalies_total.inc()
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
                producer.send(settings.topic_alerts, key=evt["sensor_id"], value=alert_payload)
            except Exception as pe:
                log.error("alert_send_failed", error=str(pe), alert=alert_payload)

        if processed_records_total._value.get() % 100 == 0:
            log.info("progress",
                     processed=int(processed_records_total._value.get()),
                     anomalies=int(anomalies_total._value.get()),
                     last_score=score,
                     threshold=thr)

if __name__ == "__main__":
    # Run in main thread; leave room for future background tasks if desired
    run_processor()
