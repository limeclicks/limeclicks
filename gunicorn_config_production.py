import multiprocessing
import os

# Server Socket
bind = "127.0.0.1:7650"
backlog = 2048

# Worker Processes - SYNC CONFIGURATION for better database connection management
workers = min(multiprocessing.cpu_count() * 2, 6)  # Reduced workers to control connections
worker_class = "sync"  # Changed from gevent to sync to prevent connection multiplication
# Note: sync workers handle one request at a time, preventing connection accumulation
keepalive = 2  # Reduced keepalive

# Worker management settings
worker_tmp_dir = "/dev/shm"  # Use RAM for worker heartbeat
max_requests = 500  # Restart workers more frequently to release resources
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
user = "ubuntu"
group = "ubuntu"
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