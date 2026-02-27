"""Unit tests for the resumes endpoints (upload / download)."""

import os
import io
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_upload_single_file_no_validation(app, auth_headers):
    """Upload a single PDF with validation disabled stores file and returns success."""
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake content")
    fake_pdf.name = "test_resume.pdf"

    with (
        patch("app.routes.v1.resumes.extract_text", return_value="Experienced Python developer..."),
        patch("app.routes.v1.resumes.store_resume") as mock_store,
        patch("app.routes.v1.resumes.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/resumes/upload",
                headers=auth_headers,
                files={"files": ("test_resume.pdf", fake_pdf, "application/pdf")},
                data={"store_db": "true", "validate": "false"},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["processed"]) == 1
    assert data["processed"][0]["filename"] == "test_resume.pdf"
    assert data["processed"][0]["status"] == "indexed"
    mock_store.assert_called_once()


@pytest.mark.asyncio
async def test_upload_with_validation(app, auth_headers, mock_validation_result):
    """Upload with validation=true triggers the validation agent."""
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake content")

    with (
        patch("app.routes.v1.resumes.extract_text", return_value="JOHN DOE\nSenior Engineer..."),
        patch("app.routes.v1.resumes.store_resume"),
        patch("app.routes.v1.resumes.safe_log_activity"),
        patch("app.routes.v1.resumes.run_resume_validation", return_value=mock_validation_result) as mock_val,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/resumes/upload",
                headers=auth_headers,
                files={"files": ("resume.pdf", fake_pdf, "application/pdf")},
                data={"store_db": "true", "validate": "true"},
            )
    assert resp.status_code == 200
    result = resp.json()["processed"][0]
    assert result["validation"] is not None
    assert result["validation"]["classification"] == "resume_valid_good"
    mock_val.assert_called_once()


@pytest.mark.asyncio
async def test_upload_skip_storage(app, auth_headers):
    """Upload with store_db=false should NOT call store_resume."""
    fake_pdf = io.BytesIO(b"%PDF-1.4 fake")

    with (
        patch("app.routes.v1.resumes.extract_text", return_value="Some text"),
        patch("app.routes.v1.resumes.store_resume") as mock_store,
        patch("app.routes.v1.resumes.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/resumes/upload",
                headers=auth_headers,
                files={"files": ("resume.pdf", fake_pdf, "application/pdf")},
                data={"store_db": "false", "validate": "false"},
            )
    assert resp.status_code == 200
    mock_store.assert_not_called()


@pytest.mark.asyncio
async def test_upload_multiple_files(app, auth_headers):
    """Upload multiple files processes each one."""
    files = [
        ("files", ("a.pdf", io.BytesIO(b"%PDF"), "application/pdf")),
        ("files", ("b.docx", io.BytesIO(b"PK"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
    ]

    with (
        patch("app.routes.v1.resumes.extract_text", return_value="Resume text"),
        patch("app.routes.v1.resumes.store_resume"),
        patch("app.routes.v1.resumes.safe_log_activity"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/resumes/upload",
                headers=auth_headers,
                files=files,
                data={"store_db": "true", "validate": "false"},
            )
    assert resp.status_code == 200
    assert len(resp.json()["processed"]) == 2


@pytest.mark.asyncio
async def test_download_nonexistent_file(app, auth_headers):
    """GET /api/v1/resumes/download/<missing> returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/resumes/download/nonexistent.pdf", headers=auth_headers)
    assert resp.status_code == 404
