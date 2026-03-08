from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import re
import shutil

from app.dependencies import get_current_user, get_user_role, resolve_credentials
from app.config import UPLOAD_DIR
from app.common import build_llm_config, safe_log_activity
from app.common import precheck_resume_validation
from services.resume_parser import extract_text, to_ats_text
from services.db.lancedb_client import (
    store_resume, list_user_resumes, delete_user_resume,
    store_resume_validation, get_resume_validations, delete_resume_validation,
)
from services.agent_controller import run_resume_validation
from services.ai.common import extract_skills_from_text
from services.export_service import generate_docx

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "rtf"}
MAX_FILES_PER_UPLOAD = 20

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

    # Limit number of files per upload
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=422,
            detail=f"Too many files. Maximum {MAX_FILES_PER_UPLOAD} files per upload."
        )

    print(f"--- Uploading {len(files)} files for user {user_id} ---")
    results = []
    store_db_bool = store_db.lower() == "true"
    validate_bool = run_validation.lower() == "true"

    for file in files:
        try:
            # Validate file extension
            file_ext = os.path.splitext(file.filename or "")[1].lstrip(".").lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                results.append({
                    "filename": file.filename,
                    "status": "rejected",
                    "error": f"File type '.{file_ext}' not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}"
                })
                continue

            # Sanitize filename — strip path separators to prevent traversal
            safe_filename = os.path.basename(file.filename or "upload")
            print(f"Processing: {safe_filename}")
            file_path = os.path.join(UPLOAD_DIR, safe_filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            text = extract_text(file_path)

            # --- AI Validation (same routine as analyze/generate paths) ---
            validation = None
            if validate_bool and text.strip():
                try:
                    validation = run_resume_validation(
                        file_name=safe_filename,
                        file_type=file_ext,
                        extracted_text=text,
                        llm_config=llm_config
                    )
                    # If the validation graph itself errored, don't treat as valid classification
                    if validation.get("error"):
                        print(f"DEBUG: Validation graph errored for {safe_filename}: {validation.get('error')}")
                    else:
                        print(f"Validation complete: {safe_filename} -> {validation.get('classification', 'unknown')}")
                except Exception as e:
                    print(f"DEBUG: Validation failed for {safe_filename}: {e}")
                    validation = {"error": str(e)}

            # --- Store in DB (regardless of validation result) ---
            if store_db_bool:
                print(f"Storing in DB: {safe_filename}")
                store_resume(safe_filename, text, user_id, api_key=creds["openrouter_key"])

            # Quick text-based field presence check (no structured JSON needed)
            extracted_skills = extract_skills_from_text(text) if text.strip() else []
            text_field_check = {
                "skills_detected": len(extracted_skills),
                "skills_sample": extracted_skills[:10],
                "has_email": bool(re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)),
                "has_phone": bool(re.search(r'[\+\(]?[\d\s\-\(\)]{7,}', text)),
                "has_education_keywords": bool(re.search(
                    r'\b(university|college|bachelor|master|ph\.?d|degree|b\.?s\.?|m\.?s\.?|b\.?a\.?|m\.?b\.?a)\b',
                    text, re.IGNORECASE
                )),
                "has_experience_keywords": bool(re.search(
                    r'\b(experience|worked|employed|managed|led|developed|engineered)\b',
                    text, re.IGNORECASE
                )),
            }

            # --- Persist validation metadata ---
            if validation and not validation.get("error"):
                store_resume_validation(user_id, file.filename, validation)

            classification = (validation or {}).get("classification", "N/A")
            results.append({
                "filename": safe_filename,
                "status": "indexed",
                "validation": validation,
                "field_check": text_field_check,
            })
            safe_log_activity(user_id, "upload", safe_filename, 0, classification)

            print(f"Completed: {safe_filename}")
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


@router.get("")
async def list_resumes_all(
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
):
    """Return distinct resume filenames with role-based access.
    - jobseeker: only their own resumes
    - recruiter/manager: all resumes across all users, with uploader attribution
    """
    from services.db.lancedb_client import get_or_create_table, list_all_resumes_with_users
    try:
        if role in ("recruiter", "manager"):
            all_resumes = list_all_resumes_with_users()
            return {"resumes": [r["filename"] for r in all_resumes], "all_resumes": all_resumes}
        table = get_or_create_table()
        rows = table.search().where(f"user_id = '{user_id}'").to_list()
        seen = set()
        filenames = []
        for row in rows:
            fn = row.get("filename")
            if fn and fn not in seen:
                seen.add(fn)
                filenames.append(fn)
        return {"resumes": filenames}
    except Exception:
        return {"resumes": []}


@router.get("/{filename}/text")
async def get_resume_text(filename: str, user_id: str = Depends(get_current_user)):
    """Return extracted text for a resume file."""
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    text = extract_text(file_path)
    return {"filename": filename, "text": text}


class ResumeTextUpdate(BaseModel):
    text: str


class ResumeRename(BaseModel):
    new_filename: str


@router.put("/{filename}/text")
async def update_resume_text(
    filename: str,
    body: ResumeTextUpdate,
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    """Update extracted text for a resume and re-index in vector DB."""
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    from services.db.lancedb_client import update_resume_text as db_update
    try:
        db_update(filename, user_id, body.text, api_key=creds["openrouter_key"])
        return {"success": True, "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{filename}/rename")
async def rename_resume(
    filename: str,
    body: ResumeRename,
    user_id: str = Depends(get_current_user)
):
    """Rename a resume and propagate the change to all dependent data."""
    from services.db.lancedb_client import rename_resume as db_rename

    new_filename = body.new_filename.strip()
    if not new_filename:
        raise HTTPException(status_code=400, detail="New filename cannot be empty")
    if new_filename == filename:
        return {"success": True, "filename": new_filename}

    old_path = os.path.join(UPLOAD_DIR, filename)
    new_path = os.path.join(UPLOAD_DIR, new_filename)

    if os.path.exists(new_path):
        raise HTTPException(status_code=409, detail="A file with that name already exists")

    file_renamed = False
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        file_renamed = True

    try:
        db_rename(filename, new_filename, user_id)
    except Exception as e:
        if file_renamed:
            os.rename(new_path, old_path)
        raise HTTPException(status_code=500, detail=str(e))

    safe_log_activity(user_id, "rename", new_filename, 0, "N/A")
    return {"success": True, "filename": new_filename}


@router.get("/download/{filename}")
async def download_resume(filename: str):
    # Sanitize filename to prevent path traversal
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=safe_filename, media_type='application/octet-stream')


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
