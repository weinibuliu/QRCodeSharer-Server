import uvicorn

from app.app import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        log_level="error",
        access_log=False,
        limit_concurrency=100,  # 限制并发连接数（防止内存溢出）
        limit_max_requests=10000,  # 每个工作进程处理10000个请求后重启
        # workers=2, # Only in Linux
    )
