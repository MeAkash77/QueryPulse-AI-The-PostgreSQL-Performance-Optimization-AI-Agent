from typing import Dict, Any
import uuid

class MultiTenantManager:
    def __init__(self, sql_agent):
        self.sql_agent = sql_agent
        self._init_tenant_tables()
    
    def _init_tenant_tables(self):
        self.sql_agent.execute_query("""
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                name TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                settings JSONB DEFAULT '{}',
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        
        self.sql_agent.execute_query("""
            CREATE TABLE IF NOT EXISTS tenant_queries (
                id SERIAL PRIMARY KEY,
                tenant_id TEXT,
                query TEXT,
                executed_at TIMESTAMP DEFAULT NOW(),
                execution_time_ms FLOAT,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            )
        """)
    
    def create_tenant(self, name: str) -> str:
        tenant_id = str(uuid.uuid4())[:8]
        self.sql_agent.execute_query("""
            INSERT INTO tenants (id, name) VALUES (%s, %s)
        """, (tenant_id, name))
        return tenant_id
    
    def get_tenant_context(self, tenant_id: str) -> Dict:
        result = self.sql_agent.execute_query("""
            SELECT * FROM tenants WHERE id = %s AND is_active = TRUE
        """, (tenant_id,))
        
        if result:
            return result[0]
        return None
    
    def log_query(self, tenant_id: str, query: str, execution_time_ms: float):
        self.sql_agent.execute_query("""
            INSERT INTO tenant_queries (tenant_id, query, execution_time_ms)
            VALUES (%s, %s, %s)
        """, (tenant_id, query, execution_time_ms))