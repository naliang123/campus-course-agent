import logging
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.config import ALLOWED_DOC_EXTENSIONS, KB_DIR, MAX_FILE_SIZE
from app.models.kb_document import KbDocument
from app.schemas.document import DocumentPreviewResponse, KbDocumentResponse
from app.services.rag_service import (
    delete_by_doc_id,
    extract_document_text,
    ingest_kb_file,
)

logger = logging.getLogger(__name__)

READ_CHUNK = 64 * 1024


def list_documents(db: Session) -> list[KbDocumentResponse]:
    """管理员资料列表，按 id 倒序。"""
    rows = db.query(KbDocument).order_by(KbDocument.id.desc()).all()
    return [KbDocumentResponse.model_validate(row) for row in rows]


def get_document(db: Session, doc_id: int) -> KbDocument:
    row = db.query(KbDocument).filter(KbDocument.id == doc_id).first()
    if not row:
        raise BusinessException(message="文档不存在", code=404)
    return row


def document_path(rel_path: str) -> Path:
    """把相对路径限制在 data/kb 目录内，避免上传者提供的路径越界。"""
    path = (KB_DIR / rel_path).resolve()
    if KB_DIR.resolve() not in path.parents:
        raise BusinessException(message="非法的资料路径")
    return path


def _save_file(upload: UploadFile, disk_name: str) -> tuple[Path, int]:
    """分块写入磁盘，返回路径与实际字节数。"""
    path = KB_DIR / disk_name
    size = 0
    with path.open("xb") as target:
        while True:
            chunk = upload.file.read(READ_CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                raise BusinessException(message="单个文件不能超过 100 MiB", code=400)
            target.write(chunk)
    if size == 0:
        path.unlink(missing_ok=True)
        raise BusinessException(message="空文件不能上传", code=400)
    return path, size


def upload_documents(db: Session, files: list[UploadFile]) -> list[KbDocumentResponse]:
    """同一批全部保存并入库成功后才提交；任一失败整批回滚文件、记录与向量。"""
    if not files:
        raise BusinessException(message="请至少上传一个文件", code=400)

    saved_paths: list[Path] = []
    ingested_ids: list[int] = []
    names: set[str] = set()
    rows: list[KbDocument] = []
    try:
        # 阶段一：整批校验并写入磁盘。空文件、非法后缀、同名都在这里拦下，
        # 与图 12 的行为一致：本批不会出现「一半入库、一半没入库」。
        for upload in files:
            original_name = (upload.filename or "").strip()
            if not original_name:
                raise BusinessException(message="文件名不能为空", code=400)
            ext = Path(original_name).suffix.lower()
            if ext not in ALLOWED_DOC_EXTENSIONS:
                raise BusinessException(
                    message=f"不支持的文件类型：{ext or '未知'}，仅支持 .txt / .md / .pdf / .docx",
                    code=400,
                )
            if original_name in names or db.query(KbDocument.id).filter(
                KbDocument.original_name == original_name
            ).first():
                raise BusinessException(message=f"已存在同名文档：{original_name}", code=400)
            names.add(original_name)

            disk_name = f"{uuid.uuid4().hex}{ext}"
            path, size = _save_file(upload, disk_name)
            saved_paths.append(path)

            row = KbDocument(
                original_name=original_name,
                disk_name=disk_name,
                rel_path=disk_name,
                size=size,
                ext=ext,
                ingested=False,
            )
            db.add(row)
            rows.append(row)

        # 阶段二：一次 flush 取得全部 ID，再逐份抽取、分块、向量化
        db.flush()
        for row in rows:
            ingest_kb_file(row.id, row.original_name, document_path(row.rel_path))
            ingested_ids.append(row.id)
            row.ingested = True

        db.commit()
        return [KbDocumentResponse.model_validate(row) for row in rows]
    except Exception as exc:
        db.rollback()
        for doc_id in ingested_ids:
            try:
                delete_by_doc_id(doc_id)
            except Exception:
                logger.exception("回滚向量片段失败：doc_id=%s", doc_id)
        for path in saved_paths:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                logger.exception("回滚资料文件失败：%s", path)
        if isinstance(exc, BusinessException):
            raise
        logger.exception("资料批量上传失败")
        raise BusinessException(message="资料上传或入库失败，本批已撤销") from exc


def preview_document(db: Session, doc_id: int) -> DocumentPreviewResponse:
    row = get_document(db, doc_id)
    text = extract_document_text(document_path(row.rel_path))
    return DocumentPreviewResponse(
        id=row.id,
        original_name=row.original_name,
        ext=row.ext,
        text=text,
        char_count=len(text),
    )


def _get_document_for_update(db: Session, doc_id: int) -> KbDocument:
    """锁定一份资料，避免删除和重新入库同时改写它的向量。"""
    row = (
        db.query(KbDocument)
        .filter(KbDocument.id == doc_id)
        .with_for_update()
        .first()
    )
    if not row:
        raise BusinessException(message="文档不存在", code=404)
    return row


def delete_document(db: Session, doc_id: int) -> None:
    """先清理向量与记录，确认提交成功后再删原文件。"""
    row = _get_document_for_update(db, doc_id)
    path = document_path(row.rel_path)
    try:
        delete_by_doc_id(row.id)
    except Exception as exc:
        logger.exception("删除向量片段失败：doc_id=%s", doc_id)
        raise BusinessException(message="向量片段清理失败，资料未删除") from exc
    db.delete(row)
    db.commit()
    try:
        path.unlink(missing_ok=True)
    except Exception:
        logger.exception("资料记录和向量已删除，但原文件清理失败：%s", path)
        raise BusinessException(message="资料记录和向量已删除，但原文件清理失败")


def reingest_document(db: Session, doc_id: int) -> KbDocumentResponse:
    """清理旧片段后重新入库；失败时保留原文件并把状态改为未入库。"""
    row = _get_document_for_update(db, doc_id)
    path = document_path(row.rel_path)
    try:
        ingest_kb_file(row.id, row.original_name, path)
    except Exception as exc:
        db.rollback()
        row = _get_document_for_update(db, doc_id)
        row.ingested = False
        db.commit()
        if isinstance(exc, BusinessException):
            raise
        logger.exception("资料重新入库失败：doc_id=%s", doc_id)
        raise BusinessException(message="资料重新入库失败，请检查 Embedding 与 Chroma 配置") from exc
    row.ingested = True
    db.commit()
    db.refresh(row)
    return KbDocumentResponse.model_validate(row)
