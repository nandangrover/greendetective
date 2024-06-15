import math

import multiprocess

bind = "0.0.0.0:8070"
pid = "/tmp/gunicorn.pid"

MAX_WORKERS = 2
MAX_THREADS = 12

# Round up for API
max_value = math.ceil(multiprocess.cpu_count() / 2) * 2 + 1
workers = max_value if max_value <= MAX_WORKERS else MAX_WORKERS
threads = max_value if max_value <= MAX_THREADS else MAX_THREADS
timeout = 1000
