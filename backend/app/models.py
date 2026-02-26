from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class SearchRequest(BaseModel):
    query: str


class AnalyzeRequest(BaseModel):
    resume_text: str
    jd_text: Optional[str] = None
    threshold: Optional[int] = 75


class GenerateRequest(BaseModel):
    profile: str


class UserSettingsUpdate(BaseModel):
    """Request body for PUT /user/settings — only non-None fields are updated."""
    openRouterKey: Optional[str] = None
    linkedinUser: Optional[str] = None
    linkedinPass: Optional[str] = None


class UserSettingsResponse(BaseModel):
    """Response body for GET /user/settings — credentials are masked."""
    openRouterKey: Optional[str] = None
    linkedinUser: Optional[str] = None
    linkedinPass: Optional[str] = None
    has_openRouterKey: bool = False
    has_linkedinUser: bool = False
    has_linkedinPass: bool = False
