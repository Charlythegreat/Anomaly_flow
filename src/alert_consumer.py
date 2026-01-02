#!/usr/bin/env python3
"""
Consumer d'alertes Kafka avec notifications optionnelles.

Ce module consomme les alertes d'anomalies depuis Kafka et peut envoyer
des notifications via Slack (webhook) et/ou Email (SMTP).

Fonctionnalités:
    - Affichage formaté des alertes en console
    - Notifications Slack via Incoming Webhooks
    - Notifications Email via SMTP (Gmail, Outlook, etc.)
    - Support de plusieurs destinataires email (séparés par virgule)

Usage:
    # Afficher les alertes en temps réel (console uniquement)
    KAFKA_BROKER=localhost:9092 python -m src.alert_consumer

    # Avec notifications Slack
    KAFKA_BROKER=localhost:9092 \\
    SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ \\
    python -m src.alert_consumer

    # Avec notifications Email (Gmail)
    KAFKA_BROKER=localhost:9092 \\
    SMTP_ENABLED=true \\
    SMTP_HOST=smtp.gmail.com \\
    SMTP_PORT=587 \\
    SMTP_USER=votre-email@gmail.com \\
    SMTP_PASSWORD=votre-app-password \\
    EMAIL_TO=destinataire@example.com \\
    python -m src.alert_consumer
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

# ═══════════════════════════════════════════════════════════════════════════
# Configuration via variables d'environnement
# ═══════════════════════════════════════════════════════════════════════════

# Configuration Kafka
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC_ALERTS = os.getenv("TOPIC_ALERTS", "alerts")

# Configuration Slack (optionnel)
# Créez un webhook: https://api.slack.com/apps → Incoming Webhooks
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Configuration Email SMTP (optionnel)
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
# Supporte les deux noms de variable pour la compatibilité
SMTP_PASS = os.getenv("SMTP_PASS") or os.getenv("SMTP_PASSWORD")
SMTP_ENABLED = os.getenv("SMTP_ENABLED", "").lower() in ("true", "1", "yes")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)


def send_slack_notification(alert: dict) -> bool:
    """
    Envoie une notification Slack via webhook.
    
    Args:
        alert: Dictionnaire contenant les données de l'alerte
    
    Returns:
        True si l'envoi a réussi, False sinon
    
    Note:
        Utilise le format Block Kit de Slack pour un affichage enrichi.
        Voir: https://api.slack.com/block-kit
    """
    if not SLACK_WEBHOOK_URL:
        return False
    
    # Formater le timestamp pour l'affichage
    timestamp = datetime.fromtimestamp(alert.get("ts", 0)).strftime("%Y-%m-%d %H:%M:%S")
    
    # ═══════════════════════════════════════════════════════════════════
    # Construction du message Slack avec Block Kit
    # Permet un affichage structuré et visuel
    # ═══════════════════════════════════════════════════════════════════
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
    
    # Ajouter les problèmes DQ si présents
    dq_issues = alert.get("dq_issues", [])
    if dq_issues:
        slack_message["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn", 
                "text": f"⚠️ *Problèmes Data Quality:*\n• " + 
                       "\n• ".join([f"`{i[0]}`: {i[1]}" for i in dq_issues])
            }
        })
    
    # ═══════════════════════════════════════════════════════════════════
    # Envoi de la requête HTTP POST au webhook Slack
    # ═══════════════════════════════════════════════════════════════════
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
        print(f"[ERREUR] Notification Slack échouée: {e}")
        return False


def send_email_notification(alert: dict) -> bool:
    """
    Envoie une notification par email via SMTP.
    
    Args:
        alert: Dictionnaire contenant les données de l'alerte
    
    Returns:
        True si l'envoi a réussi, False sinon
    
    Configuration requise:
        - SMTP_HOST: Serveur SMTP (ex: smtp.gmail.com)
        - SMTP_PORT: Port SMTP (généralement 587 pour TLS)
        - SMTP_USER: Adresse email d'envoi
        - SMTP_PASS ou SMTP_PASSWORD: Mot de passe ou App Password
        - EMAIL_TO: Adresse(s) de destination (séparées par virgule)
    
    Note pour Gmail:
        Utilisez un "App Password" au lieu de votre mot de passe normal.
        Voir: https://myaccount.google.com/apppasswords
    """
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_TO]):
        return False
    
    timestamp = datetime.fromtimestamp(alert.get("ts", 0)).strftime("%Y-%m-%d %H:%M:%S")
    
    # ═══════════════════════════════════════════════════════════════════
    # Construction de l'email multipart (texte + HTML)
    # ═══════════════════════════════════════════════════════════════════
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 Anomalie Détectée - {alert.get('sensor_id')}"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    
    # Version texte simple (pour les clients email basiques)
    text_content = f"""
Anomalie Détectée
=================

Capteur: {alert.get('sensor_id')}
Timestamp: {timestamp}
Score: {alert.get('score', 0):.4f}
Seuil: {alert.get('threshold', 0):.4f}

Features:
{json.dumps(alert.get('features', {}), indent=2)}

Problèmes DQ: {alert.get('dq_issues', [])}
"""
    
    # Version HTML (pour un affichage enrichi)
    html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px;">
<h2 style="color: #d32f2f;">🚨 Anomalie Détectée</h2>
<table style="border-collapse: collapse; width: 100%;">
    <tr>
        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Capteur</strong></td>
        <td style="padding: 8px; border: 1px solid #ddd;"><code>{alert.get('sensor_id')}</code></td>
    </tr>
    <tr>
        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Timestamp</strong></td>
        <td style="padding: 8px; border: 1px solid #ddd;">{timestamp}</td>
    </tr>
    <tr>
        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Score</strong></td>
        <td style="padding: 8px; border: 1px solid #ddd;"><code>{alert.get('score', 0):.4f}</code></td>
    </tr>
    <tr>
        <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Seuil</strong></td>
        <td style="padding: 8px; border: 1px solid #ddd;"><code>{alert.get('threshold', 0):.4f}</code></td>
    </tr>
</table>
<h3>Features</h3>
<pre style="background: #f5f5f5; padding: 10px; border-radius: 4px;">{json.dumps(alert.get('features', {}), indent=2)}</pre>
<hr style="margin: 20px 0;">
<p style="color: #666; font-size: 12px;">
    <a href="http://localhost:3000">Dashboard Grafana</a> |
    <a href="http://localhost:9090">Prometheus</a> |
    <a href="http://localhost:9093">Alertmanager</a>
</p>
</body>
</html>
"""
    
    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))
    
    # ═══════════════════════════════════════════════════════════════════
    # Envoi via SMTP avec TLS
    # ═══════════════════════════════════════════════════════════════════
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()  # Activer le chiffrement TLS
            server.login(SMTP_USER, SMTP_PASS)
            # Supporte plusieurs destinataires séparés par virgule
            server.sendmail(EMAIL_FROM, EMAIL_TO.split(","), msg.as_string())
        return True
    except Exception as e:
        print(f"[ERREUR] Notification Email échouée: {e}")
        return False


def format_alert_console(alert: dict) -> str:
    """
    Formate une alerte pour l'affichage console avec encadrement ASCII.
    
    Args:
        alert: Dictionnaire contenant les données de l'alerte
    
    Returns:
        Chaîne formatée prête à être affichée
    """
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
    
    # Afficher chaque feature
    for key, value in alert.get("features", {}).items():
        output += f"\n║    {key:<10}: {value:<48} ║"
    
    # Afficher les problèmes DQ si présents
    dq_issues = alert.get("dq_issues", [])
    if dq_issues:
        output += "\n╠══════════════════════════════════════════════════════════════╣"
        output += "\n║  ⚠️  Problèmes Data Quality:                                  ║"
        for check, msg in dq_issues:
            output += f"\n║    • {check}: {msg:<50} ║"
    
    output += "\n╚══════════════════════════════════════════════════════════════╝"
    return output


def main():
    """
    Fonction principale du consumer d'alertes.
    
    Se connecte à Kafka et traite les alertes en boucle infinie.
    Affiche chaque alerte en console et envoie des notifications
    si Slack et/ou Email sont configurés.
    """
    # ═══════════════════════════════════════════════════════════════════
    # Affichage du banner de démarrage
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 64)
    print("  ANOMALY FLOW - Consumer d'Alertes")
    print("=" * 64)
    print(f"\n  Broker Kafka : {KAFKA_BROKER}")
    print(f"  Topic        : {TOPIC_ALERTS}")
    print(f"  Slack        : {'✓ Configuré' if SLACK_WEBHOOK_URL else '✗ Non configuré'}")
    print(f"  Email        : {'✓ Configuré' if all([SMTP_HOST, EMAIL_TO]) else '✗ Non configuré'}")
    print("\n  En attente d'alertes... (Ctrl+C pour quitter)\n")
    print("-" * 64)
    
    # ═══════════════════════════════════════════════════════════════════
    # Configuration du consumer Kafka
    # auto_offset_reset="latest" = seulement les nouvelles alertes
    # ═══════════════════════════════════════════════════════════════════
    consumer = KafkaConsumer(
        TOPIC_ALERTS,
        bootstrap_servers=[KAFKA_BROKER],
        group_id="alert-consumer",
        auto_offset_reset="latest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    
    # Compteurs pour le résumé final
    alert_count = 0
    slack_sent = 0
    email_sent = 0
    
    # ═══════════════════════════════════════════════════════════════════
    # Boucle principale de consommation
    # ═══════════════════════════════════════════════════════════════════
    try:
        for msg in consumer:
            alert = msg.value
            alert_count += 1
            
            # Afficher l'alerte formatée en console
            print(format_alert_console(alert))
            
            # Envoyer notification Slack si configuré
            if SLACK_WEBHOOK_URL:
                if send_slack_notification(alert):
                    slack_sent += 1
                    print("  → Notification Slack envoyée ✓")
            
            # Envoyer notification Email si configuré
            if all([SMTP_HOST, EMAIL_TO]):
                if send_email_notification(alert):
                    email_sent += 1
                    print("  → Notification Email envoyée ✓")
            
            print()
            
    except KeyboardInterrupt:
        # ═══════════════════════════════════════════════════════════════
        # Affichage du résumé à l'arrêt (Ctrl+C)
        # ═══════════════════════════════════════════════════════════════
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
