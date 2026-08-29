from __future__ import annotations

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from app.plugins.mailmanager.main import get_mailmanager_settings

logger = logging.getLogger(__name__)


def send_verification_email(email: str, token: str, first_name: str | None = None) -> bool:
    settings = get_mailmanager_settings()
    
    primary_host = settings.get("smtp_host", "mail.vlahx.org")
    smtp_port = int(settings.get("smtp_port", 587))
    from_email = os.environ.get("SMTP_FROM_EMAIL", "no-reply@vlahx.org")
    from_name = os.environ.get("SMTP_FROM_NAME", "VlahX Core Security")
    smtp_user = os.environ.get("SMTP_USER", "no-reply@vlahx.org")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    
    domain_origin = os.environ.get("PUBLIC_SITE_ORIGIN", "https://vlahx.org").rstrip("/")
    verify_url = f"{domain_origin}/verify-email?token={token}"
    name_display = first_name or email.split("@")[0]
    
    subject = "🔑 Confirmă adresa ta de email - VlahX Core"
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
    .card {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 16px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }}
    .header {{ text-align: center; margin-bottom: 24px; }}
    .logo {{ font-size: 28px; font-weight: 800; color: #0284c7; text-decoration: none; }}
    .btn {{ display: inline-block; background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); color: #ffffff !important; padding: 14px 32px; border-radius: 50px; text-decoration: none; font-weight: 600; margin: 24px 0; text-align: center; box-shadow: 0 4px 12px rgba(2,132,199,0.3); }}
    .footer {{ font-size: 12px; color: #94a3b8; text-align: center; margin-top: 32px; border-top: 1px solid #f1f5f9; padding-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <a href="{domain_origin}" class="logo">⚡ VlahX Core</a>
    </div>
    <h2>Salut, {name_display}! 👋</h2>
    <p>Îți mulțumim că te-ai înregistrat pe platforma VlahX Core. Pentru a-ți activa contul și a continua către profilul tău, confirmă adresa de email apăsând pe butonul de mai jos:</p>
    <div style="text-align: center;">
      <a href="{verify_url}" class="btn">🔑 Confirmă Adresa de Email ↗</a>
    </div>
    <p style="font-size: 13px; color: #64748b;">Dacă nu poți apăsa pe buton, copiază acest link în browser-ul tău:<br>
    <a href="{verify_url}" style="color: #0284c7;">{verify_url}</a></p>
    <div class="footer">
      Acest mesaj a fost trimis automat de către VlahX Core ({from_email}). Dacă nu te-ai înregistrat tu, poți ignora acest email.
    </div>
  </div>
</body>
</html>
"""
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="vlahx.org")
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    
    # Try internal container relay first (instant delivery), then fallbacks
    hosts_to_try = [
        ("hosting_mailserver", 25),
        ("127.0.0.1", 25),
        (primary_host, smtp_port),
        ("hosting_mailserver", 587)
    ]
    
    for host, port in hosts_to_try:
        try:
            with smtplib.SMTP(host, port, timeout=4) as server:
                server.ehlo()
                if port == 587:
                    server.starttls()
                    server.ehlo()
                if smtp_user and smtp_pass and port == 587:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, [email], msg.as_string())
            logger.info(f"✅ Verification email sent to {email} via {host}:{port}")
            return True
        except Exception as e:
            logger.warning(f"Failed SMTP via {host}:{port}: {e}")
            
    logger.error(f"❌ All SMTP attempts failed for {email}")
    return False
