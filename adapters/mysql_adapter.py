from .base_adapter import DatabaseAdapter
import pymysql
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class MySQLAdapter(DatabaseAdapter):
    def __init__(self, config: Dict):
        self.config = config
        self.connection = None
    
    def connect(self, config: Dict) -> Any:
        self.connection = pymysql.connect(
            host=config['host'],
            port=config.get('port', 3306),
            user=config['user'],
            password=config['password'],
            database=config['database'],
            cursorclass=pymysql.cursors.DictCursor
        )
        return self.connection
    
    def execute_query(self, query: str) -> List[Dict]:
        if not self.connection:
            self.connect(self.config)
        
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    
    def get_schema(self) -> Dict:
        query = """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
            ORDER BY table_name, ordinal_position
        """
        return self.execute_query(query)
    
    def get_performance_metrics(self) -> Dict:
        metrics = {}
        
        # MySQL specific metrics
        metrics['slow_queries'] = self.execute_query("SHOW VARIABLES LIKE 'slow_query_log'")
        metrics['connections'] = self.execute_query("SHOW STATUS LIKE 'Threads_connected'")
        
        return metrics
    
    def suggest_indexes(self) -> List[Dict]:
        # MySQL-specific index suggestions
        query = """
            SELECT 
                table_name,
                index_name,
                cardinality,
                (cardinality / (SELECT COUNT(*) FROM information_schema.tables)) as selectivity
            FROM information_schema.statistics
            WHERE cardinality < 100
        """
        return self.execute_query(query)
