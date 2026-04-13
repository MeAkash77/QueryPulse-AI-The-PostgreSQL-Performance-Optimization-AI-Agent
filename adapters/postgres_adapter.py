from .base_adapter import DatabaseAdapter
from sql.sql_agent import SQLAgent
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class PostgresAdapter(DatabaseAdapter):
    def __init__(self, config: Dict):
        self.config = config
        self.agent = SQLAgent(config)
    
    def connect(self, config: Dict) -> Any:
        return self.agent.get_connection()
    
    def execute_query(self, query: str) -> List[Dict]:
        return self.agent.execute_query(query)
    
    def get_schema(self) -> Dict:
        return self.agent.get_schema()
    
    def get_performance_metrics(self) -> Dict:
        metrics = {}
        
        # Get table stats
        metrics['table_stats'] = self.agent.execute_query("""
            SELECT relname, n_live_tup, seq_scan, idx_scan
            FROM pg_stat_user_tables
        """)
        
        # Get index stats
        metrics['index_stats'] = self.agent.execute_query("""
            SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
            FROM pg_stat_user_indexes
        """)
        
        return metrics
    
    def suggest_indexes(self) -> List[Dict]:
        return self.agent.suggest_indexes()
