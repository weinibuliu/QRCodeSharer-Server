from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    """用户表模型"""

    id: Optional[int] = Field(default=None, primary_key=True)
    auth: Optional[str] = None


class Code(SQLModel, table=True):
    """二维码模型"""

    id: Optional[int] = Field(default=None, primary_key=True)
    content: Optional[str] = None
    update_at: Optional[int] = None


class CodeResult(SQLModel):
    """返回二维码模型"""

    content: Optional[str] = None
    update_at: Optional[int] = None


class CodeUpdate(SQLModel):
    """更新二维码模型"""

    content: Optional[str] = None


__all__ = ["User", "Code", "CodeResult", "CodeUpdate"]
