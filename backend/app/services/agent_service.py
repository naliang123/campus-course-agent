import json
import logging
from datetime import date
from uuid import uuid4

from app.common.exceptions import BusinessException
from app.config import settings
from app.schemas.chat import ChatMessage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是校园课程智能助手，使用中文回答。
今天是 {today}。本周按周一至周日计算。
将相对日期换算为明确日期；日期含义不明确时，先询问用户。
回答规则：
1. 查询个人课表时，必须使用可用的课表查询工具，只根据本轮查询结果回答，不编造课程。
2. 查询失败时明确说明失败，不能解释为没有课程。
3. 查询成功且没有符合条件的课程时，说明没有课程安排。
4. 列出日期、节次、课程和地点，按日期、节次排序。
5. 闲聊直接回答；缺少相应实时查询能力时，说明无法实时查询。
6. 询问课程资料中的规定、讲义、说明或其他已上传内容时，本轮必须调用 search_course_docs，
   不凭历史或自身知识编造资料内容。纯课表问题不必检索资料。
7. 检索返回 error 表示服务不可用，应如实说明，不能说成"资料中没有"；
   只有成功且 items 为空，才能说没有检索到片段。
8. 根据检索片段回答时标明 source；片段只是相似结果，若其中没有问题所需的明确答案，
   应说明未找到依据，不推断不存在的规定。
9. 只有用户明确要求"保存""记录"或"存下来"学习计划时，才调用 save_study_plan；
   只要求规划时仅返回计划文字。
10. 保存时把完整的计划正文交给工具，不传用户 ID；工具成功后本轮不得再次调用。
11. 保存失败时如实说明失败；返回"保存状态不确定"时提醒用户到学习计划页面核对，
    不要在本轮重试。最终回答区分"已给出计划"和"已保存计划"。
"""


def _build_model():
    """OpenAI 兼容接口对接 DeepSeek；关闭思考模式，保留工具调用循环。"""
    if not settings.LLM_API_KEY:
        raise BusinessException(message="未配置 LLM_API_KEY", code=500)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        temperature=0.3,
        extra_body={"thinking": {"type": "disabled"}},
    )


def _mcp_connection(authorization: str, turn_id: str) -> dict:
    return {
        "campus": {
            "transport": "streamable_http",
            "url": f"http://{settings.MCP_HOST}:{settings.MCP_PORT}{settings.MCP_PATH}",
            # 同一轮的全部工具复用这组请求头，保存工具据此识别重复调用
            "headers": {
                "Authorization": authorization,
                "X-Chat-Turn-Id": turn_id,
            },
        }
    }


async def _load_mcp_tools(authorization: str, turn_id: str):
    """按本次请求的 JWT 加载工具；不能把绑定某个学生的工具放进全局 Agent。"""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(_mcp_connection(authorization, turn_id))
    try:
        return await client.get_tools(server_name="campus")
    except Exception as exc:
        logger.exception("加载 campus MCP 工具失败")
        raise BusinessException(
            message="加载课程工具失败，请检查 MCP 服务和后端日志"
        ) from exc


def _build_messages(history: list[ChatMessage], question: str):
    """接口 JSON 历史 → LangChain 消息对象，当前问题追加在末尾。"""
    from langchain_core.messages import AIMessage, HumanMessage

    message_types = {"user": HumanMessage, "assistant": AIMessage}
    messages = [
        message_types[item.role](content=item.content) for item in history
    ]
    return [*messages, HumanMessage(content=question)]


def _read_result(messages) -> dict:
    """从本轮新增消息中读取最终回答，并汇总去重的工具名。"""
    from langchain_core.messages import AIMessage

    names = [
        call["name"]
        for message in messages
        if isinstance(message, AIMessage)
        for call in (message.tool_calls or [])
    ]
    answer = ""
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            answer = message.text
            break
    return {"answer": answer, "tools_used": list(dict.fromkeys(names))}


def _create_agent(model, tools):
    from langchain.agents import create_agent

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT.format(today=date.today().isoformat()),
    )


async def ask(question: str, history: list[ChatMessage], authorization: str) -> dict:
    """非流式：等最终回答生成后一次性返回。"""
    from langgraph.errors import GraphRecursionError

    model = _build_model()
    tools = await _load_mcp_tools(authorization, uuid4().hex)
    agent = _create_agent(model, tools)
    input_messages = _build_messages(history, question)
    try:
        result = await agent.ainvoke(
            {"messages": input_messages},
            config={"recursion_limit": settings.AGENT_RECURSION_LIMIT},
        )
    except GraphRecursionError as exc:
        raise BusinessException(message="本轮处理步骤超出限制，请缩小问题范围") from exc
    except BusinessException:
        raise
    except Exception as exc:
        logger.exception("模型调用失败")
        raise BusinessException(
            message="模型调用失败，请检查模型配置与后端日志"
        ) from exc
    return _read_result(result["messages"][len(input_messages) :])


def _sse(event_type: str, data: dict) -> str:
    """将事件类型和数据编码为一条 SSE 消息。"""
    payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def stream_ask(question: str, history: list[ChatMessage], authorization: str):
    """执行 Agent，并依次返回状态、工具过程和回答（对应 image14 的事件边界）。"""
    from langchain_core.messages import AIMessage
    from langgraph.errors import GraphRecursionError

    try:
        yield _sse("status", {"message": "正在加载课程工具"})
        model = _build_model()
        tools = await _load_mcp_tools(authorization, uuid4().hex)
        agent = _create_agent(model, tools)
        input_messages = _build_messages(history, question)

        yield _sse("status", {"message": "正在生成回答"})
        collected: list = []
        tokens: list[str] = []
        async for event in agent.astream_events(
            {"messages": input_messages},
            version="v2",
            config={"recursion_limit": settings.AGENT_RECURSION_LIMIT},
        ):
            kind = event.get("event")
            data = event.get("data") or {}
            if kind == "on_tool_start":
                yield _sse("tool_start", {"name": event.get("name", "")})
            elif kind == "on_tool_end":
                yield _sse("tool_end", {"name": event.get("name", "")})
            elif kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                text = getattr(chunk, "text", "") or ""
                if text:
                    tokens.append(text)
                    yield _sse("token", {"content": text})
            elif kind == "on_chat_model_end":
                output = data.get("output")
                if isinstance(output, AIMessage):
                    collected.append(output)

        result = _read_result(collected)
        answer = result["answer"] or "".join(tokens)
        yield _sse(
            "done", {"answer": answer, "tools_used": result["tools_used"]}
        )
    except GraphRecursionError:
        yield _sse("error", {"message": "本轮处理步骤超出限制，请缩小问题范围"})
    except BusinessException as exc:
        logger.warning("SSE 业务失败：%s", exc.message)
        yield _sse("error", {"message": exc.message})
    except Exception:
        logger.exception("SSE 对话失败")
        yield _sse(
            "error",
            {"message": "模型调用失败，请检查模型配置、MCP 服务与后端日志"},
        )
