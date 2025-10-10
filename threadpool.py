import threading
import socket
from queue import Queue
from utils import Logger, MAX_LISTEN_QUEUE
from handler import ClientHandler
import traceback
import queue  # For catching queue.Empty

class WorkerThread(threading.Thread):
    """
    WorkerThread is responsible for processing client connections.
    Each worker fetches a client socket from the shared task queue and handles the HTTP request.
    """
    def __init__(self, thread_id, task_queue, server_host, server_port):
        super().__init__()
        self.thread_id = thread_id
        self.thread_name = f"Thread-{thread_id}"
        self.task_queue = task_queue
        self.server_host = server_host
        self.server_port = server_port
        self.running = True

    def run(self):
        """
        Main loop for the worker thread.
        Waits for tasks (client connections) and processes them using ClientHandler.
        """
        Logger.thread_log(self.thread_name, "Started.")
        while self.running:
            try:
                # Wait for a client connection from the queue (with timeout)
                client_socket, client_address = self.task_queue.get(timeout=1)
                Logger.thread_log(self.thread_name, f"Serving connection from {client_address[0]}:{client_address[1]}")

                # Handle the client connection using the handler
                handler = ClientHandler(client_socket, client_address, self.server_host, self.server_port, self.thread_name)
                handler.handle_connection()

                self.task_queue.task_done()
            except queue.Empty:
                # No task available, continue waiting
                continue
            except Exception as e:
                # Log any unexpected errors that occur during request handling
                if self.running:
                    Logger.thread_log(self.thread_name, f"Unhandled error: {e}")
                    Logger.thread_log(self.thread_name, traceback.format_exc())

        Logger.thread_log(self.thread_name, "Stopped.")

    def stop(self):
        """
        Signals the worker thread to stop after finishing the current task.
        """
        self.running = False

class ThreadPool:
    """
    ThreadPool manages a pool of worker threads and a shared task queue.
    It distributes incoming client connections among available workers.
    """
    def __init__(self, max_threads, server_host, server_port):
        self.max_threads = max_threads
        self.task_queue = Queue()
        self.workers = []
        self.server_host = server_host
        self.server_port = server_port

    def start(self):
        """
        Starts all worker threads in the pool.
        """
        for i in range(1, self.max_threads + 1):
            worker = WorkerThread(i, self.task_queue, self.server_host, self.server_port)
            worker.daemon = True  # Daemon threads exit when the main program exits
            worker.start()
            self.workers.append(worker)

    def add_task(self, task):
        """
        Adds a client socket task to the queue.
        If the queue is full, the connection is rejected with a 503 response.

        Args:
            task (tuple): (client_socket, client_address)
        """
        if self.task_queue.qsize() >= MAX_LISTEN_QUEUE:
            self.handle_saturation(task[0])
        else:
            if self.task_queue.qsize() > 0:
                Logger.warning(f"Thread pool saturated, queuing connection. Queue size: {self.task_queue.qsize()}")
            self.task_queue.put(task)

    def handle_saturation(self, client_socket):
        """
        Sends a 503 Service Unavailable response when the queue is full and closes the connection.

        Args:
            client_socket (socket.socket): The client socket to reject.
        """
        retry_time = 5
        response = (
            "HTTP/1.1 503 Service Unavailable\r\n"
            "Server: Multi-threaded HTTP Server\r\n"
            f"Retry-After: {retry_time}\r\n"
            "Connection: close\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 0\r\n\r\n"
        )
        try:
            client_socket.sendall(response.encode('utf-8'))
        except Exception:
            pass
        finally:
            client_socket.close()
            Logger.warning("Connection rejected with 503 due to thread pool saturation.")

    def stop(self):
        """
        Stops all worker threads gracefully.
        """
        for worker in self.workers:
            worker.stop()
        for worker in self.workers:
            worker.join()