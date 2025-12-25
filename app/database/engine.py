import threading
import time
from queue import Queue
from typing import Literal
from sqlmodel import create_engine, Session, SQLModel

from .models import *
from ..logger import db_logger

DATABASE_URL = "sqlite:///./db.db"
# 启用WAL模式，允许读写并行，提升并发性能
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30.0,  # 锁等待超时30秒
    },
    pool_size=20,  # 连接池大小
    max_overflow=40,  # 额外连接数
    pool_pre_ping=True,  # 检查连接有效性
    echo=False,
)

# 在首次连接时启用WAL模式
with engine.connect() as conn:
    conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    conn.exec_driver_sql("PRAGMA synchronous=NORMAL")  # 提升写入性能
    conn.exec_driver_sql("PRAGMA busy_timeout=30000")  # 30秒忙等待
    conn.exec_driver_sql("PRAGMA wal_autocheckpoint=1000")  # 每1000页自动checkpoint
    result = conn.exec_driver_sql("PRAGMA journal_mode").fetchone()


def get_session():
    with Session(engine) as session:
        yield session


class DatabaseWriteQueue:
    """数据库写操作队列管理器"""

    def __init__(self, batch_interval: float = 0.5, batch_size: int = 100):
        """
        初始化写队列

        Args:
            batch_interval: 批量写入间隔（秒）
            batch_size: 每批最多处理的操作数，超过此数量会立即触发批量写入
        """
        self.queue = Queue()
        self.batch_interval = batch_interval
        self.batch_size = batch_size
        self.running = False
        self.worker_thread = None
        self.flush_event = threading.Event()  # 用于立即触发批量写入

    def start(self):
        """启动后台写入线程"""
        if self.running:
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        db_logger.info(
            f"数据库写队列已启动 | 批量间隔: {self.batch_interval}秒 | 批量大小: {self.batch_size}"
        )

    def stop(self):
        """停止后台写入线程"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        # 处理剩余的队列项
        self._flush()
        db_logger.info("数据库写队列已停止")

    def add_operation(self, type: Literal["add", "merge"], model_instance: SQLModel):
        """
        添加合并操作到队列

        Args:
            model_instance: SQLModel 实例
        """
        self.queue.put({"operation": type, "model": model_instance})

        # 如果队列大小超过批量大小，立即触发批量写入
        if self.queue.qsize() >= self.batch_size:
            self.flush_event.set()

    def _process_queue(self):
        """后台线程处理队列"""
        while self.running:
            # 等待定时器超时或立即触发事件
            triggered = self.flush_event.wait(timeout=self.batch_interval)

            if triggered:
                # 被立即触发（队列超过批量大小）
                self.flush_event.clear()

            # 执行批量写入（如果队列为空会自动跳过）
            self._flush()

    def _flush(self):
        """批量处理队列中的写操作"""
        if self.queue.empty():
            return

        operations = []
        count = 0

        # 获取一批操作
        while not self.queue.empty() and count < self.batch_size:
            try:
                operations.append(self.queue.get_nowait())
                count += 1
            except:
                break

        if not operations:
            return

        # 批量写入数据库
        start_time = time.time()
        try:
            with Session(engine) as session:
                for op in operations:
                    if op["operation"] == "merge":
                        model = op["model"]
                        session.merge(model)
                session.commit()

            elapsed = (time.time() - start_time) * 1000
            db_logger.info(
                f"批量写入成功 | 操作数: {len(operations)} " f"| 耗时: {elapsed:.2f}ms"
            )
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            db_logger.error(
                f"批量写入失败 | 操作数: {len(operations)} "
                f"| 耗时: {elapsed:.2f}ms | 错误: {str(e)}"
            )
            # 不再重新入队，避免无限循环
            db_logger.warning(f"已丢弃 {len(operations)} 条失败的操作")


# 全局写队列实例
write_queue = DatabaseWriteQueue(batch_interval=0.5, batch_size=30)
