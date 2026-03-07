from pydantic import BaseModel, Field
from typing import Optional, List


class LoginRequest(BaseModel):
    username: str
    password: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)


class AnalyzeRequest(BaseModel):
    resume_text: str = Field(..., min_length=50)
    jd_text: Optional[str] = Field(None, min_length=10)
    threshold: Optional[int] = Field(75, ge=0, le=100)


class GenerateRequest(BaseModel):
    profile: str
    refinement_instructions: Optional[str] = None


class LinkedInScrapeRequest(BaseModel):
    """Request body for POST /linkedin/scrape."""
    query: str = Field(..., min_length=10)
    retry: Optional[bool] = False
    session_id: Optional[str] = None

class LinkedInParseRequest(BaseModel):
    """Request body for POST /linkedin/parse — raw profile text pasted by user."""
    profile_text: str = Field(..., min_length=100)


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

class JobCreate(BaseModel):
    title: str
    description: str
    employer_name: str
    employer_email: str = ""
    location_name: str = ""
    location_lat: float = 0.0
    location_lng: float = 0.0
    employment_type: str = "FULL_TIME"
    job_category: str = "IT"
    job_level: str = "MID"
    skills_required: List[str] = []
    salary_min: float = 0.0
    salary_max: float = 0.0
    benefits: List[str] = []
    application_url: str = ""
    metadata: str = "{}"


class JobResponse(JobCreate):
    job_id: str
    user_id: str
    posted_date: Optional[str] = None


class JobMatchResponse(BaseModel):
    score: float
    job: JobResponse


class JobSkillMatchResponse(BaseModel):
    score: float
    job: JobResponse
    matched_skills: List[str] = []
