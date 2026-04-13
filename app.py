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
import traceback
import re
import matplotlib.pyplot as plt

# Add this at the top of app.py after imports
from auth.login_ui import show_login_page

# Initialize session state for authentication
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Set page config FIRST before any other Streamlit commands
st.set_page_config(page_title="DB Optimizer", layout="wide")

# FIX: Added encoding="utf-8" to prevent Unicode errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== AUTHENTICATION HANDLING ==========

# Function to get database config from session or defaults
def get_db_config():
    """Get database configuration from session state or return defaults"""
    if "db_config" in st.session_state:
        return st.session_state.db_config
    else:
        # Return default config for login page
        return {
            "host": "ep-divine-scene-anp4baya-pooler.c-6.us-east-1.aws.neon.tech",
            "port": 5432,
            "user": "neondb_owner",
            "password": "npg_vxGP8FcUI7gH",
            "database": "neondb",
            "ssl": True,
            "db_type": "PostgreSQL"
        }

# Check if user is authenticated
if not st.session_state["authenticated"]:
    # Show login page - this will handle authentication
    # The login page will set authenticated=True and user info in session state
    show_login_page(get_db_config())
    st.stop()  # Stop execution, don't show main app

# If authenticated, show the main app
# Show user info in sidebar
if st.session_state.get("authenticated"):
    user = st.session_state.get("user", {})
    st.sidebar.success(f"✅ Logged in as: {user.get('email', 'User')}")
    st.sidebar.caption(f"Role: {user.get('role', 'viewer')}")
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.clear()
        st.session_state["authenticated"] = False
        st.rerun()

# ========== MAIN APP CODE ==========

# Navigation sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["🏠 Home", "📊 Performance", "🔔 Alerts", "👥 Users", "⚙️ Settings"]
)

# Main title - only show on Home page
if page == "🏠 Home":
    st.title("PostgreSQL Database Optimization Assistant")

# Database configuration (use session state or defaults)
if "db_config" not in st.session_state:
    st.session_state.db_config = {
        "host": "ep-divine-scene-anp4baya-pooler.c-6.us-east-1.aws.neon.tech",
        "port": 5432,
        "user": "neondb_owner",
        "password": "npg_vxGP8FcUI7gH",
        "database": "neondb",
        "ssl": True,
        "db_type": "PostgreSQL"
    }

db_config = st.session_state.db_config

with st.sidebar:
    if page == "🏠 Home":
        st.header("Database Configuration")
        
        # Database type selector
        db_type = st.selectbox(
            "Database Type",
            ["PostgreSQL", "MySQL", "MongoDB"],
            index=["PostgreSQL", "MySQL", "MongoDB"].index(db_config.get("db_type", "PostgreSQL")),
            help="Select your database type"
        )
        
        db_host = st.text_input("Host", value=db_config.get("host", "ep-divine-scene-anp4baya-pooler.c-6.us-east-1.aws.neon.tech"))
        db_port = st.number_input("Port", value=db_config.get("port", 5432), min_value=1, max_value=65535)
        db_user = st.text_input("Username", value=db_config.get("user", "neondb_owner"))
        db_password = st.text_input("Password", type="password", value=db_config.get("password", "npg_vxGP8FcUI7gH"))
        db_name = st.text_input("Database Name", value=db_config.get("database", "neondb"))
        
        # Add SSL toggle for Neon (only for PostgreSQL)
        use_ssl = st.checkbox("Enable SSL (required for Neon)", value=db_config.get("ssl", True))
        
        # Update button
        if st.button("Update Configuration", width="stretch"):
            st.session_state.db_config = {
                "host": db_host,
                "port": db_port,
                "user": db_user,
                "password": db_password,
                "database": db_name,
                "ssl": use_ssl,
                "db_type": db_type
            }
            st.success("Configuration updated!")
            st.rerun()
        
        test_connection = st.button("Test Connection", width="stretch")
        
        # Add sidebar divider and autonomous fix mode
        st.sidebar.divider()
        st.sidebar.subheader("🤖 Autonomous Fix Mode")
        
        auto_fix_enabled = st.sidebar.checkbox("Enable Auto-Fix", value=False)
        approval_required = st.sidebar.checkbox("Require Approval", value=True)
        
        if auto_fix_enabled:
            from monitor.auto_fixer import AutoFixer
            
            if st.sidebar.button("🔍 Scan for Fixes"):
                with st.spinner("Analyzing database..."):
                    # Initialize SQL agent based on database type
                    if db_type == "PostgreSQL":
                        temp_agent = SQLAgent(db_config)
                    else:
                        # For other database types, create appropriate adapter
                        temp_agent = get_db_adapter(db_type, db_config)
                    
                    fixer = AutoFixer(temp_agent, approval_required)
                    suggestions = fixer.analyze_and_suggest_fixes()
                    
                    if suggestions:
                        st.sidebar.info(f"Found {len(suggestions)} optimization opportunities")
                        
                        for i, suggestion in enumerate(suggestions):
                            with st.sidebar.expander(f"{suggestion['type'].upper()}: {suggestion['description'][:50]}"):
                                st.code(suggestion['sql'], language='sql')
                                st.caption(f"Risk: {suggestion['risk']} | Impact: {suggestion['impact']}")
                                
                                if not approval_required or st.button(f"Apply Fix", key=f"apply_{i}"):
                                    if fixer.apply_fix(suggestion, approved=True):
                                        st.success("Fix applied successfully!")
                                        # Refresh the page to show updated state
                                        st.rerun()
                                    else:
                                        st.error("Failed to apply fix")
                    else:
                        st.sidebar.success("No fixes needed - database is optimized!")
    
    elif page == "📊 Performance":
        st.header("Performance Dashboard")
        st.info("Performance metrics and visualization will appear here after analysis")
    
    elif page == "🔔 Alerts":
        st.header("Alert Center")
        st.info("System alerts and notifications will appear here")
    
    elif page == "👥 Users":
        st.header("User Management")
        st.info("User management interface will appear here")
    
    elif page == "⚙️ Settings":
        st.header("Settings")
        st.info("Application settings and preferences")

def get_db_adapter(db_type: str, config: Dict):
    """Get the appropriate database adapter based on type"""
    try:
        if db_type == "PostgreSQL":
            from adapters.postgres_adapter import PostgresAdapter
            return PostgresAdapter(config)
        elif db_type == "MySQL":
            from adapters.mysql_adapter import MySQLAdapter
            return MySQLAdapter(config)
        elif db_type == "MongoDB":
            from adapters.mongodb_adapter import MongoDBAdapter
            return MongoDBAdapter(config)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    except ImportError as e:
        if db_type == "MySQL":
            st.error("❌ PyMySQL not installed. Run: pip install pymysql")
        elif db_type == "MongoDB":
            st.error("❌ PyMongo not installed. Run: pip install pymongo")
        raise e

def test_db_connection(config):
    """Test database connection with appropriate adapter"""
    try:
        if config["db_type"] == "PostgreSQL":
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
        
        elif config["db_type"] == "MySQL":
            try:
                import pymysql
                conn = pymysql.connect(
                    host=config["host"],
                    port=config["port"],
                    user=config["user"],
                    password=config["password"],
                    database=config["database"]
                )
                cursor = conn.cursor()
                cursor.execute("SELECT VERSION();")
                version = cursor.fetchone()
                cursor.close()
                conn.close()
                return True, f"Connected successfully! MySQL version: {version[0][:50]}..."
            except ImportError:
                return False, "PyMySQL not installed. Run: pip install pymysql"
        
        elif config["db_type"] == "MongoDB":
            try:
                from pymongo import MongoClient
                client = MongoClient(
                    host=config["host"],
                    port=config["port"],
                    username=config["user"],
                    password=config["password"],
                    authSource=config["database"]
                )
                # Ping the server
                client.admin.command('ping')
                version = client.server_info()['version']
                client.close()
                return True, f"Connected successfully! MongoDB version: {version}"
            except ImportError:
                return False, "PyMongo not installed. Run: pip install pymongo"
        
        else:
            return False, f"Unsupported database type: {config['db_type']}"
            
    except Exception as e:
        return False, str(e)

# Only show connection test and main content on Home page
if page == "🏠 Home":
    if 'test_connection' in locals() and test_connection:
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
    st.session_state.explain_results = None
if "index_suggestions" not in st.session_state:
    st.session_state.index_suggestions = None
if "performance_metrics" not in st.session_state:
    st.session_state.performance_metrics = None
if "llm" not in st.session_state:
    st.session_state.llm = None
if "alert_manager" not in st.session_state:
    st.session_state.alert_manager = None
if "monitoring_started" not in st.session_state:
    st.session_state.monitoring_started = False
if "db_adapter" not in st.session_state:
    st.session_state.db_adapter = None

def initialize_agent():
    try:
        logger.info(f"Initializing {db_config['db_type']} agent...")
        # Get appropriate adapter based on database type
        if db_config["db_type"] == "PostgreSQL":
            agent = SQLAgent(db_config)
        else:
            agent = get_db_adapter(db_config["db_type"], db_config)
        return agent
    except Exception as e:
        st.error(f"❌ Agent initialization failed: {str(e)}")
        logger.critical(f"Agent init failure: {str(e)}")
        st.stop()

def initialize_llm():
    """Initialize LLM for NLP debugging"""
    try:
        from langchain_openai import ChatOpenAI
        # You can configure this with environment variables or add to sidebar
        llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0,
            api_key=st.secrets.get("OPENAI_API_KEY", "")
        )
        return llm
    except Exception as e:
        logger.warning(f"LLM initialization failed: {e}")
        return None

def initialize_alert_manager():
    """Initialize and start the alert manager"""
    try:
        from monitor.alert_manager import AlertManager
        sql_agent = initialize_agent()
        alert_manager = AlertManager(sql_agent)
        # Start monitoring in background (every 5 minutes)
        alert_manager.start_monitoring(interval_seconds=300)
        logger.info("Alert manager initialized and monitoring started")
        return alert_manager
    except Exception as e:
        logger.error(f"Failed to initialize alert manager: {e}")
        return None

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
    
    # Get schema based on database type
    if db_config["db_type"] == "PostgreSQL":
        schema = agent.get_schema()
    else:
        # For other databases, get schema from adapter
        schema = agent.get_schema() if hasattr(agent, 'get_schema') else "Schema information available"
    
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
                    # Show raw AI output for debugging
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
                
                # Extract and store EXPLAIN ANALYZE results if present (PostgreSQL only)
                if "mrk_down" in event and db_config["db_type"] == "PostgreSQL":
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
            # Show full error traceback for debugging
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
    
    # Display Performance Analysis Section with Graphs
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
        
        # Add Performance Graph
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
            plt.close(fig)
            
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
    
    # Display EXPLAIN ANALYZE results if available (PostgreSQL only)
    if st.session_state.explain_results and db_config["db_type"] == "PostgreSQL":
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
    
    elif db_config["db_type"] != "PostgreSQL":
        st.info(f"ℹ️ Execution plan analysis is currently optimized for PostgreSQL. For {db_config['db_type']}, general optimization recommendations are provided.")
    
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
        agent = initialize_agent()
        
        if db_config["db_type"] == "PostgreSQL":
            schema = agent.get_schema()
        else:
            schema = "Schema information available"
        
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
    
    # Fallback to raw output if no SQL queries found
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
            test_button = st.form_submit_button("🧪 Test Queries", width="stretch")
        with col2:
            execute_button = st.form_submit_button("🚀 Execute Queries", width="stretch")
            
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
                agent = initialize_agent()
                
                # For different database types, use appropriate execution method
                if db_config["db_type"] == "PostgreSQL":
                    # Split queries by semicolon and filter empty ones
                    queries = [q.strip() for q in edited_queries.split(";") if q.strip()]
                else:
                    # For other databases, treat as single query or use adapter-specific logic
                    queries = [edited_queries.strip()] if edited_queries.strip() else []
                
                if not queries:
                    st.error("No valid queries found to execute")
                    return
                
                with st.status("📊 Executing queries...", expanded=True) as status:
                    successful = 0
                    failed = 0
                    
                    for i, query in enumerate(queries, 1):
                        try:
                            status.write(f"**Executing Query {i}:**")
                            st.code(query, language="sql")
                            
                            # Execute based on database type
                            if hasattr(agent, 'execute_query'):
                                result = agent.execute_query(query)
                            else:
                                # For custom adapters, try to use execute method
                                result = agent.execute(query) if hasattr(agent, 'execute') else str(agent)
                            
                            # Display results based on type
                            if isinstance(result, list):
                                if result:
                                    st.success(f"✅ Query {i} executed successfully - {len(result)} rows returned")
                                    with st.expander(f"View Query {i} Results"):
                                        st.json(result[:10])
                                        if len(result) > 10:
                                            st.info(f"Showing first 10 of {len(result)} rows")
                                else:
                                    st.success(f"✅ Query {i} executed successfully - No rows returned")
                            else:
                                st.success(f"✅ Query {i} executed successfully")
                                if result:
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

# Initialize Alert Manager after database connection is established
if page == "🏠 Home" and 'test_connection' in locals() and test_connection:
    if not st.session_state.monitoring_started:
        with st.spinner("Initializing alert manager..."):
            st.session_state.alert_manager = initialize_alert_manager()
            if st.session_state.alert_manager:
                st.session_state.monitoring_started = True
                logger.info("Alert monitoring started successfully")
            else:
                st.warning("⚠️ Alert manager initialization failed. Continuing without monitoring.")

# Display alerts in sidebar if alert manager is active
if st.session_state.alert_manager and st.session_state.alert_manager.get_active_alerts():
    st.sidebar.divider()
    st.sidebar.subheader("🚨 Active Alerts")
    
    active_alerts = st.session_state.alert_manager.get_active_alerts()
    for alert in active_alerts[:3]:
        with st.sidebar.expander(f"{alert['severity'].upper()}: {alert['title']}"):
            st.caption(alert['message'])
            st.caption(f"Predicted: {alert['predicted_issue']}")
            st.caption(f"Fix: {alert['recommendation']}")
            
            # Add quick fix button for critical alerts
            if alert['severity'].upper() == 'CRITICAL':
                if st.button(f"Apply Quick Fix", key=f"fix_alert_{alert['title']}"):
                    st.info("Quick fix feature coming soon!")

# Main UI buttons - only show on Home page
if page == "🏠 Home":
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("🚀 Start Analysis", width="stretch", type="primary"):
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
        if st.button("🔄 Clear History", width="stretch"):
            st.session_state.analysis_history = []
            st.session_state.test_results = None
            st.session_state.explain_results = None
            st.session_state.index_suggestions = None
            st.session_state.performance_metrics = None
            st.success("Analysis history cleared!")
            st.rerun()

    with col3:
        if st.button("📥 Download Logs", width="stretch"):
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

# Display results - only on Home page
if page == "🏠 Home":
    if st.session_state.analysis_history:
        st.divider()
        display_analysis()
        st.divider()
        execute_queries()
        
        # Add NLP Debugging Section after query execution
        st.divider()
        st.subheader("💬 Natural Language Debugging")
        
        debug_query = st.text_area(
            "Ask about database performance:",
            placeholder="Example: Why are my orders queries slow?",
            height=80,
            key="debug_query_input"
        )
        
        if st.button("🔍 Explain", width="stretch", key="explain_button"):
            if debug_query:
                with st.spinner("Analyzing your question..."):
                    # Initialize LLM if not already done
                    if st.session_state.llm is None:
                        st.session_state.llm = initialize_llm()
                    
                    if st.session_state.llm:
                        try:
                            from nlp.query_explainer import QueryExplainer
                            explainer = QueryExplainer(st.session_state.llm)
                            
                            # Get current performance metrics
                            metrics = {}
                            if st.session_state.performance_metrics:
                                metrics = {
                                    'execution_time': st.session_state.performance_metrics.get('after_time', 'N/A'),
                                    'improvement': st.session_state.performance_metrics.get('improvement', 0),
                                    'scan_type': 'Index Scan' if st.session_state.performance_metrics.get('improvement', 0) > 0 else 'Seq Scan',
                                    'rows_examined': 1000
                                }
                            else:
                                metrics = {
                                    'execution_time': 'N/A',
                                    'improvement': 0,
                                    'scan_type': 'Unknown',
                                    'rows_examined': 1000
                                }
                            
                            # Get execution plan if available
                            plan = st.session_state.get('plan', '')
                            if not plan and st.session_state.explain_results:
                                plan = st.session_state.explain_results
                            
                            explanation = explainer.explain_performance(
                                debug_query,
                                plan,
                                metrics
                            )
                            
                            st.info(explanation)
                        except ImportError:
                            st.error("❌ QueryExplainer module not found. Please ensure nlp.query_explainer is installed.")
                        except Exception as e:
                            st.error(f"❌ Error generating explanation: {str(e)}")
                            logger.error(f"NLP Debugging error: {traceback.format_exc()}")
                    else:
                        st.warning("⚠️ LLM not configured. Please set up OpenAI API key to use this feature.")
            else:
                st.warning("Please enter a question about database performance")
    else:
        st.info("👈 Enter an optimization request and click 'Start Analysis' to begin")

# Performance Dashboard Page
elif page == "📊 Performance":
    try:
        # Import the performance dashboard function
        from dashboard.pages.performance import show_performance_dashboard
        
        # Initialize the SQL agent
        sql_agent = initialize_agent()
        
        # Get alert manager from session state
        alert_manager = st.session_state.get('alert_manager')
        
        # Display the performance dashboard
        show_performance_dashboard(sql_agent, alert_manager)
        
    except ImportError as e:
        st.error(f"❌ Performance dashboard module not found: {e}")
        st.info("Please ensure dashboard/pages/performance.py exists with the show_performance_dashboard function.")
        
        # Provide fallback content
        st.subheader("📊 Performance Metrics (Fallback View)")
        st.info("The performance dashboard module is not available. Here's a basic metrics view:")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Avg Query Time", "45ms", "-12ms")
        with col2:
            st.metric("Index Usage", "78%", "+5%")
        with col3:
            st.metric("Active Connections", "12", "+2")
        with col4:
            st.metric("Cache Hit Ratio", "98.5%", "+0.3%")
            
        st.warning("For full dashboard features, create the dashboard/pages/performance.py file.")
        
    except Exception as e:
        st.error(f"❌ Dashboard error: {str(e)}")
        st.info("Performance dashboard will be available after fixing the module.")
        logger.error(f"Dashboard error: {traceback.format_exc()}")

# Alerts Dashboard Page
elif page == "🔔 Alerts":
    try:
        from dashboard.pages.alerts import show_alerts_dashboard
        show_alerts_dashboard(st.session_state.get('alert_manager'))
    except ImportError:
        st.error("❌ Alerts dashboard module not found. Please ensure dashboard/pages/alerts.py exists.")
        
        # Provide fallback alerts view
        st.subheader("🔔 Active Alerts")
        
        if st.session_state.alert_manager and st.session_state.alert_manager.get_active_alerts():
            active_alerts = st.session_state.alert_manager.get_active_alerts()
            for alert in active_alerts:
                with st.container():
                    if alert['severity'].upper() == 'CRITICAL':
                        st.error(f"**CRITICAL**: {alert['title']}")
                    elif alert['severity'].upper() == 'WARNING':
                        st.warning(f"**WARNING**: {alert['title']}")
                    else:
                        st.info(f"**INFO**: {alert['title']}")
                    st.caption(alert['message'])
                    st.divider()
        else:
            st.success("✅ No active alerts. System is healthy!")
            
        st.info("You can create the dashboard/pages/alerts.py module for enhanced alert management.")

# Users Management Page
elif page == "👥 Users":
    try:
        # Import the admin users functions
        from dashboard.pages.admin_users import show_admin_users, show_login_activity
        show_admin_users(auth)
        st.divider()
        show_login_activity(auth)
    except ImportError:
        st.error("❌ Admin users module not found. Please ensure dashboard/pages/admin_users.py exists.")
        
        # Provide fallback user management view
        st.subheader("👥 User Management")
        
        # Display current user info
        if st.session_state.get("authenticated"):
            user = st.session_state.get("user", {})
            st.info(f"**Current User:** {user.get('email', 'Unknown')}")
            st.info(f"**Role:** {user.get('role', 'viewer')}")
        
        st.markdown("---")
        
        # Fallback user list (read-only)
        st.subheader("System Users")
        st.info("User management features will be available when the admin_users module is created.")
        
        # Simple user info display
        users_data = [
            {"email": "admin@example.com", "role": "admin", "status": "active"},
            {"email": "user@example.com", "role": "viewer", "status": "active"}
        ]
        
        st.table(users_data)
        
        st.info("""
        **To enable full user management:**
        1. Create `dashboard/pages/admin_users.py` with the following functions:
           - `show_admin_users(auth)` - Display user management interface
           - `show_login_activity(auth)` - Display login activity log
        2. Ensure proper authentication is implemented
        """)
        
    except Exception as e:
        st.error(f"❌ Users page error: {str(e)}")
        logger.error(f"Users page error: {traceback.format_exc()}")

# Settings Page
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    
    st.subheader("Application Configuration")
    
    # LLM Settings
    st.markdown("### 🤖 LLM Configuration")
    openai_api_key = st.text_input("OpenAI API Key", type="password", 
                                   help="Enter your OpenAI API key for NLP features")
    if openai_api_key:
        st.session_state['openai_api_key'] = openai_api_key
        st.success("✅ API key saved for this session!")
    
    # Monitoring Settings
    st.markdown("### 📊 Monitoring Settings")
    monitoring_interval = st.number_input("Alert Monitoring Interval (seconds)", 
                                         min_value=60, max_value=3600, value=300,
                                         help="How often to check for database issues")
    
    alert_thresholds = st.slider("Performance Alert Threshold (ms)", 
                                 min_value=50, max_value=5000, value=500,
                                 help="Alert when query execution time exceeds this value")
    
    # Notification Settings
    st.markdown("### 🔔 Notification Settings")
    email_notifications = st.checkbox("Enable Email Notifications")
    if email_notifications:
        email_address = st.text_input("Email Address", placeholder="admin@example.com")
    
    # Database Settings
    st.markdown("### 💾 Database Settings")
    auto_backup = st.checkbox("Enable Automatic Backups", value=False)
    backup_interval = st.selectbox("Backup Frequency", ["Daily", "Weekly", "Monthly"])
    
    # UI Settings
    st.markdown("### 🎨 Display Settings")
    theme = st.selectbox("Theme", ["Light", "Dark", "System Default"])
    auto_refresh = st.checkbox("Auto-refresh dashboard", value=False)
    if auto_refresh:
        refresh_interval = st.number_input("Refresh Interval (seconds)", min_value=10, max_value=300, value=30)
    
    # Save Settings
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Settings", width="stretch", type="primary"):
            st.success("Settings saved successfully!")
            logger.info("User settings updated")
            
            # Store settings in session state
            st.session_state.settings = {
                'monitoring_interval': monitoring_interval,
                'alert_thresholds': alert_thresholds,
                'email_notifications': email_notifications,
                'auto_backup': auto_backup,
                'backup_interval': backup_interval,
                'theme': theme,
                'auto_refresh': auto_refresh
            }
    
    with col2:
        if st.button("🔄 Reset to Defaults", width="stretch"):
            st.warning("Settings reset to defaults")
            if 'settings' in st.session_state:
                del st.session_state.settings
            st.rerun()
    
    # About Section
    st.divider()
    st.markdown("### ℹ️ About")
    st.info("""
    **Database Optimization Assistant v1.0**
    
    This application helps you optimize database performance through:
    - Automated query analysis
    - Index recommendations
    - Performance monitoring
    - Alert management
    
    For support or feature requests, please contact your system administrator.
    """)

# Footer - only show on Home page
if page == "🏠 Home":
    st.divider()
    st.caption("🔧 Database Optimization Assistant | Powered by AI | Supports PostgreSQL, MySQL, and MongoDB")