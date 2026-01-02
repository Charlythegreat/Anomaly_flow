#!/usr/bin/env python3
"""
Consumer d'alertes Kafka avec notifications optionnelles.

Usage:
    # Afficher les alertes en temps réel
    KAFKA_BROKER=localhost:9092 python -m src.alert_consumer

    # Avec webhook Slack
    KAFKA_BROKER=localhost:9092 SLACK_WEBHOOK_URL=https://hooks.slack.com/... python -m src.alert_consumer

    # Avec email (nécessite SMTP configuré)
    KAFKA_BROKER=localhost:9092 SMTP_HOST=smtp.gmail.com SMTP_USER=... SMTP_PASS=... EMAIL_TO=... python -m src.alert_consumer
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional
import urllib.request
import urllib.error

from kafka import KafkaConsumer

# Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_ALERTS = os.getenv("TOPIC_ALERTS", "alerts")

# Slack (optionnel)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Email (optionnel)
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS") or os.getenv("SMTP_PASSWORD")  # Support both names
SMTP_ENABLED = os.getenv("SMTP_ENABLED", "").lower() in ("true", "1", "yes")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)


def send_slack_notification(alert: dict) -> bool:
    """Envoie une notification Slack via webhook."""
    if not SLACK_WEBHOOK_URL:
        return False
    
    # Formater le message Slack
    timestamp = datetime.fromtimestamp(alert.get("ts", 0)).strftime("%Y-%m-%d %H:%M:%S")
    
    slack_message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 Anomalie Détectée",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Capteur:*\n`{alert.get('sensor_id')}`"},
                    {"type": "mrkdwn", "text": f"*Timestamp:*\n{timestamp}"},
                    {"type": "mrkdwn", "text": f"*Score:*\n`{alert.get('score', 0):.4f}`"},
                    {"type": "mrkdwn", "text": f"*Seuil:*\n`{alert.get('threshold', 0):.4f}`"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Features:*\n```{json.dumps(alert.get('features', {}), indent=2)}```"
                }
            }
        ]
    }
    
    # Si des problèmes DQ sont présents
    dq_issues = alert.get("dq_issues", [])
    if dq_issues:
        slack_message["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn", 
                "text": f"⚠️ *Problèmes Data Quality:*\n• " + "\n• ".join([f"`{i[0]}`: {i[1]}" for i in dq_issues])
            }
        })
    
    try:
        data = json.dumps(slack_message).encode("utf-8")
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception as e:
        print(f"[ERROR] Slack notification failed: {e}")
        return False


def send_email_notification(alert: dict) -> bool:
    """Envoie une notification par email."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_TO]):
        return False
    
    timestamp = datetime.fromtimestamp(alert.get("ts", 0)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Créer le message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 Anomalie Détectée - {alert.get('sensor_id')}"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    
    # Version texte
    text_content = f"""
Anomalie Détectée

Capteur: {alert.get('sensor_id')}
Timestamp: {timestamp}
Score: {alert.get('score', 0):.4f}
Seuil: {alert.get('threshold', 0):.4f}

Features:
{json.dumps(alert.get('features', {}), indent=2)}

Problèmes DQ: {alert.get('dq_issues', [])}
"""
    
    # Version HTML
    html_content = f"""
<html>
<body>
<h2 style="color: #d32f2f;">🚨 Anomalie Détectée</h2>
<table style="border-collapse: collapse; width: 100%;">
    <tr>
        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Capteur</strong></td>
        <td style="padding: 8px; border: 1px solid #ddd;"><code>{alert.get('sensor_id')}</code></td>
    </tr>
    <tr>
        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Timestamp</strong></td>
        <td style="padding: 8px; border: 1px solid #ddd;">{timestamp}</td>
    </tr>
    <tr>
        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Score</strong></td>
        <td style="padding: 8px; border: 1px solid #ddd;"><code>{alert.get('score', 0):.4f}</code></td>
    </tr>
    <tr>
        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Seuil</strong></td>
        <td style="padding: 8px; border: 1px solid #ddd;"><code>{alert.get('threshold', 0):.4f}</code></td>
    </tr>
</table>
<h3>Features</h3>
<pre style="background: #f5f5f5; padding: 10px;">{json.dumps(alert.get('features', {}), indent=2)}</pre>
</body>
</html>
"""
    
    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))
    
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(EMAIL_FROM, EMAIL_TO.split(","), msg.as_string())
        return True
    except Exception as e:
        print(f"[ERROR] Email notification failed: {e}")
        return False


def format_alert_console(alert: dict) -> str:
    """Formate une alerte pour l'affichage console."""
    timestamp = datetime.fromtimestamp(alert.get("ts", 0)).strftime("%Y-%m-%d %H:%M:%S")
    
    output = f"""
╔══════════════════════════════════════════════════════════════╗
║  🚨 ANOMALIE DÉTECTÉE                                        ║
╠══════════════════════════════════════════════════════════════╣
║  Capteur    : {alert.get('sensor_id', 'N/A'):<47} ║
║  Timestamp  : {timestamp:<47} ║
║  Score      : {alert.get('score', 0):.6f} (seuil: {alert.get('threshold', 0):.6f}){' ':<20} ║
╠══════════════════════════════════════════════════════════════╣
║  Features:                                                   ║"""
    
    for key, value in alert.get("features", {}).items():
        output += f"\n║    {key:<10}: {value:<48} ║"
    
    dq_issues = alert.get("dq_issues", [])
    if dq_issues:
        output += "\n╠══════════════════════════════════════════════════════════════╣"
        output += "\n║  ⚠️  Problèmes Data Quality:                                  ║"
        for check, msg in dq_issues:
            output += f"\n║    • {check}: {msg:<50} ║"
    
    output += "\n╚══════════════════════════════════════════════════════════════╝"
    return output


def main():
    """Consumer principal d'alertes."""
    print("=" * 64)
    print("  ANOMALY FLOW - Consumer d'Alertes")
    print("=" * 64)
    print(f"\n  Broker Kafka : {KAFKA_BROKER}")
    print(f"  Topic        : {TOPIC_ALERTS}")
    print(f"  Slack        : {'✓ Configuré' if SLACK_WEBHOOK_URL else '✗ Non configuré'}")
    print(f"  Email        : {'✓ Configuré' if all([SMTP_HOST, EMAIL_TO]) else '✗ Non configuré'}")
    print("\n  En attente d'alertes... (Ctrl+C pour quitter)\n")
    print("-" * 64)
    
    consumer = KafkaConsumer(
        TOPIC_ALERTS,
        bootstrap_servers=[KAFKA_BROKER],
        group_id="alert-consumer",
        auto_offset_reset="latest",  # Seulement les nouvelles alertes
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    
    alert_count = 0
    slack_sent = 0
    email_sent = 0
    
    try:
        for msg in consumer:
            alert = msg.value
            alert_count += 1
            
            # Afficher dans la console
            print(format_alert_console(alert))
            
            # Envoyer notification Slack
            if SLACK_WEBHOOK_URL:
                if send_slack_notification(alert):
                    slack_sent += 1
                    print("  → Notification Slack envoyée ✓")
            
            # Envoyer notification Email
            if all([SMTP_HOST, EMAIL_TO]):
                if send_email_notification(alert):
                    email_sent += 1
                    print("  → Notification Email envoyée ✓")
            
            print()
            
    except KeyboardInterrupt:
        print("\n" + "=" * 64)
        print(f"  Arrêt du consumer")
        print(f"  Total alertes reçues : {alert_count}")
        if SLACK_WEBHOOK_URL:
            print(f"  Notifications Slack  : {slack_sent}")
        if all([SMTP_HOST, EMAIL_TO]):
            print(f"  Notifications Email  : {email_sent}")
        print("=" * 64)


if __name__ == "__main__":
    main()
