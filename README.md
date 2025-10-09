# Multi-Threaded HTTP Server

## Overview
This project implements a multi-threaded HTTP server in Python from scratch using low-level socket programming. The server is designed to handle multiple concurrent clients efficiently using a thread pool.

It serves as a comprehensive demonstration of network programming, concurrency, and essential HTTP protocol handling.

---

## Core Capabilities

- **Static File Serving:** Supports serving HTML and binary files.
- **Concurrency:** Utilizes a configurable thread pool for performance.
- **HTTP/1.1 Protocol:** Implements connection persistence (Keep-Alive) and proper header management.
- **Security:** Enforces path traversal protection and host header validation.
- **File Management:** Processes JSON data via POST requests and saves it to disk.

---

## Directory Structure

```
http-server-project/
├── server.py                 # Main entry point. Initializes server socket and ThreadPool.
├── threadpool.py             # Manages concurrency (ThreadPool and WorkerThread classes).
├── handler.py                # Core HTTP request parsing, security checks, and response generation (ClientHandler).
├── utils.py                  # Configuration constants and the centralized Logger utility.
├── resources/                # Root directory for all static content.
│   ├── index.html            # Default HTML page.
│   ├── about.html
│   ├── contact.html
│   ├── sample.txt            # Text file for binary transfer test.
│   ├── logo.jpg              # Image file for binary transfer test.
│   ├── photo.png             # Large image file for large binary transfer test.
│   └── uploads/              # Directory where files from POST requests are stored.
└── README.md                 # This documentation file.
```

---

## Requirements

- Python 3.6+ (Tested on Python 3.10)
- No external third-party libraries are required; only standard Python modules (`socket`, `threading`, `queue`, `os`, `sys`, `json`, `datetime`).

---

## How to Run

Open a terminal (Command Prompt, PowerShell, or Bash) in the root of the project directory.

Execute the server script using the desired arguments:

```bash
python server.py [PORT] [HOST] [THREAD_POOL_SIZE]
```

### Configuration Defaults

| Argument         | Default Value | Description                                |
|------------------|--------------|--------------------------------------------|
| Port             | 8080         | The port the server binds to.              |
| Host             | 127.0.0.1    | The network interface the server listens on.|
| Thread Pool Size | 10           | Maximum number of concurrent worker threads.|

#### Example

To run the server on port 8000, listening on all interfaces (0.0.0.0) with 20 threads:

```bash
python server.py 8000 0.0.0.0 20
```

---

## Features

### 1. GET Requests (File Serving)

| Feature             | Description                                                                 | Status Code         |
|---------------------|-----------------------------------------------------------------------------|---------------------|
| HTML                | Serves HTML files with Content-Type: text/html; charset=utf-8.              | 200 OK              |
| Binary Download     | .png, .jpg, .jpeg, .txt are served as binary streams with Content-Type: application/octet-stream and Content-Disposition: attachment to force download. | 200 OK              |
| Default Root        | The root path (/) automatically serves resources/index.html.                | 200 OK              |
| Unsupported Media   | Blocks requests for file extensions other than those listed above.           | 415 Unsupported Media Type |
| Not Found           | Resource does not exist in the resources directory.                          | 404 Not Found        |

### 2. POST Requests (JSON Processing)

- **Content Requirement:** Only accepts requests with Content-Type: application/json.
- **File Creation:** Parses the JSON body and writes it to a file with a unique, timestamped name (e.g., `upload_20251009_184548_a2f7d1.json`) in the `resources/uploads/` directory.
- **Invalid JSON →** 400 Bad Request.
- **Non-JSON Content →** 415 Unsupported Media Type.
- **Success Response →** 201 Created with the path to the newly created file in the JSON response body.

### 3. Concurrency and Connection Management

- **Thread Pool:** Uses a fixed-size, configurable thread pool to handle concurrent client connections.
- **Saturation Handling:** New connections are queued if the thread pool is busy. If the queue is full, the connection is rejected with a 503 Service Unavailable response.
- **Keep-Alive:** Supports persistent connections (HTTP/1.1 default) with a 30-second idle timeout and a limit of 100 requests per connection.

### 4. Security

- **Path Traversal Protection:** Strictly validates the request path, blocking attempts to access files outside the resources directory (e.g., paths containing `..` or leading `/././`). Returns 403 Forbidden.
- **Host Header Validation:** Ensures the Host header matches the server's configured address (`host:port`) or local aliases (`localhost:port`, `127.0.0.1:port`). Mismatch or missing header results in 400 Bad Request or 403 Forbidden.

---

## Testing

### Browser Testing (GET Requests)

Open your browser and test the following default URLs:

| Test Scenario      | URL (Default Port)                  |
|--------------------|-------------------------------------|
| Success (HTML)     | http://127.0.0.1:8080/              |
| Success (Download) | http://127.0.0.1:8080/logo.jpg      |
| Not Found          | http://127.0.0.1:8080/missing.file  |

### Command Line Testing (POST and Security)

**Linux/macOS (using curl):**
```bash
# Test successful JSON POST and 201 Created response
curl -X POST http://127.0.0.1:8080/upload \
     -H "Content-Type: application/json" \
     -d '{"name":"Ishan","score":100}'

# Test Path Traversal Protection (Expected: 403 Forbidden)
curl -i http://127.0.0.1:8080/../server.py
```

**Windows PowerShell (using Invoke-RestMethod):**
```powershell
# Test successful JSON POST and 201 Created response
Invoke-RestMethod -Uri http://127.0.0.1:8080/upload -Method POST -Body '{"name":"Ishan","score":100}' -ContentType "application/json"
```

---

## Logging

The server provides comprehensive, time-stamped logging to the console:

| Log Type         | Purpose                                                                 |
|------------------|-------------------------------------------------------------------------|
| SERVER           | Startup, shutdown, and configuration details.                           |
| THREAD (WORKER)  | Request reception, processing status, and response details (including byte count and connection status). |
| WARNING/SECURITY | Thread pool saturation, host header mismatch, and path traversal attempts. |

**Example Log Output:**
```
[2025-03-15 10:30:15] [Thread-1] Request: GET /index.html HTTP/1.1
[2025-03-15 10:30:15] [Thread-1] Host validation: 127.0.0.1:8080 ✓
[2025-03-15 10:30:15] [Thread-1] Sending text file: index.html (1024 bytes)
[2025-03-15 10:30:15] [Thread-1] Response: 200 OK (1024 bytes transferred)
[2025-03-15 10:30:15] [Thread-1] Connection: keep-alive
```

---

## Known Limitations

- Only supports GET and POST HTTP methods.
- Does not support advanced HTTP/1.1 features like Chunked Transfer Encoding.
- No HTTPS/SSL support is implemented.
- The maximum size for a single incoming request body is limited by `MAX_REQUEST_SIZE` (8192 bytes).

---

## Author

Ishan Ganguly

Roll No - 24BCS10330