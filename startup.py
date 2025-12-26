import uvicorn

from app.app import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        log_level="error",
        access_log=False,
        workers=2,  # On Windows, it is not meaningful
    )
