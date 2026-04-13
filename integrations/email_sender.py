import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import os

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_user)
    
    def send_alert(self, to_email: str, alert: dict):
        subject = f"[QueryPulse-AI] {alert.get('severity', 'Alert').upper()}: {alert.get('title', 'Database Alert')}"
        
        body = f"""
        <html>
        <body>
            <h2>{alert.get('title', 'Database Performance Alert')}</h2>
            <p><strong>Severity:</strong> {alert.get('severity', 'info')}</p>
            <p><strong>Message:</strong> {alert.get('message', '')}</p>
            <p><strong>Predicted Issue:</strong> {alert.get('predicted_issue', 'N/A')}</p>
            <p><strong>Recommendation:</strong> {alert.get('recommendation', 'Monitor and review')}</p>
            <hr>
            <p><small>QueryPulse-AI - Automated Database Performance Optimizer</small></p>
        </body>
        </html>
        """
        
        self._send_email(to_email, subject, body)
    
    def _send_email(self, to_email: str, subject: str, body: str):
        if not self.smtp_user or not self.smtp_password:
            logger.warning("Email credentials not configured")
            return
        
        msg = MIMEMultipart()
        msg["From"] = self.from_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info(f"Email sent to {to_email}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")