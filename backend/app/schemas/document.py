from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KbDocumentResponse(BaseModel):
    """上传结果和资料列表共用的资料记录。"""

    id: int
    original_name: str
    disk_name: str
    rel_path: str
    size: int
    ext: str
    ingested: bool
    create_time: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentPreviewResponse(BaseModel):
    """预览时抽取出的纯文本。"""

    id: int
    original_name: str
    ext: str
    text: str
    char_count: int
