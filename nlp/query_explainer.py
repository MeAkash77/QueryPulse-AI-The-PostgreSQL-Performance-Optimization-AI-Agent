import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

class QueryExplainer:
    def __init__(self, llm):
        self.llm = llm
    
    def explain_performance(self, query: str, execution_plan: str, metrics: Dict) -> str:
        """Explain why a query is slow in plain English"""
        
        prompt = f"""
        You are a PostgreSQL performance expert. Explain why this query is slow in simple English.
        
        Query: {query}
        
        Execution Plan: {execution_plan[:500]}
        
        Metrics:
        - Execution Time: {metrics.get('execution_time', 'N/A')}ms
        - Scan Type: {metrics.get('scan_type', 'N/A')}
        - Rows Examined: {metrics.get('rows_examined', 'N/A')}
        
        Please explain:
        1. What is causing the slowness (simple terms)
        2. What should be done to fix it
        3. Expected improvement after fix
        
        Keep response under 200 words, no technical jargon.
        """
        
        try:
            response = self.llm.invoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error(f"Error explaining query: {e}")
            return self._fallback_explanation(metrics)
    
    def _fallback_explanation(self, metrics: Dict) -> str:
        """Fallback explanation when AI is unavailable"""
        if metrics.get('scan_type') == 'Seq Scan':
            return ("Your query is doing a Sequential Scan (reading every row). "
                    "This is slow because the table doesn't have proper indexes. "
                    "Adding an index on the columns in your WHERE clause will make it much faster.")
        elif metrics.get('execution_time', 0) > 100:
            return ("Your query is taking too long to run. "
                    "This usually happens when the database has to examine many rows. "
                    "Consider adding indexes or breaking the query into smaller parts.")
        else:
            return ("Your query performance looks good. "
                    "Keep monitoring as data grows.")
    
    def analyze_slow_queries(self, slow_queries: list) -> str:
        """Analyze multiple slow queries and provide summary"""
        if not slow_queries:
            return "No slow queries detected. Database is healthy!"
        
        summary = f"I found {len(slow_queries)} slow queries in your database:\n\n"
        
        for i, sq in enumerate(slow_queries[:3], 1):
            summary += f"{i}. Query took {sq.get('mean_time', 0):.0f}ms\n"
            summary += f"   Problem: {sq.get('problem', 'Unknown')}\n"
            summary += f"   Fix: {sq.get('fix', 'Add appropriate indexes')}\n\n"
        
        return summary
