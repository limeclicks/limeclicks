import multiprocessing
import os

# Server Socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker Processes - GEVENT CONFIGURATION for production
workers = min(multiprocessing.cpu_count() * 2 + 1, 9)  # Cap at 9 workers for better resource management
worker_class = "gevent"  # Using gevent workers for better concurrency
worker_connections = 1000  # Max simultaneous clients per worker
keepalive = 5

# Gevent specific settings
worker_tmp_dir = "/dev/shm"  # Use RAM for worker heartbeat
max_requests = 1000  # Restart workers after this many requests to prevent memory leaks
max_requests_jitter = 50  # Randomize worker restart

# Timeouts
timeout = 300  # 5 minutes for long-running requests
graceful_timeout = 30

# Logging for production
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process Naming
proc_name = "limeclicks_gunicorn"

# Server Mechanics
daemon = False
pidfile = "/var/run/gunicorn/limeclicks.pid"
user = "www-data"
group = "www-data"
tmp_upload_dir = None

# Pre-loading application for better performance
preload_app = True

# Worker lifecycle hooks
def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def on_starting(server):
    server.log.info("Starting Gunicorn server with gevent workers")

def on_reload(server):
    server.log.info("Reloading Gunicorn server")

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)
    
    # Re-initialize database connections in each worker
    from django.db import connections
    connections.close_all()