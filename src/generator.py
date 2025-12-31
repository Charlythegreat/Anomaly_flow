import json
import os
import random
import time
from typing import Dict

from kafka import KafkaProducer

BROKER = os.getenv("KAFKA_BROKER", "redpanda:9092")
TOPIC = os.getenv("TOPIC_EVENTS", "events")

def make_event(i: int) -> Dict:
    base = random.uniform(-2.0, 2.0)
    drift = 0.02 * time.time() % 1.0
    value = base + drift

    # Inject anomalies randomly
    if random.random() < 0.02:
        value += random.choice([25, -25, 50, -50])

    temp = 25.0 + random.uniform(-1.5, 1.5)
    if random.random() < 0.01:
        temp += random.choice([20, -30])  # bad temperature

    evt = {
        "sensor_id": f"sensor-{i%5}",
        "ts": time.time(),
        "value": round(value, 4),
        "temperature": round(temp, 2),
        "status": "OK",
    }

    # Occasionally produce bad records (DQ errors)
    r = random.random()
    if r < 0.005:
        evt.pop("value")  # missing value
    elif r < 0.010:
        evt["value"] = 9999  # out of range
    elif r < 0.015:
        evt["ts"] = time.time() - 3600 * 24 * 3  # 3 days old

    return evt

def main():
    producer = KafkaProducer(
        bootstrap_servers=[BROKER],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda v: v.encode("utf-8"),
        linger_ms=5
    )
    i = 0
    print(f"Generator connected to {BROKER}, topic={TOPIC}")
    while True:
        evt = make_event(i)
        key = evt.get("sensor_id", f"k-{i}")
        try:
            producer.send(TOPIC, key=key, value=evt)
        except Exception as e:
            print("send error:", e)
        i += 1
        time.sleep(0.05)  # ~20 events/sec

if __name__ == "__main__":
    main()
