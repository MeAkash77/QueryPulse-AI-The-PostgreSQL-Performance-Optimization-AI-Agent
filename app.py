import streamlit as st
import logging
from typing import Dict, Any
from performer.performer import create_performer_graph
from agentstate.agent_state import AgentState
from utils.sql_utils import extract_sql_queries
from sql.sql_agent import SQLAgent
from tester.tester import create_tester_graph
from agentstate.agent_state import TestingState
import psycopg2
import ssl
import traceback  # ADDED for better error tracking
import re  # ADDED for parsing EXPLAIN results
import matplotlib.pyplot as plt  # ADDED for performance graphs

# FIX: Added encoding="utf-8" to prevent Unicode errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),  # ← FIXED: added encoding
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="DB Optimizer", layout="wide")
st.title("PostgreSQL Database Optimization Assistant")

with st.sidebar:
    st.header("Database Configuration")
    db_host = st.text_input("Host", value="ep-divine-scene-anp4baya-pooler.c-6.us-east-1.aws.neon.tech")
    db_port = st.number_input("Port", value=5432, min_value=1, max_value=65535)
    db_user = st.text_input("Username", value="neondb_owner")
    db_password = st.text_input("Password", type="password", value="npg_vxGP8FcUI7gH")
    db_name = st.text_input("Database Name", value="neondb")
    
    # Add SSL toggle for Neon
    use_ssl = st.checkbox("Enable SSL (required for Neon)", value=True)
    
    test_connection = st.button("Test Connection", use_container_width=True)

db_config = {
    "host": db_host,
    "port": db_port,
    "user": db_user,
    "password": db_password,
    "database": db_name,
    "ssl": use_ssl  # Add SSL flag
}

def test_db_connection(config):
    """Test database connection with SSL support"""
    try:
        # Build connection parameters
        conn_params = {
            "host": config["host"],
            "port": config["port"],
            "user": config["user"],
            "password": config["password"],
            "database": config["database"]
        }
        
        # Add SSL if required
        if config.get("ssl", False):
            conn_params["sslmode"] = "require"
        
        # Test connection
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return True, f"Connected successfully! PostgreSQL version: {version[0][:50]}..."
    except Exception as e:
        return False, str(e)

if test_connection:
    with st.spinner("Testing connection..."):
        success, message = test_db_connection(db_config)
        if success:
            st.success(f"✅ {message}")
            logger.info(f"Successful connection to {db_config['database']} on {db_config['host']}")
        else:
            st.error(f"❌ Connection failed: {message}")
            logger.error(f"Connection error: {message}")

query = st.text_area(
    "Optimization Request",
    placeholder="E.g.: 'Analyze query performance for slow orders report'",
    height=100
)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"thread_{hash(frozenset(db_config.items()))}"
if "analysis_history" not in st.session_state:
    st.session_state.analysis_history = []
if "test_results" not in st.session_state:
    st.session_state.test_results = None
if "explain_results" not in st.session_state:
    st.session_state.explain_results = None  # ADDED for storing EXPLAIN results
if "index_suggestions" not in st.session_state:
    st.session_state.index_suggestions = None  # ADDED for storing index suggestions
if "performance_metrics" not in st.session_state:
    st.session_state.performance_metrics = None  # ADDED for storing performance metrics

def initialize_agent():
    try:
        logger.info("Initializing SQL agent...")
        # Pass the SSL config to SQLAgent
        agent = SQLAgent(db_config)
        return agent
    except Exception as e:
        st.error(f"❌ Agent initialization failed: {str(e)}")
        logger.critical(f"Agent init failure: {str(e)}")
        st.stop()

def suggest_indexes_from_analysis(explain_result: str, schema: Dict) -> list:
    """Generate index suggestions based on EXPLAIN ANALYZE output and schema"""
    suggestions = []
    
    if not explain_result:
        return suggestions
    
    # Check for sequential scans
    if 'Seq Scan' in explain_result:
        # Try to extract table name from Seq Scan line
        table_match = re.search(r'Seq Scan on (\w+)', explain_result)
        if table_match:
            table_name = table_match.group(1)
            suggestions.append({
                'table': table_name,
                'type': 'Sequential Scan Detected',
                'suggestion': f'Create index on frequently queried columns in {table_name}',
                'priority': 'HIGH',
                'example': f'CREATE INDEX idx_{table_name}_columns ON {table_name}(column_name);'
            })
    
    # Check for filter conditions
    filter_matches = re.finditer(r'Filter:\s*\(?(\w+)\s*(?:=|LIKE|>|<|>=|<=)\s*(?:\'[^\']*\'|\w+)', explain_result)
    filtered_columns = set()
    for match in filter_matches:
        filtered_columns.add(match.group(1))
    
    if filtered_columns:
        table_match = re.search(r'Seq Scan on (\w+)', explain_result) or re.search(r'Index Scan on (\w+)', explain_result)
        if table_match:
            table_name = table_match.group(1)
            for col in filtered_columns:
                suggestions.append({
                    'table': table_name,
                    'type': 'Filter Condition',
                    'suggestion': f'Column "{col}" is used in WHERE clause filter',
                    'priority': 'MEDIUM',
                    'example': f'CREATE INDEX idx_{table_name}_{col} ON {table_name}({col});'
                })
    
    # Check for sort operations without index
    if 'Sort' in explain_result and 'Index' not in explain_result:
        sort_match = re.search(r'Sort Key:\s*(\w+)', explain_result)
        if sort_match:
            sort_col = sort_match.group(1)
            table_match = re.search(r' on (\w+)', explain_result)
            if table_match:
                table_name = table_match.group(1)
                suggestions.append({
                    'table': table_name,
                    'type': 'Sort Without Index',
                    'suggestion': f'ORDER BY on "{sort_col}" without index causes explicit sort',
                    'priority': 'MEDIUM',
                    'example': f'CREATE INDEX idx_{table_name}_{sort_col} ON {table_name}({sort_col});'
                })
    
    # Check for join conditions
    if 'Hash Join' in explain_result or 'Merge Join' in explain_result:
        join_conditions = re.finditer(r'Join Filter:\s*\(?(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)', explain_result)
        for match in join_conditions:
            table1, col1, table2, col2 = match.group(1), match.group(2), match.group(3), match.group(4)
            suggestions.append({
                'table': table1,
                'type': 'Join Condition',
                'suggestion': f'Join on {table1}.{col1} = {table2}.{col2}',
                'priority': 'HIGH',
                'example': f'CREATE INDEX idx_{table1}_{col1} ON {table1}({col1});\nCREATE INDEX idx_{table2}_{col2} ON {table2}({col2});'
            })
    
    # Remove duplicates based on table and suggestion
    unique_suggestions = []
    seen = set()
    for s in suggestions:
        key = f"{s['table']}-{s['suggestion']}"
        if key not in seen:
            seen.add(key)
            unique_suggestions.append(s)
    
    return unique_suggestions

def run_analysis():
    agent = initialize_agent()
    schema = agent.get_schema()
    
    st.session_state.graph = create_performer_graph(db_config)
    
    initial_state = AgentState(
        query=query,
        schema=str(schema),
        db_config=db_config,
        analysis="",
        feedback="",
        execute=False,
        reanalyze=False,
        execute_query="",
        mrk_down=""
    )
    
    with st.status("Running optimization analysis...", expanded=True) as status:
        try:
            for event in st.session_state.graph.stream(
                initial_state,
                {"configurable": {"thread_id": st.session_state.thread_id}},
                stream_mode="values"
            ):
                if "analysis" in event:
                    # FIX #2: DEBUG LLM OUTPUT - Show raw AI response
                    st.write("**🔍 RAW LLM OUTPUT:**")
                    st.code(event["analysis"], language="markdown")
                    st.divider()
                    
                    # Store performance metrics if available
                    if "before_time" in event and event["before_time"] is not None:
                        st.session_state.performance_metrics = {
                            "before_time": event["before_time"],
                            "after_time": event["after_time"],
                            "improvement": event["improvement"],
                            "plan": event.get("plan"),
                            "indexes_applied": event.get("indexes_applied", [])
                        }
                        logger.info(f"Performance metrics captured: {event['improvement']}% improvement")
                    
                    st.session_state.analysis_history.append(event["analysis"])
                    status.write(f"Analysis iteration {len(st.session_state.analysis_history)} completed")
                    logger.info(f"New analysis generated: {event['analysis'][:50]}...")
                
                # STEP 4: Extract and store EXPLAIN ANALYZE results if present
                if "mrk_down" in event:
                    # Look for EXPLAIN ANALYZE section in the markdown
                    explain_section_match = re.search(
                        r'## 📊 Query Execution Plan \(EXPLAIN ANALYZE\)\n+```\n(.*?)\n```',
                        event["mrk_down"],
                        re.DOTALL | re.IGNORECASE
                    )
                    
                    if explain_section_match:
                        explain_result = explain_section_match.group(1)
                        st.session_state.explain_results = explain_result
                        logger.info("EXPLAIN ANALYZE results extracted from report")
                        
                        # Generate index suggestions from the EXPLAIN results
                        st.session_state.index_suggestions = suggest_indexes_from_analysis(
                            explain_result, 
                            schema
                        )
                        logger.info(f"Generated {len(st.session_state.index_suggestions)} index suggestions")
            
            status.update(label="Analysis complete!", state="complete", expanded=False)
            st.success("✅ Optimization analysis completed successfully!")
            
        except Exception as e:
            # FIX #1: ERROR VISIBILITY - Show full traceback
            st.error(f"❌ Analysis pipeline failed: {str(e)}")
            st.error("**Full error traceback:**")
            st.code(traceback.format_exc(), language="python")
            logger.error(f"Graph stream error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            st.stop()

def display_analysis():
    if not st.session_state.analysis_history:
        return

    latest = st.session_state.analysis_history[-1]
    
    # STEP 4 & 5: Display Performance Analysis Section with Graphs
    st.subheader("⚡ Performance Analysis")
    
    # Display performance metrics with graphs if available
    if st.session_state.performance_metrics:
        metrics = st.session_state.performance_metrics
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Before (ms)", f"{metrics['before_time']:.2f}" if metrics['before_time'] else "N/A")
        with col2:
            st.metric("After (ms)", f"{metrics['after_time']:.2f}" if metrics['after_time'] else "N/A")
        with col3:
            improvement_color = "normal" if metrics['improvement'] >= 0 else "inverse"
            st.metric("Improvement (%)", f"{metrics['improvement']:.1f}%" if metrics['improvement'] else "N/A", 
                     delta=f"{metrics['improvement']:.1f}%" if metrics['improvement'] else None,
                     delta_color=improvement_color)
        
        # STEP 5: Add Performance Graph
        if metrics['before_time'] and metrics['after_time']:
            st.markdown("### 📊 Performance Comparison Chart")
            
            fig, ax = plt.subplots(figsize=(10, 6))
            bars = ax.bar(["Before Optimization", "After Optimization"], 
                         [metrics['before_time'], metrics['after_time']],
                         color=['#ff6b6b', '#51cf66'],
                         edgecolor='black',
                         linewidth=1.5)
            
            # Add value labels on top of bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 5,
                       f'{height:.2f}ms',
                       ha='center', va='bottom', fontweight='bold')
            
            ax.set_ylabel("Execution Time (ms)", fontsize=12, fontweight='bold')
            ax.set_title("Query Performance Comparison", fontsize=14, fontweight='bold', pad=20)
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            
            # Add improvement annotation
            if metrics['improvement'] > 0:
                ax.text(0.5, 0.95, f"🚀 {metrics['improvement']:.1f}% Improvement!", 
                       transform=ax.transAxes, ha='center', fontsize=12,
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7))
            elif metrics['improvement'] < 0:
                ax.text(0.5, 0.95, f"⚠️ Performance degraded by {abs(metrics['improvement']):.1f}%", 
                       transform=ax.transAxes, ha='center', fontsize=12,
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="red", alpha=0.7))
            
            st.pyplot(fig)
            plt.close(fig)  # Close figure to free memory
            
            # Display applied indexes
            if metrics.get('indexes_applied') and len(metrics['indexes_applied']) > 0:
                st.markdown("### 🗂️ Indexes Applied")
                for idx in metrics['indexes_applied']:
                    st.success(f"✅ Created index on `{idx}`")
            
            # Add performance insight
            st.markdown("### 💡 Performance Insight")
            if metrics['improvement'] > 30:
                st.success(f"🎉 Excellent improvement! Query is now {metrics['improvement']:.1f}% faster.")
            elif metrics['improvement'] > 10:
                st.info(f"📈 Good improvement. Query is now {metrics['improvement']:.1f}% faster.")
            elif metrics['improvement'] > 0:
                st.info(f"✅ Slight improvement of {metrics['improvement']:.1f}% achieved.")
            elif metrics['improvement'] == 0:
                st.warning("ℹ️ No performance change detected. Consider alternative optimization strategies.")
            else:
                st.error(f"⚠️ Performance degraded by {abs(metrics['improvement']):.1f}%. Review the applied changes.")
    
    # Display EXPLAIN ANALYZE results if available
    if st.session_state.explain_results:
        st.markdown("### 📊 Execution Plan Analysis")
        
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Execution Plan", "🔍 Performance Insights", "📌 Index Suggestions", "💡 Recommendations"])
        
        with tab1:
            st.text("Execution Plan:")
            st.code(st.session_state.explain_results, language="sql")
        
        with tab2:
            # Parse and display performance metrics
            st.markdown("#### Key Performance Metrics")
            
            # Extract metrics using regex
            metrics = {}
            
            # Extract execution time
            exec_time_match = re.search(r'Execution Time:\s*([\d.]+)\s*ms', st.session_state.explain_results, re.IGNORECASE)
            if exec_time_match:
                exec_time = float(exec_time_match.group(1))
                metrics['Execution Time'] = f"{exec_time} ms"
                if exec_time > 100:
                    st.warning(f"⚠️ **High execution time**: {exec_time} ms - Query may need optimization")
                elif exec_time > 10:
                    st.info(f"📊 **Execution time**: {exec_time} ms - Acceptable but could be improved")
                else:
                    st.success(f"✅ **Execution time**: {exec_time} ms - Good performance")
            
            # Extract planning time
            plan_time_match = re.search(r'Planning Time:\s*([\d.]+)\s*ms', st.session_state.explain_results, re.IGNORECASE)
            if plan_time_match:
                plan_time = float(plan_time_match.group(1))
                metrics['Planning Time'] = f"{plan_time} ms"
                st.metric("Planning Time", f"{plan_time} ms")
            
            # Detect sequential scans
            if re.search(r'Seq Scan', st.session_state.explain_results, re.IGNORECASE):
                metrics['Scan Type'] = "Sequential Scan"
                st.warning("⚠️ **Sequential Scan detected** - Consider adding an index")
            
            # Detect index scans
            index_scan_match = re.search(r'Index Scan using (\w+)', st.session_state.explain_results, re.IGNORECASE)
            if index_scan_match:
                metrics['Scan Type'] = f"Index Scan ({index_scan_match.group(1)})"
                st.success(f"✅ **Using index**: {index_scan_match.group(1)}")
            
            # Extract cost
            cost_match = re.search(r'cost=([\d.]+)\.\.([\d.]+)', st.session_state.explain_results)
            if cost_match:
                startup_cost = float(cost_match.group(1))
                total_cost = float(cost_match.group(2))
                metrics['Startup Cost'] = startup_cost
                metrics['Total Cost'] = total_cost
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Startup Cost", f"{startup_cost:.2f}")
                with col2:
                    st.metric("Total Cost", f"{total_cost:.2f}")
            
            # Extract rows
            rows_match = re.search(r'rows=(\d+)', st.session_state.explain_results)
            if rows_match:
                rows = int(rows_match.group(1))
                metrics['Estimated Rows'] = rows
                st.metric("Estimated Rows", f"{rows:,}")
            
            # Display all metrics in a nice format
            if metrics:
                st.markdown("#### Summary Metrics")
                for key, value in metrics.items():
                    if key not in ['Startup Cost', 'Total Cost', 'Estimated Rows']:
                        st.write(f"- **{key}**: {value}")
        
        with tab3:
            st.markdown("#### 🗂️ Index Suggestions Based on Query Analysis")
            
            if st.session_state.index_suggestions and len(st.session_state.index_suggestions) > 0:
                st.success(f"Found {len(st.session_state.index_suggestions)} index optimization opportunity(s)")
                
                # Group suggestions by priority
                high_priority = [s for s in st.session_state.index_suggestions if s.get('priority') == 'HIGH']
                medium_priority = [s for s in st.session_state.index_suggestions if s.get('priority') == 'MEDIUM']
                
                if high_priority:
                    st.markdown("##### 🔴 High Priority (Strongly Recommended)")
                    for suggestion in high_priority:
                        with st.container():
                            st.markdown(f"**Table:** `{suggestion['table']}`")
                            st.markdown(f"**Issue:** {suggestion['type']}")
                            st.markdown(f"**Suggestion:** {suggestion['suggestion']}")
                            st.code(suggestion['example'], language="sql")
                            st.divider()
                
                if medium_priority:
                    st.markdown("##### 🟡 Medium Priority (Consider if performance is critical)")
                    for suggestion in medium_priority:
                        with st.container():
                            st.markdown(f"**Table:** `{suggestion['table']}`")
                            st.markdown(f"**Issue:** {suggestion['type']}")
                            st.markdown(f"**Suggestion:** {suggestion['suggestion']}")
                            st.code(suggestion['example'], language="sql")
                            st.divider()
                
                # Add option to generate CREATE INDEX statements
                st.markdown("---")
                st.markdown("#### 📝 Generate CREATE INDEX Statements")
                
                all_indexes = "\n\n".join([s['example'] for s in st.session_state.index_suggestions])
                st.code(all_indexes, language="sql")
                
                if st.button("📋 Copy All CREATE INDEX Statements", key="copy_indexes"):
                    st.toast("Index statements copied to clipboard!", icon="✅")
                    st.write("You can now paste these statements in your database client")
            else:
                st.info("✅ No specific index suggestions found. Your query may already be optimized!")
                st.markdown("""
                ### General Index Guidelines:
                - Index columns used in WHERE clauses
                - Index columns used in JOIN conditions
                - Index columns used in ORDER BY
                - Consider composite indexes for multiple filters
                - Use partial indexes for conditional queries
                """)
        
        with tab4:
            st.markdown("#### Optimization Recommendations")
            
            recommendations = []
            
            # Generate recommendations based on EXPLAIN output
            if 'Seq Scan' in st.session_state.explain_results:
                recommendations.append("🔹 **Create indexes** on columns used in WHERE, JOIN, and ORDER BY clauses")
                recommendations.append("🔹 **Consider composite indexes** for multiple filtering conditions")
            
            if 'Execution Time' in st.session_state.explain_results:
                exec_time_match = re.search(r'Execution Time:\s*([\d.]+)', st.session_state.explain_results)
                if exec_time_match and float(exec_time_match.group(1)) > 100:
                    recommendations.append("🔹 **Query optimization needed** - Consider rewriting query or adding indexes")
                    recommendations.append("🔹 **Review join conditions** - Ensure joins use indexed columns")
            
            if 'Sort' in st.session_state.explain_results and 'Index' not in st.session_state.explain_results:
                recommendations.append("🔹 **Add index on ORDER BY columns** to eliminate sorting")
            
            if 'Hash Join' in st.session_state.explain_results:
                recommendations.append("🔹 **Consider increasing work_mem** for better hash join performance")
            
            if st.session_state.index_suggestions and len(st.session_state.index_suggestions) > 0:
                recommendations.append("🔹 **Implement suggested indexes** to improve query performance")
            
            if not recommendations:
                recommendations.append("✅ **Query performance looks good!** No major issues detected.")
                recommendations.append("💡 **Consider monitoring** query performance over time as data grows")
            
            for rec in recommendations:
                st.write(rec)
    
    else:
        st.info("No execution plan available. Run analysis to see performance metrics.")
    
    st.divider()
    
    # Display the full analysis report
    with st.expander("📊 Latest Optimization Report", expanded=True):
        st.markdown(latest)
    
    if len(st.session_state.analysis_history) > 1:
        st.subheader("📜 Analysis History")
        for i, analysis in enumerate(st.session_state.analysis_history[:-1], 1):
            with st.expander(f"Iteration {i}", expanded=False):
                st.markdown(analysis)

def run_performance_test(queries: str):
    """Run performance tests on the queries before execution"""
    try:
        agent = SQLAgent(db_config)
        schema = agent.get_schema()
        
        test_graph = create_tester_graph()
        
        initial_test_state = TestingState(
            schema=str(schema),
            execute_query=queries,
            before_exec="",
            after_exec="",
            results="",
            wind_up=""
        )
        
        test_id = f"{schema}-{queries}"
        test_thread_id = f"test_{hash(test_id)}"
        
        with st.status("Running performance tests...", expanded=True) as status:
            current_state = initial_test_state
            
            for event in test_graph.stream(
                current_state,
                {"configurable": {
                    "thread_id": test_thread_id,
                    "checkpoint_ns": "test_performance",
                    "checkpoint_id": f"query_{hash(queries)}"
                }},
                stream_mode="values"
            ):
                if "before_exec" in event:
                    status.write("✅ Initial performance baseline established")
                    current_state.update(event)
                if "after_exec" in event:
                    status.write("✅ Optimization impact measured")
                    current_state.update(event)
                if "results" in event:
                    status.write("✅ Analysis complete")
                    st.markdown("### Performance Analysis")
                    st.markdown(event["results"])   
                    current_state.update(event)
            
            return current_state.get("results")
            
    except Exception as e:
        st.error(f"❌ Testing failed: {str(e)}")
        logger.error(f"Testing error: {str(e)}")
        return None

def execute_queries():
    if not st.session_state.analysis_history:
        st.info("No analysis history yet. Run an analysis first.")
        return
    
    current_analysis = st.session_state.analysis_history[-1]
    sql_queries = extract_sql_queries(current_analysis)
    
    # FIX #3: NO SQL QUERIES FOUND - Fallback to raw output
    if not sql_queries:
        st.warning("⚠️ No SQL queries found in the analysis — using raw output as fallback")
        sql_queries = current_analysis
        st.info("💡 Tip: Make sure your analysis includes SQL queries with proper formatting (e.g., SELECT, INSERT, UPDATE statements)")
    
    with st.form("query_execution"):
        edited_queries = st.text_area(
            "📝 SQL Queries to Execute",
            value=sql_queries,
            height=300,
            help="Edit the SQL queries before execution if needed"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            test_button = st.form_submit_button("🧪 Test Queries", use_container_width=True)
        with col2:
            execute_button = st.form_submit_button("🚀 Execute Queries", use_container_width=True)
            
        if test_button:
            with st.spinner("Running performance tests..."):
                test_results = run_performance_test(edited_queries)
                if test_results:
                    st.session_state.test_results = test_results
                    st.success("✅ Performance tests completed!")
                
        if execute_button:
            if not st.session_state.test_results:
                st.warning("⚠️ Please run performance tests before executing queries")
                return
                
            try:
                agent = SQLAgent(db_config)
                # Split queries by semicolon and filter empty ones
                queries = [q.strip() for q in edited_queries.split(";") if q.strip()]
                
                if not queries:
                    st.error("No valid SQL queries found to execute")
                    return
                
                with st.status("📊 Executing SQL queries...", expanded=True) as status:
                    successful = 0
                    failed = 0
                    
                    for i, query in enumerate(queries, 1):
                        try:
                            status.write(f"**Executing Query {i}:**")
                            st.code(query, language="sql")
                            
                            result = agent.execute_query(query)
                            
                            # Display results based on type
                            if isinstance(result, list):
                                if result:
                                    st.success(f"✅ Query {i} executed successfully - {len(result)} rows returned")
                                    with st.expander(f"View Query {i} Results"):
                                        st.json(result[:10])  # Show first 10 rows
                                        if len(result) > 10:
                                            st.info(f"Showing first 10 of {len(result)} rows")
                                else:
                                    st.success(f"✅ Query {i} executed successfully - No rows returned")
                            else:
                                st.success(f"✅ Query {i} executed successfully")
                                st.json(result)
                            
                            successful += 1
                            logger.info(f"Executed query {i}: {query[:50]}...")
                            
                        except Exception as e:
                            st.error(f"❌ Query {i} execution failed: {str(e)}")
                            logger.error(f"Query {i} error: {str(e)}")
                            failed += 1
                            # Ask if user wants to continue
                            if not st.checkbox(f"Continue with next query?", key=f"continue_{i}"):
                                break
                    
                    status.update(label=f"Execution complete! ({successful} successful, {failed} failed)", state="complete")
                    
                    if successful > 0:
                        st.success(f"✅ Successfully executed {successful} queries")
                    if failed > 0:
                        st.warning(f"⚠️ {failed} queries failed")
                    
            except Exception as e:
                st.error(f"❌ Execution setup failed: {str(e)}")
                logger.error(f"Execution setup error: {str(e)}")

# Main UI buttons
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    if st.button("🚀 Start Analysis", use_container_width=True, type="primary"):
        if not all([db_config['host'], db_config['user'], db_config['password'], db_config['database']]):
            st.error("❌ Please fill all database credentials")
        elif not query:
            st.error("❌ Please enter an optimization request")
        else:
            # Test connection before starting analysis
            with st.spinner("Testing database connection..."):
                success, message = test_db_connection(db_config)
                if success:
                    st.success("✅ Database connection verified!")
                    run_analysis()
                else:
                    st.error(f"❌ Cannot start analysis: {message}")

with col2:
    if st.button("🔄 Clear History", use_container_width=True):
        st.session_state.analysis_history = []
        st.session_state.test_results = None
        st.session_state.explain_results = None  # Clear EXPLAIN results too
        st.session_state.index_suggestions = None  # Clear index suggestions
        st.session_state.performance_metrics = None  # Clear performance metrics
        st.success("Analysis history cleared!")
        st.rerun()

with col3:
    if st.button("📥 Download Logs", use_container_width=True):
        try:
            with open("app.log", "r", encoding="utf-8") as f:
                log_content = f.read()
            st.download_button(
                label="📥 Click to Download",
                data=log_content,
                file_name="app.log",
                mime="text/plain"
            )
        except Exception as e:
            st.error(f"Could not read log file: {e}")

# Display results
if st.session_state.analysis_history:
    st.divider()
    display_analysis()
    st.divider()
    execute_queries()
else:
    st.info("👈 Enter an optimization request and click 'Start Analysis' to begin")

# Footer
st.divider()
st.caption("🔧 PostgreSQL Database Optimization Assistant | Powered by AI")