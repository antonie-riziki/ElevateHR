import multiprocessing

# Gunicorn configuration for render.com
bind = "0.0.0.0:10000"  # Default port for render.com
workers = 2  # Reduced number of workers to save memory
worker_class = "sync"  # Use sync workers instead of async
threads = 1  # Single thread per worker
worker_connections = 1000
timeout = 30  # Increased timeout
keepalive = 2

# Worker settings
max_requests = 1000  # Restart workers after handling 1000 requests
max_requests_jitter = 50  # Add randomness to max_requests
worker_tmp_dir = "/tmp"  # Temporary directory for worker heartbeat

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "warning"  # Reduce logging verbosity

# Process naming
proc_name = "elevate_hr_bot"

# Limit memory usage
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190 