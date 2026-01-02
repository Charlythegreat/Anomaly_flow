# 🔍 Anomaly Flow

> **Solution de Monitoring Temps Réel : Data Quality & Détection d'Anomalies**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Kafka](https://img.shields.io/badge/Kafka-Redpanda-red.svg)](https://redpanda.com/)
[![Prometheus](https://img.shields.io/badge/Monitoring-Prometheus-orange.svg)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Dashboard-Grafana-green.svg)](https://grafana.com/)

---

## 📋 Table des matières

- [Présentation](#-présentation)
- [Fonctionnalités](#-fonctionnalités)
- [Architecture](#️-architecture)
- [Démarrage rapide](#-démarrage-rapide)
- [Composants du système](#-composants-du-système)
- [Métriques et monitoring](#-métriques-et-monitoring)
- [Configuration](#-configuration)
- [Détection d'anomalies](#-détection-danomalies)
- [Contrôles Data Quality](#-contrôles-data-quality)
- [Alerting](#-alerting)
- [Dépendances](#-dépendances)
- [Développement](#️-développement)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Présentation

**Anomaly Flow** est une plateforme complète de monitoring temps réel conçue pour :

1. **Ingérer des flux de données** via Apache Kafka (implémenté avec Redpanda)
2. **Valider la qualité des données** en temps réel (schéma, valeurs, fraîcheur)
3. **Détecter les anomalies** avec des algorithmes de Machine Learning streaming
4. **Exposer des métriques** pour Prometheus et visualiser dans Grafana
5. **Alerter** en cas de problème (anomalies, erreurs de qualité)

Cette solution est idéale pour :
- Monitoring de capteurs IoT
- Surveillance de systèmes de production
- Détection de fraudes en temps réel
- Observabilité de pipelines de données

---

## ✨ Fonctionnalités

### 🔄 Ingestion Streaming
- **Kafka API** via Redpanda (léger, compatible Kafka)
- Consommation en temps réel avec auto-commit
- Sérialisation JSON optimisée avec `orjson`

### 📊 Contrôles Data Quality
| Contrôle | Description |
|----------|-------------|
| **Schéma** | Validation Pydantic (champs requis, types) |
| **Valeurs nulles** | Détection des champs manquants obligatoires |
| **Intervalles** | Vérification que les valeurs sont dans les bornes acceptables |
| **Fraîcheur** | Rejet des événements trop anciens (> 5 min par défaut) |

### 🤖 Détection d'Anomalies
- **Algorithme** : Half-Space Trees (River ML)
- **Apprentissage en ligne** : le modèle s'adapte en continu
- **Seuil dynamique** : basé sur le quantile 99.5% des scores
- **Sans supervision** : pas besoin de données étiquetées

### 📈 Observabilité
- **Métriques Prometheus** exposées sur `:8000/metrics`
- **Dashboard Grafana** pré-provisionné
- **Alertes** configurables (taux d'anomalies, erreurs DQ)

---

## 🏗️ Architecture

```
                                    ┌─────────────────────────────────────────────────┐
                                    │              ANOMALY FLOW SYSTEM                │
                                    └─────────────────────────────────────────────────┘

    ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────────────┐
    │                 │         │                 │         │                         │
    │    GENERATOR    │────────▶│    REDPANDA     │────────▶│       PROCESSOR         │
    │                 │         │    (Kafka)      │         │                         │
    │  src/generator  │         │                 │         │    src/processor        │
    │                 │         │   Topic:events  │         │                         │
    └─────────────────┘         └─────────────────┘         └───────────┬─────────────┘
           │                           │                                │
           │                           │                                │
           │ ~20 events/sec            │                    ┌───────────┴───────────┐
           │                           │                    │                       │
           ▼                           ▼                    ▼                       ▼
    ┌─────────────────┐         ┌─────────────────┐  ┌─────────────┐        ┌─────────────┐
    │  Simule des     │         │   Topic:alerts  │  │ Prometheus  │        │   Grafana   │
    │  capteurs IoT   │         │   (anomalies)   │  │   :9090     │        │   :3000     │
    │                 │         │                 │  │             │        │             │
    │ • Valeurs norm. │         └─────────────────┘  │ • Scrape    │        │ • Dashboard │
    │ • Anomalies 2%  │                              │ • Alerting  │        │ • Graphes   │
    │ • Erreurs DQ 1% │                              │ • Stockage  │        │ • Temps réel│
    └─────────────────┘                              └─────────────┘        └─────────────┘

    ════════════════════════════════════════════════════════════════════════════════════

    FLUX DE DONNÉES :

    1. Generator → Produit des événements JSON simulant des capteurs
    2. Redpanda  → Buffer les messages dans le topic "events"
    3. Processor → Consomme, valide, détecte les anomalies
    4. Processor → Expose les métriques sur :8000/metrics
    5. Processor → Publie les alertes sur le topic "alerts"
    6. Prometheus → Scrape les métriques toutes les 5s
    7. Grafana   → Visualise en temps réel
```

### Flux de données détaillé

```
┌────────────┐     JSON Event      ┌────────────┐    Validated     ┌────────────┐
│            │  ──────────────────▶│            │  ─────────────▶  │            │
│  Capteur   │  {                  │   Schema   │                  │  DQ Checks │
│  (Source)  │    sensor_id,       │ Validation │                  │            │
│            │    ts, value,       │  (Pydantic)│                  │ • Required │
└────────────┘    temperature      └────────────┘                  │ • Range    │
                  }                      │                         │ • Freshness│
                                         │ Invalid                 └─────┬──────┘
                                         ▼                               │
                                 ┌───────────────┐                       │ Valid
                                 │ dq_records_   │                       ▼
                                 │ total{invalid}│              ┌────────────────┐
                                 └───────────────┘              │                │
                                                                │ Anomaly        │
                                                                │ Detection      │
                                                                │                │
                                                                │ • HST Model    │
                                                                │ • Score        │
                                                                │ • Threshold    │
                                                                └───────┬────────┘
                                                                        │
                                         ┌──────────────────────────────┴──────┐
                                         │                                     │
                                         ▼                                     ▼
                                 ┌───────────────┐                    ┌────────────────┐
                                 │  Normal       │                    │  ANOMALY!      │
                                 │               │                    │                │
                                 │ last_anomaly_ │                    │ anomalies_total│
                                 │ score (Gauge) │                    │ + alert topic  │
                                 └───────────────┘                    └────────────────┘
```

---

## 🚀 Démarrage rapide

### Prérequis

- **GitHub Codespaces** (recommandé) ou Docker + Python 3.12 local
- Ports disponibles : 3000, 8000, 9090, 9092

### Étape 1 : Ouvrir dans GitHub Codespaces

1. Allez sur le repository GitHub
2. Cliquez sur **Code** → **Codespaces** → **Create codespace on main**
3. Attendez que l'environnement se construise (~2-3 min)

### Étape 2 : Démarrer les services Docker

```bash
# Depuis la racine du projet
cd .devcontainer && docker compose up -d redpanda prometheus grafana
```

**Vérifier que les services sont lancés :**
```bash
docker compose ps
```

Résultat attendu :
```
NAME                        STATUS
devcontainer-grafana-1      Up
devcontainer-prometheus-1   Up
devcontainer-redpanda-1     Up
```

### Étape 3 : Configurer l'environnement Python

```bash
# Revenir à la racine
cd /workspaces/Anomaly_flow

# Créer l'environnement virtuel
python3 -m venv .venv

# Activer l'environnement
source .venv/bin/activate

# Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt
```

### Étape 4 : Lancer le Processeur (Terminal 1)

```bash
source .venv/bin/activate
KAFKA_BROKER=localhost:9092 python -m src.processor
```

**Output attendu :**
```
2026-01-02 10:00:00 [info] metrics_server_started port=8000
2026-01-02 10:00:01 [info] processor_started broker=localhost:9092 topic=events
```

### Étape 5 : Lancer le Générateur (Terminal 2)

```bash
source .venv/bin/activate
KAFKA_BROKER=localhost:9092 python -m src.generator
```

**Output attendu :**
```
Generator connected to localhost:9092, topic=events
```

### Étape 6 : Accéder aux interfaces

| Service | URL | Identifiants |
|---------|-----|--------------|
| **Grafana** | http://localhost:3000 | Accès anonyme (pas de login) |
| **Prometheus** | http://localhost:9090 | - |
| **Prometheus Targets** | http://localhost:9090/targets | Vérifier que le target est "UP" |
| **Prometheus Alerts** | http://localhost:9090/alerts | Voir les alertes actives |
| **Alertmanager** | http://localhost:9093 | Gestion des notifications |
| **Metrics brutes** | http://localhost:8000/metrics | Endpoint Prometheus du processeur |

---

## � Commandes rapides

### ▶️ Tout démarrer

```bash
# 1. Démarrer les services Docker
cd /workspaces/Anomaly_flow/.devcontainer && docker compose up -d

# 2. Lancer le processor (Terminal 1)
cd /workspaces/Anomaly_flow && source .venv/bin/activate
KAFKA_BROKER=localhost:9092 python -m src.processor

# 3. Lancer le generator (Terminal 2)
cd /workspaces/Anomaly_flow && source .venv/bin/activate
KAFKA_BROKER=localhost:9092 python -m src.generator

# 4. (Optionnel) Lancer le consumer d'alertes avec email (Terminal 3)
cd /workspaces/Anomaly_flow && source .venv/bin/activate
KAFKA_BROKER=localhost:9092 \
SMTP_ENABLED=true \
SMTP_HOST=smtp.gmail.com \
SMTP_PORT=587 \
SMTP_USER=votre-email@gmail.com \
SMTP_PASSWORD=votre-app-password \
EMAIL_TO=destinataire@example.com \
python -m src.alert_consumer
```

### ⏹️ Tout arrêter

```bash
# Arrêter les processus Python et les services Docker
cd /workspaces/Anomaly_flow && pkill -f "python -m src" 2>/dev/null
cd .devcontainer && docker compose down
```

### 🔄 Redémarrer uniquement les services Docker

```bash
cd /workspaces/Anomaly_flow/.devcontainer && docker compose restart
```

### 📊 Vérifier l'état des services

```bash
# Services Docker
cd /workspaces/Anomaly_flow/.devcontainer && docker compose ps

# Processus Python
ps aux | grep "python -m src"
```

---

## �🔧 Composants du système

### Generator (`src/generator.py`)

Le générateur simule des capteurs IoT en produisant ~20 événements/seconde.

**Structure d'un événement :**
```json
{
  "sensor_id": "sensor-0",
  "ts": 1767347851.123,
  "value": 1.2345,
  "temperature": 24.5,
  "status": "OK"
}
```

**Injection de données anormales :**
| Type | Probabilité | Description |
|------|-------------|-------------|
| Anomalie valeur | 2% | `value` avec offset ±25 ou ±50 |
| Anomalie température | 1% | `temperature` avec offset ±20/30 |
| Champ manquant | 0.5% | Suppression du champ `value` |
| Valeur hors range | 0.5% | `value = 9999` |
| Événement ancien | 0.5% | `ts` = il y a 3 jours |

### Processor (`src/processor.py`)

Le cœur du système qui :

1. **Consomme** les messages Kafka du topic `events`
2. **Valide** le schéma avec Pydantic
3. **Exécute** les contrôles Data Quality
4. **Calcule** le score d'anomalie avec Half-Space Trees
5. **Met à jour** les métriques Prometheus
6. **Publie** les alertes sur le topic `alerts`

**Logs de progression :**
```
[info] progress processed=1000 anomalies=15 last_score=0.65 threshold=0.999
```

### Schema (`src/schema.py`)

Définition Pydantic du schéma d'événement :

```python
class Event(BaseModel):
    sensor_id: str          # Identifiant du capteur (obligatoire)
    ts: float               # Timestamp Unix en secondes
    value: float            # Valeur mesurée (obligatoire)
    temperature: float      # Température (optionnel)
    status: str = "OK"      # Statut : OK, WARN, FAIL
```

**Validations automatiques :**
- `sensor_id` : minimum 1 caractère
- `ts` : doit être dans une fenêtre de ±1 jour
- `status` : doit être "OK", "WARN" ou "FAIL"

---

## 📊 Métriques et Monitoring

### Métriques Prometheus exposées

| Métrique | Type | Labels | Description |
|----------|------|--------|-------------|
| `processed_records_total` | Counter | - | Nombre total d'événements traités |
| `dq_records_total` | Counter | `outcome`, `check` | Résultats des contrôles qualité |
| `anomalies_total` | Counter | - | Nombre d'anomalies détectées |
| `last_anomaly_score` | Gauge | - | Score de la dernière anomalie (0-1) |
| `anomaly_threshold` | Gauge | - | Seuil dynamique actuel (quantile 99.5%) |
| `event_value` | Histogram | - | Distribution des valeurs `value` |

### Exemples de requêtes PromQL

```promql
# Taux de traitement (events/sec)
rate(processed_records_total[1m])

# Taux d'anomalies (anomalies/sec)
rate(anomalies_total[1m])

# Pourcentage d'événements invalides
sum(rate(dq_records_total{outcome="invalid"}[5m])) 
/ 
sum(rate(dq_records_total[5m])) * 100

# Score d'anomalie actuel vs seuil
last_anomaly_score / anomaly_threshold

# Événements invalides par type de contrôle
sum by (check) (increase(dq_records_total{outcome="invalid"}[5m]))
```

### Dashboard Grafana

Le dashboard pré-provisionné inclut :

| Panel | Description |
|-------|-------------|
| **Events Processed** | Compteur total d'événements traités |
| **Anomalies Detected** | Compteur total d'anomalies |
| **Processing Rate** | Graphe du débit (events/sec) |
| **Anomaly Score** | Score actuel vs seuil dynamique |
| **DQ Errors** | Répartition des erreurs par type |
| **Value Distribution** | Histogramme des valeurs |

---

## ⚙️ Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `KAFKA_BROKER` | `redpanda:9092` | Adresse du broker Kafka |
| `TOPIC_EVENTS` | `events` | Topic d'entrée des événements |
| `TOPIC_ALERTS` | `alerts` | Topic de sortie des alertes |

### Paramètres (`src/config.py`)

```python
@dataclass
class Settings:
    # Kafka
    kafka_broker: str = "redpanda:9092"
    topic_events: str = "events"
    topic_alerts: str = "alerts"

    # Data Quality - Intervalles acceptables
    value_range = (-100.0, 100.0)       # Bornes pour 'value'
    temperature_range = (-20.0, 80.0)   # Bornes pour 'temperature'
    freshness_max_lag_sec = 300.0       # Max 5 minutes de retard

    # Anomaly Detection - Half-Space Trees
    quantile_p = 0.995      # Seuil = quantile 99.5% des scores
    hst_n_trees = 25        # Nombre d'arbres
    hst_height = 15         # Profondeur des arbres
    hst_window_size = 250   # Taille de la fenêtre glissante
```

### Personnaliser les seuils

**Exemple : Réduire la sensibilité aux anomalies**
```python
# Dans src/config.py
quantile_p = 0.999  # Seulement le top 0.1% sera considéré anomalie
```

**Exemple : Élargir les intervalles acceptables**
```python
value_range = (-500.0, 500.0)
temperature_range = (-50.0, 100.0)
```

---

## 🤖 Détection d'Anomalies

### Algorithme : Half-Space Trees (HST)

**Principe :**
- Algorithme de forêt aléatoire pour la détection d'anomalies en streaming
- Pas besoin d'entraînement préalable
- S'adapte en continu aux données
- Complexité O(1) par événement

**Fonctionnement :**
1. Chaque arbre partitionne l'espace des features aléatoirement
2. Les points "normaux" tombent dans des régions denses
3. Les anomalies tombent dans des régions peu peuplées
4. Le score = moyenne des scores de tous les arbres

### Seuil dynamique

Au lieu d'un seuil fixe, nous utilisons le **quantile 99.5%** des scores historiques :

```
Score > Quantile(99.5%) → ANOMALIE
```

**Avantages :**
- S'adapte automatiquement à la distribution des données
- Pas besoin de calibration manuelle
- Robuste aux changements de régime

### Features utilisées

| Feature | Source | Description |
|---------|--------|-------------|
| `value` | Événement | Valeur principale du capteur |
| `temperature` | Événement | Température (si présente) |

---

## ✅ Contrôles Data Quality

### Liste des contrôles

| Contrôle | Code | Condition de rejet |
|----------|------|-------------------|
| **Champs requis** | `required` | `sensor_id`, `ts`, ou `value` manquant |
| **Intervalle value** | `range_value` | `value` hors [-100, 100] |
| **Intervalle temperature** | `range_temperature` | `temperature` hors [-20, 80] |
| **Fraîcheur** | `freshness` | `ts` > 5 minutes dans le passé |

### Métriques DQ

```promql
# Total des erreurs par type
dq_records_total{outcome="invalid", check="schema"}
dq_records_total{outcome="invalid", check="range_value"}
dq_records_total{outcome="invalid", check="freshness"}

# Événements valides
dq_records_total{outcome="ok", check="all"}
```

---

## 🚨 Alerting

### Règles Prometheus (`prometheus/alerts.yml`)

#### 1. HighAnomalyRate
```yaml
alert: HighAnomalyRate
expr: rate(anomalies_total[1m]) > 0.1
for: 30s
severity: warning
```
**Déclenché quand :** Plus de 0.1 anomalie/seconde pendant 30s

#### 2. DataQualityErrors
```yaml
alert: DataQualityErrors
expr: increase(dq_records_total{outcome="invalid"}[1m]) > 0
for: 0s
severity: critical
```
**Déclenché quand :** Toute erreur DQ dans la dernière minute

### Alertes publiées sur Kafka

Chaque anomalie génère un message sur le topic `alerts` :

```json
{
  "type": "anomaly",
  "sensor_id": "sensor-2",
  "ts": 1767347851.123,
  "score": 0.9998,
  "threshold": 0.9995,
  "features": {
    "value": 52.34,
    "temperature": 25.1
  },
  "dq_issues": []
}
```

### Consommateur d'alertes (`src/alert_consumer.py`)

Un script dédié permet de consommer les alertes Kafka et d'envoyer des notifications :

```bash
# Affichage console uniquement
KAFKA_BROKER=localhost:9092 python -m src.alert_consumer
```

**Output :**
```
╔══════════════════════════════════════════════════════════════╗
║  🚨 ANOMALIE DÉTECTÉE                                        ║
╠══════════════════════════════════════════════════════════════╣
║  Capteur    : sensor-2                                       ║
║  Timestamp  : 2026-01-02 14:30:45                           ║
║  Score      : 0.6523 (seuil: 0.5891)                        ║
║  Features   : value=52.34, temperature=25.1                 ║
╚══════════════════════════════════════════════════════════════╝
```

### Notifications Slack

1. **Créer une app Slack** : https://api.slack.com/apps
2. **Activer Incoming Webhooks** et créer un webhook pour votre channel
3. **Lancer le consumer avec le webhook** :

```bash
KAFKA_BROKER=localhost:9092 \
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/XXX/YYY/ZZZ" \
python -m src.alert_consumer
```

### Notifications Email (Gmail)

#### Prérequis : Créer un App Password Gmail

1. Activez la **Vérification en 2 étapes** : https://myaccount.google.com/signinoptions/two-step-verification
2. Créez un **Mot de passe d'application** : https://myaccount.google.com/apppasswords
   - Sélectionnez "Autre (nom personnalisé)" → "Anomaly Flow"
   - Copiez le code à 16 caractères

#### Lancer avec notifications Email

```bash
KAFKA_BROKER=localhost:9092 \
SMTP_ENABLED=true \
SMTP_HOST=smtp.gmail.com \
SMTP_PORT=587 \
SMTP_USER=votre-email@gmail.com \
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx \
EMAIL_TO=destinataire@example.com \
python -m src.alert_consumer
```

#### Tester la configuration Email

```bash
SMTP_HOST=smtp.gmail.com \
SMTP_PORT=587 \
SMTP_USER=votre-email@gmail.com \
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx \
EMAIL_TO=destinataire@example.com \
python -m src.test_email
```

#### Autres serveurs SMTP

| Provider | Host | Port |
|----------|------|------|
| Gmail | smtp.gmail.com | 587 |
| Outlook | smtp.office365.com | 587 |
| Yahoo | smtp.mail.yahoo.com | 587 |
| SendGrid | smtp.sendgrid.net | 587 |

### Alertmanager Prometheus (production)

Pour une gestion avancée des alertes en production, Alertmanager est configuré :

```bash
# Démarrer Alertmanager
cd .devcontainer && docker compose up -d alertmanager
```

**Accès :** http://localhost:9093

**Configuration :** Éditez `prometheus/alertmanager.yml` pour configurer :
- Routes d'alertes par sévérité
- Groupement d'alertes
- Inhibition des alertes redondantes
- Notifications Slack/Email natives

---

## 📦 Dépendances

### Python (`requirements.txt`)

| Package | Version | Rôle |
|---------|---------|------|
| `kafka-python-ng` | latest | Client Kafka compatible Python 3.12 |
| `pydantic` | 2.8.2 | Validation de schéma et sérialisation |
| `prometheus-client` | 0.20.0 | Export des métriques |
| `river` | 0.23+ | Machine Learning streaming (Half-Space Trees) |
| `structlog` | 24.1.0 | Logging structuré JSON |
| `orjson` | 3.10.3 | Sérialisation JSON haute performance |

### Services Docker

| Service | Image | Port | Rôle |
|---------|-------|------|------|
| **Redpanda** | `redpandadata/redpanda:v23.3.14` | 9092 | Broker Kafka |
| **Prometheus** | `prom/prometheus:v2.53.0` | 9090 | Collecte métriques |
| **Grafana** | `grafana/grafana:11.1.0` | 3000 | Visualisation |
| **Alertmanager** | `prom/alertmanager:v0.27.0` | 9093 | Gestion des alertes |

---

## 🛠️ Développement

### Structure du projet

```
Anomaly_flow/
├── .devcontainer/
│   └── docker-compose.yml      # Services Docker
├── grafana/
│   ├── dashboards/             # JSON des dashboards
│   └── provisioning/           # Auto-configuration Grafana
├── prometheus/
│   ├── prometheus.yml          # Config scraping
│   ├── alerts.yml              # Règles d'alertes
│   └── alertmanager.yml        # Config notifications Slack/Email
├── src/
│   ├── __init__.py
│   ├── anomaly.py              # Détecteur Half-Space Trees
│   ├── config.py               # Paramètres
│   ├── generator.py            # Générateur d'événements
│   ├── processor.py            # Pipeline principal
│   ├── quality.py              # Contrôles DQ
│   ├── schema.py               # Schéma Pydantic
│   ├── alert_consumer.py       # Consumer alertes + notifications
│   └── test_email.py           # Test configuration SMTP
├── requirements.txt
└── README.md
```

### Commandes utiles

```bash
# Activer l'environnement
source .venv/bin/activate

# Voir les logs du processeur en temps réel
KAFKA_BROKER=localhost:9092 python -m src.processor 2>&1 | head -100

# Tester les métriques
curl -s http://localhost:8000/metrics | grep -E "^(processed|anomalies|dq_)"

# Vérifier Prometheus
curl -s "http://localhost:9090/api/v1/query?query=up"

# Redémarrer les services Docker
cd .devcontainer && docker compose restart

# Voir les logs Docker
docker compose logs -f prometheus
```

### Tests (à implémenter)

```bash
# Installer pytest
pip install pytest pytest-cov

# Lancer les tests
pytest tests/ -v --cov=src
```

---

## 🔧 Troubleshooting

### Erreur : `NoBrokersAvailable`

**Cause :** Kafka/Redpanda n'est pas accessible

**Solution :**
```bash
# Vérifier que Redpanda tourne
docker compose ps

# Relancer si nécessaire
cd .devcontainer && docker compose up -d redpanda

# Vérifier la connectivité
nc -zv localhost 9092
```

### Erreur : `Address already in use` (port 8000)

**Cause :** Un autre processus utilise le port

**Solution :**
```bash
# Tuer le processus sur le port
fuser -k 8000/tcp

# Ou trouver le PID
lsof -i :8000
kill <PID>
```

### Prometheus ne scrape pas les métriques

**Cause :** Le target n'est pas accessible depuis le container

**Solution :**
1. Vérifier que `prometheus.yml` pointe vers `host.docker.internal:8000`
2. Vérifier que `extra_hosts` est configuré dans `docker-compose.yml`
3. Redémarrer Prometheus : `docker compose restart prometheus`

### Les données n'apparaissent pas dans Grafana

**Causes possibles :**
1. Le processeur n'est pas lancé
2. Le générateur n'est pas lancé
3. Prometheus ne scrape pas

**Vérifications :**
```bash
# 1. Métriques exposées ?
curl http://localhost:8000/metrics | grep processed

# 2. Prometheus scrape OK ?
curl "http://localhost:9090/api/v1/targets" | python3 -m json.tool

# 3. Données dans Prometheus ?
curl "http://localhost:9090/api/v1/query?query=processed_records_total"
```

---

## 📝 Licence

MIT License - Voir le fichier [LICENSE](LICENSE)

---

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amelioration`)
3. Commit vos changements (`git commit -am 'Ajout fonctionnalité'`)
4. Push la branche (`git push origin feature/amelioration`)
5. Ouvrir une Pull Request

---

**Développé avec ❤️ pour le monitoring temps réel**
