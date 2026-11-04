import logging
from pathlib import Path

from app.common.exceptions import BusinessException
from app.config import (
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_EMBED_BATCH,
    RAG_TOP_K,
    settings,
)

logger = logging.getLogger(__name__)


def extract_document_text(path: Path) -> str:
    """把 .txt / .md / .pdf / .docx 抽取为纯文本，不还原版式。"""
    ext = path.suffix.lower()
    try:
        if ext in (".txt", ".md"):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise BusinessException(message="文本文件不是 UTF-8 编码，无法读取") from exc
        elif ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif ext == ".docx":
            from docx import Document

            doc = Document(str(path))
            parts = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    parts.append("\t".join(cell.text for cell in row.cells))
            text = "\n".join(parts)
        else:
            raise BusinessException(message=f"不支持的资料类型：{ext}")
    except BusinessException:
        raise
    except ImportError as exc:
        raise BusinessException(
            message=f"缺少解析 {ext} 所需依赖，请安装 pypdf / python-docx"
        ) from exc
    except Exception as exc:
        logger.exception("读取资料失败：%s", path)
        raise BusinessException(message="资料无法读取或已损坏") from exc

    text = text.strip()
    if not text:
        raise BusinessException(message="资料中没有可抽取的文本（扫描件需先 OCR）")
    return text


def _embeddings():
    """创建向量模型客户端；缺少密钥时先停止，避免把配置缺失误判为服务故障。"""
    if not settings.EMBEDDING_API_KEY:
        raise BusinessException(message="请先配置 EMBEDDING_API_KEY", code=500)
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        api_key=settings.EMBEDDING_API_KEY,
        base_url=settings.EMBEDDING_BASE_URL,
        model=settings.EMBEDDING_MODEL,
        check_embedding_ctx_length=False,
        chunk_size=RAG_EMBED_BATCH,
    )


def get_vectorstore(with_embeddings: bool = True):
    """连接独立 Chroma 服务；只做删除/读取时可以不带向量模型。"""
    from langchain_chroma import Chroma

    kwargs = {
        "collection_name": settings.CHROMA_COLLECTION,
        "host": settings.CHROMA_HOST,
        "port": settings.CHROMA_PORT,
    }
    if with_embeddings:
        kwargs["embedding_function"] = _embeddings()
    return Chroma(**kwargs)


def delete_by_doc_id(doc_id: int) -> None:
    """按文档 ID 清理该资料的向量片段，不影响其他资料。"""
    store = get_vectorstore(with_embeddings=False)
    result = store.get(where={"doc_id": str(doc_id)}, include=[])
    ids = result.get("ids") or []
    if ids:
        store.delete(ids=ids)


def ingest_kb_file(doc_id: int, source: str, path: Path) -> int:
    """提取文字 → 分块 → Embedding → 写入 Chroma，返回片段数。"""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    text = extract_document_text(path)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=RAG_CHUNK_SIZE, chunk_overlap=RAG_CHUNK_OVERLAP
    )
    chunks = splitter.split_text(text)
    if not chunks:
        raise BusinessException(message="资料中没有可入库的文本")

    # 先清旧片段，保证重复入库不会累积重复片段
    delete_by_doc_id(doc_id)

    ids = [f"doc-{doc_id}-chunk-{index}" for index in range(len(chunks))]
    metadatas = [
        {"doc_id": str(doc_id), "source": source, "scope": "kb"} for _ in chunks
    ]
    store = get_vectorstore()
    for start in range(0, len(chunks), RAG_EMBED_BATCH):
        end = start + RAG_EMBED_BATCH
        store.add_texts(
            texts=chunks[start:end],
            metadatas=metadatas[start:end],
            ids=ids[start:end],
        )
    logger.info("资料入库完成：doc_id=%s source=%s chunks=%s", doc_id, source, len(chunks))
    return len(chunks)


def search_docs(query: str) -> dict:
    """检索最相近的 3 个片段，区分「服务失败」与「没有可用片段」。"""
    question = (query or "").strip()
    if not question:
        return {"ok": False, "error": "检索问题不能为空", "items": []}
    try:
        documents = get_vectorstore().similarity_search(question, k=RAG_TOP_K)
    except BusinessException as exc:
        return {"ok": False, "error": exc.message, "items": []}
    except Exception as exc:
        logger.exception("资料检索失败")
        return {"ok": False, "error": f"资料检索服务暂时不可用：{exc}", "items": []}
    items = [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source", "未知来源"),
        }
        for doc in documents
    ]
    return {"ok": True, "items": items}
