from typing import Dict, Any, List
import re

class ConfidenceScorer:
    def __init__(self):
        self.patterns = {
            "index_suggestion": [
                r"CREATE INDEX",
                r"idx_\w+",
                r"ON \w+\("
            ],
            "query_rewrite": [
                r"SELECT.*FROM",
                r"WHERE.*=",
                r"JOIN.*ON"
            ],
            "performance_issue": [
                r"Seq Scan",
                r"slow",
                r"bottleneck"
            ]
        }
    
    def calculate_confidence(self, suggestion: str, metrics: Dict) -> float:
        confidence = 0.5  # Base confidence
        
        # Factor 1: Pattern matching
        pattern_score = self._check_patterns(suggestion)
        confidence += pattern_score * 0.2
        
        # Factor 2: Metrics support
        if metrics.get("seq_scan", 0) > 100:
            confidence += 0.15
        if metrics.get("idx_scan", 0) < 50:
            confidence += 0.15
        
        # Factor 3: Historical success rate
        if metrics.get("historical_success_rate"):
            confidence *= metrics["historical_success_rate"]
        
        # Factor 4: Data volume
        row_count = metrics.get("row_count", 0)
        if row_count > 10000:
            confidence += 0.1
        elif row_count < 100:
            confidence -= 0.1
        
        return min(0.95, max(0.1, confidence))
    
    def _check_patterns(self, text: str) -> float:
        matches = 0
        total = 0
        
        for category, patterns in self.patterns.items():
            for pattern in patterns:
                total += 1
                if re.search(pattern, text, re.IGNORECASE):
                    matches += 1
        
        return matches / total if total > 0 else 0.5
    
    def get_confidence_level(self, confidence: float) -> Dict:
        if confidence >= 0.8:
            return {
                "level": "HIGH",
                "color": "green",
                "icon": "✅",
                "message": "High confidence - Strongly recommend implementing"
            }
        elif confidence >= 0.6:
            return {
                "level": "MEDIUM",
                "color": "yellow",
                "icon": "⚠️",
                "message": "Medium confidence - Consider testing first"
            }
        else:
            return {
                "level": "LOW",
                "color": "red",
                "icon": "❌",
                "message": "Low confidence - Manual review recommended"
            }