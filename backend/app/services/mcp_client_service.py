import json
import logging

from app.common.exceptions import BusinessException
from app.config import settings

logger = logging.getLogger(__name__)


def _connection(authorization: str) -> dict:
    return {
        "campus": {
            "transport": "streamable_http",
            "url": f"http://{settings.MCP_HOST}:{settings.MCP_PORT}{settings.MCP_PATH}",
            "headers": {"Authorization": authorization},
        }
    }


def _normalize_result(result) -> dict:
    """适配 MCP content block：result[0]['text'] 里是 JSON 字符串。"""
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        return json.loads(result)
    if isinstance(result, list) and result:
        block = result[0]
        text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
        if text is None:
            raise ValueError("MCP 返回内容中没有 text")
        return json.loads(text)
    raise ValueError("MCP 返回结果为空")


async def call_get_my_schedules(authorization: str, date: str | None = None) -> dict:
    """调试通道：由服务端连接 MCP 拉取并按指定参数调用课表工具。"""
    if not authorization:
        raise BusinessException(message="缺少登录凭证", code=401)
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as exc:
        raise BusinessException(message="未安装 langchain-mcp-adapters，无法连接 MCP") from exc

    try:
        client = MultiServerMCPClient(_connection(authorization))
        tools = await client.get_tools(server_name="campus")
        tool = next((item for item in tools if item.name == "get_my_schedules"), None)
        if tool is None:
            raise BusinessException(message="未找到课表工具 get_my_schedules")
        result = await tool.ainvoke({"date": date} if date else {})
        return _normalize_result(result)
    except BusinessException:
        raise
    except Exception as exc:
        logger.exception("调用 MCP 课表工具失败")
        raise BusinessException(message="MCP 服务不可用，请检查 MCP 进程与日志") from exc
