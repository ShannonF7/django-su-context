import signal

def post_fork(server, worker):
    signal.signal(signal.SIGWINCH, signal.SIG_IGN)

bind = "0.0.0.0:8001"
backlog = 4096  # 增大连接队列长度
workers = 4  # 根据 CPU 核心数调整（4 核 CPU 时设置为 4）
worker_class = "gevent"  # 切换为异步 worker
threads = 100  # 每个 worker 的并发连接数
timeout = 30  # 缩短超时时间
keepalive = 60  # 增加 keepalive 时间
errorlog = "/home/lab420pro/tsn/feedback_project/gunicorn_error.log"
accesslog = "/home/lab420pro/tsn/feedback_project/gunicorn_access.log"
loglevel = "info"
