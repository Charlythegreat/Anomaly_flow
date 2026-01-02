#!/usr/bin/env python3
"""
Script de test pour vérifier la configuration email SMTP.

Ce script permet de tester la configuration SMTP avant d'utiliser
le consumer d'alertes. Il envoie un email de test et affiche
les résultats détaillés de chaque étape.

Usage:
    SMTP_HOST=smtp.gmail.com \\
    SMTP_PORT=587 \\
    SMTP_USER=votre-email@gmail.com \\
    SMTP_PASSWORD=votre-app-password \\
    EMAIL_TO=destinataire@example.com \\
    python -m src.test_email

Configuration Gmail:
    1. Activez la vérification en 2 étapes sur votre compte Google
    2. Créez un "App Password": https://myaccount.google.com/apppasswords
    3. Utilisez ce mot de passe (16 caractères) comme SMTP_PASSWORD
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def test_email_config():
    """
    Teste la configuration SMTP et envoie un email de test.
    
    Vérifie:
        1. Que toutes les variables d'environnement sont définies
        2. La connexion au serveur SMTP
        3. L'activation du chiffrement TLS
        4. L'authentification
        5. L'envoi effectif de l'email
    
    Returns:
        True si le test a réussi, False sinon
    """
    # ═══════════════════════════════════════════════════════════════════
    # Récupération de la configuration depuis les variables d'environnement
    # ═══════════════════════════════════════════════════════════════════
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "") or os.getenv("SMTP_PASS", "")
    email_to = os.getenv("EMAIL_TO", "")
    
    # ═══════════════════════════════════════════════════════════════════
    # Affichage de la configuration actuelle
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 60)
    print("🧪 TEST DE CONFIGURATION EMAIL SMTP")
    print("=" * 60)
    print(f"\n📧 Configuration actuelle:")
    print(f"   SMTP_HOST:     {smtp_host}")
    print(f"   SMTP_PORT:     {smtp_port}")
    print(f"   SMTP_USER:     {smtp_user or '❌ NON CONFIGURÉ'}")
    print(f"   SMTP_PASSWORD: {'✅ Configuré' if smtp_password else '❌ NON CONFIGURÉ'}")
    print(f"   EMAIL_TO:      {email_to or '❌ NON CONFIGURÉ'}")
    print()
    
    # ═══════════════════════════════════════════════════════════════════
    # Vérification des paramètres requis
    # ═══════════════════════════════════════════════════════════════════
    missing = []
    if not smtp_user:
        missing.append("SMTP_USER")
    if not smtp_password:
        missing.append("SMTP_PASSWORD")
    if not email_to:
        missing.append("EMAIL_TO")
    
    if missing:
        print("❌ Paramètres manquants:", ", ".join(missing))
        print("\n📝 Exemple d'utilisation:")
        print("""
    SMTP_HOST=smtp.gmail.com \\
    SMTP_PORT=587 \\
    SMTP_USER=votre-email@gmail.com \\
    SMTP_PASSWORD=votre-app-password \\
    EMAIL_TO=destinataire@example.com \\
    python -m src.test_email
        """)
        return False
    
    # ═══════════════════════════════════════════════════════════════════
    # Construction de l'email de test
    # ═══════════════════════════════════════════════════════════════════
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🧪 Test Anomaly Flow - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    msg["From"] = smtp_user
    msg["To"] = email_to
    
    # Contenu texte simple
    text_content = f"""
Test de configuration email Anomaly Flow
=========================================

Ce message confirme que votre configuration SMTP fonctionne correctement.

Détails:
- Serveur SMTP: {smtp_host}:{smtp_port}
- Expéditeur: {smtp_user}
- Date: {datetime.now().isoformat()}

Vous recevrez désormais les alertes d'anomalies par email.
    """
    
    # Contenu HTML enrichi
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #2196F3;">🧪 Test Anomaly Flow</h2>
        <p>Ce message confirme que votre configuration SMTP fonctionne correctement.</p>
        
        <table style="border-collapse: collapse; margin: 20px 0;">
            <tr>
                <td style="padding: 10px; background: #f5f5f5; border: 1px solid #ddd;"><strong>Serveur SMTP</strong></td>
                <td style="padding: 10px; border: 1px solid #ddd;">{smtp_host}:{smtp_port}</td>
            </tr>
            <tr>
                <td style="padding: 10px; background: #f5f5f5; border: 1px solid #ddd;"><strong>Expéditeur</strong></td>
                <td style="padding: 10px; border: 1px solid #ddd;">{smtp_user}</td>
            </tr>
            <tr>
                <td style="padding: 10px; background: #f5f5f5; border: 1px solid #ddd;"><strong>Date</strong></td>
                <td style="padding: 10px; border: 1px solid #ddd;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
        </table>
        
        <p style="color: #4CAF50;">✅ Vous recevrez désormais les alertes d'anomalies par email.</p>
        
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
    # Tentative de connexion et d'envoi
    # ═══════════════════════════════════════════════════════════════════
    print("📤 Tentative de connexion au serveur SMTP...")
    
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            print(f"   ✅ Connexion à {smtp_host}:{smtp_port} réussie")
            
            server.starttls()
            print("   ✅ Chiffrement TLS activé")
            
            server.login(smtp_user, smtp_password)
            print("   ✅ Authentification réussie")
            
            server.sendmail(smtp_user, email_to, msg.as_string())
            print(f"   ✅ Email envoyé à {email_to}")
        
        print("\n" + "=" * 60)
        print("✅ TEST RÉUSSI!")
        print("=" * 60)
        print(f"\n📬 Vérifiez votre boîte de réception: {email_to}")
        print("   (Vérifiez aussi les spams si vous ne voyez pas l'email)")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"\n❌ ERREUR D'AUTHENTIFICATION:")
        print(f"   {e}")
        print("\n💡 Solutions possibles:")
        print("   1. Vérifiez que SMTP_USER et SMTP_PASSWORD sont corrects")
        print("   2. Pour Gmail, utilisez un 'App Password' (pas votre mot de passe normal)")
        print("   3. Activez la vérification en 2 étapes sur votre compte Google")
        print("   4. Créez un App Password: https://myaccount.google.com/apppasswords")
        return False
        
    except smtplib.SMTPConnectError as e:
        print(f"\n❌ ERREUR DE CONNEXION:")
        print(f"   {e}")
        print("\n💡 Solutions possibles:")
        print(f"   1. Vérifiez que {smtp_host}:{smtp_port} est accessible")
        print("   2. Vérifiez votre connexion internet")
        return False
        
    except Exception as e:
        print(f"\n❌ ERREUR INATTENDUE:")
        print(f"   {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    test_email_config()
