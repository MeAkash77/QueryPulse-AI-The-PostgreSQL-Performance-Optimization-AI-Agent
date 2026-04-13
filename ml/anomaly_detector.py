import numpy as np
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class AnomalyDetector:
    def __init__(self, window_size: int = 30, threshold: float = 2.0):
        self.window_size = window_size
        self.threshold = threshold
        self.history = []
    
    def add_metric(self, value: float, timestamp: datetime = None):
        if timestamp is None:
            timestamp = datetime.now()
        self.history.append({"value": value, "timestamp": timestamp})
        
        if len(self.history) > self.window_size * 10:
            self.history = self.history[-self.window_size * 10:]
    
    def detect_anomaly(self, value: float) -> Tuple[bool, float, Dict]:
        if len(self.history) < self.window_size:
            return False, 0, {"reason": "Insufficient data"}
        
        recent_values = [h["value"] for h in self.history[-self.window_size:]]
        mean = np.mean(recent_values)
        std = np.std(recent_values)
        
        if std == 0:
            return False, 0, {"reason": "No variation in data"}
        
        z_score = abs((value - mean) / std)
        is_anomaly = z_score > self.threshold
        
        return is_anomaly, z_score, {
            "mean": mean,
            "std": std,
            "expected_range": f"{mean - self.threshold * std:.2f} - {mean + self.threshold * std:.2f}",
            "current": value
        }
    
    def predict_trend(self, days_ahead: int = 7) -> Dict:
        if len(self.history) < 10:
            return {"error": "Insufficient data for prediction"}
        
        values = [h["value"] for h in self.history[-50:]]
        x = np.arange(len(values))
        
        # Simple linear regression
        slope, intercept = np.polyfit(x, values, 1)
        
        predicted = intercept + slope * (len(values) + days_ahead)
        growth_rate = (slope / (np.mean(values) + 0.01)) * 100
        
        return {
            "predicted_value": predicted,
            "growth_rate_percent": growth_rate,
            "trend": "increasing" if slope > 0 else "decreasing",
            "days_to_double": abs(70 / growth_rate) if growth_rate != 0 else None
        }