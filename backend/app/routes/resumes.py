from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header, Depends
from fastapi.responses import FileResponse
from typing import List, Optional
import os
import shutil

from app.dependencies import get_current_user
from app.config import UPLOAD_DIR
from services.resume_parser import extract_text
from services.db.lancedb_client import store_resume, log_activity

router = APIRouter()


@router.post("/upload")
async def upload_resumes(
    files: List[UploadFile] = File(...),
    store_db: str = Form("true"),
    x_openrouter_key: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user)
):
    print(f"--- Uploading {len(files)} files for user {user_id} ---")
    results = []
    store_db_bool = store_db.lower() == "true"

    for file in files:
        try:
            print(f"Processing: {file.filename}")
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            text = extract_text(file_path)
            if store_db_bool:
                print(f"Storing in DB: {file.filename}")
                store_resume(file.filename, text, user_id, api_key=x_openrouter_key)

            results.append({"filename": file.filename, "status": "indexed"})
            # Log activity
            log_activity(user_id, "upload", file.filename, 0, "N/A")

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
