import json
import logging
import redis
from datetime import datetime
from typing import Dict, Any, Callable
import threading
import time

logger = logging.getLogger(__name__)

class QueueWorker:
    def __init__(self, redis_url: str = "redis://localhost:6379", queue_name: str = "optimization_tasks"):
        self.redis_client = redis.from_url(redis_url)
        self.queue_name = queue_name
        self.running = False
        self.worker_thread = None
        self.handlers = {}
    
    def register_handler(self, task_type: str, handler: Callable):
        self.handlers[task_type] = handler
    
    def enqueue_task(self, task_type: str, data: Dict[str, Any]) -> str:
        task_id = f"{task_type}_{datetime.now().timestamp()}"
        task = {
            "id": task_id,
            "type": task_type,
            "data": data,
            "created_at": datetime.now().isoformat()
        }
        self.redis_client.lpush(self.queue_name, json.dumps(task))
        logger.info(f"Enqueued task {task_id} of type {task_type}")
        return task_id
    
    def start(self):
        self.running = True
        self.worker_thread = threading.Thread(target=self._work_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Queue worker started")
    
    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Queue worker stopped")
    
    def _work_loop(self):
        while self.running:
            try:
                task_data = self.redis_client.brpop(self.queue_name, timeout=1)
                if task_data:
                    _, task_json = task_data
                    task = json.loads(task_json)
                    self._process_task(task)
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(1)
    
    def _process_task(self, task: Dict[str, Any]):
        task_type = task.get("type")
        handler = self.handlers.get(task_type)
        
        if handler:
            try:
                logger.info(f"Processing task {task['id']}")
                result = handler(task["data"])
                logger.info(f"Task {task['id']} completed successfully")
                self._store_result(task["id"], result, "success")
            except Exception as e:
                logger.error(f"Task {task['id']} failed: {e}")
                self._store_result(task["id"], str(e), "failed")
        else:
            logger.warning(f"No handler for task type: {task_type}")
    
    def _store_result(self, task_id: str, result: Any, status: str):
        result_data = {
            "task_id": task_id,
            "status": status,
            "result": result,
            "completed_at": datetime.now().isoformat()
        }
        self.redis_client.set(f"task_result:{task_id}", json.dumps(result_data), ex=3600)