import os
from datetime import datetime

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8080
DEFAULT_THREAD_POOL_SIZE = 10
MAX_REQUEST_SIZE = 8192
MAX_LISTEN_QUEUE = 50
RESOURCE_DIR = 'resources'
UPLOAD_DIR = os.path.join(RESOURCE_DIR, 'uploads')
KEEP_ALIVE_TIMEOUT = 30  
KEEP_ALIVE_MAX_REQUESTS = 100

class Logger:
    """Utility class for centralized, time-stamped logging."""
    @staticmethod
    def log(message, level="INFO", thread_name=None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        thread_info = f"[{thread_name}] " if thread_name else ""
        print(f"[{timestamp}] {thread_info}{level.upper()}: {message}")

    @staticmethod
    def server_log(message):
        Logger.log(message, level="SERVER")

    @staticmethod
    def thread_log(thread_name, message):
        Logger.log(message, level="THREAD", thread_name=thread_name)

    @staticmethod
    def warning(message):
        Logger.log(message, level="WARNING")