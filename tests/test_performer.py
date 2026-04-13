import pytest
from unittest.mock import Mock, patch
from performer.performer import create_performer_graph
from agentstate.agent_state import AgentState

class TestPerformer:
    @pytest.fixture
    def mock_db_config(self):
        return {
            "host": "localhost",
            "port": 5432,
            "user": "test_user",
            "password": "test_pass",
            "database": "test_db"
        }
    
    @pytest.fixture
    def mock_state(self):
        return AgentState(
            query="Optimize orders query",
            schema="users(id, name), orders(id, user_id, status)",
            db_config={},
            analysis="",
            feedback="",
            execute=False,
            reanalyze=False,
            execute_query="",
            mrk_down=""
        )
    
    def test_create_performer_graph(self, mock_db_config):
        graph = create_performer_graph(mock_db_config)
        assert graph is not None
    
    @patch('performer.performer.SQLAgent')
    def test_analyze_database_success(self, mock_sql_agent, mock_state, mock_db_config):
        mock_agent = Mock()
        mock_agent.get_connection.return_value = Mock()
        mock_sql_agent.return_value = mock_agent
        
        graph = create_performer_graph(mock_db_config)
        assert hasattr(graph, 'stream')
    
    def test_extract_sql_queries(self):
        from utils.sql_utils import extract_sql_queries
        text = "SELECT * FROM users; SELECT * FROM orders;"
        queries = extract_sql_queries(text)
        assert "SELECT" in queries
    
    def test_has_seq_scan_in_plan(self):
        from performer.performer import has_seq_scan_in_plan
        plan = "Seq Scan on users"
        assert has_seq_scan_in_plan(plan) is True
    
    def test_has_index_scan_in_plan(self):
        from performer.performer import has_index_scan_in_plan
        plan = "Index Scan using idx_users"
        assert has_index_scan_in_plan(plan) is True