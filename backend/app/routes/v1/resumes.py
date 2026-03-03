from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header, Depends
from fastapi.responses import FileResponse
from typing import List, Optional
import os
import shutil

from app.dependencies import get_current_user, resolve_credentials
from app.config import UPLOAD_DIR
from app.common import build_llm_config, safe_log_activity
from app.common import precheck_resume_validation
from services.resume_parser import extract_text
from services.db.lancedb_client import store_resume
from services.agent_controller import run_resume_validation

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "rtf"}
MAX_FILES_PER_UPLOAD = 20

router = APIRouter()


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

            classification = (validation or {}).get("classification", "N/A")
            results.append({
                "filename": safe_filename,
                "status": "indexed",
                "validation": validation
            })
            safe_log_activity(user_id, "upload", safe_filename, 0, classification)

            print(f"Completed: {safe_filename}")
        except Exception as e:
            print(f"Error processing {file.filename}: {e}")
            results.append({"filename": file.filename, "status": "error", "error": str(e)})

    return {"success": True, "processed": results}


@router.get("/download/{filename}")
async def download_resume(filename: str):
    # Sanitize filename to prevent path traversal
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=safe_filename, media_type='application/octet-stream')
