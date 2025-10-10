import os
from datetime import datetime

# =========================
# Server Configuration Constants
# =========================

DEFAULT_HOST = '127.0.0.1'           # Default IP address to bind the server
DEFAULT_PORT = 8080                  # Default port to listen on
DEFAULT_THREAD_POOL_SIZE = 10        # Default number of worker threads in the thread pool
MAX_REQUEST_SIZE = 8192              # Maximum size (in bytes) for a single HTTP request
MAX_LISTEN_QUEUE = 50                # Maximum number of queued connections (backlog)
RESOURCE_DIR = 'resources'           # Directory for static files to be served
UPLOAD_DIR = os.path.join(RESOURCE_DIR, 'uploads')  # Directory for uploaded files via POST
KEEP_ALIVE_TIMEOUT = 30              # Timeout (in seconds) for persistent connections (Keep-Alive)
KEEP_ALIVE_MAX_REQUESTS = 100        # Maximum number of requests per persistent connection

# =========================
# Logger Utility Class
# =========================

class Logger:
    """
    Utility class for centralized, time-stamped logging.
    Provides static methods for different log types (server, thread, warning).
    """

    @staticmethod
    def log(message, level="INFO", thread_name=None):
        """
        Print a log message with a timestamp, log level, and optional thread name.

        Args:
            message (str): The message to log.
            level (str): The log level (e.g., INFO, SERVER, THREAD, WARNING).
            thread_name (str, optional): The name of the thread (for thread logs).
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        thread_info = f"[{thread_name}] " if thread_name else ""
        print(f"[{timestamp}] {thread_info}{level.upper()}: {message}")

    @staticmethod
    def server_log(message):
        """
        Log a server-level message (startup, shutdown, configuration).
        Args:
            message (str): The message to log.
        """
        Logger.log(message, level="SERVER")

    @staticmethod
    def thread_log(thread_name, message):
        """
        Log a message from a worker thread.
        Args:
            thread_name (str): The name of the thread.
            message (str): The message to log.
        """
        Logger.log(message, level="THREAD", thread_name=thread_name)

    @staticmethod
    def warning(message):
        """
        Log a warning or security-related message.
        Args:
            message (str): The warning message to log.
        """
        Logger.log(message, level="WARNING")