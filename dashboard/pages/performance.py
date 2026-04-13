import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def show_performance_dashboard(sql_agent, alert_manager):
    """
    Display performance dashboard with metrics, charts, and recommendations
    
    Args:
        sql_agent: SQL agent instance for database queries
        alert_manager: Alert manager instance for collecting metrics
    """
    st.title("📊 Performance Dashboard")
    
    # Get metrics with error handling
    metrics = {}
    if alert_manager:
        try:
            metrics = alert_manager.collect_metrics() if hasattr(alert_manager, 'collect_metrics') else {}
            logger.info("Successfully collected performance metrics")
        except Exception as e:
            st.warning(f"Could not fetch metrics: {e}")
            logger.warning(f"Metrics collection failed: {e}")
    
    # Row 1: Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Avg Query Time",
            f"{metrics.get('avg_query_time', 45)}ms",
            delta="-12ms",
            delta_color="normal",
            help="Average response time for database queries"
        )
    
    with col2:
        st.metric(
            "Index Usage",
            f"{metrics.get('index_ratio', 78)}%",
            delta="+5%",
            delta_color="normal",
            help="Percentage of queries using indexes effectively"
        )
    
    with col3:
        st.metric(
            "Active Connections",
            f"{metrics.get('active_connections', 12)}",
            delta="+2",
            delta_color="inverse",
            help="Current number of active database connections"
        )
    
    with col4:
        st.metric(
            "Cache Hit Ratio",
            f"{metrics.get('cache_hit_ratio', 98.5)}%",
            delta="+0.3%",
            delta_color="normal",
            help="Percentage of queries served from cache"
        )
    
    # Row 2: Performance Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Query Performance Trend")
        
        # Create sample data for query performance trend
        df = pd.DataFrame({
            'time': pd.date_range(start='2024-01-01', periods=24, freq='h'),
            'response_time': [45, 47, 43, 48, 52, 55, 50, 46, 44, 42, 41, 40,
                             39, 38, 37, 36, 35, 34, 33, 32, 31, 30, 29, 28]
        })
        
        fig = px.line(df, x='time', y='response_time', title="Response Time (ms)")
        fig.update_layout(
            height=300,
            xaxis_title="Time",
            yaxis_title="Response Time (ms)",
            hovermode='x unified'
        )
        fig.update_traces(line=dict(color='#2E86AB', width=2))
        st.plotly_chart(fig, width="stretch")
    
    with col2:
        st.subheader("Index Usage Analysis")
        
        index_data = pd.DataFrame({
            'Table': ['orders', 'orders', 'users', 'users', 'products'],
            'Index': ['user_id', 'status', 'email', 'created_at', 'name'],
            'Usage (%)': [95, 82, 67, 45, 23],
            'Size': ['12MB', '8MB', '6MB', '4MB', '2MB']
        })
        
        fig = px.bar(index_data, x='Index', y='Usage (%)', color='Table',
                     title="Index Usage Percentage", text='Usage (%)')
        fig.update_layout(
            height=300,
            xaxis_title="Index Name",
            yaxis_title="Usage (%)",
            showlegend=True
        )
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, width="stretch")
    
    # Row 3: Slow Queries Table
    st.subheader("🔍 Top 10 Slow Queries")
    
    slow_queries = pd.DataFrame({
        'Query ID': range(1, 6),
        'Query': [
            'SELECT * FROM orders WHERE status = "completed" AND created_at > NOW() - INTERVAL 7 DAY',
            'SELECT * FROM users WHERE email LIKE "%gmail.com" ORDER BY created_at',
            'SELECT o.*, u.* FROM orders o JOIN users u ON o.user_id = u.id WHERE o.status = "pending"',
            'SELECT COUNT(*), status, DATE(created_at) FROM orders GROUP BY status, DATE(created_at)',
            'SELECT * FROM orders WHERE user_id IN (SELECT id FROM users WHERE active = 1) ORDER BY created_at DESC'
        ],
        'Execution Time (ms)': [245, 189, 156, 134, 98],
        'Calls': [1234, 987, 654, 432, 321],
        'Rows/Exec': [10000, 5000, 2500, 1000, 500],
        'Suggested Index': [
            'idx_orders_status_created',
            'idx_users_email',
            'idx_orders_user_status',
            'idx_orders_status_date',
            'idx_orders_user_created'
        ]
    })
    
    # Display dataframe with modern syntax
    st.dataframe(
        slow_queries,
        column_config={
            "Query ID": st.column_config.NumberColumn(width="small"),
            "Query": st.column_config.TextColumn(width="large"),
            "Execution Time (ms)": st.column_config.NumberColumn(
                format="%.0f ms",
                help="Time taken to execute the query"
            ),
            "Calls": st.column_config.NumberColumn(
                format="%d",
                help="Number of times query was executed"
            ),
            "Rows/Exec": st.column_config.NumberColumn(
                format="%d",
                help="Average rows returned per execution"
            ),
            "Suggested Index": st.column_config.TextColumn(
                help="Recommended index to optimize this query"
            )
        },
        hide_index=True,
        width="stretch"
    )
    
    # Add download button for slow queries
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("📋 Export Slow Queries", width="stretch"):
            csv = slow_queries.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"slow_queries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                width="stretch"
            )
    
    # Row 4: Recommendations
    st.subheader("💡 Optimization Recommendations")
    
    recommendations = [
        {
            "priority": "High",
            "recommendation": "Add composite index on orders(status, user_id, created_at)",
            "impact": "Expected 80% performance improvement",
            "effort": "Low"
        },
        {
            "priority": "High",
            "recommendation": "Consider partitioning orders table by created_at",
            "impact": "5M rows, growing 10% weekly",
            "effort": "Medium"
        },
        {
            "priority": "Medium",
            "recommendation": "Update statistics on users table",
            "impact": "Last analyzed 14 days ago",
            "effort": "Low"
        },
        {
            "priority": "Low",
            "recommendation": "Remove unused index idx_orders_old on orders",
            "impact": "Never used, size 8MB",
            "effort": "Low"
        }
    ]
    
    for rec in recommendations:
        if rec['priority'] == 'High':
            st.error(f"**🚨 {rec['priority']} Priority**: {rec['recommendation']}")
            st.caption(f"💪 Impact: {rec['impact']} | ⏱️ Effort: {rec['effort']}")
        elif rec['priority'] == 'Medium':
            st.warning(f"**⚠️ {rec['priority']} Priority**: {rec['recommendation']}")
            st.caption(f"💪 Impact: {rec['impact']} | ⏱️ Effort: {rec['effort']}")
        else:
            st.info(f"**ℹ️ {rec['priority']} Priority**: {rec['recommendation']}")
            st.caption(f"💪 Impact: {rec['impact']} | ⏱️ Effort: {rec['effort']}")
    
    # Row 5: System Health with progress bars
    with st.expander("🖥️ System Health Metrics", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            cpu_usage = 45
            st.metric("CPU Usage", f"{cpu_usage}%", delta="-2%")
            st.progress(cpu_usage / 100, text=f"CPU: {cpu_usage}%")
            
            mem_usage = 62
            st.metric("Memory Usage", f"{mem_usage}%", delta="+1%")
            st.progress(mem_usage / 100, text=f"Memory: {mem_usage}%")
            
            disk_usage = 34
            st.metric("Disk Usage", f"{disk_usage}%", delta="+3%")
            st.progress(disk_usage / 100, text=f"Disk: {disk_usage}%")
        
        with col2:
            st.metric("IOPS", "234", delta="-12")
            st.metric("Network In", "1.2 MB/s", delta="-0.3")
            st.metric("Network Out", "0.8 MB/s", delta="+0.1")
            
            st.divider()
            st.metric("Database Size", "2.4 GB", delta="+120 MB")
            st.metric("WAL Size", "45 MB", delta="-5 MB")
    
    # Row 6: Additional Analytics (Collapsible)
    with st.expander("📈 Advanced Analytics", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            # Query performance distribution pie chart
            query_dist = pd.DataFrame({
                'Category': ['Fast (<50ms)', 'Medium (50-200ms)', 'Slow (>200ms)'],
                'Percentage': [65, 25, 10]
            })
            fig = px.pie(query_dist, values='Percentage', names='Category', 
                        title="Query Performance Distribution",
                        color_discrete_sequence=['#2E86AB', '#A23B72', '#F18F01'])
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, width="stretch")
        
        with col2:
            # Hourly query volume
            hourly_queries = pd.DataFrame({
                'hour': list(range(24)),
                'queries': [120, 80, 60, 45, 40, 55, 150, 350, 500, 620, 
                           680, 590, 550, 520, 580, 650, 720, 750, 680, 
                           590, 480, 380, 250, 180]
            })
            fig = px.bar(hourly_queries, x='hour', y='queries', 
                        title="Hourly Query Volume",
                        labels={'hour': 'Hour of Day', 'queries': 'Number of Queries'})
            fig.update_layout(height=300)
            st.plotly_chart(fig, width="stretch")
    
    # Row 7: Real-time Performance Metrics (if available from sql_agent)
    if sql_agent and hasattr(sql_agent, 'get_performance_metrics'):
        with st.expander("⚡ Real-time Performance Metrics", expanded=False):
            try:
                realtime_metrics = sql_agent.get_performance_metrics()
                if realtime_metrics:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Queries/sec", realtime_metrics.get('queries_per_sec', 'N/A'))
                        st.metric("Avg Latency", realtime_metrics.get('avg_latency', 'N/A'))
                    with col2:
                        st.metric("Connections", realtime_metrics.get('total_connections', 'N/A'))
                        st.metric("Idle Connections", realtime_metrics.get('idle_connections', 'N/A'))
                    with col3:
                        st.metric("Transactions/sec", realtime_metrics.get('tps', 'N/A'))
                        st.metric("Rollback Rate", realtime_metrics.get('rollback_rate', 'N/A'))
            except Exception as e:
                st.info(f"Real-time metrics unavailable: {e}")
    
    # Footer with timestamp
    st.divider()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"📊 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    with col2:
        if st.button("🔄 Refresh Dashboard", width="stretch"):
            st.rerun()

# For testing the dashboard independently
if __name__ == "__main__":
    # Mock classes for testing
    class MockSQLAgent:
        def get_performance_metrics(self):
            return {
                'queries_per_sec': 125,
                'avg_latency': '45ms',
                'total_connections': 12,
                'idle_connections': 5,
                'tps': 98,
                'rollback_rate': '2.3%'
            }
    
    class MockAlertManager:
        def collect_metrics(self):
            return {
                'avg_query_time': 45,
                'index_ratio': 78,
                'active_connections': 12,
                'cache_hit_ratio': 98.5
            }
    
    # Test the dashboard
    sql_agent = MockSQLAgent()
    alert_manager = MockAlertManager()
    show_performance_dashboard(sql_agent, alert_manager)
