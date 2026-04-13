# sql_agent.py
import logging
from typing import Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql as psql
import re  # ADDED for regex operations

logger = logging.getLogger(__name__)

class SQLAgent:
    def __init__(self, db_config: Dict[str, Any], name: str = "SQLAgent"):
        self.db_config = db_config
        self.name = name
        self._schema = None
        logger.info(f"Initialized SQLAgent for {db_config['database']}")

    def get_connection(self):
        try:
            # Build connection parameters
            conn_params = {
                "host": self.db_config["host"],
                "port": self.db_config["port"],
                "user": self.db_config["user"],
                "password": self.db_config["password"],
                "database": self.db_config["database"]
            }
            
            # Add SSL support for Neon and other cloud databases
            # Check for SSL flag in config or default to True for security
            if self.db_config.get("ssl", True) or "neon.tech" in self.db_config["host"]:
                conn_params["sslmode"] = "require"
                logger.debug("SSL mode enabled for connection")
            
            conn = psycopg2.connect(**conn_params)
            conn.autocommit = False
            return conn
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            raise

    def get_schema(self) -> Dict[str, List[str]]:
        if self._schema:
            return self._schema
            
        logger.debug("Fetching schema...")
        schema = {}
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT table_name, column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public'
                        ORDER BY table_name, ordinal_position;
                    """)
                    for table, column, dtype in cursor.fetchall():
                        if table not in schema:
                            schema[table] = []
                        schema[table].append(f"{column} ({dtype})")
                    self._schema = schema
                    logger.info(f"Schema loaded with {len(schema)} tables")
                    return schema
        except Exception as e:
            logger.error(f"Schema fetch failed: {str(e)}")
            raise

    def execute_query(self, query: str) -> List[Dict]:
        logger.info(f"Executing query: {query[:100]}...")
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query)
                
                # Check if it's a SELECT query
                if query.strip().upper().startswith('SELECT'):
                    result = cursor.fetchall()
                    logger.debug(f"Query returned {len(result)} rows")
                    conn.commit()
                    return result
                else:
                    # For INSERT, UPDATE, DELETE, etc.
                    conn.commit()
                    result = [{"affected_rows": cursor.rowcount, "status": "success"}]
                    logger.debug(f"Query affected {cursor.rowcount} rows")
                    return result
                    
        except psycopg2.Error as e:
            logger.error(f"Query error: {str(e)}")
            if conn:
                conn.rollback()
            raise RuntimeError(f"SQL Error: {str(e)}") from e
        except Exception as e:
            logger.error(f"Execution failed: {str(e)}")
            if conn:
                conn.rollback()
            raise RuntimeError(f"Execution error: {str(e)}") from e
        finally:
            if conn:
                conn.close()

    def validate_query(self, query: str) -> bool:
        """Validate SQL query syntax using EXPLAIN"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # Use EXPLAIN to validate without executing
                    explain_query = f"EXPLAIN {query}"
                    cursor.execute(explain_query)
                    return True
        except Exception as e:
            logger.warning(f"Invalid query: {str(e)}")
            return False
    
    def test_connection(self) -> bool:
        """Test database connection with current config"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version();")
                    version = cursor.fetchone()
                    logger.info(f"Connection successful: {version[0][:50]}...")
                    return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific table"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Get column info
                    cursor.execute("""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = %s
                        ORDER BY ordinal_position;
                    """, (table_name,))
                    columns = cursor.fetchall()
                    
                    # Get index info
                    cursor.execute("""
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE schemaname = 'public' AND tablename = %s;
                    """, (table_name,))
                    indexes = cursor.fetchall()
                    
                    # Get row count
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name};")
                    row_count = cursor.fetchone()
                    
                    return {
                        "table_name": table_name,
                        "columns": columns,
                        "indexes": indexes,
                        "row_count": row_count['count'] if row_count else 0
                    }
        except Exception as e:
            logger.error(f"Failed to get table info for {table_name}: {str(e)}")
            raise
    
    def get_query_plan(self, query: str) -> List[Dict]:
        """Get PostgreSQL query execution plan (EXPLAIN format JSON)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    explain_query = f"EXPLAIN (FORMAT JSON) {query}"
                    cursor.execute(explain_query)
                    plan = cursor.fetchone()
                    return plan['QUERY PLAN'] if plan else []
        except Exception as e:
            logger.error(f"Failed to get query plan: {str(e)}")
            raise
    
    def run_explain_analyze(self, query: str) -> List[Dict]:
        """
        Run EXPLAIN ANALYZE on a query to get actual execution statistics.
        
        Args:
            query: The SQL query to analyze
            
        Returns:
            List of dictionaries containing the execution plan with actual timings
            
        Example:
            agent = SQLAgent(db_config)
            plan = agent.run_explain_analyze("SELECT * FROM users WHERE id = 1")
            for step in plan:
                print(step['QUERY PLAN'])
        """
        logger.info(f"Running EXPLAIN ANALYZE on: {query[:100]}...")
        
        # Validate that it's a SELECT query (EXPLAIN ANALYZE should only be used on SELECT)
        upper_query = query.strip().upper()
        if not upper_query.startswith(('SELECT', 'WITH', 'EXPLAIN')):
            logger.warning(f"EXPLAIN ANALYZE on non-SELECT query: {query[:50]}...")
            # Still allow but with warning
        
        # Construct the EXPLAIN ANALYZE query
        explain_query = f"EXPLAIN ANALYZE {query}"
        
        try:
            # Use execute_query which handles connection management
            result = self.execute_query(explain_query)
            logger.info(f"EXPLAIN ANALYZE completed successfully")
            
            # Format the result for better readability
            if result and len(result) > 0:
                # For EXPLAIN ANALYZE, results come as text lines in the first column
                formatted_result = []
                for row in result:
                    # The plan is typically in a column named 'QUERY PLAN' or the first column
                    plan_text = row.get('QUERY PLAN', list(row.values())[0] if row else '')
                    formatted_result.append({'QUERY PLAN': plan_text})
                return formatted_result
            return []
            
        except Exception as e:
            logger.error(f"EXPLAIN ANALYZE failed: {str(e)}")
            raise RuntimeError(f"EXPLAIN ANALYZE error: {str(e)}") from e
    
    def run_explain_analyze_verbose(self, query: str) -> List[Dict]:
        """
        Run EXPLAIN ANALYZE with verbose output for more detailed statistics.
        
        Args:
            query: The SQL query to analyze
            
        Returns:
            List of dictionaries containing detailed execution plan with actual timings
        """
        logger.info(f"Running EXPLAIN ANALYZE VERBOSE on: {query[:100]}...")
        
        explain_query = f"EXPLAIN (ANALYZE, VERBOSE, BUFFERS, FORMAT JSON) {query}"
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(explain_query)
                    result = cursor.fetchone()
                    
                    if result and 'QUERY PLAN' in result:
                        logger.info("EXPLAIN ANALYZE VERBOSE completed successfully")
                        return result['QUERY PLAN']
                    return []
        except Exception as e:
            logger.error(f"EXPLAIN ANALYZE VERBOSE failed: {str(e)}")
            raise
    
    def compare_query_plans(self, original_query: str, optimized_query: str) -> Dict[str, Any]:
        """
        Compare execution plans of original and optimized queries.
        
        Args:
            original_query: The original query to analyze
            optimized_query: The optimized query to compare against
            
        Returns:
            Dictionary with comparison metrics
        """
        logger.info("Comparing query execution plans...")
        
        try:
            # Get plans for both queries
            original_plan = self.run_explain_analyze(original_query)
            optimized_plan = self.run_explain_analyze(optimized_query)
            
            # Extract key metrics from plans (simplified extraction)
            def extract_cost(plan_result):
                if not plan_result or len(plan_result) == 0:
                    return None
                
                plan_text = str(plan_result[0].get('QUERY PLAN', ''))
                # Look for cost patterns like "cost=0.00..123.45"
                cost_match = re.search(r'cost=([\d.]+)\.\.([\d.]+)', plan_text)
                if cost_match:
                    return {
                        'startup_cost': float(cost_match.group(1)),
                        'total_cost': float(cost_match.group(2))
                    }
                return None
            
            original_costs = extract_cost(original_plan)
            optimized_costs = extract_cost(optimized_plan)
            
            comparison = {
                'original_query': original_query[:200],
                'optimized_query': optimized_query[:200],
                'original_plan': original_plan,
                'optimized_plan': optimized_plan,
                'original_costs': original_costs,
                'optimized_costs': optimized_costs,
                'improvement': None
            }
            
            if original_costs and optimized_costs:
                improvement_pct = ((original_costs['total_cost'] - optimized_costs['total_cost']) 
                                   / original_costs['total_cost'] * 100)
                comparison['improvement'] = {
                    'percentage': round(improvement_pct, 2),
                    'original_total': original_costs['total_cost'],
                    'optimized_total': optimized_costs['total_cost']
                }
            
            logger.info(f"Query comparison complete. Improvement: {comparison['improvement']}")
            return comparison
            
        except Exception as e:
            logger.error(f"Query comparison failed: {str(e)}")
            raise

    # STEP 5: Add Index Suggestion Engine
    def suggest_indexes(self, min_seq_scan_threshold: int = 100) -> List[Dict[str, Any]]:
        """
        Analyze database statistics and suggest missing indexes.
        
        This method queries PostgreSQL statistics to find tables that might benefit
        from additional indexes based on sequential scan patterns.
        
        Args:
            min_seq_scan_threshold: Minimum number of sequential scans to consider a table for indexing
            
        Returns:
            List of dictionaries containing index suggestions with table info and recommendations
            
        Example:
            agent = SQLAgent(db_config)
            suggestions = agent.suggest_indexes()
            for suggestion in suggestions:
                print(f"Table: {suggestion['table_name']}")
                print(f"Sequential Scans: {suggestion['seq_scan']}")
                print(f"Index Scans: {suggestion['idx_scan']}")
        """
        logger.info("Analyzing tables for index suggestions...")
        
        try:
            # Query to find tables with high sequential scans but low index usage
            query = """
            SELECT 
                schemaname,
                relname as table_name,
                seq_scan,
                seq_tup_read,
                idx_scan,
                idx_tup_fetch,
                n_tup_ins,
                n_tup_upd,
                n_tup_del,
                n_live_tup,
                n_dead_tup
            FROM pg_stat_user_tables
            WHERE seq_scan > %s
            ORDER BY seq_scan DESC;
            """
            
            result = self.execute_query(query, (min_seq_scan_threshold,))
            
            if not result:
                logger.info("No tables found with significant sequential scans")
                return []
            
            suggestions = []
            for row in result:
                # Calculate index efficiency ratio
                total_scans = row['seq_scan'] + row['idx_scan']
                index_ratio = (row['idx_scan'] / total_scans * 100) if total_scans > 0 else 0
                
                suggestion = {
                    'table_name': row['table_name'],
                    'schema': row['schemaname'],
                    'seq_scan': row['seq_scan'],
                    'idx_scan': row['idx_scan'],
                    'index_ratio': round(index_ratio, 2),
                    'seq_tup_read': row['seq_tup_read'],
                    'n_live_tup': row['n_live_tup'],
                    'n_dead_tup': row['n_dead_tup'],
                    'recommendation': '',
                    'priority': ''
                }
                
                # Generate recommendation based on metrics
                if row['seq_scan'] > 1000 and index_ratio < 20:
                    suggestion['priority'] = 'HIGH'
                    suggestion['recommendation'] = f"Table '{row['table_name']}' has {row['seq_scan']} sequential scans but only {row['idx_scan']} index scans. Consider adding indexes on frequently queried columns."
                elif row['seq_scan'] > 500 and index_ratio < 30:
                    suggestion['priority'] = 'MEDIUM'
                    suggestion['recommendation'] = f"Table '{row['table_name']}' shows moderate sequential scan activity. Review query patterns and consider indexing."
                elif row['seq_scan'] > 100:
                    suggestion['priority'] = 'LOW'
                    suggestion['recommendation'] = f"Table '{row['table_name']}' has {row['seq_scan']} sequential scans. Monitor performance and consider indexing if queries are slow."
                else:
                    suggestion['priority'] = 'INFO'
                    suggestion['recommendation'] = f"Table '{row['table_name']}' has reasonable index usage ({index_ratio}% index scans)."
                
                suggestions.append(suggestion)
            
            logger.info(f"Generated index suggestions for {len(suggestions)} tables")
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to generate index suggestions: {str(e)}")
            raise

    def suggest_indexes_detailed(self, table_name: str = None) -> Dict[str, Any]:
        """
        Provide detailed index suggestions for specific tables or all tables.
        
        Args:
            table_name: Optional specific table name to analyze
            
        Returns:
            Dictionary with detailed index recommendations including column suggestions
        """
        logger.info(f"Generating detailed index suggestions for {table_name or 'all tables'}...")
        
        try:
            # Get base suggestions
            base_suggestions = self.suggest_indexes()
            
            if not base_suggestions:
                return {'suggestions': [], 'summary': 'No index suggestions available'}
            
            detailed_suggestions = []
            
            for suggestion in base_suggestions:
                if table_name and suggestion['table_name'] != table_name:
                    continue
                
                # Get table information for more detailed recommendations
                try:
                    table_info = self.get_table_info(suggestion['table_name'])
                    
                    # Analyze column usage patterns
                    column_suggestions = []
                    
                    # Check for primary key
                    has_primary_key = any('PRIMARY KEY' in str(idx) for idx in table_info.get('indexes', []))
                    
                    # Check for foreign keys (simplified check)
                    foreign_keys = []
                    for col in table_info.get('columns', []):
                        if 'foreign key' in str(col).lower():
                            foreign_keys.append(col)
                    
                    # Generate specific index recommendations
                    if suggestion['priority'] in ['HIGH', 'MEDIUM']:
                        # Suggest composite index for high-activity tables
                        column_suggestions.append({
                            'type': 'composite',
                            'description': 'Consider creating composite indexes on columns used together in WHERE clauses',
                            'example': f"CREATE INDEX CONCURRENTLY idx_{suggestion['table_name']}_composite ON {suggestion['table_name']}(column1, column2);"
                        })
                        
                        # Suggest partial index for conditional queries
                        column_suggestions.append({
                            'type': 'partial',
                            'description': 'Consider partial indexes for frequently filtered conditions',
                            'example': f"CREATE INDEX CONCURRENTLY idx_{suggestion['table_name']}_active ON {suggestion['table_name']}(column) WHERE condition;"
                        })
                    
                    detailed_suggestions.append({
                        'table_name': suggestion['table_name'],
                        'metrics': suggestion,
                        'table_info': {
                            'row_count': table_info.get('row_count', 0),
                            'index_count': len(table_info.get('indexes', [])),
                            'column_count': len(table_info.get('columns', []))
                        },
                        'column_suggestions': column_suggestions,
                        'has_primary_key': has_primary_key,
                        'foreign_keys': foreign_keys
                    })
                    
                except Exception as e:
                    logger.warning(f"Could not get detailed info for {suggestion['table_name']}: {str(e)}")
                    detailed_suggestions.append({
                        'table_name': suggestion['table_name'],
                        'metrics': suggestion,
                        'error': str(e)
                    })
            
            # Generate summary
            summary = {
                'total_tables_analyzed': len(detailed_suggestions),
                'high_priority_count': len([s for s in detailed_suggestions if s['metrics']['priority'] == 'HIGH']),
                'medium_priority_count': len([s for s in detailed_suggestions if s['metrics']['priority'] == 'MEDIUM']),
                'total_sequential_scans': sum(s['metrics']['seq_scan'] for s in detailed_suggestions),
                'total_index_scans': sum(s['metrics']['idx_scan'] for s in detailed_suggestions)
            }
            
            return {
                'suggestions': detailed_suggestions,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Failed to generate detailed index suggestions: {str(e)}")
            raise

    def get_missing_indexes(self) -> List[Dict[str, Any]]:
        """
        Query PostgreSQL for missing indexes using pg_stat_statements.
        
        Returns:
            List of missing index recommendations from PostgreSQL's statistics
        """
        logger.info("Checking for missing indexes in PostgreSQL statistics...")
        
        try:
            # First ensure pg_stat_statements extension is available
            try:
                self.execute_query("CREATE EXTENSION IF NOT EXISTS pg_stat_statements;")
                logger.info("pg_stat_statements extension enabled")
            except Exception as e:
                logger.warning(f"Could not enable pg_stat_statements: {str(e)}")
            
            # Query for missing indexes (requires pg_stat_statements)
            query = """
            SELECT 
                schemaname,
                tablename,
                attname,
                n_distinct,
                correlation,
                most_common_vals,
                most_common_freqs
            FROM pg_stats 
            WHERE schemaname = 'public' 
            AND n_distinct > 0
            AND correlation < 0.9
            ORDER BY n_distinct DESC
            LIMIT 20;
            """
            
            try:
                result = self.execute_query(query)
                if result:
                    logger.info(f"Found {len(result)} potential missing indexes")
                    return result
            except Exception as e:
                logger.warning(f"Could not query missing indexes: {str(e)}")
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get missing indexes: {str(e)}")
            return []

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """
        Execute a SQL query with optional parameters.
        
        Args:
            query: SQL query to execute
            params: Optional parameters for parameterized queries
            
        Returns:
            List of dictionaries containing query results
        """
        logger.info(f"Executing query: {query[:100]}...")
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                # Check if it's a SELECT query
                if query.strip().upper().startswith('SELECT'):
                    result = cursor.fetchall()
                    logger.debug(f"Query returned {len(result)} rows")
                    conn.commit()
                    return result
                else:
                    # For INSERT, UPDATE, DELETE, etc.
                    conn.commit()
                    result = [{"affected_rows": cursor.rowcount, "status": "success"}]
                    logger.debug(f"Query affected {cursor.rowcount} rows")
                    return result
                    
        except psycopg2.Error as e:
            logger.error(f"Query error: {str(e)}")
            if conn:
                conn.rollback()
            raise RuntimeError(f"SQL Error: {str(e)}") from e
        except Exception as e:
            logger.error(f"Execution failed: {str(e)}")
            if conn:
                conn.rollback()
            raise RuntimeError(f"Execution error: {str(e)}") from e
        finally:
            if conn:
                conn.close()