"""MCP 工具鉴权：从 Authorization 解析并校验 user_id。

与 FastAPI 的 get_current_user 规则一致：验签 → 取 user_id → 确认用户存在且启用。
差别是 MCP 侧自己读请求头，不用 FastAPI 的 Depends。
"""

from app.common.exceptions import BusinessException
from app.database import SessionLocal
from app.models.user import User
from app.utils.jwt import decode_access_token


def user_id_from_authorization(authorization: str | None) -> int:
    """解析 Token 拿到用户 ID；身份绝不由模型或调用方参数填写。"""
    if not authorization:
        raise BusinessException(message="缺少 Authorization", code=401)
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        raise BusinessException(message="缺少 Authorization", code=401)
    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise BusinessException(message="登录凭证无效或已过期", code=401) from exc
    user_id = payload.get("user_id")
    if not user_id:
        raise BusinessException(message="无效的登录凭证", code=401)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.status == 1).first()
        if not user:
            raise BusinessException(message="用户不存在或已被禁用", code=401)
        return user.id
    finally:
        db.close()


# 兼容文档中出现的原始命名（笔误 form），保留为别名
user_id_form_authorization = user_id_from_authorization
