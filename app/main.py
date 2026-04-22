from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.core.config import AppConfig
from app.ingestion.service import DocumentIngestionService
from app.workflow.runtime import DrawAgentRuntime


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "app" / "frontend"
FRONTEND_STATIC_DIR = FRONTEND_DIR / "static"
CONFIG = AppConfig.load(ROOT_DIR)
RUNTIME = DrawAgentRuntime(ROOT_DIR)
INGESTION = DocumentIngestionService()

app = FastAPI(title="drawAgent-v2")
app.mount("/outputs", StaticFiles(directory=CONFIG.output_dir), name="outputs")
app.mount("/static", StaticFiles(directory=FRONTEND_STATIC_DIR), name="static")


class ConfirmGenerationRequest(BaseModel):
    checkpoint_id: str = Field(min_length=1)


def _staging_batch_dir(upload_batch_id: str) -> Path:
    return CONFIG.upload_dir / "staging" / upload_batch_id


def _upload_manifest_path(upload_batch_id: str) -> Path:
    return _staging_batch_dir(upload_batch_id) / "upload_result.json"


def _write_upload_manifest(upload_batch_id: str, uploaded_files: list[dict]) -> None:
    manifest_path = _upload_manifest_path(upload_batch_id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "upload_batch_id": upload_batch_id,
                "uploaded_files": uploaded_files,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _read_upload_manifest(upload_batch_id: str) -> dict:
    manifest_path = _upload_manifest_path(upload_batch_id)
    if not manifest_path.exists():
        return {
            "upload_batch_id": upload_batch_id,
            "uploaded_files": [],
        }
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _save_uploaded_files(files: list[UploadFile], target_dir: Path) -> list[dict]:
    target_dir.mkdir(parents=True, exist_ok=True)
    saved: list[dict] = []
    for item in files:
        original_name = Path(item.filename or "uploaded_file").name
        path = target_dir / original_name
        with path.open("wb") as handle:
            shutil.copyfileobj(item.file, handle)
        saved.append(
            {
                "name": original_name,
                "content_type": item.content_type or "application/octet-stream",
                "size_bytes": path.stat().st_size,
                "saved_path": str(path),
            }
        )
    return saved


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/agents")
def list_agents() -> dict:
    return {"agents": RUNTIME.describe_agents()}


@app.get("/skills")
def list_skills() -> dict:
    return {"skills": RUNTIME.describe_skills()}


@app.get("/workflow")
def describe_workflow() -> dict:
    return RUNTIME.describe_workflow()


@app.post("/session/upload-files-form", response_class=HTMLResponse)
async def upload_files_form(
    files: list[UploadFile] = File(default_factory=list),
    upload_batch_id: str | None = Form(default=None),
) -> HTMLResponse:
    upload_batch_id = upload_batch_id or str(uuid4())
    batch_dir = _staging_batch_dir(upload_batch_id)
    uploaded_files = _save_uploaded_files(files, batch_dir)
    _write_upload_manifest(upload_batch_id, uploaded_files)
    payload = json.dumps(
        {
            "type": "drawagent-upload-result",
            "ok": True,
            "payload": {
                "upload_batch_id": upload_batch_id,
                "uploaded_files": uploaded_files,
            },
        },
        ensure_ascii=False,
    )
    return HTMLResponse(
        f"""
<!DOCTYPE html>
<html lang="zh-CN">
  <body>
    <script>
      window.parent.postMessage({payload}, "*");
    </script>
  </body>
</html>
"""
    )


@app.post("/session/upload-files")
async def upload_files(
    files: list[UploadFile] = File(default_factory=list),
    upload_batch_id: str | None = Form(default=None),
) -> dict:
    upload_batch_id = upload_batch_id or str(uuid4())
    batch_dir = _staging_batch_dir(upload_batch_id)
    uploaded_files = _save_uploaded_files(files, batch_dir)
    _write_upload_manifest(upload_batch_id, uploaded_files)
    return {
        "ok": True,
        "upload_batch_id": upload_batch_id,
        "uploaded_files": uploaded_files,
    }


@app.get("/session/upload-status/{upload_batch_id}")
def upload_status(upload_batch_id: str) -> dict:
    payload = _read_upload_manifest(upload_batch_id)
    return {
        "ok": True,
        **payload,
    }


@app.post("/session/start")
async def start_session(
    user_input: str = Form(""),
    files: list[UploadFile] = File(default_factory=list),
    staged_files_json: str = Form("[]"),
    upload_batch_id: str = Form(""),
) -> dict:
    session_id = str(uuid4())
    session_dir = CONFIG.upload_dir / session_id
    uploaded_files = _save_uploaded_files(files, session_dir)
    try:
        staged_files = json.loads(staged_files_json or "[]")
    except json.JSONDecodeError:
        staged_files = []
    if (not staged_files) and upload_batch_id:
        manifest_payload = _read_upload_manifest(upload_batch_id)
        manifest_files = manifest_payload.get("uploaded_files", [])
        if isinstance(manifest_files, list):
            staged_files = manifest_files
    for item in staged_files if isinstance(staged_files, list) else []:
        if not isinstance(item, dict) or not item.get("saved_path"):
            continue
        source = Path(str(item["saved_path"]))
        if not source.exists():
            continue
        target = session_dir / Path(str(item.get("name") or source.name)).name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        uploaded_files.append(
            {
                "name": target.name,
                "content_type": item.get("content_type", "application/octet-stream"),
                "size_bytes": target.stat().st_size,
                "saved_path": str(target),
            }
        )

    document_context = INGESTION.ingest_uploaded_files(
        uploaded_files=uploaded_files,
        artifact_dir=session_dir,
    )
    result = RUNTIME.start_prompt_pipeline(
        session_id=session_id,
        user_input=user_input,
        document_context=document_context,
    )
    return {
        "session_id": result.session_id,
        "stage": result.stage,
        "checkpoint_id": result.checkpoint_id,
        "payload_final": result.payload_final,
        "workflow_state": result.workflow_state,
        "document_context_summary": result.document_context_summary,
        "selected_skill": result.selected_skill,
        "uploaded_files": uploaded_files,
        "confirm_required": bool(result.checkpoint_id),
    }


@app.post("/session/confirm-image-generation")
def confirm_image_generation(request: ConfirmGenerationRequest) -> dict:
    return RUNTIME.confirm_image_generation(request.checkpoint_id)
