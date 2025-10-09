import threading
import socket
from queue import Queue
from utils import Logger, MAX_LISTEN_QUEUE 
from handler import ClientHandler          
import traceback
import queue  # <-- Add this import

class WorkerThread(threading.Thread):
    def __init__(self, thread_id, task_queue, server_host, server_port):
        super().__init__()
        self.thread_id = thread_id
        self.thread_name = f"Thread-{thread_id}"
        self.task_queue = task_queue
        self.server_host = server_host
        self.server_port = server_port
        self.running = True

    def run(self):
        Logger.thread_log(self.thread_name, "Started.")
        while self.running:
            try:
                client_socket, client_address = self.task_queue.get(timeout=1)
                Logger.thread_log(self.thread_name, f"Serving connection from {client_address[0]}:{client_address[1]}")

                handler = ClientHandler(client_socket, client_address, self.server_host, self.server_port, self.thread_name)
                handler.handle_connection()

                self.task_queue.task_done()
            except queue.Empty:
                continue  # No task, just loop again
            except Exception as e:
                if self.running:
                    Logger.thread_log(self.thread_name, f"Unhandled error: {e}")
                    Logger.thread_log(self.thread_name, traceback.format_exc())

        Logger.thread_log(self.thread_name, "Stopped.")

    def stop(self):
        self.running = False

class ThreadPool:
    def __init__(self, max_threads, server_host, server_port):
        self.max_threads = max_threads
        self.task_queue = Queue() 
        self.workers = []
        self.server_host = server_host
        self.server_port = server_port

    def start(self):
        for i in range(1, self.max_threads + 1):
            worker = WorkerThread(i, self.task_queue, self.server_host, self.server_port)
            worker.daemon = True 
            worker.start()
            self.workers.append(worker)

    def add_task(self, task):
        """Adds a client socket task to the queue."""
        if self.task_queue.qsize() >= MAX_LISTEN_QUEUE:
            self.handle_saturation(task[0])
        else:
            if self.task_queue.qsize() > 0:
                Logger.warning(f"Thread pool saturated, queuing connection. Queue size: {self.task_queue.qsize()}")
            self.task_queue.put(task)

    def handle_saturation(self, client_socket):
        """Sends a 503 Service Unavailable response when the queue is full."""
        retry_time = 5
        response = f"HTTP/1.1 503 Service Unavailable\r\n" \
                   f"Server: Multi-threaded HTTP Server\r\n" \
                   f"Retry-After: {retry_time}\r\n" \
                   f"Connection: close\r\n" \
                   f"Content-Type: text/plain\r\n" \
                   f"Content-Length: 0\r\n\r\n"
        
        try:
            client_socket.sendall(response.encode('utf-8'))
        except Exception:
            pass
        finally:
            client_socket.close()
            Logger.warning("Connection rejected with 503 due to thread pool saturation.")

    def stop(self):
        """Stops all worker threads."""
        for worker in self.workers:
            worker.stop()
        for worker in self.workers:
            worker.join()