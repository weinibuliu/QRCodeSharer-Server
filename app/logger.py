"""日志配置模块"""

import logging
import logging.handlers
from queue import Queue
from pathlib import Path


# 确保debug目录存在
DEBUG_DIR = Path(__file__).parent.parent / "debug"
DEBUG_DIR.mkdir(exist_ok=True)

# 日志文件路径
REQUEST_LOG_FILE = DEBUG_DIR / "request.log"
DB_LOG_FILE = DEBUG_DIR / "db.log"

# 保留天数
RETENTION_DAYS = 14


def setup_queue_logger(name: str, log_file: Path, level=logging.INFO):
    """
    使用 QueueHandler + QueueListener 实现高性能并发日志记录

    优点：
    - 日志写入不阻塞业务逻辑（异步队列）
    - 避免多线程锁竞争
    - 适合高并发场景

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径
        level: 日志级别

    Returns:
        配置好的 Logger 实例和 QueueListener 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加处理器
    if logger.hasHandlers():
        return logger, None

    # 创建日志队列（线程安全的FIFO队列）
    log_queue = Queue(maxsize=1000)

    # 创建QueueHandler：将日志放入队列（非常快，不阻塞）
    queue_handler = logging.handlers.QueueHandler(log_queue)
    logger.addHandler(queue_handler)

    # 创建实际的文件处理器（在单独的线程中执行）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        interval=1,
        backupCount=RETENTION_DAYS,
        encoding="utf-8",
    )

    # 设置日期轮转的文件名格式
    def namer(name):
        base_name = str(log_file)
        date_str = name.split(".")[-1]
        return f"{base_name}.{date_str}"

    file_handler.namer = namer

    # 设置日志格式
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)

    # 创建QueueListener：在独立线程中消费队列和写入文件
    listener = logging.handlers.QueueListener(
        log_queue, file_handler, respect_handler_level=True
    )

    return logger, listener


# 创建请求日志记录器
request_logger, request_listener = setup_queue_logger("request", REQUEST_LOG_FILE)

# 创建数据库日志记录器
db_logger, db_listener = setup_queue_logger("database", DB_LOG_FILE)

# 启动监听器
if request_listener:
    request_listener.start()
if db_listener:
    db_listener.start()


def stop_logger_listeners():
    """
    停止日志监听器（应用关闭时调用）
    """
    if request_listener:
        request_listener.stop()
    if db_listener:
        db_listener.stop()
