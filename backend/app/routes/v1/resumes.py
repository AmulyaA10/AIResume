from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import shutil

from app.dependencies import get_current_user, resolve_credentials
from app.config import UPLOAD_DIR
from app.common import build_llm_config, safe_log_activity
from services.resume_parser import extract_text, to_ats_text
from services.db.lancedb_client import (
    store_resume, list_user_resumes, delete_user_resume,
    store_resume_validation, get_resume_validations, delete_resume_validation,
)
from services.agent_controller import run_resume_validation
from services.export_service import generate_docx

router = APIRouter()


class SaveGeneratedRequest(BaseModel):
    original_filename: Optional[str] = None
    new_filename: Optional[str] = None
    resume_json: Dict[str, Any]
    validation: Optional[Dict[str, Any]] = None


@router.get("/list")
async def list_resumes(user_id: str = Depends(get_current_user)):
    """Return the list of resumes with validation metadata for the current user."""
    filenames = list_user_resumes(user_id)
    validations = get_resume_validations(user_id)
    resumes = [{"filename": f, "validation": validations.get(f)} for f in filenames]
    return {"resumes": resumes}


@router.post("/upload")
async def upload_resumes(
    files: List[UploadFile] = File(...),
    store_db: str = Form("true"),
    run_validation: str = Form("true"),
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    llm_config = build_llm_config(creds["openrouter_key"], creds["llm_model"])

    print(f"--- Uploading {len(files)} files for user {user_id} ---")
    results = []
    store_db_bool = store_db.lower() == "true"
    validate_bool = run_validation.lower() == "true"

    for file in files:
        try:
            print(f"Processing: {file.filename}")
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            text = extract_text(file_path)

            # --- AI Validation ---
            validation = None
            if validate_bool and text.strip():
                try:
                    file_type = os.path.splitext(file.filename)[1].lstrip(".")
                    validation = run_resume_validation(
                        file_name=file.filename,
                        file_type=file_type,
                        extracted_text=text,
                        llm_config=llm_config
                    )
                    print(f"Validation complete: {file.filename} -> {validation.get('classification', 'unknown')}")
                except Exception as e:
                    print(f"DEBUG: Validation failed for {file.filename}: {e}")
                    validation = {"error": str(e)}

            # --- Store in DB (regardless of validation result) ---
            if store_db_bool:
                print(f"Storing in DB: {file.filename}")
                store_resume(file.filename, text, user_id, api_key=creds["openrouter_key"])

            # --- Persist validation metadata ---
            if validation and not validation.get("error"):
                store_resume_validation(user_id, file.filename, validation)

            classification = (validation or {}).get("classification", "N/A")
            results.append({
                "filename": file.filename,
                "status": "indexed",
                "validation": validation
            })
            safe_log_activity(user_id, "upload", file.filename, 0, classification)

            print(f"Completed: {file.filename}")
        except Exception as e:
            print(f"Error processing {file.filename}: {e}")
            results.append({"filename": file.filename, "status": "error", "error": str(e)})

    return {"success": True, "processed": results}


@router.delete("/{filename}")
async def delete_resume(filename: str, user_id: str = Depends(get_current_user)):
    """Delete a resume from LanceDB and the filesystem for the current user."""
    delete_user_resume(user_id, filename)
    delete_resume_validation(user_id, filename)
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return {"success": True, "deleted": filename}


@router.get("/text/{filename}")
async def get_resume_text(filename: str, user_id: str = Depends(get_current_user)):
    """Return ATS-normalized plain text for refinement input."""
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        text = to_ats_text(extract_text(file_path))
        return {"filename": filename, "text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {str(e)}")


@router.get("/download/{filename}")
async def download_resume(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')


def _resume_json_to_text(resume_json: Dict[str, Any]) -> str:
    """Convert structured resume JSON back to plain text."""
    contact = resume_json.get("contact", {})
    parts = [
        contact.get("name", ""),
        " | ".join(filter(None, [contact.get("email"), contact.get("phone"), contact.get("location")])),
        f"LinkedIn: {contact.get('linkedin', '')}" if contact.get("linkedin") else "",
        "",
        "PROFESSIONAL SUMMARY",
        resume_json.get("summary", ""),
        "",
        "CORE COMPETENCIES",
        ", ".join(resume_json.get("skills", [])),
        "",
        "PROFESSIONAL EXPERIENCE",
    ]
    for exp in resume_json.get("experience", []):
        parts += [
            f"{exp.get('title', '')} | {exp.get('company', '')} | {exp.get('period', '')}",
            *[f"• {b}" for b in exp.get("bullets", [])],
            "",
        ]
    parts.append("EDUCATION")
    for edu in resume_json.get("education", []):
        parts.append(f"{edu.get('degree', '')} — {edu.get('school', '')} ({edu.get('year', '')})")
    return "\n".join(parts)


@router.post("/save-generated")
async def save_generated_resume(
    body: SaveGeneratedRequest,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user),
):
    """Save an AI-generated or refined resume, overwriting the original or as a new file."""
    if not body.resume_json:
        raise HTTPException(status_code=400, detail="resume_json is required")
    if not body.original_filename and not body.new_filename:
        raise HTTPException(status_code=400, detail="original_filename or new_filename is required")

    overwrite = body.new_filename is None
    filename = body.original_filename if overwrite else body.new_filename
    if not filename.endswith((".docx", ".doc", ".pdf", ".txt")):
        filename = filename + ".docx"

    file_path = os.path.join(UPLOAD_DIR, filename)

    # Save to filesystem — use proper DOCX for .doc/.docx, plain text otherwise
    if filename.endswith((".docx", ".doc")):
        docx_stream = generate_docx(body.resume_json)
        with open(file_path, "wb") as f:
            f.write(docx_stream.read())
        # Extract plain text for LanceDB indexing
        text = _resume_json_to_text(body.resume_json)
    else:
        text = _resume_json_to_text(body.resume_json)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)

    # For overwrite: remove old LanceDB entry then re-insert
    if overwrite and body.original_filename:
        delete_user_resume(user_id, body.original_filename)
        delete_resume_validation(user_id, body.original_filename)

    store_resume(filename, text, user_id, api_key=creds["openrouter_key"])

    if body.validation and not body.validation.get("error"):
        store_resume_validation(user_id, filename, body.validation)

    safe_log_activity(user_id, "save_generated", filename, 0, (body.validation or {}).get("classification", "N/A"))
    return {"success": True, "filename": filename}
