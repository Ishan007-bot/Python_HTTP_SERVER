import socket
import sys
import os

from utils import (
    Logger,
    RESOURCE_DIR,
    UPLOAD_DIR,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_THREAD_POOL_SIZE,
    MAX_LISTEN_QUEUE
)
from threadpool import ThreadPool

class HTTPServer:
    """
    Main HTTP server class.
    Handles socket setup, thread pool management, and incoming client connections.
    """
    def __init__(self, host, port, max_threads):
        self.host = host
        self.port = port
        self.max_threads = max_threads
        self.server_socket = None
        self.thread_pool = None
        self._setup_directories()

    def _setup_directories(self):
        """
        Ensures the resource and upload directories exist.
        Creates them if they do not exist.
        """
        os.makedirs(RESOURCE_DIR, exist_ok=True)
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    def start(self):
        """
        Binds the server socket, starts the thread pool, and accepts incoming connections.
        Each connection is handed off to the thread pool for processing.
        """
        try:
            # Create and configure the server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(MAX_LISTEN_QUEUE)

            # Initialize and start the thread pool
            self.thread_pool = ThreadPool(self.max_threads, self.host, self.port)
            self.thread_pool.start()

            Logger.server_log(f"HTTP Server started on http://{self.host}:{self.port}")
            Logger.server_log(f"Thread pool size: {self.max_threads}")
            Logger.server_log(f"Serving files from '{RESOURCE_DIR}' directory")
            Logger.server_log("Press Ctrl+C to stop the server")

            # Main loop: accept and delegate connections
            while True:
                client_socket, client_address = self.server_socket.accept()
                Logger.log(f"Connection from {client_address[0]}:{client_address[1]}")
                self.thread_pool.add_task((client_socket, client_address))

        except KeyboardInterrupt:
            # Graceful shutdown on Ctrl+C
            Logger.server_log("Server shutting down...")
        except Exception as e:
            # Log any unexpected server errors
            Logger.log(f"Server error: {e}", level="FATAL")
        finally:
            # Cleanup: stop thread pool and close socket
            if self.thread_pool:
                self.thread_pool.stop()
            if self.server_socket:
                self.server_socket.close()
            Logger.server_log("Server stopped.")

def parse_arguments():
    """
    Parses command line arguments for host, port, and thread pool size.
    Returns default values if not provided or invalid.
    """
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else DEFAULT_PORT
    host = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_HOST
    max_threads = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else DEFAULT_THREAD_POOL_SIZE

    # Clamp thread pool size between 1 and 100
    max_threads = max(1, min(max_threads, 100))

    return host, port, max_threads

if __name__ == '__main__':
    # Parse arguments and start the server
    host, port, max_threads = parse_arguments()
    server = HTTPServer(host, port, max_threads)
    server.start()