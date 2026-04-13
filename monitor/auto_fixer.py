import logging
import time
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class AutoFixer:
    def __init__(self, sql_agent, approval_required=True):
        self.sql_agent = sql_agent
        self.approval_required = approval_required
        self.pending_changes = []
        self.applied_changes = []
        
    def analyze_and_suggest_fixes(self):
        """Analyze database and suggest fixes"""
        suggestions = []
        
        # Check for missing indexes
        missing_indexes = self.find_missing_indexes()
        if missing_indexes:
            suggestions.extend(missing_indexes)
        
        # Check for unused indexes
        unused_indexes = self.find_unused_indexes()
        if unused_indexes:
            suggestions.extend(unused_indexes)
        
        # Check for outdated statistics
        if self.needs_analyze():
            suggestions.append({
                'type': 'analyze',
                'description': 'Update table statistics for better query planning',
                'sql': 'ANALYZE orders; ANALYZE users;',
                'risk': 'low'
            })
        
        return suggestions
    
    def find_missing_indexes(self):
        """Find tables that need indexes based on sequential scans"""
        query = """
        SELECT 
            schemaname,
            relname as table_name,
            seq_scan,
            idx_scan,
            seq_tup_read,
            n_live_tup
        FROM pg_stat_user_tables
        WHERE seq_scan > idx_scan * 2
        AND seq_scan > 100
        ORDER BY seq_scan DESC
        LIMIT 5;
        """
        
        try:
            result = self.sql_agent.execute_query(query)
            suggestions = []
            
            for row in result:
                suggestions.append({
                    'type': 'index',
                    'table': row['table_name'],
                    'description': f"Table '{row['table_name']}' has {row['seq_scan']} seq scans but only {row['idx_scan']} index scans",
                    'sql': f"CREATE INDEX CONCURRENTLY idx_{row['table_name']}_auto ON {row['table_name']}(user_id, status);",
                    'risk': 'medium',
                    'impact': f"Expected to reduce scans by up to 80%"
                })
            
            return suggestions
        except Exception as e:
            logger.error(f"Error finding missing indexes: {e}")
            return []
    
    def find_unused_indexes(self):
        """Find indexes that are never used"""
        query = """
        SELECT 
            schemaname,
            relname as table_name,
            indexrelname as index_name,
            idx_scan,
            pg_size_pretty(pg_relation_size(indexrelname::regclass)) as size
        FROM pg_stat_user_indexes
        WHERE idx_scan = 0
        AND indexrelname NOT LIKE '%pkey%'
        ORDER BY pg_relation_size(indexrelname::regclass) DESC
        LIMIT 5;
        """
        
        try:
            result = self.sql_agent.execute_query(query)
            suggestions = []
            
            for row in result:
                suggestions.append({
                    'type': 'drop_index',
                    'table': row['table_name'],
                    'index': row['index_name'],
                    'description': f"Index '{row['index_name']}' on {row['table_name']} is never used (size: {row['size']})",
                    'sql': f"DROP INDEX CONCURRENTLY {row['index_name']};",
                    'risk': 'low',
                    'impact': f"Will free {row['size']} of storage and improve write performance"
                })
            
            return suggestions
        except Exception as e:
            logger.error(f"Error finding unused indexes: {e}")
            return []
    
    def needs_analyze(self):
        """Check if tables need statistics update"""
        query = """
        SELECT COUNT(*) > 0 as needs_analyze
        FROM pg_stat_user_tables
        WHERE last_analyze IS NULL 
        OR last_analyze < now() - interval '7 days';
        """
        
        try:
            result = self.sql_agent.execute_query(query)
            return result[0]['needs_analyze'] if result else False
        except Exception as e:
            logger.error(f"Error checking analyze need: {e}")
            return False
    
    def apply_fix(self, suggestion, approved=True):
        """Apply a fix after approval"""
        if not approved:
            logger.info(f"Suggestion rejected: {suggestion['description']}")
            return False
        
        try:
            logger.info(f"Applying fix: {suggestion['description']}")
            
            if suggestion['type'] == 'index':
                self.sql_agent.execute_query(suggestion['sql'])
                self.applied_changes.append({
                    **suggestion,
                    'applied_at': datetime.now().isoformat(),
                    'status': 'success'
                })
                return True
                
            elif suggestion['type'] == 'drop_index':
                self.sql_agent.execute_query(suggestion['sql'])
                self.applied_changes.append({
                    **suggestion,
                    'applied_at': datetime.now().isoformat(),
                    'status': 'success'
                })
                return True
                
            elif suggestion['type'] == 'analyze':
                self.sql_agent.execute_query(suggestion['sql'])
                self.applied_changes.append({
                    **suggestion,
                    'applied_at': datetime.now().isoformat(),
                    'status': 'success'
                })
                return True
                
        except Exception as e:
            logger.error(f"Failed to apply fix: {e}")
            return False
    
    def rollback_fix(self, fix_id):
        """Rollback a previously applied fix"""
        fix = next((f for f in self.applied_changes if f.get('id') == fix_id), None)
        if not fix:
            return False
        
        try:
            if fix['type'] == 'index':
                rollback_sql = f"DROP INDEX CONCURRENTLY {fix['sql'].split('ON')[0].split('idx_')[1].strip()};"
                self.sql_agent.execute_query(rollback_sql)
                fix['rolled_back_at'] = datetime.now().isoformat()
                return True
        except Exception as e:
            logger.error(f"Failed to rollback: {e}")
            return False
