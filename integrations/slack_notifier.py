import requests
import logging
from typing import Dict, Any
import os

logger = logging.getLogger(__name__)

class SlackNotifier:
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    
    def send_alert(self, alert: Dict):
        if not self.webhook_url:
            logger.warning("Slack webhook not configured")
            return
        
        color_map = {
            "critical": "danger",
            "warning": "warning",
            "info": "good"
        }
        
        payload = {
            "attachments": [{
                "color": color_map.get(alert.get("severity", "info"), "good"),
                "title": alert.get("title", "Database Alert"),
                "text": alert.get("message", ""),
                "fields": [
                    {"title": "Predicted Issue", "value": alert.get("predicted_issue", "N/A"), "short": False},
                    {"title": "Recommendation", "value": alert.get("recommendation", "Monitor"), "short": False}
                ],
                "footer": "QueryPulse-AI",
                "ts": int(alert.get("timestamp", 0))
            }]
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            logger.info("Slack alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
    
    def send_performance_report(self, metrics: Dict):
        if not self.webhook_url:
            return
        
        payload = {
            "text": f"📊 *Daily Performance Report*\n"
                    f"• Avg Query Time: {metrics.get('avg_time', 'N/A')}ms\n"
                    f"• Index Usage: {metrics.get('index_usage', 'N/A')}%\n"
                    f"• Slow Queries: {metrics.get('slow_queries', 0)}\n"
                    f"• Improvement: {metrics.get('improvement', 'N/A')}%"
        }
        
        try:
            requests.post(self.webhook_url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send report: {e}")