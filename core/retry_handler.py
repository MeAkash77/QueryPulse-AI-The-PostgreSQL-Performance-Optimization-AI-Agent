import time
import logging
from functools import wraps
from typing import Callable, Any, List, Union

logger = logging.getLogger(__name__)

class RetryHandler:
    def __init__(self, max_retries: int = 3, delay: float = 1.0, 
                 backoff: float = 2.0, exceptions: List[Exception] = None):
        self.max_retries = max_retries
        self.delay = delay
        self.backoff = backoff
        self.exceptions = exceptions or [Exception]
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        last_exception = None
        current_delay = self.delay
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except tuple(self.exceptions) as e:
                last_exception = e
                if attempt == self.max_retries:
                    logger.error(f"Failed after {self.max_retries} retries: {e}")
                    raise
                
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {current_delay}s")
                time.sleep(current_delay)
                current_delay *= self.backoff
        
        raise last_exception

def retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = RetryHandler(max_retries, delay, backoff)
            return handler.execute(func, *args, **kwargs)
        return wrapper
    return decorator