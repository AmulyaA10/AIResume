<<<<<<< HEAD
from pydantic import BaseModel, Field
from typing import Optional, List
=======
from pydantic import BaseModel
from typing import Optional
>>>>>>> 9d136502ee9374e86211849855e67746afb88872


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
<<<<<<< HEAD


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
=======
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
