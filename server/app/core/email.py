import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def send_reset_password_email(email_to: str, token: str) -> None:
    subject = f"Password reset for {settings.PROJECT_NAME}"
    link = f"omnisource://reset-password?token={token}"

    html_content = f"""
    <html>
        <head>
            <style>
                .container {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f9f9f9;
                }}
                .card {{
                    background-color: #ffffff;
                    padding: 40px;
                    border-radius: 12px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
                    border: 1px solid #e1e4e8;
                }}
                .logo {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #2D3436;
                    margin-bottom: 20px;
                    text-align: center;
                }}
                .button {{
                    display: inline-block;
                    padding: 14px 30px;
                    background-color: #0984E3;
                    color: #ffffff !important;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    margin: 20px 0;
                }}
                .token-box {{
                    background-color: #f1f2f6;
                    padding: 15px;
                    text-align: center;
                    font-size: 24px;
                    letter-spacing: 5px;
                    font-weight: bold;
                    border-radius: 8px;
                    color: #2D3436;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    font-size: 12px;
                    color: #636E72;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="logo">{settings.PROJECT_NAME}</div>
                <div class="card">
                    <h2 style="margin-top: 0;">Reset Your Password</h2>
                    <p>Hello,</p>
                    <p>We received a request to reset the password for your <b>{settings.PROJECT_NAME}</b> account. If you didn't make this request, you can safely ignore this email.</p>
                    
                    <p style="text-align: center;">
                        <a href="{link}" class="button">Reset Password</a>
                    </p>
                    
                    <p>Or use this direct reset code:</p>
                    <div class="token-box">{token}</div>
                    
                    <p style="font-size: 14px; color: #b2bec3;">* This link and code will expire in 15 minutes.</p>
                </div>
                <div class="footer">
                    &copy; 2026 {settings.PROJECT_NAME} AI. All rights reserved.<br>
                    Integrated Intelligence for Your Media Sources.
                </div>
            </div>
        </body>
    </html>
    """

    message = MIMEMultipart()
    message["From"] = settings.EMAILS_FROM_EMAIL
    message["To"] = email_to
    message["Subject"] = subject
    message.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=15,
        ) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        logger.info("Password reset email sent to %s", email_to)
    except Exception as e:
        logger.exception("Error sending reset email to %s: %s", email_to, e)
        raise
