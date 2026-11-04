from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """历史消息：只允许 user / assistant，不能提交系统或工具消息。"""

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """一次提问的请求。"""

    question: str = Field(min_length=1, description="用户问题")
    history: list[ChatMessage] = Field(default_factory=list)
