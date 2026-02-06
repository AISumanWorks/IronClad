from datetime import datetime
from collections import deque

class SystemLogger:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemLogger, cls).__new__(cls)
            cls._instance.logs = deque(maxlen=50) # Keep last 50 logs in memory
        return cls._instance

    def log(self, message: str, category: str = "INFO"):
        """
        Logs a message with timestamp and category.
        Categories: INFO, SCAN, TRADE, ERROR, VETO
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "time": timestamp,
            "message": message,
            "category": category
        }
        print(f"[{timestamp}] [{category}] {message}") # Ensure it still prints to console
        self.logs.appendleft(entry) # Newest first

    def get_logs(self):
        return list(self.logs)

# Global Instance
logger = SystemLogger()
