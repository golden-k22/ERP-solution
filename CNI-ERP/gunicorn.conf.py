"""Gunicorn *development* config file"""

import multiprocessing

# The socket to bind
bind = "0.0.0.0:8001"
# The number of worker processes for handling requests
workers = multiprocessing.cpu_count() * 2 + 1
timeout = 30
# Write access and error info to 
accesslog = "./access.log"
errorlog = "./error.log"
# The granularity of Error log outputs
loglevel = "debug"
