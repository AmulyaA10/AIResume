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
