"""认证与权限模块：JWT 登录态 + 角色校验。"""
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .models.database import get_db
from .models.all_models import User

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = float(os.environ.get("SCHEDULER_TOKEN_EXPIRE_MIN", 12 * 60))  # 默认12小时

# secret 优先取环境变量，否则运行时随机生成（随机则不跨重启，token 随之失效，可接受）
_SECRET = os.environ.get("SCHEDULER_SECRET")


def _get_secret() -> str:
    global _SECRET
    if not _SECRET:
        _SECRET = secrets.token_urlsafe(48)
    return _SECRET


def create_token(user: User) -> str:
    """为用户签发 JWT。"""
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, _get_secret(), algorithm=ALGORITHM)


def _decode_token(token: str):
    try:
        return jwt.decode(token, _get_secret(), algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_bearer_token(authorization: str = Header(default="")) -> str:
    """从 Authorization 头解析 Bearer token。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        return ""
    return authorization.split(" ", 1)[1].strip()


def get_current_user(
    token: str = Depends(get_bearer_token), db: Session = Depends(get_db)
) -> User:
    """校验登录态，返回当前用户；未登录直接 401。"""
    payload = _decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="未登录或登录已过期，请重新登录")
    user = db.query(User).get(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """校验管理员角色；普通用户访问管理操作返回 403。"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限：该操作仅限管理员")
    return user
