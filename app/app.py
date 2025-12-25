import time
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from fastapi import FastAPI, Depends, HTTPException

from .database.models import *
from .database.engine import get_session, write_queue
from .auth import check_user, check_root
from .logger import request_logger, stop_logger_listeners
from .rate_limiter import RateLimitMiddleware, rate_limiter


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 记录请求信息
        request_logger.info(
            f"[{request.method}] {request.url.path} "
            f"| 客户端: {request.client.host if request.client else 'unknown'} "
            f"| 查询参数: {dict(request.query_params) if request.query_params else 'none'}"
        )

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # 记录响应信息
            request_logger.info(
                f"[{request.method}] {request.url.path} "
                f"| 状态码: {response.status_code} "
                f"| 耗时: {process_time*1000:.2f}ms"
            )

            return response
        except Exception as e:
            process_time = time.time() - start_time
            request_logger.error(
                f"[{request.method}] {request.url.path} "
                f"| 错误: {str(e)} "
                f"| 耗时: {process_time*1000:.2f}ms"
            )
            raise


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 应用启动时启动写队列
    write_queue.start()
    request_logger.info("应用已启动，数据库写队列已启动")
    yield
    # 应用关闭时停止写队列和日志监听器
    write_queue.stop()
    request_logger.info("应用已关闭，数据库写队列已停止")
    request_logger.info("关闭日志队列监听器")
    # 等待日志队列处理完所有消息后再关闭
    stop_logger_listeners()


app = FastAPI(lifespan=lifespan)

# 添加速率限制中间件（必须在请求日志中间件之前）
app.add_middleware(RateLimitMiddleware)

# 添加请求日志中间件
app.add_middleware(RequestLoggingMiddleware)


@app.get("/", dependencies=[Depends(check_user)])
async def test_connection():
    return {"detail": "Connection successful!"}


@app.get("/code/get", response_model=CodeResult, dependencies=[Depends(check_user)])
async def get_code(follow_user_id: int) -> CodeResult:
    """异步读取二维码数据"""
    with next(get_session()) as session:
        code = session.get(Code, follow_user_id)
        if code is None:
            raise HTTPException(status_code=404, detail="Code not found")
        return CodeResult(**code.model_dump())


@app.patch("/code/patch", status_code=202, dependencies=[Depends(check_user)])
async def patch_code(code_data: CodeUpdate, id: int):
    """异步写入队列，立即返回"""
    code = Code(id=id, content=code_data.content, update_at=int(time.time()))
    write_queue.add_operation("merge", code)
    return {"detail": "Added to queue."}


@app.get("/user/get", dependencies=[Depends(check_user)])
async def get_user(check_id: int):
    """
    异步读取用户
    检查 Code 而非 User 因为 Code 中可能不存在对应 User
    """
    with next(get_session()) as session:
        code = session.get(Code, check_id)
        if code is None:
            raise HTTPException(status_code=404, detail="User not found")
        return {"detail": "User is existing."}


@app.get("/admin/blocklist", dependencies=[Depends(check_root)])
async def get_blocklist(request: Request):
    """获取被禁用的 IP 列表（管理员权限）"""
    blocklist = []
    current_time = time.time()

    for ip, unblock_time in rate_limiter.blocked_ips.items():
        remaining_seconds = max(0, int(unblock_time - current_time))
        blocklist.append(
            {
                "ip": ip,
                "remaining_seconds": remaining_seconds,
                "failed_attempts": rate_limiter.failed_attempts.get(ip, 0),
            }
        )

    return {"total_blocked": len(blocklist), "blocklist": blocklist}


@app.post("/admin/unblock/{ip}", dependencies=[Depends(check_root)])
async def unblock_ip(request: Request, ip: str):
    """解除对特定 IP 的禁用（管理员权限）"""
    if ip in rate_limiter.blocked_ips:
        del rate_limiter.blocked_ips[ip]
        rate_limiter.failed_attempts[ip] = 0
        return {"detail": f"IP {ip} 已解除禁用"}
    return {"detail": f"IP {ip} 未被禁用"}


@app.get("/admin/block-status/{ip}", dependencies=[Depends(check_root)])
async def get_block_status(request: Request, ip: str):
    """查询特定 IP 的禁用状态（管理员权限）"""
    return {
        "ip": ip,
        **rate_limiter.get_block_info(ip),
        "failed_attempts": rate_limiter.failed_attempts.get(ip, 0),
    }
