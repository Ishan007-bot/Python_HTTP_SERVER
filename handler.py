import socket
import os
import json
from datetime import datetime
from utils import (
    Logger, 
    RESOURCE_DIR, 
    UPLOAD_DIR, 
    MAX_REQUEST_SIZE, 
    KEEP_ALIVE_TIMEOUT,
    KEEP_ALIVE_MAX_REQUESTS
)

class ClientHandler:
    """
    Handles a single client connection.
    Responsible for parsing HTTP requests, enforcing security, and sending responses.
    Supports persistent connections (Keep-Alive) and both GET/POST methods.
    """
    def __init__(self, client_socket, client_address, server_host, server_port, thread_name):
        self.client_socket = client_socket
        self.client_address = client_address
        self.server_host = server_host
        self.server_port = server_port
        self.thread_name = thread_name
        self.is_persistent = False
        self.request_count = 0
        self.request = {}  # Stores parsed request data

    def handle_connection(self):
        """
        Manages the lifecycle of a single client connection, including Keep-Alive.
        Handles multiple requests per connection if allowed by the client.
        """
        self.client_socket.settimeout(KEEP_ALIVE_TIMEOUT)
        try:
            while True:
                self.request_count += 1

                # Receive and parse the HTTP request
                raw_request = self._receive_request()
                if not raw_request:
                    break
                if not self._parse_request(raw_request):
                    break

                # Enforce Keep-Alive request limit
                if self.request_count > KEEP_ALIVE_MAX_REQUESTS:
                    Logger.thread_log(self.thread_name, "Connection limit reached. Closing.")
                    self._send_error_response(400, "Bad Request", close_connection=True)
                    break

                # Security checks (host header, path traversal)
                if not self._validate_security():
                    break

                # Dispatch request based on method
                self._handle_request_type()

                # Close connection if not persistent
                if not self.is_persistent:
                    Logger.thread_log(self.thread_name, "Connection: close")
                    break

                Logger.thread_log(self.thread_name, f"Connection: keep-alive (Request count: {self.request_count})")

        except socket.timeout:
            Logger.thread_log(self.thread_name, "Connection timeout. Closing idle connection.")
        except ConnectionResetError:
            Logger.thread_log(self.thread_name, "Connection reset by client.")
        except Exception as e:
            Logger.thread_log(self.thread_name, f"Error during connection handling: {e}")
            self._send_error_response(500, "Internal Server Error", close_connection=True)
        finally:
            self.client_socket.close()

    # --- Request Receiving and Parsing ---

    def _receive_request(self):
        """
        Receives the full HTTP request up to MAX_REQUEST_SIZE.
        Returns the raw request string, or None if the connection is closed.
        """
        try:
            raw_request = self.client_socket.recv(MAX_REQUEST_SIZE).decode('utf-8')
            if not raw_request:
                return None
            return raw_request
        except socket.timeout:
            raise
        except Exception:
            return None

    def _parse_request(self, raw_request):
        """
        Parses the raw request string into method, path, version, headers, and body.
        Returns True if parsing is successful, False otherwise.
        """
        try:
            lines = raw_request.split('\r\n')
            if not lines:
                return False

            status_line_parts = lines[0].split()
            if len(status_line_parts) != 3:
                self._send_error_response(400, "Bad Request: Invalid Status Line")
                return False

            self.request['method'], self.request['path'], self.request['version'] = status_line_parts
            self.request['headers'] = {}
            self.request['body'] = ""

            # Parse headers
            header_end_index = lines.index("")
            for line in lines[1:header_end_index]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    self.request['headers'][key.strip().lower()] = value.strip()

            # Parse body (if any)
            self.request['body'] = '\r\n'.join(lines[header_end_index + 1:])

            Logger.thread_log(self.thread_name, f"Request: {self.request['method']} {self.request['path']} {self.request['version']}")

            # Determine connection persistence
            connection_header = self.request['headers'].get('connection', '').lower()
            if self.request['version'] == 'HTTP/1.1':
                self.is_persistent = (connection_header != 'close')
            elif self.request['version'] == 'HTTP/1.0':
                self.is_persistent = (connection_header == 'keep-alive')
            else:
                self.is_persistent = False

            return True

        except Exception:
            self._send_error_response(400, "Bad Request")
            return False

    # --- Security ---

    def _validate_security(self):
        """
        Performs Host header validation and path traversal protection.
        Returns True if the request passes security checks, False otherwise.
        """
        host_header = self.request['headers'].get('host')
        expected_host = f"{self.server_host}:{self.server_port}"

        # Host header must be present and valid
        if not host_header:
            Logger.thread_log(self.thread_name, "Security Violation: Missing Host header ❌")
            self._send_error_response(400, "Bad Request: Missing Host header", close_connection=True)
            return False

        if host_header != expected_host and host_header.split(':')[0] not in ('localhost', '127.0.0.1'):
            Logger.thread_log(self.thread_name, f"Security Violation: Host mismatch ({host_header} != {expected_host}) ❌")
            self._send_error_response(403, "Forbidden: Host header mismatch", close_connection=True)
            return False

        Logger.thread_log(self.thread_name, f"Host validation: {host_header} ✓")

        # Path traversal protection
        if '..' in self.request['path'] or '//' in self.request['path']:
            Logger.thread_log(self.thread_name, f"Security Violation: Path Traversal attempt ({self.request['path']}) ❌")
            self._send_error_response(403, "Forbidden: Path Traversal detected", close_connection=True)
            return False

        # Normalize and resolve the requested path
        if self.request['path'] == '/':
            relative_path = 'index.html'
        else:
            relative_path = os.path.normpath(self.request['path'].lstrip('/'))

        clean_path = os.path.join(RESOURCE_DIR, relative_path)

        # Ensure the resolved path is within the resource directory
        if not os.path.abspath(clean_path).startswith(os.path.abspath(RESOURCE_DIR)):
            Logger.thread_log(self.thread_name, f"Security Violation: Path outside resource directory ({clean_path}) ❌")
            self._send_error_response(403, "Forbidden: Path outside resource directory", close_connection=True)
            return False

        self.request['safe_path'] = clean_path
        return True

    # --- Request Dispatching ---

    def _handle_request_type(self):
        """
        Dispatches the request based on the HTTP method.
        Supports GET and POST. Sends 405 for unsupported methods.
        """
        method = self.request['method']

        if method == 'GET':
            self._handle_get_request()
        elif method == 'POST':
            self._handle_post_request()
        else:
            self._send_error_response(405, "Method Not Allowed", close_connection=True)

    def _handle_get_request(self):
        """
        Handles static file serving for GET requests.
        Supports HTML and binary file downloads.
        """
        file_path = self.request['safe_path']

        # Check if file exists and is not a directory
        if not os.path.exists(file_path) or os.path.isdir(file_path):
            self._send_error_response(404, "Not Found")
            return

        filename = os.path.basename(file_path)
        ext = filename.split('.')[-1].lower()

        # Determine content type and mode
        if ext == 'html':
            content_type = 'text/html; charset=utf-8'
            mode = 'r'
            is_binary_download = False
        elif ext in ('txt', 'png', 'jpg', 'jpeg'):
            content_type = 'application/octet-stream'
            mode = 'rb'
            is_binary_download = True
        else:
            self._send_error_response(415, "Unsupported Media Type")
            return

        try:
            file_size = os.path.getsize(file_path)

            # Build and send HTTP header
            header = self._build_header(
                status_code=200,
                status_text="OK",
                content_type=content_type,
                content_length=file_size,
                filename=filename if is_binary_download else None
            )
            self.client_socket.sendall(header.encode('utf-8'))

            # Send file content in chunks
            CHUNK_SIZE = 8192
            with open(file_path, mode) as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    if mode == 'r':
                        self.client_socket.sendall(chunk.encode('utf-8'))
                    else:
                        self.client_socket.sendall(chunk)

            Logger.thread_log(self.thread_name, f"Sending {'binary' if is_binary_download else 'text'} file: {filename} ({file_size} bytes)")

        except Exception as e:
            Logger.thread_log(self.thread_name, f"File reading or transfer error: {e}")
            self._send_error_response(500, "Internal Server Error")

    def _handle_post_request(self):
        """
        Handles POST requests with JSON data.
        Saves the JSON body to a uniquely named file in the uploads directory.
        """
        content_type = self.request['headers'].get('content-type', '').lower()
        body = self.request['body']

        # Only accept application/json
        if 'application/json' not in content_type:
            self._send_error_response(415, "Unsupported Media Type: Only application/json is accepted for POST")
            return

        try:
            json_data = json.loads(body)
        except json.JSONDecodeError:
            self._send_error_response(400, "Bad Request: Invalid JSON in body")
            return

        # Generate unique filename for the upload
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_id = os.urandom(4).hex()
        filename = f"upload_{timestamp}_{random_id}.json"
        file_path = os.path.join(UPLOAD_DIR, filename)

        try:
            # Save JSON data to file
            with open(file_path, 'w') as f:
                json.dump(json_data, f, indent=4)

            response_json = {
                "status": "success",
                "message": "File created successfully",
                "filepath": f"/uploads/{filename}"
            }
            response_body = json.dumps(response_json, indent=2).encode('utf-8')

            self._send_success_response(
                status_code=201,
                status_text="Created",
                content_type="application/json",
                body=response_body
            )
            Logger.thread_log(self.thread_name, f"Created file: {file_path} ({len(response_body)} bytes)")

        except Exception as e:
            Logger.thread_log(self.thread_name, f"POST file creation error: {e}")
            self._send_error_response(500, "Internal Server Error")

    # --- Response Helpers ---

    def _get_common_headers(self, connection_close=False):
        """
        Generates common HTTP headers for all responses.
        Handles connection persistence and keep-alive settings.
        """
        headers = {
            'Date': datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT"),
            'Server': 'Multi-threaded HTTP Server',
            'Connection': 'close' if connection_close or not self.is_persistent else 'keep-alive'
        }

        if not connection_close and self.is_persistent:
            headers['Keep-Alive'] = f'timeout={KEEP_ALIVE_TIMEOUT}, max={KEEP_ALIVE_MAX_REQUESTS}'

        return headers

    def _build_header(self, status_code, status_text, content_type, content_length, filename=None):
        """
        Constructs the full HTTP header string for a response.
        Optionally includes Content-Disposition for downloads.
        """
        connection_close = not self.is_persistent and (status_code not in (200, 201))
        common_headers = self._get_common_headers(connection_close=connection_close)

        response_lines = [
            f"HTTP/1.1 {status_code} {status_text}",
            f"Content-Type: {content_type}",
            f"Content-Length: {content_length}"
        ]

        if filename:
            response_lines.append(f'Content-Disposition: attachment; filename="{filename}"')

        for k, v in common_headers.items():
            if k != 'Keep-Alive':
                response_lines.append(f"{k}: {v}")

        if self.is_persistent and not connection_close:
            response_lines.append(f'Keep-Alive: {common_headers["Keep-Alive"]}')

        return "\r\n".join(response_lines) + "\r\n\r\n"

    def _send_error_response(self, status_code, status_text, close_connection=False):
        """
        Constructs and sends an error response with the given status code and message.
        Optionally closes the connection.
        """
        response_body = f"Error {status_code}: {status_text}\n".encode('utf-8')

        header = self._build_header(
            status_code=status_code,
            status_text=status_text,
            content_type="text/plain",
            content_length=len(response_body),
            filename=None
        )

        try:
            self.client_socket.sendall(header.encode('utf-8') + response_body)
            Logger.thread_log(self.thread_name, f"Response: {status_code} {status_text}")
            if close_connection:
                self.is_persistent = False
        except Exception:
            pass

    def _send_success_response(self, status_code, status_text, content_type, body):
        """
        Constructs and sends a successful response (used for 201 POST).
        """
        header = self._build_header(
            status_code=status_code,
            status_text=status_text,
            content_type=content_type,
            content_length=len(body)
        )

        try:
            self.client_socket.sendall(header.encode('utf-8'))
            self.client_socket.sendall(body)
            Logger.thread_log(self.thread_name, f"Response: {status_code} {status_text} ({len(body)} bytes)")
        except Exception:
            pass