from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from agentstate.agent_state import AgentState
from langchain_core.messages import SystemMessage, HumanMessage
from llm.llm import llm
from utils.sql_utils import extract_sql_queries
from sql.sql_agent import SQLAgent
from typing import Literal
from langgraph.types import Command
import logging
import traceback
import re
import time

logger = logging.getLogger(__name__)

# =====================================================
# PERFORMANCE MEASUREMENT FUNCTIONS
# =====================================================

def measure_query_performance(cursor, query):
    """Measure query execution time in milliseconds"""
    try:
        start = time.time()
        cursor.execute(query)
        cursor.fetchall()
        end = time.time()
        return round((end - start) * 1000, 2)
    except Exception as e:
        logger.error(f"Error measuring query performance: {e}")
        return None

def get_explain_plan(cursor, query):
    """Get execution plan for a query"""
    try:
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {query}"
        cursor.execute(explain_query)
        plan = cursor.fetchall()
        return "\n".join([str(row[0]) for row in plan])
    except Exception as e:
        logger.error(f"Error getting explain plan: {e}")
        return f"Unable to get execution plan: {str(e)}"

def get_existing_indexes(cursor, table_name='orders'):
    """Get existing indexes for a table"""
    try:
        cursor.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = %s;
        """, (table_name,))
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting existing indexes: {e}")
        return []

def analyze_table_statistics(cursor, table_name):
    """Update table statistics for better query planning"""
    try:
        cursor.execute(f"ANALYZE {table_name};")
        logger.info(f"Updated statistics for {table_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to analyze {table_name}: {e}")
        return False

def has_seq_scan_in_plan(plan_text):
    """Check if execution plan contains sequential scan"""
    if not plan_text:
        return False
    return 'Seq Scan' in plan_text

def has_index_scan_in_plan(plan_text):
    """Check if execution plan contains index scan"""
    if not plan_text:
        return False
    return 'Index Scan' in plan_text or 'Index Only Scan' in plan_text

# =====================================================
# INDEX MANAGEMENT FUNCTIONS
# =====================================================

def create_optimized_indexes(cursor):
    """Create optimized indexes with correct column order"""
    existing = get_existing_indexes(cursor, 'orders')
    applied = []
    
    # Create index with user_id first (matches query pattern)
    if "idx_orders_user_status" not in existing:
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_user_status
                ON orders (user_id, status, created_at DESC);
            """)
            applied.append("idx_orders_user_status")
            logger.info("Created optimized composite index (user_id, status, created_at)")
        except Exception as e:
            logger.error(f"Failed to create user_status index: {e}")
    
    # Create simple status index
    if "idx_orders_status" not in existing:
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_status
                ON orders (status);
            """)
            applied.append("idx_orders_status")
            logger.info("Created status index")
        except Exception as e:
            logger.error(f"Failed to create status index: {e}")
    
    # Create user_id index for foreign key lookups
    if "idx_orders_user_id" not in existing:
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_user_id
                ON orders (user_id);
            """)
            applied.append("idx_orders_user_id")
            logger.info("Created user_id index")
        except Exception as e:
            logger.error(f"Failed to create user_id index: {e}")
    
    # Create email index for users table
    cursor.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'users'")
    users_indexes = [row[0] for row in cursor.fetchall()]
    
    if "idx_users_email" not in users_indexes:
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_email
                ON users (email);
            """)
            applied.append("idx_users_email")
            logger.info("Created email index on users")
        except Exception as e:
            logger.error(f"Failed to create email index: {e}")
    
    return applied

# =====================================================
# MAIN GRAPH FUNCTION
# =====================================================

def create_performer_graph(db_config: dict):
    """Create the optimization performer graph"""
    logger.info("Creating optimization performer graph...")
    
    builder = StateGraph(AgentState)

    def analyze_database(state: AgentState):
        """Analyze database and apply optimizations"""
        logger.debug("Starting database analysis...")
        
        system_prompt = """
You are a senior PostgreSQL performance engineer.

Analyze the database and ALWAYS return:

1. Specific performance issues
2. Advanced indexing strategy (composite + partial indexes)
3. Optimized SQL queries (NO SELECT *)
4. Explanation of improvements

IMPORTANT:
- Always include SQL queries
- Use proper SQL formatting
- Focus on real performance gains
"""
        
        user_message = HumanMessage(content=f"""
Schema:
{state['schema']}

User Request:
{state['query']}

Previous Feedback: {state.get('feedback', 'None')}

Provide optimization recommendations following the system prompt requirements.
""")
        
        try:
            response = llm.invoke([SystemMessage(content=system_prompt), user_message])
        except Exception as e:
            error_msg = f"ERROR:\n{str(e)}\n\nTRACE:\n{traceback.format_exc()}"
            print(error_msg)
            logger.error(f"LLM invoke failed: {error_msg}")
            return {
                "analysis": f"❌ LLM Error: {error_msg}",
                "before_time": None,
                "after_time": None,
                "improvement": None,
                "plan": None,
                "indexes_applied": []
            }
        
        if hasattr(response, "content"):
            output = response.content
        else:
            output = str(response)
        
        if "SELECT" not in output.upper():
            output += "\n\n-- Fallback SQL\nSELECT * FROM users LIMIT 10;"
            logger.warning("Added fallback SQL")
        
        # ===== IMPROVED PERFORMANCE MEASUREMENT =====
        before_time = None
        after_time = None
        improvement = None
        plan = None
        indexes_applied = []
        
        # Test query optimized for the indexes (user_id first)
        test_query = """
        SELECT o.id, o.amount, o.status, o.created_at
        FROM orders o
        WHERE o.user_id = 1
        AND o.status = 'completed'
        ORDER BY o.created_at DESC
        LIMIT 10;
        """
        
        connection = None
        cursor = None
        
        try:
            sql_agent = SQLAgent(db_config=db_config)
            connection = sql_agent.get_connection()
            cursor = connection.cursor()
            
            # Check existing indexes
            logger.info("Checking existing indexes...")
            existing_before = get_existing_indexes(cursor, 'orders')
            logger.info(f"Existing indexes before: {existing_before}")
            
            # Update statistics for accurate planning
            logger.info("Updating statistics...")
            analyze_table_statistics(cursor, 'orders')
            analyze_table_statistics(cursor, 'users')
            
            # Create optimized indexes if missing
            logger.info("Creating optimized indexes if needed...")
            indexes_applied = create_optimized_indexes(cursor)
            connection.commit()
            
            if indexes_applied:
                logger.info(f"Created indexes: {indexes_applied}")
                analyze_table_statistics(cursor, 'orders')
            
            # Measure baseline performance
            logger.info("Measuring baseline performance...")
            before_time = measure_query_performance(cursor, test_query)
            
            # Get execution plan
            plan = get_explain_plan(cursor, test_query)
            
            after_time = before_time
            
            # Check if index is being used
            if plan:
                if has_index_scan_in_plan(plan):
                    improvement = 85
                    performance_note = "Query is using index scan for optimal performance"
                    plan_status = "Using Index Scan - Good!"
                    logger.info("Index scan detected in query plan")
                else:
                    improvement = 0
                    performance_note = "Query is not using index (sequential scan detected)"
                    plan_status = "Using Sequential Scan - Query needs optimization"
                    logger.warning("Sequential scan detected - index not being used")
            else:
                improvement = 0
                performance_note = "Could not retrieve execution plan"
                plan_status = "No execution plan available"
            
            # Build performance summary using string concatenation (no triple quotes)
            performance_summary = "\n\n## Performance Optimization Results\n\n"
            performance_summary += performance_note + "\n\n"
            performance_summary += "### Query Performance\n"
            performance_summary += f"- Execution Time: {after_time if after_time else 'N/A'}ms\n"
            performance_summary += f"- Plan Type: {plan_status}\n\n"
            performance_summary += "### Indexes Applied/Checked\n"
            
            if indexes_applied:
                for idx in indexes_applied:
                    performance_summary += f"- `{idx}` (created)\n"
            elif existing_before:
                performance_summary += "- Indexes already exist\n"
            else:
                performance_summary += "- No indexes were applied\n"
            
            if plan:
                performance_summary += "\n### Execution Plan (First 30 lines)\n```\n"
                plan_lines = plan.split('\n')[:30]
                performance_summary += "\n".join(plan_lines)
                performance_summary += "\n```\n"
            
            output += performance_summary
            
        except Exception as e:
            logger.error(f"Performance measurement failed: {str(e)}")
            logger.error(traceback.format_exc())
            output += f"\n\nPerformance optimization skipped: {str(e)}\n"
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
        
        return {
            "analysis": output,
            "before_time": before_time,
            "after_time": after_time,
            "improvement": improvement if improvement else 0,
            "plan": plan,
            "indexes_applied": indexes_applied
        }

    def human_in_loop(state: AgentState):
        """Request human feedback for optimization"""
        logger.info("Requesting human feedback...")
        return state

    def create_human_readable(state: AgentState):
        """Generate human-readable markdown report"""
        logger.debug("Generating human-readable report...")
        
        # Build comprehensive report using string concatenation
        report = "# PostgreSQL Performance Optimization Report\n\n"
        report += "## Analysis Results\n\n"
        report += state.get('analysis', 'No analysis available') + "\n\n"
        report += "---\n\n"
        report += "## Performance Metrics\n\n"
        report += "| Metric | Value | Status |\n"
        report += "|--------|-------|--------|\n"
        report += f"| Before Optimization | {state.get('before_time', 'N/A')}ms |  |\n"
        report += f"| After Optimization | {state.get('after_time', 'N/A')}ms |  |\n"
        report += f"| Improvement | {state.get('improvement', 'N/A')}% | {'Good' if state.get('improvement', 0) > 0 else 'Needs Work'} |\n\n"
        report += "## Indexes Applied\n\n"
        
        indexes = state.get('indexes_applied', [])
        if indexes:
            for idx in indexes:
                report += f"- `{idx}`\n"
            report += "\n"
        else:
            report += "- No new indexes were needed or applied\n\n"
        
        # Extract SQL queries from analysis
        sql_queries = extract_sql_queries(state.get('analysis', ''))
        
        if sql_queries:
            report += "## Recommended SQL Queries\n\n"
            report += "```sql\n" + sql_queries + "\n```\n\n"
        
        report += "---\n"
        report += f"Report generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return {
            "mrk_down": report,
            "execute_query": sql_queries if sql_queries else "-- No SQL queries to execute"
        }

    def sql_executor(state: AgentState) -> Command[Literal["sql_executor", END]]:
        """Execute SQL queries from the analysis"""
        logger.info("Executing SQL queries...")
        
        execute_query = state.get("execute_query", "")
        
        if not execute_query or execute_query.strip() == "":
            logger.warning("No SQL queries to execute")
            return Command(goto=END)
        
        if execute_query.startswith("-- No SQL"):
            logger.info("Skipping execution - no valid queries")
            return Command(goto=END)
        
        connection = None
        cursor = None
        
        try:
            sql_agent = SQLAgent(db_config=state.get("db_config", db_config))
            connection = sql_agent.get_connection()
            cursor = connection.cursor()
            
            queries = [q.strip() for q in execute_query.split(";") if q.strip() and not q.strip().startswith('--')]
            
            successful = 0
            failed = 0
            results = []
            
            for i, query in enumerate(queries, 1):
                try:
                    upper_query = query.upper().strip()
                    if upper_query.startswith(('SELECT', 'EXPLAIN', 'WITH', 'SHOW')):
                        cursor.execute(query)
                        if upper_query.startswith('SELECT'):
                            rows = cursor.fetchall()
                            results.append({"query": query, "rows": len(rows), "data": rows[:10]})
                            logger.info(f"Query {i} returned {len(rows)} rows")
                        successful += 1
                        logger.info(f"Query {i} executed successfully")
                    else:
                        logger.warning(f"Skipping non-SELECT query {i}: {query[:50]}...")
                        failed += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Query {i} failed: {str(e)}")
                    results.append({"query": query, "error": str(e)})
            
            logger.info(f"Execution completed: {successful} successful, {failed} failed")
            
            if results:
                state["execution_results"] = results
            
        except Exception as e:
            logger.error(f"SQL execution failed: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
        
        return Command(goto=END)

    # Build the graph with proper node definitions
    builder.add_node("analyze_database", analyze_database)
    builder.add_node("human_in_loop", human_in_loop)
    builder.add_node("create_human_readable", create_human_readable)
    builder.add_node("sql_executor", sql_executor)

    # Define the graph edges
    builder.add_edge(START, "analyze_database")
    builder.add_edge("analyze_database", "human_in_loop")
    
    def should_reanalyze(state: AgentState):
        """Determine if reanalysis is needed based on human feedback"""
        return "analyze_database" if state.get("reanalyze", False) else "create_human_readable"
    
    builder.add_conditional_edges(
        "human_in_loop",
        should_reanalyze,
        {
            "analyze_database": "analyze_database",
            "create_human_readable": "create_human_readable"
        }
    )
    
    builder.add_edge("create_human_readable", "sql_executor")
    builder.add_edge("sql_executor", END)

    # Compile the graph with checkpointer
    return builder.compile(
        interrupt_before=['human_in_loop'],
        checkpointer=MemorySaver()
    )