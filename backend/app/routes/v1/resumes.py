from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header, Depends
from fastapi.responses import FileResponse
from typing import List, Optional
import os
import shutil

from app.dependencies import get_current_user
from app.config import UPLOAD_DIR
from app.common import build_llm_config, safe_log_activity
from services.resume_parser import extract_text
from services.db.lancedb_client import store_resume
from services.agent_controller import run_resume_validation

router = APIRouter()


@router.post("/upload")
async def upload_resumes(
    files: List[UploadFile] = File(...),
    store_db: str = Form("true"),
    validate: str = Form("true"),
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    print(f"--- Uploading {len(files)} files for user {user_id} ---")
    results = []
    store_db_bool = store_db.lower() == "true"
    validate_bool = validate.lower() == "true"

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
                    llm_config = build_llm_config(x_openrouter_key, x_llm_model)
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
                store_resume(file.filename, text, user_id, api_key=x_openrouter_key)

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


@router.get("/download/{filename}")
async def download_resume(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')
