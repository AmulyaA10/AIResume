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


_REGION_KEYWORDS: list[tuple[str, list[str]]] = [
    ("United Kingdom", ["united kingdom", " uk", "england", "london", "manchester", "birmingham", "scotland", "wales"]),
    ("Canada", ["canada", "toronto", "vancouver", "montreal", "calgary", "ontario", "british columbia"]),
    ("India", ["india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai", "pune", "kolkata"]),
    ("Europe", ["europe", "germany", "france", "spain", "italy", "netherlands", "sweden", "norway", "denmark", "finland", "switzerland", "austria", "poland", "berlin", "paris", "amsterdam", "stockholm", "madrid", "rome", "barcelona", "munich", "dublin", "ireland", "portugal", "belgium", "czech"]),
    ("Australia / NZ", ["australia", "new zealand", "sydney", "melbourne", "brisbane", "auckland", "perth"]),
    ("Asia Pacific", ["singapore", "japan", "china", "hong kong", "south korea", "taiwan", "vietnam", "thailand", "malaysia", "philippines", "indonesia", "tokyo", "beijing", "shanghai"]),
    ("Middle East / Africa", ["dubai", "uae", "saudi", "israel", "south africa", "nigeria", "kenya", "egypt", "qatar", "bahrain"]),
    ("Latin America", ["brazil", "mexico", "argentina", "colombia", "chile", "peru", "bogota", "sao paulo"]),
]

_US_STATE_CODES: frozenset[str] = frozenset({
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
})

_NOISE_LOCATIONS: frozenset[str] = frozenset({
    "not specified", "n/a", "na", "none", "unknown", "not available",
    "unspecified", "tbd",
})

# Metro / "Greater" area aliases → canonical "City, ST"
_METRO_ALIASES: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\blos angeles\b.*(?:metro|area|region|county)', re.I), "Los Angeles, CA"),
    (re.compile(r'\bgreater\s+los\s+angeles\b', re.I),                   "Los Angeles, CA"),
    (re.compile(r'\bgreater\s+new\s+york\b', re.I),                      "New York, NY"),
    (re.compile(r'\bnew\s+york\b.*(?:metro|area|region)', re.I),         "New York, NY"),
    (re.compile(r'\bgreater\s+san\s+francisco\b', re.I),                 "San Francisco, CA"),
    (re.compile(r'\bsan\s+francisco\s+bay\s+area\b', re.I),              "San Francisco, CA"),
    (re.compile(r'\bgreater\s+seattle\b', re.I),                         "Seattle, WA"),
    (re.compile(r'\bgreater\s+boston\b', re.I),                          "Boston, MA"),
    (re.compile(r'\bgreater\s+chicago\b', re.I),                         "Chicago, IL"),
    (re.compile(r'\bgreater\s+washington\b', re.I),                      "Washington, DC"),
    (re.compile(r'\bgreater\s+miami\b', re.I),                           "Miami, FL"),
    (re.compile(r'\bgreater\s+atlanta\b', re.I),                         "Atlanta, GA"),
    (re.compile(r'\bgreater\s+dallas\b', re.I),                          "Dallas, TX"),
    (re.compile(r'\bgreater\s+houston\b', re.I),                         "Houston, TX"),
    (re.compile(r'\bgreater\s+austin\b', re.I),                          "Austin, TX"),
    (re.compile(r'\bgreater\s+denver\b', re.I),                          "Denver, CO"),
    (re.compile(r'\bgreater\s+phoenix\b', re.I),                         "Phoenix, AZ"),
    (re.compile(r'\bgreater\s+london\b', re.I),                          "London, UK"),
    (re.compile(r'\bgreater\s+toronto\b', re.I),                         "Toronto, Canada"),
    (re.compile(r'\bgreater\s+sydney\b', re.I),                          "Sydney, Australia"),
    (re.compile(r'\bgreater\s+bangalore\b', re.I),                       "Bangalore, India"),

    # ── Bangalore sub-areas / spellings ─────────────────────────────────────
    # Neighborhoods: Koramangala, Whitefield, HSR Layout, Indiranagar, etc.
    (re.compile(r'\b(koramangala|whitefield|electronic\s+city|hsr\s+layout|'
                r'indiranagar|marathahalli|hebbal|jp\s+nagar|jayanagar|'
                r'bannerghatta|sarjapur|btm\s+layout|malleswaram|'
                r'rajajinagar|yeshwanthpur|yelahanka)\b', re.I),           "Bangalore, India"),
    # Variant spellings and state-level
    (re.compile(r'\bbengaluru\b', re.I),                                  "Bangalore, India"),
    (re.compile(r'\bkarnataka\b', re.I),                                  "Bangalore, India"),

    # ── Hyderabad sub-areas ──────────────────────────────────────────────────
    (re.compile(r'\b(gachibowli|hitech\s+city|hitec\s+city|madhapur|'
                r'secunderabad|banjara\s+hills|jubilee\s+hills|'
                r'kondapur|miyapur|kukatpally|manikonda)\b', re.I),        "Hyderabad, India"),
    (re.compile(r'\btelangana\b', re.I),                                  "Hyderabad, India"),

    # ── Mumbai / Pune sub-areas ──────────────────────────────────────────────
    (re.compile(r'\b(bandra|andheri|powai|thane|navi\s+mumbai|'
                r'worli|lower\s+parel|goregaon|malad|borivali)\b', re.I), "Mumbai, India"),
    (re.compile(r'\bpune\b', re.I),                                       "Pune, India"),
    (re.compile(r'\b(hinjewadi|kharadi|baner|wakad|viman\s+nagar|'
                r'hadapsar|pune\s+cantonment)\b', re.I),                   "Pune, India"),
    (re.compile(r'\bmaharashtra\b', re.I),                                "Mumbai, India"),

    # ── Delhi NCR sub-areas ──────────────────────────────────────────────────
    (re.compile(r'\b(gurgaon|gurugram|faridabad|ghaziabad)\b', re.I),    "Gurugram, India"),
    (re.compile(r'\bnoida\b', re.I),                                      "Noida, India"),
    (re.compile(r'\b(haryana|uttar\s+pradesh)\b', re.I),                  "New Delhi, India"),

    # ── Chennai sub-areas ────────────────────────────────────────────────────
    (re.compile(r'\b(anna\s+nagar|adyar|velachery|perambur|tambaram|'
                r'sholinganallur|omr|old\s+mahabalipuram)\b', re.I),      "Chennai, India"),
    (re.compile(r'\btamil\s+nadu\b', re.I),                               "Chennai, India"),

    # ── London variants ──────────────────────────────────────────────────────
    (re.compile(r'\b(england|great\s+britain|united\s+kingdom)\b', re.I), "London, UK"),
    (re.compile(r'\b(canary\s+wharf|shoreditch|islington|hackney|'
                r'brixton|croydon|wimbledon|richmond)\b', re.I),           "London, UK"),
]


def _normalize_location(raw: str) -> Optional[str]:
    """Normalize a raw LLM-extracted location to a clean canonical string."""
    if not raw:
        return None
    loc = raw.strip()
    if not loc or loc.lower() in _NOISE_LOCATIONS:
        return None
    # Remote: any mention of "remote" collapses to just "Remote"
    if re.search(r'\bremote\b', loc, re.IGNORECASE):
        return "Remote"
    # Strip work-mode prefixes: "Hybrid — ", "On-site — ", "On-site or Hybrid — ", etc.
    loc = re.sub(
        r'^(?:hybrid|on-?site|on-?site\s+or\s+hybrid|in-?office)\s*[-—–]\s*',
        '', loc, flags=re.IGNORECASE
    ).strip()
    # Strip parenthetical suffixes: "(hybrid)", "(Manhattan)", "(on-site or hybrid)", "(2 days in office)", etc.
    loc = re.sub(r'\s*\([^)]+\)', '', loc, flags=re.IGNORECASE).strip()
    # Strip trailing punctuation / dashes left over
    loc = loc.rstrip(' ,;-—').strip()
    if not loc or loc.lower() in _NOISE_LOCATIONS:
        return None
    # Metro / Greater area → canonical city
    for pattern, canonical in _METRO_ALIASES:
        if pattern.search(loc):
            return canonical
    # Title-case if entirely lowercase (e.g. "austin" → "Austin")
    if loc == loc.lower():
        loc = loc.title()
    # Trim overly verbose strings (> 40 chars are free-text, not a location)
    if len(loc) > 40:
        parts = [p.strip() for p in loc.split(",")]
        loc = ", ".join(parts[:2]) if len(parts) >= 2 else parts[0]
    return loc or None


def _classify_region(location: str) -> str:
    """Map a location string to a region bucket.

    Priority:
    1. Remote
    2. US state code detection (covers any 'City, ST' not in keyword list)
    3. Keyword matching for international regions
    """
    if re.search(r'\bremote\b', location, re.IGNORECASE):
        return "Remote"
    # Detect US state code: "City, ST" or "City, ST, USA"
    state_match = re.search(r',\s*([A-Z]{2})\b', location)
    if state_match and state_match.group(1) in _US_STATE_CODES:
        return "United States"
    # Keyword matching for international
    loc_lower = location.lower()
    for region, keywords in _REGION_KEYWORDS:
        if any(kw.strip() in loc_lower for kw in keywords):
            return region
    # Fallback: if "united states" or "usa" anywhere
    if any(kw in loc_lower for kw in ("united states", " usa", "u.s.")):
        return "United States"
    return "Other"


# ---------------------------------------------------------------------------
# Query-time location signal extraction
# ---------------------------------------------------------------------------

# Location keyword → list of city/country fragments to match against stored location strings
_QUERY_LOCATION_SIGNALS: list[tuple[list[str], list[str]]] = [
    # (query keywords,  stored location keywords to match)
    (["bay area", "san francisco", "sf bay", "silicon valley", "palo alto", "mountain view",
      "sunnyvale", "san jose", "santa clara", "foster city", "menlo park"],
     ["san francisco", "palo alto", "mountain view", "sunnyvale", "san jose", "santa clara",
      "foster city", "menlo park", "oakland", "berkeley"]),

    (["new york", "nyc", "manhattan", "brooklyn", "queens", "bronx", "jersey city", "hoboken"],
     ["new york", "manhattan", "brooklyn", "queens", "bronx", "jersey city", "hoboken"]),

    (["seattle", "bellevue", "redmond", "kirkland"],
     ["seattle", "bellevue", "redmond", "kirkland"]),

    (["austin", "round rock"],
     ["austin", "round rock"]),

    (["london", "uk", "england"],
     ["london", "england", "united kingdom"]),

    (["berlin", "germany", "munich", "hamburg"],
     ["berlin", "germany", "munich", "hamburg"]),

    (["bangalore", "bengaluru", "koramangala", "whitefield", "electronic city",
      "indiranagar", "hsr layout"],
     ["bangalore", "bengaluru", "karnataka"]),

    (["hyderabad", "gachibowli", "hitec city"],
     ["hyderabad", "telangana"]),

    (["mumbai", "pune", "thane"],
     ["mumbai", "pune", "thane", "maharashtra"]),

    (["chennai", "madras"],
     ["chennai", "tamil"]),

    (["delhi", "noida", "gurgaon", "gurugram", "ncr"],
     ["delhi", "noida", "gurugram", "gurgaon", "haryana"]),

    (["india"],
     ["india"]),

    (["singapore"],
     ["singapore"]),

    (["toronto", "canada"],
     ["toronto", "canada"]),

    (["remote"],
     ["remote"]),
]

# Preposition + location stop-phrases to strip from query for semantic search
_LOCATION_STRIP_PATTERNS = [
    re.compile(r'\b(?:from|in|based in|located in|near|around|at)\s+', re.I),
    re.compile(r'\b(?:bay area|san francisco|silicon valley|palo alto|mountain view|sunnyvale|san jose)\b', re.I),
    re.compile(r'\b(?:new york|nyc|manhattan|brooklyn|jersey city)\b', re.I),
    re.compile(r'\b(?:seattle|bellevue|redmond)\b', re.I),
    re.compile(r'\b(?:london|england|berlin|germany)\b', re.I),
    re.compile(r'\b(?:bangalore|bengaluru|hyderabad|mumbai|chennai|delhi|noida|gurugram|india)\b', re.I),
    re.compile(r'\b(?:singapore|toronto|canada|remote)\b', re.I),
    re.compile(r'\b(?:austin|texas|tx)\b', re.I),
    re.compile(r'\b(?:candidate[s]?|developer[s]?|engineer[s]?)\b', re.I),  # generic noise in location queries
]


# ---------------------------------------------------------------------------
# Query-time exp_level signal extraction
# ---------------------------------------------------------------------------
_QUERY_EXP_SIGNALS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\b(c-suite|c\s+suite|ceo|cto|cfo|coo|vp\s+of|vice\s+president|chief\s+\w+\s+officer|executive)\b', re.I), "Executive"),
    (re.compile(r'\b(principal|staff\s+engineer|tech\s+lead|team\s+lead|engineering\s+lead|lead\s+(engineer|developer|architect))\b', re.I), "Lead"),
    (re.compile(r'\b(senior|sr\.?)\b', re.I), "Senior"),
    (re.compile(r'\b(mid.?level|mid\s+level|intermediate)\b', re.I), "Mid-level"),
    (re.compile(r'\b(junior|jr\.?)\b', re.I), "Junior"),
    (re.compile(r'\b(entry.?level|entry\s+level|fresh(er|man|graduate)|new\s+grad|graduate)\b', re.I), "Entry"),
]

_EXP_STRIP_RE = re.compile(
    r'\b(executive|c-suite|senior|sr\.?|junior|jr\.?|mid.?level|entry.?level|'
    r'lead|principal|staff\s+engineer|fresher|new\s+grad|'
    r'level\s+candidate|level\s+engineer|level\s+developer)\b', re.I
)


def _parse_exp_level_from_query(query: str) -> Optional[str]:
    """Extract an exp_level value from a natural language query, or None."""
    for pattern, level in _QUERY_EXP_SIGNALS:
        if pattern.search(query):
            return level
    return None


# Regex to extract a raw location phrase from natural language queries.
# Matches text after prepositions like "from", "in", "based in", "located in", "near".
# Stops at sentence-end or connectors like "who", "with", "and", "having".
_RE_LOC_EXTRACT = re.compile(
    r'\b(?:from|in|based\s+in|located\s+in|near|around)\s+'
    r'([A-Za-z][A-Za-z\s\.,]{1,40}?)'
    r'(?=\s*(?:who|with|that|having|and\s+|\Z|$))',
    re.IGNORECASE,
)


def _parse_location_from_query(query: str) -> tuple[list[str], str]:
    """
    Extract location signals from a natural language search query.
    Returns (location_keywords_to_match, cleaned_query_for_semantic_search).

    Two-pass:
    1. Static alias map — handles multi-word aliases like "bay area" → SF city list.
    2. Regex fallback — extracts raw location phrase for any city not in the map.

    e.g. "Python developer from bay area"   → (["san francisco", ...], "Python developer")
         "candidate from Atlanta, GA"        → (["atlanta"], "candidate")
         "senior dev in Chicago"             → (["chicago"], "senior dev")
    """
    q_lower = query.lower()
    matched_loc_keywords: list[str] = []
    loc_phrase_extracted: str = ""

    # Pass 1: static alias map
    for query_kws, loc_match_kws in _QUERY_LOCATION_SIGNALS:
        for kw in query_kws:
            if kw in q_lower:
                matched_loc_keywords = loc_match_kws
                break
        if matched_loc_keywords:
            break

    # Pass 2: generic regex extraction (any city not covered by the static map)
    if not matched_loc_keywords:
        m = _RE_LOC_EXTRACT.search(query)
        if m:
            loc_phrase_extracted = m.group(1).strip().rstrip(",. ")
            # Build match keywords: individual tokens (words ≥ 3 chars), lowercased
            matched_loc_keywords = [
                t.lower() for t in re.split(r'[\s,]+', loc_phrase_extracted)
                if len(t) >= 3 and t.upper() not in {
                    "THE", "AND", "FOR", "WITH", "FROM", "NEAR",
                }
            ]

    # Build a cleaned query by stripping location terms (for better semantic search)
    cleaned = query
    if matched_loc_keywords:
        for pat in _LOCATION_STRIP_PATTERNS:
            cleaned = pat.sub(' ', cleaned)
        # Also strip the raw extracted phrase if present
        if loc_phrase_extracted:
            cleaned = re.sub(re.escape(loc_phrase_extracted), ' ', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
        if len(cleaned) < 3:
            cleaned = query  # fallback: don't over-strip

    return matched_loc_keywords, cleaned


@router.get("/locations")
async def get_resume_locations(
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
):
    """Return candidate locations read directly from resume_meta DB — no cache needed."""
    from services.db.lancedb_client import get_or_create_resume_meta_table
    is_recruiter = role in ("recruiter", "manager")
    try:
        df = get_or_create_resume_meta_table().to_pandas()
        if not is_recruiter:
            df = df[df["user_id"] == user_id]
        groups: Dict[str, list] = {}
        seen: set = set()
        for raw_loc in df["location"].dropna():
            loc = _normalize_location(str(raw_loc))
            if not loc or loc in seen:
                continue
            seen.add(loc)
            region = _classify_region(loc)
            groups.setdefault(region, []).append({"value": loc, "label": loc})
        for region in groups:
            groups[region].sort(key=lambda x: x["label"])
        return {"groups": groups, "total": len(seen)}
    except Exception as e:
        print(f"DEBUG: [locations] DB read failed: {e}")
        return {"groups": {}, "total": 0}


_VALID_EXP_LEVELS = {"Entry", "Junior", "Mid-level", "Senior", "Lead", "Executive"}

# Normalize legacy stored values → current canonical values
_EXP_LEVEL_ALIASES: dict[str, str] = {
    "entry level": "Entry",
    "entry-level": "Entry",
    "mid level":   "Mid-level",
    "mid-level":   "Mid-level",
    "mid":         "Mid-level",
    "lead/principal": "Lead",
    "principal":   "Lead",
    "senior":      "Senior",
    "junior":      "Junior",
    "entry":       "Entry",
    "lead":        "Lead",
    "executive":   "Executive",
}

def _normalize_exp_level(raw: str | None) -> str | None:
    if not raw:
        return None
    return _EXP_LEVEL_ALIASES.get(raw.strip().lower()) or next(
        (v for v in _VALID_EXP_LEVELS if v.lower() == raw.strip().lower()), None
    )
_VALID_INDUSTRIES = {
    "Technology", "Finance", "Healthcare", "Education", "Marketing",
    "Engineering", "Legal", "Sales", "Operations", "Design", "Other",
}


def _ai_normalize_location(raw: str, llm_config: dict = None) -> str:
    """
    Use an LLM to canonicalize a location string to city-level format.
    Returns the normalized string, or the original if the LLM call fails.

    Called only when the location looks like it contains sub-areas
    (e.g. 3+ comma-separated parts, or known neighborhood/district patterns).
    """
    if not raw or raw.strip().lower() in ("remote", ""):
        return raw

    loc = raw.strip()

    # Only invoke AI when the location looks sub-city (3+ parts, or contains known suburb markers)
    parts = [p.strip() for p in loc.split(",")]
    _SUBURB_HINTS = re.compile(
        r'\b(layout|nagar|puram|pur|city|district|ward|sector|colony|'
        r'township|heights|hills|gardens|park|village|area|zone|'
        r'county|borough|township|quarters)\b', re.IGNORECASE
    )
    needs_ai = len(parts) >= 3 or bool(_SUBURB_HINTS.search(loc))
    if not needs_ai:
        return loc

    try:
        from services.ai.common.llm_factory import get_llm
        prompt = (
            "Normalize the following location to a clean canonical city-level format.\n"
            "Rules:\n"
            "- US: return 'City, ST' with 2-letter state code, e.g. 'San Francisco, CA'\n"
            "- International: return 'City, Country' only — no state, province, or district, "
            "e.g. 'Bangalore, India', 'London, UK', 'Toronto, Canada'\n"
            "- Never include neighborhoods, districts, sub-areas, or postal codes\n"
            "- Standardize common variants: Bengaluru → Bangalore, New York City → New York, NY\n"
            "- If already canonical (e.g. 'Austin, TX'), return as-is\n"
            "Return ONLY the normalized location string. No explanation, no quotes.\n\n"
            f"Location: {raw}"
        )
        llm = get_llm(llm_config or {}, temperature=0)
        response = llm.invoke(prompt)
        result = response.content.strip().strip('"').strip("'")
        if result and len(result) < 80:
            print(f"DEBUG: [location-ai] '{raw}' → '{result}'")
            return result
    except Exception as e:
        print(f"DEBUG: [location-ai] failed for '{raw}': {e}")

    return raw


def _clean_metadata(meta: dict, llm_config: dict = None) -> dict:
    """Normalize and validate LLM-extracted candidate metadata before storage."""
    if not meta:
        return {}
    cleaned = {}

    name = str(meta.get("candidate_name") or "").strip().title()
    cleaned["candidate_name"] = name if len(name) > 1 else None

    company = str(meta.get("current_company") or "").strip()
    cleaned["current_company"] = company if company and company.lower() not in ("n/a", "none", "unknown") else None

    raw_loc = str(meta.get("location") or "")
    normalized_loc = _normalize_location(raw_loc)
    # AI safety net: canonicalize any sub-neighborhood location the regex missed
    if normalized_loc:
        normalized_loc = _ai_normalize_location(normalized_loc, llm_config)
    cleaned["location"] = normalized_loc

    # Normalize phone — strip non-phone chars, format, extract extension
    phone_raw = re.sub(r'[^\d\s\+\-\(\)\.extEXT]', '', str(meta.get("phone") or "")).strip()
    # Extract extension before stripping
    ext_match = re.search(r'[eE]xt?\.?\s*(\d{2,6})', phone_raw)
    ext_suffix = f" ext. {ext_match.group(1)}" if ext_match else ""
    if ext_match:
        phone_raw = phone_raw[:ext_match.start()].strip()
    if re.search(r'\d{7,}', phone_raw.replace(" ", "")):
        digits_only = re.sub(r'\D', '', phone_raw)
        # Infer country code from location for formatting
        _loc = str(meta.get("location") or "").lower()
        _INTL = {"united kingdom": "+44", "uk": "+44", "england": "+44", "scotland": "+44",
                 "wales": "+44", "india": "+91", "australia": "+61", "germany": "+49",
                 "france": "+33", "netherlands": "+31", "singapore": "+65",
                 "new zealand": "+64", "ireland": "+353", "pakistan": "+92",
                 "uae": "+971", "dubai": "+971", "philippines": "+63",
                 "brazil": "+55", "mexico": "+52", "south africa": "+27"}
        cc = next((code for kw, code in _INTL.items() if kw in _loc), "+1")
        if len(digits_only) == 10:
            phone_raw = f"{cc} ({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
        elif len(digits_only) == 11 and digits_only[0] == '1':
            phone_raw = f"+1 ({digits_only[1:4]}) {digits_only[4:7]}-{digits_only[7:]}"
        # else keep as-is (international with country code already present)
        cleaned["phone"] = phone_raw + ext_suffix
    else:
        cleaned["phone"] = None

    email = str(meta.get("email") or "").strip().lower()
    cleaned["email"] = email if re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email) else None

    def _clean_profile_url(raw: str, keywords: list[str]) -> str | None:
        raw = str(raw or "").strip()
        if not raw or raw.lower() in ("n/a", "none", "unknown"):
            return None
        # Accept bare handle (e.g. "janesmith") only if it contains a keyword path
        if any(kw in raw.lower() for kw in keywords):
            return raw
        return None

    cleaned["linkedin_url"] = _clean_profile_url(meta.get("linkedin_url"), ["linkedin"])
    cleaned["github_url"]   = _clean_profile_url(meta.get("github_url"),   ["github"])

    industry_raw = str(meta.get("industry") or "").strip()
    industry = next((v for v in _VALID_INDUSTRIES if v.lower() == industry_raw.lower()), None)
    cleaned["industry"] = industry

    role = str(meta.get("role") or "").strip()
    # Title-case role but preserve all-caps acronyms (e.g. "CTO", "CEO")
    role = " ".join(w if w.isupper() and len(w) <= 5 else w.capitalize() for w in role.split())
    cleaned["role"] = role if 2 < len(role) < 80 else None

    cleaned["exp_level"] = _normalize_exp_level(str(meta.get("exp_level") or ""))

    _VALID_LEVELS = {"Expert", "Advanced", "Intermediate", "Beginner"}
    skills_raw = meta.get("skills") or []
    cleaned_skills = []
    if isinstance(skills_raw, list):
        for s in skills_raw[:8]:
            if isinstance(s, dict):
                name = str(s.get("name") or "").strip()
                level = str(s.get("level") or "").strip()
                level = next((v for v in _VALID_LEVELS if v.lower() == level.lower()), None)
                if name:
                    cleaned_skills.append({"name": name, "level": level})
            elif isinstance(s, str) and s.strip():
                cleaned_skills.append({"name": s.strip(), "level": None})
    cleaned["skills"] = cleaned_skills

    summary = str(meta.get("summary") or "").strip()
    cleaned["summary"] = summary if 10 < len(summary) < 500 else None

    try:
        yoe = int(meta.get("years_experience") or 0)
        cleaned["years_experience"] = str(yoe) if 0 < yoe < 60 else None
    except (ValueError, TypeError):
        cleaned["years_experience"] = None

    education = str(meta.get("education") or "").strip()
    cleaned["education"] = education if 5 < len(education) < 200 else None

    certs_raw = meta.get("certifications") or []
    if isinstance(certs_raw, list):
        cleaned["certifications"] = [str(c).strip() for c in certs_raw if str(c).strip()][:10]
    else:
        cleaned["certifications"] = []

    return cleaned


def _llm_classify_batch(
    snippets: list[tuple[str, str]],
    llm_config: Optional[dict],
) -> dict[str, dict]:
    """
    LLM call: given [(filename, text_snippet), …] return
    {filename: {industry, role, exp_level, candidate_name, skills}}.
    Falls back to {} on any error.
    """
    import json as _json
    from services.ai.common.llm_factory import get_llm
    if not snippets:
        return {}
    payload = "\n---\n".join(
        f"[{fn}]\n{text[:2500]}" for fn, text in snippets
    )
    prompt = (
        "You are a resume classifier. For each resume snippet, extract these fields:\n"
        "  candidate_name: full name of the person, e.g. 'Jane Smith'\n"
        "  current_company: most recent employer name, e.g. 'Google', 'Acme Corp'\n"
        "  location: canonical city-level location only — NEVER include neighborhoods, districts, or sub-areas. "
        "Format: 'City, ST' for US (2-letter state code, e.g. 'Seattle, WA', 'Atlanta, GA'), "
        "'City, Country' for international (e.g. 'London, UK', 'Bangalore, India', 'Toronto, Canada'), "
        "or 'Remote'. "
        "Examples of what NOT to do: 'Koramangala, Bangalore' → use 'Bangalore, India'; "
        "'Whitefield, Bangalore, India' → use 'Bangalore, India'; "
        "'Hyderabad, Telangana, India' → use 'Hyderabad, India'; "
        "'New York City, New York, USA' → use 'New York, NY'. "
        "Do NOT include timezone, state/province for international cities, or work preferences.\n"
        "  phone: candidate phone number if present, e.g. '+1 415-555-0123'\n"
        "  email: candidate email address if present, e.g. 'jane@example.com'\n"
        "  linkedin_url: LinkedIn profile URL or handle if present, e.g. 'linkedin.com/in/janesmith'\n"
        "  github_url: GitHub profile URL or handle if present, e.g. 'github.com/janesmith'\n"
        "  industry: one of Technology, Finance, Healthcare, Education, Marketing, "
        "Engineering, Legal, Sales, Operations, Design, Other\n"
        "  role: concise job title of the most recent/primary position, e.g. 'Software Engineer', "
        "'Data Scientist', 'Product Manager', 'UX Designer', 'DevOps Engineer'\n"
        "  exp_level: overall career seniority — one of: Entry, Junior, Mid-level, Senior, Lead, Executive. "
        "Use total years of experience and role titles as signals. "
        "Entry=0-1yr, Junior=1-3yr, Mid-level=3-6yr, Senior=6-10yr, Lead=people/tech lead or principal, Executive=VP/Director/C-suite.\n"
        "  skills: top 6 domain-relevant skills as a JSON array of objects {name, level}. "
        "Choose skills that define the candidate's work domain (e.g. programming languages, frameworks, tools, methodologies). "
        "Level must be one of: Expert, Advanced, Intermediate, Beginner — infer rigorously from the resume text:\n"
        "    Expert: 8+ years with the skill, explicitly described as deep expertise, leads/architects using it, "
        "mentors others, wrote about it (publications/talks/patents), or it appears as a primary skill in multiple senior roles.\n"
        "    Advanced: 4-8 years, proficient and used in complex/senior projects, appears consistently across roles.\n"
        "    Intermediate: 2-4 years, used regularly in projects but not as a primary differentiator.\n"
        "    Beginner: <2 years, listed as familiar/learning, or appears briefly in one role as a secondary tool.\n"
        "e.g. [{\"name\": \"Python\", \"level\": \"Expert\"}, {\"name\": \"React\", \"level\": \"Intermediate\"}]\n"
        "  summary: 1-2 sentence professional headline capturing the candidate's domain and standout value, e.g. "
        "'Senior data engineer with 9 years building real-time pipelines at scale. Expert in Kafka and Spark.'\n"
        "  years_experience: total years of professional work experience as an integer, e.g. 11\n"
        "  education: highest academic degree and institution, e.g. 'M.S. Computer Science, Stanford University (2018)'. "
        "Include graduation year if present. Omit if no degree found.\n"
        "  certifications: list of professional certifications as a JSON array of strings, e.g. "
        "[\"AWS Solutions Architect\", \"PMP\", \"CKA\"]. Include only formal certs, not courses.\n"
        "Return ONLY a JSON object: "
        "{\"filename\": {\"candidate_name\": \"...\", \"current_company\": \"...\", \"location\": \"...\", \"phone\": \"...\", \"email\": \"...\", \"linkedin_url\": \"...\", \"github_url\": \"...\", \"industry\": \"...\", \"role\": \"...\", \"exp_level\": \"...\", \"summary\": \"...\", \"years_experience\": 5, \"education\": \"...\", \"certifications\": [...], \"skills\": [...]}}. "
        "Omit the key if you cannot determine the value. JSON only, no explanation.\n\n"
        + payload
    )
    try:
        llm = get_llm(llm_config, temperature=0)
        response = llm.invoke(prompt)
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return _json.loads(content.strip())
    except Exception as e:
        print(f"DEBUG: [classify] LLM batch failed: {e}")
        return {}


@router.get("/filter-options")
async def get_filter_options(
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
):
    """Return unique industries, roles and exp levels read directly from resume_meta DB."""
    from services.db.lancedb_client import get_or_create_resume_meta_table
    is_recruiter = role in ("recruiter", "manager")
    try:
        df = get_or_create_resume_meta_table().to_pandas()
        if not is_recruiter:
            df = df[df["user_id"] == user_id]
        industries = sorted(set(str(v).strip() for v in df["industry"].dropna() if str(v).strip()))
        roles = sorted(set(str(v).strip() for v in df["role"].dropna() if str(v).strip()))
        all_exp = set(str(v).strip() for v in df["exp_level"].dropna() if str(v).strip())
        ordered = ["Entry", "Junior", "Mid-level", "Senior", "Lead", "Executive"]
        exp_levels = [e for e in ordered if e in all_exp]
        return {"industries": industries, "roles": roles, "exp_levels": exp_levels}
    except Exception as e:
        print(f"DEBUG: [filter-options] DB read failed: {e}")
        return {"industries": [], "roles": [], "exp_levels": []}


@router.get("/database")
async def get_resume_database(
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    classification: Optional[str] = None,
    date_range: Optional[int] = None,
    location: Optional[str] = None,
    industry: Optional[str] = None,
    role: Optional[str] = None,
    exp_level: Optional[str] = None,
    applied: Optional[str] = None,
    user_id: str = Depends(get_current_user),
    current_role: str = Depends(get_user_role),
):
    """Return resumes with validation metadata, with optional search/filter."""
    import json
    from datetime import datetime, timedelta
    from services.db.lancedb_client import (
        list_all_resumes_with_users, get_or_create_resume_meta_table,
        search_resumes_semantic,
    )
    is_recruiter = current_role in ("recruiter", "manager")

    # 1. Load validation metadata once (1 row per resume, much smaller than chunk table)
    meta_table = get_or_create_resume_meta_table()
    try:
        meta_df = meta_table.to_pandas()
    except Exception:
        meta_df = None

    def _parse_certs(raw) -> list:
        try:
            if raw and str(raw).strip() not in ("", "nan", "None"):
                return json.loads(raw)
        except Exception:
            pass
        return []

    def _build_meta_lookup(df) -> Dict[str, Dict[str, Any]]:
        lookup: Dict[str, Dict[str, Any]] = {}
        if df is None or getattr(df, "empty", True):
            return lookup

        scoped_df = df if is_recruiter else df[df["user_id"] == user_id]
        if scoped_df.empty:
            return lookup

        try:
            scoped_df = scoped_df.sort_values(by="uploaded_at", ascending=False)
        except Exception:
            pass

        for _, row in scoped_df.iterrows():
            fn = str(row.get("filename") or "")
            if not fn or fn in lookup:
                continue

            def _str(v):
                """Return None for NaN/empty, else string."""
                import math
                if v is None:
                    return None
                try:
                    if math.isnan(float(v)):
                        return None
                except Exception:
                    pass
                s = str(v).strip()
                return s if s else None

            # Parse skills JSON
            skills: list = []
            try:
                sj = row.get("skills_json")
                if sj and str(sj).strip() not in ("", "nan", "None"):
                    skills = json.loads(sj)
            except Exception:
                pass

            record: Dict[str, Any] = {
                "filename": fn,
                "user_id": str(row.get("user_id") or ""),
                "classification": None,
                "total_score": None,
                "scores": {},
                "uploaded_at": row.get("uploaded_at"),
                # Candidate metadata — stored at upload time, no LLM on read path
                "candidate_name": _str(row.get("candidate_name")),
                "role": _str(row.get("role")),
                "industry": _str(row.get("industry")),
                "exp_level": _normalize_exp_level(_str(row.get("exp_level"))),
                "current_company": _str(row.get("current_company")),
                "location": _str(row.get("location")),
                "phone": _str(row.get("phone")),
                "email": _str(row.get("email")),
                "linkedin_url": _str(row.get("linkedin_url")),
                "github_url": _str(row.get("github_url")),
                "skills": skills,
                "summary": _str(row.get("summary")),
                "years_experience": _str(row.get("years_experience")),
                "education": _str(row.get("education")),
                "certifications": _parse_certs(row.get("certifications_json")),
            }

            try:
                val = json.loads(row.get("validation_json") or "{}")
                record["classification"] = val.get("classification")
                record["total_score"] = val.get("total_score")
                record["scores"] = val.get("scores", {})
            except Exception:
                pass

            lookup[fn] = record
        return lookup

    meta_lookup = _build_meta_lookup(meta_df)
    filename_to_user = {fn: rec.get("user_id", "") for fn, rec in meta_lookup.items()}
    base_filenames = list(meta_lookup.keys())

    # Build per-resume apply/shortlist counts from job_resume_applied table
    _apply_counts: Dict[str, int] = {}
    _shortlist_counts: Dict[str, int] = {}
    try:
        from services.db.lancedb_client import get_or_create_job_applied_table
        adf = get_or_create_job_applied_table().to_pandas()
        if not adf.empty:
            applied_mask = adf["applied_status"].isin(["applied", "selected", "rejected"])
            shortlist_mask = adf["applied_status"].isin(["shortlisted", "invited"])
            for fn, cnt in adf[applied_mask].groupby("resume_id").size().items():
                _apply_counts[str(fn)] = int(cnt)
            for fn, cnt in adf[shortlist_mask].groupby("resume_id").size().items():
                _shortlist_counts[str(fn)] = int(cnt)
    except Exception:
        pass

    # Always merge with the full resume list so resumes without validation metadata still appear.
    if is_recruiter:
        all_resumes = list_all_resumes_with_users()
        for r in all_resumes:
            fn = r["filename"]
            if fn not in meta_lookup:
                base_filenames.append(fn)
                filename_to_user[fn] = r["user_id"]
    else:
        for fn in list_user_resumes(user_id):
            if fn not in meta_lookup:
                base_filenames.append(fn)
                filename_to_user[fn] = user_id

    # 2. Semantic search — re-rank filenames by similarity
    if search and search.strip():
        # Extract location and exp_level signals from the query text
        loc_match_kws, semantic_query = _parse_location_from_query(search.strip())
        query_exp_level = _parse_exp_level_from_query(search.strip())
        if loc_match_kws:
            print(f"DEBUG: [search] location signal detected: {loc_match_kws} | semantic query: '{semantic_query}'")
        if query_exp_level:
            print(f"DEBUG: [search] exp_level signal detected: '{query_exp_level}'")

        # Pre-filter the candidate pool from metadata (complete, no chunk-limit gaps)
        # using any location and exp_level signals extracted from the query text.
        def _loc_matches(fn: str) -> bool:
            stored_loc = str(meta_lookup.get(fn, {}).get("location") or "").lower()
            return any(kw in stored_loc for kw in loc_match_kws)

        def _exp_matches(fn: str) -> bool:
            stored_exp = str(meta_lookup.get(fn, {}).get("exp_level") or "").strip().lower()
            return stored_exp == query_exp_level.lower()

        pre_filtered = list(base_filenames)
        if loc_match_kws:
            pre_filtered = [fn for fn in pre_filtered if _loc_matches(fn)]
            print(f"DEBUG: [search] location pre-filter: {len(pre_filtered)} resumes")
        if query_exp_level and not exp_level:
            # Only apply query exp_level if the dropdown filter isn't already set
            exp_filtered = [fn for fn in pre_filtered if _exp_matches(fn)]
            if exp_filtered:
                pre_filtered = exp_filtered
                print(f"DEBUG: [search] exp_level pre-filter '{query_exp_level}': {len(pre_filtered)} resumes")
            else:
                print(f"DEBUG: [search] exp_level '{query_exp_level}' had 0 matches — skipping filter")

        loc_pool = pre_filtered if (loc_match_kws or query_exp_level) else None

        try:
            # Search limit: cover entire loc_pool (or full DB if no location filter)
            sem_limit = max(500, len(loc_pool) * 3) if loc_pool is not None else 500
            results = search_resumes_semantic(semantic_query or search.strip(), user_id, limit=sem_limit, is_recruiter=is_recruiter)
            if results is not None and not results.empty:
                seen: set = set()
                ranked = []
                global_user_map: Optional[Dict[str, str]] = None
                for _, row in results.iterrows():
                    fn = str(row.get("filename", ""))
                    if not fn:
                        continue

                    # Lazy-resolve uploader mapping for files missing metadata.
                    if fn not in filename_to_user:
                        if not is_recruiter:
                            filename_to_user[fn] = user_id
                        else:
                            if global_user_map is None:
                                all_resumes = list_all_resumes_with_users()
                                global_user_map = {r["filename"]: r["user_id"] for r in all_resumes}
                            if fn in global_user_map:
                                filename_to_user[fn] = global_user_map[fn]

                    if fn in filename_to_user and fn not in seen:
                        seen.add(fn)
                        ranked.append(fn)

                if loc_pool is not None:
                    # Keep only location-matching resumes, in semantic rank order.
                    # Any loc_pool members not returned by semantic search are appended
                    # at the end so they are never silently dropped.
                    loc_pool_set = set(loc_pool)
                    ranked_loc = [fn for fn in ranked if fn in loc_pool_set]
                    missed     = [fn for fn in loc_pool if fn not in set(ranked_loc)]
                    ranked = ranked_loc + missed
                    if not ranked:
                        # Fallback: no semantic results at all — return full loc_pool
                        ranked = loc_pool
                    print(f"DEBUG: [search] location result: {len(ranked_loc)} semantic, {len(missed)} appended")

                base_filenames = ranked
        except Exception as e:
            print(f"DEBUG: [resume db] semantic search failed: {e}")
            if loc_pool is not None:
                base_filenames = loc_pool  # fall back to metadata-filtered list
            else:
                s = search.strip().lower()
                base_filenames = [f for f in base_filenames if s in f.lower()]

    # 4. Build enriched records
    resumes = []
    for fn in base_filenames:
        record: Dict[str, Any] = dict(meta_lookup.get(fn) or {
            "filename": fn,
            "user_id": "",
            "classification": None,
            "total_score": None,
            "scores": {},
            "uploaded_at": None,
        })
        if not record.get("user_id"):
            record["user_id"] = filename_to_user.get(fn, "" if is_recruiter else user_id)
        record["apply_count"] = _apply_counts.get(fn, 0)
        record["shortlist_count"] = _shortlist_counts.get(fn, 0)
        resumes.append(record)

    # 5. Classification filter
    if classification:
        resumes = [r for r in resumes if r.get("classification") == classification]

    # 5a. Metadata is already in each record from _build_meta_lookup (stored at upload time).
    # Apply industry / role / exp_level / location filters directly — no LLM, no cache.
    if industry and industry.strip():
        target = industry.strip().lower()
        resumes = [r for r in resumes if str(r.get("industry") or "").strip().lower() == target]
    if role and role.strip():
        target = role.strip().lower()
        resumes = [r for r in resumes if str(r.get("role") or "").strip().lower() == target]
    if exp_level and exp_level.strip():
        target = exp_level.strip().lower()
        resumes = [r for r in resumes if str(r.get("exp_level") or "").strip().lower() == target]
    if location and location.strip():
        # Normalize the filter value the same way stored values are normalized
        norm_filter = (_normalize_location(location.strip()) or location.strip()).lower()
        city_only = norm_filter.split(",")[0].strip()
        resumes = [
            r for r in resumes
            if norm_filter in (_normalize_location(str(r.get("location") or "")) or "").lower()
            or city_only in str(r.get("location") or "").lower()
        ]

    # 5b. Applied filter — sourced from job_resume_applied counts built above
    if applied == "applied":
        resumes = [r for r in resumes if r.get("apply_count", 0) > 0]
    elif applied == "not_applied":
        resumes = [r for r in resumes if r.get("apply_count", 0) == 0]

    # 6. Date range filter
    if date_range:
        cutoff = datetime.now() - timedelta(days=date_range)
        def _parse_dt(d: Any) -> datetime:
            try:
                return datetime.fromisoformat(str(d)[:19])
            except Exception:
                return datetime.min
        resumes = [r for r in resumes if _parse_dt(r.get("uploaded_at") or "") >= cutoff]

    # 7. Sort newest first — skip when search is active (preserve semantic/boost ranking)
    if not (search and search.strip()):
        def _sort_key(r: Dict[str, Any]) -> datetime:
            try:
                return datetime.fromisoformat(str(r.get("uploaded_at") or "")[:19])
            except Exception:
                return datetime.min
        resumes.sort(key=_sort_key, reverse=True)

    total = len(resumes)
    return {"resumes": resumes[skip: skip + limit], "total": total}


@router.get("/{filename:path}/applied-jobs")
async def get_resume_applied_jobs(
    filename: str,
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
):
    """Return the jobs a specific resume has been applied to."""
    from services.db.lancedb_client import get_or_create_job_applied_table, get_or_create_jobs_table

    is_recruiter = role in ("recruiter", "manager")

    try:
        adf = get_or_create_job_applied_table().to_pandas()
        if adf.empty:
            return {"jobs": []}
        rows = adf[adf["resume_id"] == filename]
        if not is_recruiter:
            rows = rows[rows["user_id"] == user_id]
        if rows.empty:
            return {"jobs": []}

        job_ids = rows["job_id"].tolist()
        statuses = dict(zip(rows["job_id"], rows["applied_status"]))
        timestamps = dict(zip(rows["job_id"], rows["timestamp"]))

        jobs_table = get_or_create_jobs_table()
        results = []
        for jid in job_ids:
            try:
                jrows = jobs_table.search().where(f"job_id = '{jid}'").limit(1).to_list()
                if jrows:
                    j = {k: v for k, v in jrows[0].items() if k != "vector"}
                    j["applied_status"] = statuses.get(jid, "applied")
                    j["applied_at"] = timestamps.get(jid)
                    results.append(j)
            except Exception:
                pass

        return {"jobs": results}
    except Exception as e:
        print(f"DEBUG: [applied-jobs] failed: {e}")
        return {"jobs": []}


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
    db_changed = False

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

            classification = (validation or {}).get("classification", "N/A")

            # --- Reject documents that are clearly not a resume ---
            if validation and not validation.get("error") and classification == "not_resume":
                if os.path.exists(file_path):
                    os.remove(file_path)
                print(f"Rejected (not a resume): {safe_filename}")
                results.append({
                    "filename": safe_filename,
                    "status": "rejected",
                    "error": "This document does not appear to be a resume. Please upload a valid resume file.",
                    "validation": validation,
                })
                safe_log_activity(user_id, "upload_rejected", safe_filename, 0, classification)
                continue

            # --- Store in DB ---
            if store_db_bool:
                print(f"Storing in DB: {safe_filename}")
                store_resume(safe_filename, text, user_id, api_key=creds["openrouter_key"])
                # Register in resume_meta immediately so the tile appears right away,
                # even before LLM metadata extraction completes.
                store_resume_validation(user_id, safe_filename, {}, {})
                db_changed = True

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

            # --- Extract candidate metadata (name, role, company, etc.) ---
            # Done at upload time so /database is a plain DB read — no LLM on query path.
            candidate_meta: dict = {}
            if text.strip():
                try:
                    cls_result = _llm_classify_batch([(safe_filename, text)], llm_config)
                    candidate_meta = _clean_metadata(cls_result.get(safe_filename, {}), llm_config)
                except Exception as e:
                    print(f"DEBUG: [upload] metadata extraction failed for {safe_filename}: {e}")

            # --- Persist validation + metadata ---
            if validation and not validation.get("error"):
                store_resume_validation(user_id, safe_filename, validation, candidate_meta)
            elif not validation:
                # No validation run (e.g. store_db only) — still store metadata
                store_resume_validation(user_id, safe_filename, {}, candidate_meta)

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
    from services.db.lancedb_client import list_all_resumes_with_users, list_user_resumes
    try:
        if role in ("recruiter", "manager"):
            all_resumes = list_all_resumes_with_users()
            return {"resumes": [r["filename"] for r in all_resumes], "all_resumes": all_resumes}
        filenames = list_user_resumes(user_id)
        return {"resumes": filenames}
    except Exception:
        return {"resumes": []}


@router.get("/{filename}/text")
async def get_resume_text(filename: str, user_id: str = Depends(get_current_user)):
    """Return ATS-normalized extracted text for a resume file."""
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    raw = extract_text(file_path)
    text = to_ats_text(raw)
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
async def download_resume(filename: str, inline: bool = False):
    # Sanitize filename to prevent path traversal
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    media_type = "application/pdf" if ext == "pdf" else "application/octet-stream"
    disposition = "inline" if inline and ext == "pdf" else f"attachment; filename=\"{safe_filename}\""
    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


@router.get("/preview/{filename}")
async def preview_resume(filename: str, user_id: str = Depends(get_current_user)):
    """Return the resume file with inline Content-Disposition for browser preview."""
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    media_type = "application/pdf" if ext == "pdf" else "application/octet-stream"
    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename=\"{safe_filename}\""},
    )


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
