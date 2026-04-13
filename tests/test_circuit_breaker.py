import pytest
import time
from core.circuit_breaker import CircuitBreaker, CircuitState

class TestCircuitBreaker:
    def test_closed_state_on_success(self):
        breaker = CircuitBreaker("test")
        
        def successful_func():
            return "success"
        
        result = breaker.call(successful_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
    
    def test_open_state_after_failures(self):
        breaker = CircuitBreaker("test", failure_threshold=2, recovery_timeout=1)
        
        def failing_func():
            raise Exception("Failed")
        
        with pytest.raises(Exception):
            breaker.call(failing_func)
        assert breaker.failure_count == 1
        assert breaker.state == CircuitState.CLOSED
        
        with pytest.raises(Exception):
            breaker.call(failing_func)
        assert breaker.state == CircuitState.OPEN
    
    def test_half_open_after_timeout(self):
        breaker = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.5)
        
        def failing_func():
            raise Exception("Failed")
        
        with pytest.raises(Exception):
            breaker.call(failing_func)
        assert breaker.state == CircuitState.OPEN
        
        time.sleep(0.6)
        assert breaker.state == CircuitState.HALF_OPEN