"""FastMCP Streamable HTTP 服务。

在 backend/ 下执行（需设置 PYTHONPATH=.）：
    python mcp_server.py
对外地址：http://127.0.0.1:8001/mcp
"""

import logging
import re
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.common.exceptions import BusinessException
from app.config import settings
from app.database import SessionLocal
from app.dependencies.mcp_auth import user_id_from_authorization
from app.models.study_plan import StudyPlan
from app.models.user import User
from app.schemas.study_plan import StudyPlanCreateRequest
from app.services import rag_service
from app.services.schedule_service import list_schedules_as_dict
from app.services.study_plan_service import create_study_plan

mcp = FastMCP("campus-course-agent")
logger = logging.getLogger(__name__)

TURN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def _headers() -> dict:
    """读取本次 MCP 请求头；不同 FastMCP 版本参数名略有差异。"""
    try:
        raw = get_http_headers(include_all=True) or {}
    except TypeError:
        raw = get_http_headers(include={"authorization", "x-chat-turn-id"}) or {}
    return {str(key).lower(): value for key, value in raw.items()}


def _current_user_id() -> int:
    """身份只来自 Authorization 中的 JWT，工具参数里没有 user_id。"""
    return user_id_from_authorization(_headers().get("authorization"))


def _current_turn_id() -> str:
    turn_id = (_headers().get("x-chat-turn-id") or "").strip()
    if not TURN_ID_PATTERN.fullmatch(turn_id):
        raise BusinessException(message="缺少或无效的对话轮次 ID，无法保存计划")
    return turn_id


@mcp.tool()
def get_my_schedules(
    date: Annotated[
        str | None,
        Field(
            description="可选参数，上课的日期，格式：YYYY-MM-DD，不传则返回全部的列表"
        ),
    ] = None,
) -> dict:
    """查询当前登录用户自己的课表，不能通过参数指定其他用户。

    可查询指定日期或全部课表，不支持日期范围参数。
    返回 {"items": [...], "count": n}；失败时带 error 且 items 为空列表。
    """
    try:
        user_id = _current_user_id()
    except BusinessException as exc:
        return {"error": exc.message, "items": [], "count": 0}
    except Exception:
        logger.exception("MCP 课表工具鉴权失败")
        return {"error": "身份验证服务异常，请稍后重试", "items": [], "count": 0}

    db = SessionLocal()
    try:
        items = list_schedules_as_dict(db, user_id=user_id, date_str=date)
        return {"items": items, "count": len(items)}
    except BusinessException as exc:
        return {"error": exc.message, "items": [], "count": 0}
    except Exception:
        logger.exception("MCP 查询课表失败")
        return {"error": "课表查询服务异常，请稍后重试", "items": [], "count": 0}
    finally:
        db.close()


@mcp.tool()
def search_course_docs(
    query: Annotated[str, Field(description="要从课程资料中检索的问题或关键词")],
) -> dict:
    """只读检索全站共享的课程资料；用户身份来自 JWT，不由模型填写。"""
    try:
        _current_user_id()
    except BusinessException as exc:
        return {"error": exc.message, "items": []}
    except Exception:
        logger.exception("MCP 资料工具鉴权失败")
        return {"error": "身份验证服务异常，请稍后重试", "items": []}

    result = rag_service.search_docs(query)
    if not result.get("ok"):
        return {"error": result.get("error") or "资料检索不可用", "items": []}
    return {"items": result["items"], "count": len(result["items"])}


@mcp.tool()
def save_study_plan(
    content: Annotated[str, Field(description="要保存的完整学习计划正文")],
) -> dict:
    """仅在用户明确要求保存时，将计划写入当前用户的数据库。"""
    try:
        user_id = _current_user_id()
        turn_id = _current_turn_id()
    except BusinessException as exc:
        return {"ok": False, "error": exc.message}
    except Exception:
        logger.exception("MCP 保存工具鉴权失败")
        return {"ok": False, "error": "身份验证服务异常，请稍后重试"}

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if not user or user.status != 1:
            return {"ok": False, "error": "用户不存在或已被禁用"}

        # 预先查询给出易懂提示；真正防并发重复的是 (user_id, turn_id) 唯一约束
        exists = db.scalar(
            select(StudyPlan.id).where(
                StudyPlan.user_id == user_id, StudyPlan.turn_id == turn_id
            )
        )
        if exists:
            return {"ok": False, "error": "本轮已保存学习计划，请勿重复保存"}

        try:
            row = create_study_plan(
                db,
                user,
                StudyPlanCreateRequest(content=content),
                turn_id=turn_id,
            )
        except BusinessException as exc:
            db.rollback()
            return {"ok": False, "error": exc.message}
        except IntegrityError:
            db.rollback()
            return {"ok": False, "error": "本轮已保存学习计划，请勿重复保存"}
        except Exception:
            db.rollback()
            logger.exception("MCP 保存学习计划失败")
            try:
                with SessionLocal() as check:
                    saved = check.scalar(
                        select(StudyPlan.id).where(
                            StudyPlan.user_id == user_id,
                            StudyPlan.turn_id == turn_id,
                        )
                    )
            except Exception:
                return {"ok": False, "error": "保存状态不确定，请到学习计划页面核对"}
            if saved:
                return {"ok": False, "error": "保存状态不确定，请到学习计划页面核对"}
            return {"ok": False, "error": "保存失败，请稍后重试"}
        return {"ok": True, "id": row.id, "message": "学习计划已保存"}
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    mcp.run(
        transport="http",
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        path=settings.MCP_PATH,
    )
