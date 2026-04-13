import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any
import pandas as pd

logger = logging.getLogger(__name__)

class AlertManager:
    def __init__(self, sql_agent):
        self.sql_agent = sql_agent
        self.alerts = []
        self.metrics_history = []
        self.running = False
        self.alert_callbacks = []
    
    def start_monitoring(self, interval_seconds=60):
        """Start background monitoring thread"""
        self.running = True
        
        def monitor_loop():
            while self.running:
                try:
                    self.collect_metrics()
                    self.check_predictive_alerts()
                    time.sleep(interval_seconds)
                except Exception as e:
                    logger.error(f"Monitor loop error: {e}")
        
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        logger.info("Monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
    
    def collect_metrics(self):
        """Collect current database metrics"""
        queries = {
            'table_sizes': """
                SELECT relname, n_live_tup, 
                       pg_size_pretty(pg_total_relation_size(relid)) as size
                FROM pg_stat_user_tables
                ORDER BY n_live_tup DESC
                LIMIT 10;
            """,
            'slow_queries': """
                SELECT query, calls, mean_time, max_time
                FROM pg_stat_statements
                ORDER BY mean_time DESC
                LIMIT 5;
            """,
            'index_usage': """
                SELECT relname, idx_scan, seq_scan,
                       CASE WHEN seq_scan > 0 
                            THEN round(100.0 * idx_scan / (seq_scan + idx_scan), 2)
                            ELSE 100 END as index_ratio
                FROM pg_stat_user_tables
                WHERE seq_scan + idx_scan > 0;
            """
        }
        
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'metrics': {}
        }
        
        for name, query in queries.items():
            try:
                result = self.sql_agent.execute_query(query)
                metrics['metrics'][name] = result
            except Exception as e:
                logger.error(f"Failed to collect {name}: {e}")
        
        self.metrics_history.append(metrics)
        
        # Keep last 24 hours of data (1440 data points at 1 minute intervals)
        if len(self.metrics_history) > 1440:
            self.metrics_history = self.metrics_history[-1440:]
        
        return metrics
    
    def check_predictive_alerts(self):
        """Analyze metrics for upcoming performance issues"""
        if len(self.metrics_history) < 10:
            return
        
        # Check for growth trends
        growth_alerts = self.detect_growth_trends()
        for alert in growth_alerts:
            self.add_alert(alert)
        
        # Check for index degradation
        index_alerts = self.detect_index_degradation()
        for alert in index_alerts:
            self.add_alert(alert)
        
        # Check for query time increases
        query_alerts = self.detect_slow_query_trends()
        for alert in query_alerts:
            self.add_alert(alert)
    
    def detect_growth_trends(self):
        """Detect tables growing too fast"""
        alerts = []
        
        try:
            # Get growth data from last 24 hours
            if len(self.metrics_history) < 2:
                return alerts
            
            first_metrics = self.metrics_history[0].get('metrics', {}).get('table_sizes', [])
            last_metrics = self.metrics_history[-1].get('metrics', {}).get('table_sizes', [])
            
            for last_table in last_metrics:
                first_table = next((f for f in first_metrics if f['relname'] == last_table['relname']), None)
                
                if first_table:
                    growth = last_table['n_live_tup'] - first_table['n_live_tup']
                    growth_rate = growth / len(self.metrics_history)
                    
                    if growth_rate > 1000:  # Growing by >1000 rows per minute
                        alerts.append({
                            'type': 'growth',
                            'severity': 'warning',
                            'title': f"Rapid growth detected in {last_table['relname']}",
                            'message': f"Table growing at {growth_rate:.0f} rows/minute. Will hit size limits soon.",
                            'predicted_issue': 'Table size will become unmanageable within 7 days',
                            'recommendation': 'Consider partitioning or archiving old data',
                            'timestamp': datetime.now().isoformat()
                        })
        except Exception as e:
            logger.error(f"Growth detection error: {e}")
        
        return alerts
    
    def detect_index_degradation(self):
        """Detect when indexes are becoming less effective"""
        alerts = []
        
        try:
            index_metrics = self.metrics_history[-1].get('metrics', {}).get('index_usage', [])
            
            for table in index_metrics:
                if table['index_ratio'] < 50:  # Less than 50% index usage
                    alerts.append({
                        'type': 'index_degradation',
                        'severity': 'critical',
                        'title': f"Poor index usage on {table['relname']}",
                        'message': f"Only {table['index_ratio']}% of queries use indexes on this table",
                        'predicted_issue': 'Query performance will degrade as table grows',
                        'recommendation': 'Review and optimize indexes on this table',
                        'timestamp': datetime.now().isoformat()
                    })
        except Exception as e:
            logger.error(f"Index degradation detection error: {e}")
        
        return alerts
    
    def detect_slow_query_trends(self):
        """Detect queries getting slower over time"""
        alerts = []
        
        try:
            if len(self.metrics_history) < 60:  # Need at least 1 hour of data
                return alerts
            
            slow_queries = self.metrics_history[-1].get('metrics', {}).get('slow_queries', [])
            
            for query in slow_queries:
                if query.get('mean_time', 0) > 100:  # Query taking >100ms
                    alerts.append({
                        'type': 'slow_query',
                        'severity': 'warning',
                        'title': f"Slow query detected",
                        'message': f"Query averaging {query['mean_time']:.0f}ms, called {query['calls']} times",
                        'predicted_issue': 'Will become slower as data grows',
                        'recommendation': 'Add indexes or rewrite query',
                        'query': query['query'][:200],
                        'timestamp': datetime.now().isoformat()
                    })
        except Exception as e:
            logger.error(f"Slow query detection error: {e}")
        
        return alerts
    
    def add_alert(self, alert):
        """Add alert and trigger callbacks"""
        self.alerts.append(alert)
        
        # Keep last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        # Trigger callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        logger.warning(f"Alert: {alert['title']}")
    
    def get_active_alerts(self):
        """Get alerts from last hour"""
        one_hour_ago = datetime.now() - timedelta(hours=1)
        return [a for a in self.alerts if datetime.fromisoformat(a['timestamp']) > one_hour_ago]
    
    def get_alert_history(self, limit=50):
        """Get alert history"""
        return self.alerts[-limit:]
