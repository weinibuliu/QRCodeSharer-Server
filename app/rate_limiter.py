import time
from collections import defaultdict
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimiter:
    """IP 黑名单和速率限制器"""

    def __init__(
        self,
        max_failed_attempts: int = 5,
        block_duration: int = 300,
        max_blocked_ips: int = 1000,
    ):
        """
        Args:
            max_failed_attempts: 禁用前的最大失败次数（默认5次）
            block_duration: 禁用时长（秒，默认300秒=5分钟）
            max_blocked_ips: 最大黑名单大小，防止内存溢出（默认1000）
        """
        self.max_failed_attempts = max_failed_attempts
        self.block_duration = block_duration
        self.max_blocked_ips = max_blocked_ips
        self.last_cleanup = time.time()
        self.cleanup_interval = 60  # 每60秒清理一次

        # 存储 IP 的失败次数: {ip: count}
        self.failed_attempts = defaultdict(int)

        # 存储 IP 的最后失败时间: {ip: timestamp}
        self.last_failed_time = {}

        # 存储被禁用的 IP: {ip: unblock_time}
        self.blocked_ips = {}

    def cleanup_expired(self):
        """清理过期的黑名单记录"""
        current_time = time.time()

        # 检查是否需要清理（降低清理频率）
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        self.last_cleanup = current_time

        # 删除过期的黑名单
        expired_ips = [
            ip
            for ip, unblock_time in self.blocked_ips.items()
            if unblock_time <= current_time
        ]
        for ip in expired_ips:
            del self.blocked_ips[ip]
            self.failed_attempts[ip] = 0
            if ip in self.last_failed_time:
                del self.last_failed_time[ip]

        # 如果黑名单超过限制，删除最早的记录
        if len(self.blocked_ips) > self.max_blocked_ips:
            # 删除剩余时间最长的 IP（即最新封禁的）
            oldest_ips = sorted(self.blocked_ips.items(), key=lambda x: x[1])[
                : len(self.blocked_ips) - self.max_blocked_ips
            ]
            for ip, _ in oldest_ips:
                del self.blocked_ips[ip]

    def is_blocked(self, ip: str) -> bool:
        """检查 IP 是否被禁用"""
        self.cleanup_expired()

        if ip in self.blocked_ips:
            if time.time() < self.blocked_ips[ip]:
                return True
            else:
                del self.blocked_ips[ip]
                self.failed_attempts[ip] = 0
                if ip in self.last_failed_time:
                    del self.last_failed_time[ip]
        return False

    def record_failed_attempt(self, ip: str) -> bool:
        """记录失败的尝试"""
        current_time = time.time()

        if ip in self.last_failed_time:
            if current_time - self.last_failed_time[ip] > self.block_duration:
                self.failed_attempts[ip] = 0

        self.failed_attempts[ip] += 1
        self.last_failed_time[ip] = current_time

        if self.failed_attempts[ip] >= self.max_failed_attempts:
            self.blocked_ips[ip] = current_time + self.block_duration
            return True

        return False

    def get_block_info(self, ip: str) -> dict:
        """获取 IP 的禁用信息"""
        if ip in self.blocked_ips:
            unblock_time = self.blocked_ips[ip]
            remaining_seconds = int(unblock_time - time.time())
            return {
                "blocked": True,
                "remaining_seconds": max(0, remaining_seconds),
                "unblock_time": datetime.fromtimestamp(unblock_time).isoformat(),
            }
        return {"blocked": False, "remaining_seconds": 0}


# 全局速率限制器实例
rate_limiter = RateLimiter(
    max_failed_attempts=5, block_duration=6000, max_blocked_ips=1000
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""

    async def dispatch(self, request: Request, call_next):
        # 获取客户端 IP
        client_ip = request.client.host if request.client else "unknown"

        # 检查 IP 是否被禁用（快速检查，避免处理被禁 IP）
        if rate_limiter.is_blocked(client_ip):
            block_info = rate_limiter.get_block_info(client_ip)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Please retry after {block_info['remaining_seconds']}s"
                },
            )

        return await call_next(request)
