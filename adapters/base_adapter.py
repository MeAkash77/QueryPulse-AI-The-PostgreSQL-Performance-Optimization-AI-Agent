from abc import ABC, abstractmethod
from typing import Dict, Any, List

class DatabaseAdapter(ABC):
    @abstractmethod
    def connect(self, config: Dict) -> Any:
        pass
    
    @abstractmethod
    def execute_query(self, query: str) -> List[Dict]:
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict:
        pass
    
    @abstractmethod
    def get_performance_metrics(self) -> Dict:
        pass
    
    @abstractmethod
    def suggest_indexes(self) -> List[Dict]:
        pass
