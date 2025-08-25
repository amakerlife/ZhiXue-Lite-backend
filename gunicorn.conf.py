# Gunicorn 配置文件
import os
import multiprocessing

# 服务器套接字
bind = "0.0.0.0:5000"
backlog = 2048

# 进程配置
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100

# 日志配置
loglevel = "info"
accesslog = "/app/logs/gunicorn-access.log"
errorlog = "/app/logs/gunicorn-error.log"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程名称
proc_name = "zhixuelite"

# 安全配置
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# 优雅关闭
graceful_timeout = 30

# 预加载应用
preload_app = True

# 用户和组
user = None
group = None

# SSL（如果需要）
# keyfile = None
# certfile = None