from fastapi import HTTPException, Request

from .database.engine import get_session
from .database.models import User
from .rate_limiter import rate_limiter


def check_root(request: Request, auth: str | None) -> None:
    client_ip = request.client.host if request.client else "unknown"

    if auth is None:
        rate_limiter.record_failed_attempt(client_ip)
        raise HTTPException(status_code=403, detail="Unauthorized")

    with next(get_session()) as session:
        user = session.get(User, 1)  # user 1 = root user
        if not (user and user.auth == auth):
            rate_limiter.record_failed_attempt(client_ip)
            raise HTTPException(status_code=403, detail="Unauthorized")


def check_user(request: Request, id: int | None, auth: str | None) -> None:
    client_ip = request.client.host if request.client else "unknown"

    if id is None or auth is None:
        rate_limiter.record_failed_attempt(client_ip)
        raise HTTPException(status_code=403, detail="Unauthorized")

    with next(get_session()) as session:
        user = session.get(User, id)
        if not (user and user.auth == auth):
            rate_limiter.record_failed_attempt(client_ip)
            raise HTTPException(status_code=403, detail="Unauthorized")
