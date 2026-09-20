"""Gunicorn configuration.

A file rather than a wall of command line flags, so the reasoning can live next
to the numbers.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Sync workers: this is a database-bound app with no long-polling. Async
# workers would add complexity and buy nothing until there is real I/O waiting.
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))
worker_class = "sync"
threads = int(os.environ.get("GUNICORN_THREADS", "1"))

# Shorter than the load balancer's own timeout, so a stuck worker is recycled
# here rather than surfacing to the client as a gateway error.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))

# Must exceed the load balancer's idle timeout, or the balancer will reuse a
# connection gunicorn has already closed and the client sees a random 502.
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "65"))

# Recycling workers papers over slow memory leaks in dependencies. The jitter
# stops every worker restarting at the same moment.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "100"))

accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms "%(a)s"'

# The container runtime captures stdout; writing to a file inside a container
# is how logs get lost.
capture_output = True
