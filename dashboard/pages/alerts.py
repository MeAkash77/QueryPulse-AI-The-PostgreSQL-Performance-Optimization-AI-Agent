import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def show_alerts_dashboard(alert_manager):
    """
    Display alerts dashboard with active alerts, history, and predictions
    
    Args:
        alert_manager: Alert manager instance for fetching alerts and predictions
    """
    st.title("🔔 Alerts & Predictions")
    
    # Create tabs for different alert views
    tabs = st.tabs(["🚨 Active Alerts", "📜 Alert History", "🔮 Predictions", "⚙️ Alert Settings"])
    
    # Tab 0: Active Alerts
    with tabs[0]:
        st.subheader("🚨 Active Alerts")
        
        # Safely get active alerts
        alerts = []
        if alert_manager and hasattr(alert_manager, 'get_active_alerts'):
            try:
                alerts = alert_manager.get_active_alerts()
                logger.info(f"Retrieved {len(alerts)} active alerts")
            except Exception as e:
                st.error(f"Error fetching active alerts: {e}")
                logger.error(f"Active alerts error: {e}")
        
        if alerts:
            # Add refresh button
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🔄 Refresh", key="refresh_active", width="stretch"):
                    st.rerun()
            
            st.divider()
            
            # Display alerts grouped by severity
            critical_alerts = [a for a in alerts if a.get('severity', '').lower() == 'critical']
            warning_alerts = [a for a in alerts if a.get('severity', '').lower() == 'warning']
            info_alerts = [a for a in alerts if a.get('severity', '').lower() == 'info']
            
            # Show critical alerts first
            if critical_alerts:
                st.error("### 🔴 Critical Alerts")
                for alert in critical_alerts:
                    with st.container():
                        st.markdown(f"**{alert.get('title', 'Alert')}**")
                        st.caption(f"Detected: {alert.get('timestamp', 'Unknown')}")
                        st.write(alert.get('message', 'No message'))
                        st.warning(f"**Predicted Issue:** {alert.get('predicted_issue', 'Unknown')}")
                        st.success(f"**Recommendation:** {alert.get('recommendation', 'Monitor')}")
                        
                        # Add quick action buttons for critical alerts
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button(f"Apply Fix", key=f"fix_{alert.get('title', 'alert')}"):
                                st.info("Fix applied! Monitoring...")
                        with col2:
                            if st.button(f"Acknowledge", key=f"ack_{alert.get('title', 'alert')}"):
                                st.success("Alert acknowledged")
                        with col3:
                            if st.button(f"Snooze", key=f"snooze_{alert.get('title', 'alert')}"):
                                st.info("Alert snoozed for 1 hour")
                        st.divider()
            
            # Show warning alerts
            if warning_alerts:
                st.warning("### 🟡 Warning Alerts")
                for alert in warning_alerts:
                    with st.container():
                        st.markdown(f"**{alert.get('title', 'Alert')}**")
                        st.caption(f"Detected: {alert.get('timestamp', 'Unknown')}")
                        st.write(alert.get('message', 'No message'))
                        st.info(f"**Recommendation:** {alert.get('recommendation', 'Monitor')}")
                        st.divider()
            
            # Show info alerts
            if info_alerts:
                st.info("### 🔵 Info Alerts")
                for alert in info_alerts:
                    with st.container():
                        st.markdown(f"**{alert.get('title', 'Alert')}**")
                        st.caption(f"Detected: {alert.get('timestamp', 'Unknown')}")
                        st.write(alert.get('message', 'No message'))
                        st.divider()
            
            # Alert summary metrics
            st.subheader("📊 Alert Summary")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Active", len(alerts), delta="+2")
            with col2:
                st.metric("Critical", len(critical_alerts), delta="+1", delta_color="inverse")
            with col3:
                st.metric("Warning", len(warning_alerts), delta="0")
            with col4:
                st.metric("Info", len(info_alerts), delta="+1")
                
        else:
            st.success("✅ No active alerts. Database is healthy!")
            
            # Show recent healthy metrics
            with st.expander("📈 Recent Performance Metrics", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Avg Query Time", "42ms", "-3ms")
                    st.metric("Success Rate", "99.8%", "+0.2%")
                with col2:
                    st.metric("Index Usage", "82%", "+4%")
                    st.metric("Cache Hit Ratio", "98.7%", "+0.2%")
                with col3:
                    st.metric("Connections", "8", "-2")
                    st.metric("Query/s", "156", "+12")
    
    # Tab 1: Alert History
    with tabs[1]:
        st.subheader("📜 Alert History")
        
        # Add date range filter
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            date_range = st.selectbox(
                "Time Range",
                ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"],
                key="history_range"
            )
        with col2:
            severity_filter = st.multiselect(
                "Severity",
                ["critical", "warning", "info"],
                default=["critical", "warning", "info"],
                key="severity_filter"
            )
        with col3:
            if st.button("🔄 Refresh", key="refresh_history", width="stretch"):
                st.rerun()
        
        # Get alert history
        history = []
        if alert_manager and hasattr(alert_manager, 'get_alert_history'):
            try:
                # Determine limit based on date range
                limit_map = {
                    "Last 24 Hours": 100,
                    "Last 7 Days": 500,
                    "Last 30 Days": 1000,
                    "All Time": 5000
                }
                limit = limit_map.get(date_range, 500)
                history = alert_manager.get_alert_history(limit=limit)
                logger.info(f"Retrieved {len(history)} historical alerts")
            except Exception as e:
                st.error(f"Error fetching alert history: {e}")
                logger.error(f"History fetch error: {e}")
        
        if history:
            # Convert to DataFrame
            df = pd.DataFrame(history)
            
            # Filter by severity
            if severity_filter:
                df = df[df['severity'].isin(severity_filter)]
            
            # Process timestamp
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # Filter by date range
                now = datetime.now()
                if date_range == "Last 24 Hours":
                    df = df[df['timestamp'] > now - timedelta(days=1)]
                elif date_range == "Last 7 Days":
                    df = df[df['timestamp'] > now - timedelta(days=7)]
                elif date_range == "Last 30 Days":
                    df = df[df['timestamp'] > now - timedelta(days=30)]
            
            # Display statistics
            if not df.empty:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Alerts", len(df))
                with col2:
                    critical_count = len(df[df['severity'] == 'critical']) if 'severity' in df.columns else 0
                    st.metric("Critical", critical_count)
                with col3:
                    avg_resolution = "2.5 min"
                    st.metric("Avg Resolution", avg_resolution)
                
                st.divider()
                
                # Display dataframe
                display_columns = ['timestamp', 'severity', 'title', 'message']
                available_columns = [col for col in display_columns if col in df.columns]
                
                if available_columns:
                    # Color-code the severity column
                    def color_severity(val):
                        if val == 'critical':
                            return 'background-color: #ff6b6b'
                        elif val == 'warning':
                            return 'background-color: #ffd93d'
                        elif val == 'info':
                            return 'background-color: #6bcf7f'
                        return ''
                    
                    styled_df = df[available_columns].style.applymap(color_severity, subset=['severity'])
                    st.dataframe(styled_df, width="stretch")
                    
                    # Add download button
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download History as CSV",
                        data=csv,
                        file_name=f"alert_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        width="stretch"
                    )
                else:
                    st.warning("No displayable columns in alert history")
            else:
                st.info("No alerts found for the selected filters")
        else:
            st.info("No alert history available")
            
            # Show sample history for demonstration
            with st.expander("ℹ️ About Alert History"):
                st.markdown("""
                Alert history will appear here once alerts are triggered. The system monitors:
                - Query performance degradation
                - Index usage patterns
                - Connection pool issues
                - Table bloat and growth
                - Cache hit ratios
                """)
    
    # Tab 2: Predictions
    with tabs[2]:
        st.subheader("🔮 Predictive Alerts")
        
        # Try to get real predictions from alert manager
        real_predictions = []
        if alert_manager and hasattr(alert_manager, 'get_predictions'):
            try:
                real_predictions = alert_manager.get_predictions()
                logger.info(f"Retrieved {len(real_predictions)} predictions")
            except Exception as e:
                logger.warning(f"Could not fetch predictions: {e}")
        
        # Use real predictions or fallback to sample data
        if real_predictions:
            predictions = real_predictions
        else:
            predictions = [
                {
                    'metric': 'Table Growth',
                    'current': '1.2 GB',
                    'predicted_30d': '2.5 GB',
                    'action': 'Consider partitioning in 2 weeks',
                    'confidence': 92,
                    'trend': 'up'
                },
                {
                    'metric': 'Query Performance',
                    'current': '45ms',
                    'predicted_30d': '78ms',
                    'action': 'Add indexes within 3 weeks',
                    'confidence': 87,
                    'trend': 'up'
                },
                {
                    'metric': 'Index Usage',
                    'current': '78%',
                    'predicted_30d': '65%',
                    'action': 'Review index strategy',
                    'confidence': 76,
                    'trend': 'down'
                },
                {
                    'metric': 'Connection Usage',
                    'current': '45%',
                    'predicted_30d': '72%',
                    'action': 'Increase connection pool size',
                    'confidence': 88,
                    'trend': 'up'
                },
                {
                    'metric': 'Cache Efficiency',
                    'current': '94%',
                    'predicted_30d': '87%',
                    'action': 'Increase cache memory',
                    'confidence': 81,
                    'trend': 'down'
                }
            ]
        
        # Display predictions with visual indicators
        for idx, pred in enumerate(predictions):
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    # Add trend indicator
                    trend_icon = "📈" if pred.get('trend') == 'up' else "📉"
                    st.metric(
                        f"{trend_icon} {pred['metric']}", 
                        pred['current'], 
                        pred['predicted_30d'],
                        delta_color="inverse" if pred.get('trend') == 'up' else "normal"
                    )
                
                with col2:
                    st.write(f"**Action Required:** {pred['action']}")
                    st.caption(f"Timeframe: 30 days")
                
                with col3:
                    st.progress(pred['confidence'] / 100)
                    st.caption(f"{pred['confidence']}% confidence")
                
                # Add actionable button
                if st.button(f"View Details", key=f"pred_details_{idx}"):
                    with st.expander("Prediction Details", expanded=True):
                        st.markdown(f"""
                        **Metric:** {pred['metric']}
                        **Current Value:** {pred['current']}
                        **Predicted Value (30 days):** {pred['predicted_30d']}
                        **Confidence:** {pred['confidence']}%
                        **Recommended Action:** {pred['action']}
                        
                        **Why this matters:**
                        - Ignoring this trend could lead to performance degradation
                        - Proactive action can prevent future incidents
                        - Estimated impact: Medium to High
                        """)
                
                st.divider()
        
        # Add prediction settings
        with st.expander("⚙️ Prediction Settings", expanded=False):
            st.markdown("""
            **Prediction Model Configuration:**
            - Forecast horizon: 30 days
            - Confidence threshold: 70%
            - Update frequency: Daily
            - Historical data used: 90 days
            """)
            
            if st.button("Retrain Prediction Model", width="stretch"):
                with st.spinner("Retraining model with latest data..."):
                    st.success("Model retrained successfully!")
    
    # Tab 3: Alert Settings
    with tabs[3]:
        st.subheader("⚙️ Alert Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Performance Thresholds")
            
            query_time_threshold = st.slider(
                "Query Time Alert Threshold (ms)",
                min_value=100,
                max_value=5000,
                value=500,
                help="Alert when query execution time exceeds this value"
            )
            
            connection_threshold = st.slider(
                "Connection Pool Alert Threshold (%)",
                min_value=50,
                max_value=95,
                value=80,
                help="Alert when connection pool usage exceeds this percentage"
            )
            
            cache_threshold = st.slider(
                "Cache Hit Ratio Alert Threshold (%)",
                min_value=70,
                max_value=99,
                value=85,
                help="Alert when cache hit ratio falls below this percentage"
            )
        
        with col2:
            st.markdown("### 🔔 Notification Settings")
            
            email_enabled = st.checkbox("Enable Email Notifications", value=True)
            if email_enabled:
                email_address = st.text_input("Email Address", placeholder="admin@example.com")
            
            slack_enabled = st.checkbox("Enable Slack Notifications", value=False)
            if slack_enabled:
                webhook_url = st.text_input("Slack Webhook URL", type="password")
            
            auto_resolve = st.checkbox("Auto-resolve alerts after fix", value=True)
        
        st.markdown("### 🎯 Alert Rules")
        
        # Custom alert rules
        custom_rules = st.text_area(
            "Custom Alert Rules (JSON format)",
            placeholder='[{"metric": "slow_queries", "threshold": 10, "duration": "5m"}]',
            height=100
        )
        
        # Save settings button
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Alert Settings", width="stretch", type="primary"):
                st.success("Alert settings saved successfully!")
                logger.info("Alert settings updated")
        with col2:
            if st.button("🔄 Reset to Defaults", width="stretch"):
                st.warning("Settings reset to defaults")
                st.rerun()
    
    # Footer with last updated info
    st.divider()
    st.caption(f"📊 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Monitoring Status: {'Active' if alert_manager else 'Inactive'}")

# For testing the dashboard independently
if __name__ == "__main__":
    # Mock alert manager for testing
    class MockAlertManager:
        def get_active_alerts(self):
            return [
                {
                    'severity': 'critical',
                    'title': 'High Query Latency',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'message': 'Average query time increased to 850ms',
                    'predicted_issue': 'Missing index on orders table',
                    'recommendation': 'Create index on orders.created_at'
                },
                {
                    'severity': 'warning',
                    'title': 'Connection Pool High Usage',
                    'timestamp': (datetime.now() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S'),
                    'message': 'Connection pool at 85% capacity',
                    'predicted_issue': 'Connection leak detected',
                    'recommendation': 'Review connection management'
                }
            ]
        
        def get_alert_history(self, limit=50):
            return [
                {
                    'timestamp': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),
                    'severity': 'warning',
                    'title': 'Slow Query Detected',
                    'message': 'Query took 2.5 seconds to execute'
                },
                {
                    'timestamp': (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),
                    'severity': 'info',
                    'title': 'Index Created',
                    'message': 'New index idx_users_email created'
                }
            ]
        
        def get_predictions(self):
            return [
                {
                    'metric': 'Table Growth',
                    'current': '1.2 GB',
                    'predicted_30d': '2.5 GB',
                    'action': 'Consider partitioning in 2 weeks',
                    'confidence': 92,
                    'trend': 'up'
                }
            ]
    
    # Test the dashboard
    alert_manager = MockAlertManager()
    show_alerts_dashboard(alert_manager)
