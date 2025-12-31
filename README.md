# Anomaly_flow

# Anomqly Flow — Real-time Monitoring: Data Quality & Anomaly Detection (Codespaces)

Solution de monitoring technique temps réel avec focus Data Quality et détection d'anomalies, prête pour GitHub Codespaces.

## Fonctionnalités
- Ingestion streaming (Kafka API via Redpanda)
- Contrôles Data Quality (schéma, nulls, intervalles, fraîcheur)
- Détection d’anomalies en ligne (River: Half-Space Trees + quantile 99.5%)
- Export métriques Prometheus (+ règles d’alerting)
- Dashboard Grafana provisionné

## Démarrage rapide (Codespaces)
1. Ouvrez ce repo dans GitHub Codespaces.
2. Le container démarre Prometheus, Grafana et Redpanda (Kafka). Les dépendances Python s’installent automatiquement.
3. Dans le terminal, lancez le processeur:
   ```bash
   python -m src.processor
   ```
4. Dans un second terminal, lancez le générateur:
   ```bash
   python -m src.generator
   ```
5. Ouvrez les ports:
   - Prometheus: 9090
   - Grafana: 3000 (datasource Prometheus préconfigurée, dashboard auto-provisionné)
   - Metrics du processeur: 8000

## Topics
- Ingestion: `events`
- Alertes (émises par le processeur): `alerts`

## Où regarder ?
- Grafana: courbes `anomalies_total`, `dq_records_total{outcome="invalid"}`, `last_anomaly_score`
- Prometheus (http://localhost:9090/targets): statut de scrape
- Prometheus Alerts: http://localhost:9090/alerts

## Customisation
- Règles DQ et seuils dans `src/config.py`
- Règles d’alerting Prometheus dans `prometheus/alerts.yml`
- Dashboard Grafana dans `grafana/dashboards/realtime-monitoring.json`

## Notes
- Redpanda auto-crée les topics si absents.
- Pour Slack/Email, connectez Alertmanager (non inclus par défaut) ou configurez l’alerting Grafana.

## Dev
- Format/Qualité: à compléter (ruff/pytest) si souhaité
- Python 3.11 (devcontainer feature)