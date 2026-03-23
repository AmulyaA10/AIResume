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
from app.common.skill_utils import canonicalize_skill
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
    ("United Kingdom", [
        "united kingdom", " uk", "england", "london", "manchester", "birmingham",
        "scotland", "wales", "edinburgh", "glasgow", "leeds", "bristol", "sheffield",
        "liverpool", "cambridge", "oxford", "nottingham", "newcastle",
    ]),
    ("Canada", [
        "canada", "ontario", "british columbia", "alberta", "quebec", "manitoba",
        "saskatchewan", "nova scotia", "new brunswick",
        # Major cities and suburbs — listed explicitly to catch "City, CA" patterns
        "toronto", "vancouver", "montreal", "calgary", "ottawa", "edmonton",
        "winnipeg", "mississauga", "brampton", "hamilton", "waterloo", "kitchener",
        "markham", "richmond hill", "scarborough", "etobicoke", "north york",
        "surrey", "burnaby", "richmond", "abbotsford", "kelowna", "victoria",
        "laval", "gatineau", "longueuil", "saskatoon", "regina", "halifax",
    ]),
    ("India", [
        "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai",
        "pune", "kolkata", "gurgaon", "gurugram", "noida", "ahmedabad", "jaipur",
        "surat", "lucknow", "chandigarh", "coimbatore", "kochi", "indore", "nagpur",
        "visakhapatnam", "bhopal", "vadodara", "thiruvananthapuram",
    ]),
    ("Europe", [
        "europe", "germany", "france", "spain", "italy", "netherlands", "sweden",
        "norway", "denmark", "finland", "switzerland", "austria", "poland",
        "berlin", "paris", "amsterdam", "stockholm", "madrid", "rome", "barcelona",
        "munich", "frankfurt", "hamburg", "cologne", "düsseldorf", "zurich",
        "brussels", "dublin", "ireland", "portugal", "lisbon", "prague", "warsaw",
        "vienna", "copenhagen", "oslo", "helsinki", "budapest", "bucharest",
        "athens", "greece", "belgium", "czech", "croatia", "romania", "ukraine",
    ]),
    ("Australia / NZ", [
        "australia", "new zealand", "sydney", "melbourne", "brisbane", "auckland",
        "perth", "adelaide", "gold coast", "canberra", "newcastle", "wollongong",
        "wellington", "christchurch", "queensland", "victoria", "new south wales",
    ]),
    ("Asia Pacific", [
        "singapore", "japan", "china", "hong kong", "south korea", "taiwan",
        "vietnam", "thailand", "malaysia", "philippines", "indonesia",
        "tokyo", "osaka", "beijing", "shanghai", "shenzhen", "guangzhou",
        "seoul", "taipei", "kuala lumpur", "jakarta", "manila", "hanoi",
        "ho chi minh", "bangkok", "yangon", "myanmar",
    ]),
    ("Middle East / Africa", [
        "dubai", "uae", "saudi", "israel", "south africa", "nigeria", "kenya",
        "egypt", "qatar", "bahrain", "kuwait", "oman", "jordan", "lebanon",
        "abu dhabi", "riyadh", "tel aviv", "johannesburg", "cape town", "lagos",
        "nairobi", "cairo", "tunis", "morocco", "casablanca",
    ]),
    ("Latin America", [
        "brazil", "mexico", "argentina", "colombia", "chile", "peru",
        "bogota", "sao paulo", "buenos aires", "lima", "santiago", "medellin",
        "guadalajara", "monterrey", "caracas", "venezuela", "ecuador", "uruguay",
    ]),
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


# Maps US suburb / satellite city patterns → canonical metro city.
# Used when building the /locations dropdown so that e.g. "Foothill Ranch, CA"
# is counted under "Los Angeles, CA" rather than shown as its own entry.
_US_SUBURB_TO_METRO: list[tuple[re.Pattern, str]] = [
    # ── Greater Los Angeles ───────────────────────────────────────────────────
    (re.compile(
        r'\b(foothill ranch|irvine|anaheim|orange county|long beach|burbank|'
        r'pasadena|glendale|torrance|santa ana|garden grove|corona|pomona|'
        r'ontario|rancho cucamonga|compton|inglewood|santa monica|culver city|'
        r'el monte|downey|west covina|norwalk|fullerton|el segundo|'
        r'thousand oaks|simi valley|oxnard|ventura|camarillo|'
        r'lake forest|mission viejo|laguna|aliso viejo|'
        r'chino|chino hills|fontana|riverside|moreno valley|'
        r'covina|azusa|glendora|diamond bar|walnut|'
        r'hawthorne|gardena|lawndale|redondo beach|manhattan beach|hermosa beach|'
        r'studio city|sherman oaks|encino|van nuys|north hollywood|'
        r'chatsworth|canoga park|woodland hills|calabasas)\b',
        re.I,
    ), "Los Angeles, CA"),

    # ── San Francisco Bay Area ────────────────────────────────────────────────
    (re.compile(
        r'\b(palo alto|mountain view|sunnyvale|santa clara|menlo park|'
        r'cupertino|redwood city|foster city|san mateo|daly city|'
        r'fremont|hayward|milpitas|livermore|pleasanton|dublin|san ramon|'
        r'walnut creek|concord|richmond|berkeley|oakland|'
        r'south san francisco|san bruno|burlingame|millbrae|belmont|'
        r'san carlos|campbell|los gatos|saratoga|los altos|'
        r'emeryville|alameda|union city|newark|santa cruz)\b',
        re.I,
    ), "San Francisco, CA"),

    # ── San Diego metro ───────────────────────────────────────────────────────
    (re.compile(
        r'\b(chula vista|el cajon|santee|la mesa|escondido|'
        r'oceanside|carlsbad|vista|san marcos|national city|'
        r'el cajon|santee|poway|spring valley)\b',
        re.I,
    ), "San Diego, CA"),

    # ── Greater Seattle ───────────────────────────────────────────────────────
    (re.compile(
        r'\b(bellevue|redmond|kirkland|renton|kent|auburn|federal way|'
        r'tukwila|burien|des moines|bothell|woodinville|sammamish|'
        r'issaquah|mercer island|shoreline|lynnwood|everett|tacoma)\b',
        re.I,
    ), "Seattle, WA"),

    # ── Greater New York ──────────────────────────────────────────────────────
    (re.compile(
        r'\b(jersey city|hoboken|newark|stamford|white plains|yonkers|'
        r'bronx|brooklyn|queens|staten island|manhattan|'
        r'long island|nassau|suffolk)\b',
        re.I,
    ), "New York, NY"),

    # ── Greater Boston ────────────────────────────────────────────────────────
    (re.compile(
        r'\b(cambridge|somerville|newton|quincy|brookline|waltham|'
        r'woburn|watertown|malden|medford|lexington|concord|'
        r'framingham|natick|burlington|woburn|lowell|worcester)\b',
        re.I,
    ), "Boston, MA"),

    # ── Greater Chicago ───────────────────────────────────────────────────────
    (re.compile(
        r'\b(evanston|naperville|aurora|joliet|rockford|elgin|'
        r'schaumburg|oak park|berwyn|cicero|arlington heights|'
        r'bolingbrook|palatine|waukegan|skokie|des plaines)\b',
        re.I,
    ), "Chicago, IL"),

    # ── Greater Dallas / Fort Worth ───────────────────────────────────────────
    (re.compile(
        r'\b(fort worth|arlington|plano|frisco|mckinney|garland|'
        r'irving|grand prairie|mesquite|carrollton|richardson|'
        r'denton|allen|lewisville|flower mound|addison)\b',
        re.I,
    ), "Dallas, TX"),

    # ── Greater Houston ───────────────────────────────────────────────────────
    (re.compile(
        r'\b(sugar land|pearland|pasadena|the woodlands|katy|'
        r'league city|baytown|conroe|friendswood|galveston|'
        r'stafford|missouri city|tomball|spring)\b',
        re.I,
    ), "Houston, TX"),

    # ── Greater Washington DC ─────────────────────────────────────────────────
    (re.compile(
        r'\b(arlington|alexandria|bethesda|rockville|silver spring|'
        r'tysons|mclean|reston|herndon|falls church|'
        r'fairfax|gaithersburg|germantown|greenbelt|'
        r'annapolis|baltimore)\b',
        re.I,
    ), "Washington, DC"),

    # ── Greater Miami ─────────────────────────────────────────────────────────
    (re.compile(
        r'\b(fort lauderdale|boca raton|west palm beach|hollywood|'
        r'pompano beach|coral springs|miramar|hialeah|'
        r'doral|miami beach|homestead|pembroke pines)\b',
        re.I,
    ), "Miami, FL"),

    # ── Greater Atlanta ───────────────────────────────────────────────────────
    (re.compile(
        r'\b(alpharetta|roswell|sandy springs|marietta|smyrna|'
        r'peachtree city|kennesaw|duluth|norcross|lawrenceville|'
        r'decatur|dunwoody|johns creek|cumming)\b',
        re.I,
    ), "Atlanta, GA"),

    # ── Greater Denver ────────────────────────────────────────────────────────
    (re.compile(
        r'\b(aurora|lakewood|englewood|arvada|westminster|'
        r'thornton|brighton|boulder|longmont|fort collins|'
        r'castle rock|parker|centennial|highlands ranch|littleton)\b',
        re.I,
    ), "Denver, CO"),

    # ── Greater Phoenix ───────────────────────────────────────────────────────
    (re.compile(
        r'\b(scottsdale|tempe|mesa|chandler|gilbert|glendale|'
        r'peoria|surprise|goodyear|avondale|fountain hills)\b',
        re.I,
    ), "Phoenix, AZ"),

    # ── Greater Austin ────────────────────────────────────────────────────────
    (re.compile(
        r'\b(round rock|cedar park|pflugerville|georgetown|'
        r'kyle|buda|leander|manor|bastrop)\b',
        re.I,
    ), "Austin, TX"),
]


def _suburb_to_metro(city: str) -> Optional[str]:
    """If city is a known US suburb, return its canonical metro city; else None."""
    for pattern, metro in _US_SUBURB_TO_METRO:
        if pattern.search(city):
            return metro
    return None


_US_STATE_NAMES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "Washington DC",
}

# Maps filter display value → substring used to match stored location strings.
# For state-level filters this is just ", ST" (e.g. ", CA"), which matches any
# "City, CA" or "City, CA, USA" string — no hardcoded city list needed.
_METRO_TO_SUBSTRINGS: dict[str, list[str]] = {
    state_name: [f", {code}"] for code, state_name in _US_STATE_NAMES.items()
}

# Reverse lookup: "california" → "CA"  (used by _city_to_metro for full-name matching)
_STATE_NAME_LOWER_TO_CODE: dict[str, str] = {v.lower(): k for k, v in _US_STATE_NAMES.items()}


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
    2. International keyword matching (before state-code check to avoid false
       positives from shared codes like CA=Canada/California, IN=India/Indiana,
       DE=Germany/Delaware)
    3. US state code detection
    4. "united states" / "usa" fallback
    """
    if re.search(r'\bremote\b', location, re.IGNORECASE):
        return "Remote"
    # Keyword matching first — catches international cities that share ISO codes
    # with US states (e.g. "Calgary, CA" must be Canada, not United States).
    loc_lower = location.lower()
    for region, keywords in _REGION_KEYWORDS:
        if any(kw.strip() in loc_lower for kw in keywords):
            return region
    # US state code detection (safe now that international keywords were checked)
    state_match = re.search(r',\s*([A-Z]{2})\b', location)
    if state_match and state_match.group(1) in _US_STATE_CODES:
        return "United States"
    # Fallback: explicit US mentions
    if any(kw in loc_lower for kw in ("united states", " usa", "u.s.")):
        return "United States"
    return "Other"


def _city_to_metro(loc: str) -> Optional[str]:
    """Map a normalized US location string to its state-level display name.

    'San Francisco, CA'         → 'California'
    'San Francisco, California' → 'California'
    'Foothill Ranch, CA'        → 'California'
    'Seattle, WA'               → 'Washington'
    'Calgary, CA'               → None  (CA = Canada ISO code, not California)
    'Toronto'                   → None  (keyword matched as Canada)
    'Mississauga'               → None  (keyword matched as Canada)
    Returns None for non-US or unrecognised formats.
    """
    # Delegate country classification to _classify_region so that ambiguous
    # 2-letter codes (CA=Canada/California, IN=India/Indiana, DE=Germany/Delaware)
    # are resolved correctly via the international keyword list.
    if _classify_region(loc) != "United States":
        return None

    loc_lower = loc.lower()
    # Try 2-letter state code: "San Jose, CA"
    m = re.search(r',\s*([A-Z]{2})\b', loc)
    if m:
        state = _US_STATE_NAMES.get(m.group(1))
        if state:
            return state
    # Fall back to full state name: "San Jose, California"
    for name_lower, code in _STATE_NAME_LOWER_TO_CODE.items():
        if re.search(r',\s*' + re.escape(name_lower) + r'\b', loc_lower):
            return _US_STATE_NAMES[code]
    return None


# ---------------------------------------------------------------------------
# Query-time location signal extraction
# ---------------------------------------------------------------------------

# Location keyword → list of city/country fragments to match against stored location strings
_QUERY_LOCATION_SIGNALS: list[tuple[list[str], list[str]]] = [
    # (query keywords,  stored location keywords to match)
    (["bay area", "san francisco", "sf bay", "silicon valley", "palo alto", "mountain view",
      "sunnyvale", "san jose", "santa clara", "foster city", "menlo park",
      "sf metro", "sf area", "50 mile radius"],
     ["san francisco", "palo alto", "mountain view", "sunnyvale", "san jose", "santa clara",
      "foster city", "menlo park", "oakland", "berkeley"]),

    (["southern california", "socal", "so cal", "los angeles", "la metro",
      "la area", "greater la", "greater los angeles", "orange county",
      "san diego", "irvine", "anaheim", "santa ana", "riverside", "pasadena",
      "long beach", "culver city", "santa monica", "burbank"],
     ["los angeles", "san diego", "orange county", "irvine", "anaheim",
      "riverside", "pasadena", "long beach", "santa monica", "burbank",
      "culver city", "santa ana", "torrance"]),

    (["new york", "nyc", "manhattan", "brooklyn", "queens", "bronx", "jersey city", "hoboken"],
     ["new york", "manhattan", "brooklyn", "queens", "bronx", "jersey city", "hoboken", ", ny"]),

    (["europe", "european", "western europe", "eu"],
     ["london", "berlin", "paris", "amsterdam", "stockholm", "zurich", "dublin",
      "madrid", "rome", "england", "germany", "france", "netherlands", "sweden",
      "switzerland", "ireland", "spain", "italy", "uk", "united kingdom"]),

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

    # US state full names → state abbreviation in stored location (e.g. ", CA")
    (["california", "the golden state"],
     [", ca"]),
    (["new york state", "new york"],      # "new york" already covered above for NYC; this catches state-wide
     [", ny"]),
    (["texas", "the lone star state"],
     [", tx"]),
    (["washington state"],               # "washington" alone is ambiguous (DC), so require "state"
     [", wa"]),
    (["illinois"],
     [", il"]),
    (["florida", "the sunshine state"],
     [", fl"]),
    (["georgia"],
     [", ga"]),
    (["massachusetts"],
     [", ma"]),
    (["colorado"],
     [", co"]),
    (["arizona"],
     [", az"]),
    (["pennsylvania"],
     [", pa"]),
    (["ohio"],
     [", oh"]),
    (["michigan"],
     [", mi"]),
    (["north carolina"],
     [", nc"]),
    (["virginia"],
     [", va"]),
    (["minnesota"],
     [", mn"]),
    (["oregon"],
     [", or"]),
]

# Maps 2-letter US state codes (lowercase) to stored location keywords.
# Used for queries like "executives from NY" where "NY" can't be matched by the
# multi-word static map above (which requires len >= 3 in the generic fallback).
_STATE_CODE_TO_LOC_KWS: dict[str, list[str]] = {
    "ny": ["new york", "manhattan", "brooklyn", "queens", "bronx", "jersey city", "hoboken", ", ny"],
    "nj": ["new jersey", "hoboken", "jersey city"],
    "wa": ["seattle", "bellevue", "redmond", "kirkland"],
    "tx": ["austin", "dallas", "houston", "round rock"],
    "il": ["chicago"],
    "fl": ["miami", "orlando", "tampa"],
    "ga": ["atlanta"],
    "ma": ["boston"],
    "co": ["denver", "boulder"],
    "az": ["phoenix", "scottsdale"],
    "pa": ["philadelphia", "pittsburgh"],
    "oh": ["columbus", "cleveland"],
    "mi": ["detroit", "ann arbor"],
    "nc": ["charlotte", "raleigh"],
    "va": ["virginia", "arlington"],
    "mn": ["minneapolis"],
    "or": ["portland"],
    "in": None,  # reserved — "in" is a preposition, not a state here; skip indiana to avoid ambiguity
}

_RE_STATE_CODE = re.compile(
    r'\b(?:from|based\s+in|located\s+in)\s+([A-Z]{2})\b',
    re.IGNORECASE,
)

# Preposition + location stop-phrases to strip from query for semantic search
_LOCATION_STRIP_PATTERNS = [
    re.compile(r'\b(?:from|in|based in|located in|near|around|at)\s+', re.I),
    re.compile(r'\b(?:bay area|san francisco|silicon valley|palo alto|mountain view|sunnyvale|san jose)\b', re.I),
    re.compile(r'\b(?:new york|nyc|manhattan|brooklyn|jersey city|\bNY\b)\b', re.I),
    re.compile(r'\b(?:seattle|bellevue|redmond)\b', re.I),
    re.compile(r'\b(?:london|england|berlin|germany)\b', re.I),
    re.compile(r'\b(?:bangalore|bengaluru|hyderabad|mumbai|chennai|delhi|noida|gurugram|india)\b', re.I),
    re.compile(r'\b(?:singapore|toronto|canada|remote)\b', re.I),
    re.compile(r'\b(?:austin|texas|tx)\b', re.I),
    re.compile(r'\b(?:california|new\s+york\s+state|washington\s+state|illinois|florida|georgia|massachusetts|colorado|arizona|pennsylvania|ohio|michigan|north\s+carolina|virginia|minnesota|oregon)\b', re.I),
    re.compile(r'\b(?:candidate[s]?|developer[s]?|engineer[s]?)\b', re.I),  # generic noise in location queries
    re.compile(r'\b(?:southern california|silicon valley|europe|fang|faang|big tech)\b', re.I),
    re.compile(r'\b(?:los angeles|la metro|la area|greater la|greater los angeles|orange county)\b', re.I),
    re.compile(r'\b(?:metro\s+area|greater\s+\w+|metro\s+region|metropolitan)\b', re.I),
    re.compile(r'\b(?:area|region|vicinity|zone|district|suburb[s]?)\b', re.I),
]

# Tokens that look geographic in regex but are NOT geographic — skip location pre-filter if
# all extracted tokens are in this set (e.g. "experts in ML", "working in FANG").
_NON_LOCATION_TOKENS: set[str] = {
    "ml", "ai", "fang", "faang", "nlp", "llm", "rag",
    "machine", "learning", "deep", "data", "science", "analytics",
    "cloud", "storage", "distributed", "computing", "platform",
    "technology", "tech", "engineering", "software", "hardware",
    "finance", "fintech", "healthcare", "education", "gaming",
    "kubernetes", "docker", "aws", "gcp", "azure", "devops",
    "blockchain", "crypto", "web3", "defi",
    "big", "startup", "enterprise",
}


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

    # Pass 1.5: 2-letter US state codes (e.g. "from NY", "based in WA")
    if not matched_loc_keywords:
        sm = _RE_STATE_CODE.search(query)
        if sm:
            code = sm.group(1).lower()
            kws = _STATE_CODE_TO_LOC_KWS.get(code)
            if kws:  # None sentinel means skip (e.g. "in" is ambiguous)
                matched_loc_keywords = kws
                loc_phrase_extracted = sm.group(1)

    # Pass 2: generic regex extraction (any city not covered by the static map)
    if not matched_loc_keywords:
        m = _RE_LOC_EXTRACT.search(query)
        if m:
            loc_phrase_extracted = m.group(1).strip().rstrip(",. ")
            # Build match keywords: individual tokens (words ≥ 3 chars), lowercased
            tokens = [
                t.lower() for t in re.split(r'[\s,]+', loc_phrase_extracted)
                if len(t) >= 3 and t.upper() not in {
                    "THE", "AND", "FOR", "WITH", "FROM", "NEAR",
                }
            ]
            # Discard if ALL tokens are known non-geographic terms (e.g. "ML", "FANG", "cloud storage")
            if tokens and not all(t in _NON_LOCATION_TOKENS for t in tokens):
                matched_loc_keywords = tokens

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
            cleaned = "software engineer"  # generic fallback when location fully consumed query

    return matched_loc_keywords, cleaned


# ---------------------------------------------------------------------------
# AI-powered candidate search intent parser
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Intent parse cache — avoids redundant LLM calls for the same query string.
# Key: (query_lower, llm_model).  Evicts oldest entries when full.
# ---------------------------------------------------------------------------
from collections import OrderedDict as _OD

_INTENT_CACHE: "_OD[tuple, dict]" = _OD()
_INTENT_CACHE_MAX = 256

def _intent_cache_get(key: tuple) -> Optional[dict]:
    if key in _INTENT_CACHE:
        _INTENT_CACHE.move_to_end(key)
        return _INTENT_CACHE[key]
    return None

def _intent_cache_set(key: tuple, value: dict) -> None:
    _INTENT_CACHE[key] = value
    _INTENT_CACHE.move_to_end(key)
    if len(_INTENT_CACHE) > _INTENT_CACHE_MAX:
        _INTENT_CACHE.popitem(last=False)


# Queries that require LLM: company names/acronyms and group terms.
# Geographic location signals are handled by the static parser (_QUERY_LOCATION_SIGNALS)
# which is MORE accurate than the LLM for known cities/metros — the LLM tends to
# over-broaden (e.g. "greater LA" → ", ca" matching all of California).
_INTENT_NEEDS_LLM = re.compile(
    r'\b(faang|fang|manga|witch|big\s*[34]|tier.?1'
    r'|working at|works at|currently at|ex-|alumni|worked at'
    r'|google|microsoft|amazon|apple|meta|netflix|nvidia|openai'
    r'|deloitte|mckinsey|pwc|kpmg|bcg|bain|accenture|ibm|oracle|salesforce'
    r'|uber|lyft|airbnb|stripe|shopify|twitter|linkedin|snap|pinterest|reddit'
    r'|palantir|databricks|confluent|snowflake|datadog|cloudflare|hashicorp)\b',
    re.IGNORECASE,
)


async def _parse_candidate_search_intent(query: str, api_key: Optional[str], llm_model: Optional[str]) -> dict:
    """
    Use an LLM to extract structured intent from a natural-language candidate search query.

    Returns a dict with:
        locationAliases  — substrings to match against stored candidate location fields
        companyFilter    — company name substrings to match against current_company ONLY for
                           "currently working at" queries. Empty for past-tense ("worked at",
                           "previously", "ex-") queries — those are handled via cleanQuery.
        expLevel         — canonical exp_level string or None
        cleanQuery       — query stripped of intent tokens, ready for vector search.
                           MUST include company names when company context is present so that
                           semantic search finds both current AND past employees via resume text.

    Falls back to static parsing (regex + alias map) if no API key or LLM fails.
    """
    cache_key = (query.strip().lower(), llm_model or "")

    # 1. Cache hit — skip LLM entirely
    cached = _intent_cache_get(cache_key)
    if cached is not None:
        print(f"DEBUG: [search intent] cache hit for {query!r:.40}")
        return cached

    # 2. Static fast-path — if the query contains no location/company signals,
    #    skip the LLM and use the regex parser. Saves ~1-2s per search.
    if not api_key or not _INTENT_NEEDS_LLM.search(query):
        loc_kws, clean = _parse_location_from_query(query)
        exp = _parse_exp_level_from_query(query)
        result = {"locationAliases": loc_kws, "locationExclusions": [], "companyFilter": [],
                  "strictCompany": False, "hasRoleSignal": bool(clean.strip()), "expLevel": exp,
                  "cleanQuery": clean}
        _intent_cache_set(cache_key, result)
        return result

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        import json as _json

        llm = ChatOpenAI(
            model=llm_model or "gpt-4o-mini",
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            max_tokens=300,
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a candidate/resume search query parser. Given a natural-language recruiter query, "
             "extract structured intent. Return ONLY valid JSON — no markdown, no explanation.\n\n"
             "KEY RULE 1 — company keyword expansion: whenever the query contains an industry group name, acronym, "
             "or collective term that refers to a set of companies, expand it to the actual company names.\n"
             "  FANG / FAANG → google, meta/facebook, amazon, apple, netflix (+ microsoft for FAANG)\n"
             "  MANGA → meta, apple, netflix, google, amazon\n"
             "  WITCH → wipro, infosys, tcs, cognizant, hcl\n"
             "  Big 4 (consulting) → deloitte, pwc, ernst & young, kpmg\n"
             "  Big 3 (consulting) → mckinsey, bain, bcg\n"
             "  Big Tech → google, microsoft, amazon, apple, meta\n"
             "  FAANG+ / Tier-1 tech → google, meta, amazon, apple, netflix, microsoft, nvidia, openai\n"
             "  Any other recognisable industry group → expand to its well-known member companies\n\n"
             "KEY RULE 2 — geographic region expansion: when the query mentions a macro region, "
             "expand it to specific city/country substrings that appear in candidate location strings. "
             "Candidate locations may use full state names ('California') OR abbreviations (', CA') — "
             "include BOTH forms for US states. Choose 6-8 most representative aliases:\n"
             "  Asia            → india, singapore, japan, china, hong kong, south korea, tokyo, bangalore, hyderabad, mumbai, beijing, shanghai, seoul\n"
             "  Southeast Asia  → singapore, vietnam, thailand, philippines, malaysia, indonesia, jakarta, kuala lumpur, ho chi minh, bangkok\n"
             "  South Asia      → india, bangalore, hyderabad, mumbai, delhi, pune, chennai, kolkata, pakistan, sri lanka\n"
             "  Europe          → london, uk, germany, france, netherlands, sweden, ireland, switzerland, italy, spain, berlin, paris, amsterdam, stockholm, dublin, munich, barcelona, zurich\n"
             "  North America   → usa, united states, canada, toronto, vancouver, montreal, california, new york, texas, washington\n"
             "  USA (whole)     → usa, united states, california, new york, texas, washington, illinois, florida, georgia, , ca, , ny, , tx, , wa, , il\n"
             "  West Coast      → san francisco, los angeles, seattle, california, washington, oregon, silicon valley, bay area, , ca, , wa, , or\n"
             "  California      → california, san francisco, los angeles, silicon valley, bay area, san jose, sacramento, , ca\n"
             "  Silicon Valley / Bay Area / SF metro / SF area → san francisco, palo alto, mountain view, sunnyvale, san jose, santa clara, menlo park, foster city, oakland, berkeley, cupertino, redwood city, fremont, hayward, san mateo, napa, vallejo, concord\n"
             "  IMPORTANT: 'Silicon Valley', 'SF metro', 'Bay Area', 'SF area', '50 mile radius of SF' are Bay Area ONLY — do NOT include Seattle, Washington, Oregon, Los Angeles, San Diego, or any non-Bay-Area cities. Do NOT use ', ca' for these since that matches all of California.\n"
             "  East Coast      → new york, boston, washington dc, philadelphia, miami, atlanta, new york, , ny, , ma, , pa, , fl, , ga\n"
             "  Midwest USA     → chicago, detroit, minneapolis, cleveland, columbus, milwaukee, illinois, michigan, ohio, minnesota, , il, , mi, , oh, , mn\n"
             "  South USA       → dallas, houston, austin, atlanta, miami, charlotte, nashville, texas, georgia, florida, , tx, , ga, , fl, , nc, , tn\n"
             "  Middle East     → dubai, uae, saudi, israel, qatar, bahrain, abu dhabi, riyadh\n"
             "  Africa          → south africa, nigeria, kenya, egypt, johannesburg, lagos, nairobi, cairo\n"
             "  Australia       → australia, new zealand, sydney, melbourne, brisbane, auckland, perth\n"
             "  Latin America   → brazil, argentina, colombia, chile, mexico, sao paulo, bogota, buenos aires, lima\n\n"
             "Fields:\n"
             '  "locationAliases": array of lowercase substrings that a stored location must CONTAIN at least one of. '
             "For broad regions use the state/country abbreviation (', ca', ', ny') so ANY city in that state matches — "
             "do NOT enumerate individual cities for large regions, that will miss lesser-known cities. "
             "For sub-regions (Southern California, Bay Area) use the state abbreviation PLUS a few anchor city names.\n"
             '  "locationExclusions": array of lowercase substrings to EXCLUDE from results — any candidate whose '
             "location contains one of these is filtered out. Use this for sub-region searches to exclude the "
             "opposite sub-region. E.g. SoCal search: exclude NorCal cities. Bay Area search: exclude LA/SD.\n"
             '  "companyFilter": array of lowercase company name substrings. Populate whenever a company '
             "or company group is mentioned (present OR past tense). Always expand acronyms/group names "
             "to individual company name substrings.\n"
             '  "strictCompany": true when the query uses present tense implying the candidate IS CURRENTLY '
             "at the company ('working in', 'works at', 'currently at'). "
             "false for past tense ('worked at', 'ex-', 'alumni', 'from') — those also include past employees.\n"
             '  "hasRoleSignal": true when a specific role, skill, or technology is stated beyond just company/location '
             "(e.g. 'java developer', 'data scientist', 'ML engineer', 'python'). "
             "false when the query is purely about company/location/seniority with no specific role "
             "(e.g. 'candidates from apple', 'engineers from FANG'). "
             "Use this to decide whether role or company is the primary filter.\n"
             '  "expLevel": one of "Entry","Junior","Mid-level","Senior","Lead","Executive" or null.\n'
             '  "cleanQuery": the role/skill signal for vector search — location, seniority, and company tokens removed. '
             "When hasRoleSignal=true put ONLY the role/skill. "
             "When hasRoleSignal=false include company names so semantic search finds past employees. "
             "If nothing meaningful remains, infer a generic role.\n\n"
             "Examples:\n"
             '  "java developer from apple" → {{"locationAliases":[],"companyFilter":["apple"],"strictCompany":false,"hasRoleSignal":true,"expLevel":null,"cleanQuery":"java developer"}}\n'
             '  "senior python engineer at google" → {{"locationAliases":[],"companyFilter":["google"],"strictCompany":true,"hasRoleSignal":true,"expLevel":"Senior","cleanQuery":"python engineer"}}\n'
             '  "candidates from southern california" → {{"locationAliases":[", ca"],"locationExclusions":["san francisco","bay area","palo alto","mountain view","sunnyvale","san jose","santa clara","menlo park","oakland","berkeley","cupertino","redwood city","sacramento","fresno","stockton","modesto"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidates from northern california" → {{"locationAliases":[", ca"],"locationExclusions":["los angeles","san diego","irvine","anaheim","riverside","long beach","santa monica","burbank","orange county","chula vista","san bernardino","oxnard","fontana","moreno valley"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidates from Asia" → {{"locationAliases":["india","singapore","japan","china","hong kong","south korea","bangalore","tokyo","shanghai","seoul"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidates from Europe" → {{"locationAliases":["london","uk","germany","france","netherlands","berlin","paris","amsterdam","dublin","zurich"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidates from USA" → {{"locationAliases":["usa","united states","california","new york","texas","washington",", ca",", ny",", tx",", wa"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidates from west coast" → {{"locationAliases":["san francisco","los angeles","seattle","california","washington","oregon","silicon valley","bay area",", ca",", wa"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidates from midwest USA" → {{"locationAliases":["chicago","detroit","minneapolis","cleveland","illinois","michigan","ohio","minnesota",", il",", mi",", oh",", mn"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "senior managers from europe" → {{"locationAliases":["london","berlin","paris","amsterdam","uk","germany","france","netherlands","ireland"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":"Senior","cleanQuery":"engineering manager"}}\n'
             '  "candidates from Southeast Asia" → {{"locationAliases":["singapore","vietnam","thailand","philippines","malaysia","indonesia","jakarta","kuala lumpur","bangkok"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidates from South Asia" → {{"locationAliases":["india","bangalore","hyderabad","mumbai","delhi","pune","chennai","kolkata","pakistan"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidates currently working in FANG" → {{"locationAliases":[],"companyFilter":["google","meta","amazon","apple","netflix","microsoft"],"strictCompany":true,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidate working in microsoft" → {{"locationAliases":[],"companyFilter":["microsoft"],"strictCompany":true,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidates who worked in FANG" → {{"locationAliases":[],"companyFilter":["google","meta","amazon","apple","netflix","microsoft","facebook"],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer Google Meta Amazon Apple Netflix"}}\n'
             '  "candidate worked in apple" → {{"locationAliases":[],"companyFilter":["apple"],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer Apple"}}\n'
             '  "candidate from apple and google" → {{"locationAliases":[],"companyFilter":["apple","google"],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer Apple Google"}}\n'
             '  "experts in ML or machine learning" → {{"locationAliases":[],"companyFilter":[],"strictCompany":false,"hasRoleSignal":true,"expLevel":null,"cleanQuery":"machine learning expert"}}\n'
             '  "smart engineers in data science" → {{"locationAliases":[],"companyFilter":[],"strictCompany":false,"hasRoleSignal":true,"expLevel":null,"cleanQuery":"data science engineer"}}\n'
             '  "candidates from silicon valley" → {{"locationAliases":["san francisco","palo alto","mountain view","sunnyvale","san jose","santa clara","menlo park","foster city","oakland","berkeley","cupertino","redwood city"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidates from SF metro area" → {{"locationAliases":["san francisco","palo alto","mountain view","sunnyvale","san jose","santa clara","menlo park","foster city","oakland","berkeley","redwood city","cupertino"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}\n'
             '  "candidates from SF metro area or 50 mile radius" → {{"locationAliases":["san francisco","palo alto","mountain view","sunnyvale","san jose","santa clara","menlo park","foster city","oakland","berkeley","redwood city","cupertino","fremont","hayward","san mateo","napa","vallejo","concord","walnut creek"],"companyFilter":[],"strictCompany":false,"hasRoleSignal":false,"expLevel":null,"cleanQuery":"software engineer"}}'
            ),
            ("human", "Query: {query}"),
        ])
        chain = prompt | llm | StrOutputParser()
        raw = await chain.ainvoke({"query": query})
        parsed = _json.loads(raw.strip())
        result = {
            "locationAliases":    parsed.get("locationAliases")    or [],
            "locationExclusions": parsed.get("locationExclusions") or [],
            "companyFilter":      parsed.get("companyFilter")      or [],
            "strictCompany":      bool(parsed.get("strictCompany", False)),
            "hasRoleSignal":      bool(parsed.get("hasRoleSignal", False)),
            "expLevel":           parsed.get("expLevel"),
            "cleanQuery":         parsed.get("cleanQuery") or query,
        }
        _intent_cache_set(cache_key, result)
        return result
    except Exception as e:
        print(f"DEBUG: [search intent] LLM parse failed ({e}), falling back to static parser")
        loc_kws, clean = _parse_location_from_query(query)
        exp = _parse_exp_level_from_query(query)
        result = {"locationAliases": loc_kws, "locationExclusions": [], "companyFilter": [],
                  "strictCompany": False, "hasRoleSignal": False, "expLevel": exp, "cleanQuery": clean}
        _intent_cache_set(cache_key, result)
        return result


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
        from collections import Counter
        # Count resumes by metro_location (LLM-resolved at ingest).
        # For older resumes without metro_location, fall back to _suburb_to_metro.
        city_counts: Counter = Counter()
        has_metro_col = "metro_location" in df.columns
        for _, row in df.iterrows():
            metro = str(row.get("metro_location") or "") if has_metro_col else ""
            if not metro or metro == "nan":
                # Legacy row — derive metro on the fly
                raw_loc = str(row.get("location") or "")
                loc = _normalize_location(raw_loc)
                if not loc:
                    continue
                metro = _suburb_to_metro(loc) or loc
            city_counts[metro] += 1

        # Group cities by state (US) or region (international) with their counts
        state_cities: Dict[str, list] = {}   # state   → [(city, count)]
        region_cities: Dict[str, list] = {}  # region  → [(city, count)]
        for loc, count in city_counts.items():
            state = _city_to_metro(loc)
            if state:
                state_cities.setdefault(state, []).append((loc, count))
            else:
                region = _classify_region(loc)
                region_cities.setdefault(region, []).append((loc, count))

        # Show only cities with 2+ resumes; cap international regions at 5.
        MIN_COUNT = 2
        MAX_PER_REGION = 5
        groups: Dict[str, list] = {}

        # US states: "All {State}" + all cities with 2+ resumes, sorted by frequency.
        for state in sorted(state_cities):
            cities = state_cities[state]
            qualifying = sorted(
                [(c, n) for c, n in cities if n >= MIN_COUNT],
                key=lambda x: (-x[1], x[0]),
            )
            groups[state] = [{"value": state, "label": f"All {state}"}]
            for city, _ in qualifying:
                groups[state].append({"value": city, "label": city})

        # International regions: show top cities by frequency, capped at MAX_PER_REGION
        for region in sorted(region_cities):
            cities = region_cities[region]
            top = sorted(
                [(c, n) for c, n in cities if n >= MIN_COUNT],
                key=lambda x: (-x[1], x[0]),
            )[:MAX_PER_REGION]
            for city, _ in top:
                groups.setdefault(region, []).append({"value": city, "label": city})

        total = sum(city_counts.values())
        return {"groups": groups, "total": total}
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

    # Skip LLM entirely if no config/key provided (e.g. during demo ingest)
    if not llm_config:
        return raw

    # Only invoke AI when the location looks sub-city (3+ parts, or contains known suburb markers)
    parts = [p.strip() for p in loc.split(",")]
    _SUBURB_HINTS = re.compile(
        r'\b(layout|nagar|puram|pur|district|ward|sector|colony|'
        r'township|heights|hills|gardens|park|village|area|zone|'
        r'county|borough|quarters)\b', re.IGNORECASE
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


def _ai_metro_for_location(location: str, llm_config: dict = None) -> Optional[str]:
    """Use LLM to resolve a city to its canonical major metro area.

    'Foothill Ranch, CA'  → 'Los Angeles, CA'
    'Palo Alto, CA'       → 'San Francisco, CA'
    'San Francisco, CA'   → 'San Francisco, CA'  (already a metro)
    'London, UK'          → 'London, UK'
    'Remote'              → None

    Falls back to None on failure so callers can use _suburb_to_metro as backup.
    """
    if not location or location.strip().lower() in ("remote", ""):
        return None
    if not llm_config:
        return None
    try:
        from services.ai.common.llm_factory import get_llm
        prompt = (
            "You are a geography assistant. Given a city or location, return the nearest "
            "major metropolitan city that a recruiter would recognize.\n\n"
            "Rules:\n"
            "- US locations: return 'City, ST' with 2-letter state code, e.g. 'Los Angeles, CA'\n"
            "- International: return 'City, Country', e.g. 'London, UK', 'Bangalore, India'\n"
            "- If the input is already a major metro city, return it as-is\n"
            "- Suburbs and satellite cities must be mapped to their metro: "
            "'Foothill Ranch, CA' → 'Los Angeles, CA', 'Palo Alto, CA' → 'San Francisco, CA', "
            "'Bellevue, WA' → 'Seattle, WA', 'Round Rock, TX' → 'Austin, TX'\n"
            "- Remote or no location: return the string 'Remote'\n"
            "- Return ONLY the metro city string. No explanation, no quotes.\n\n"
            f"Location: {location}"
        )
        llm = get_llm(llm_config or {}, temperature=0)
        response = llm.invoke(prompt)
        result = response.content.strip().strip('"').strip("'")
        if result and len(result) < 60:
            return result
    except Exception as e:
        print(f"DEBUG: [metro-ai] failed for '{location}': {e}")
    return None


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

    # Resolve to major metro area via LLM (e.g. "Foothill Ranch, CA" → "Los Angeles, CA").
    # Falls back to hardcoded _suburb_to_metro for any LLM failure.
    metro_loc: Optional[str] = None
    if normalized_loc and normalized_loc.lower() != "remote":
        metro_loc = _ai_metro_for_location(normalized_loc, llm_config)
        if not metro_loc:
            metro_loc = _suburb_to_metro(normalized_loc) or normalized_loc
    cleaned["metro_location"] = metro_loc

    # Normalize phone — strip non-phone chars, format, extract extension
    phone_raw = re.sub(r'[^\d\s\+\-\(\)\.extEXT]', '', str(meta.get("phone") or "")).strip()
    # Extract extension before stripping
    ext_match = re.search(r'[eE]xt?\.?\s*(\d{2,6})', phone_raw)
    ext_suffix = f" ext. {ext_match.group(1)}" if ext_match else ""
    if ext_match:
        phone_raw = phone_raw[:ext_match.start()].strip()
    # Check digit count on digits-only string (dots/dashes break consecutive-digit regex)
    digits_only = re.sub(r'\D', '', phone_raw)
    if len(digits_only) >= 7:
        # Infer country code from candidate location
        _loc = str(meta.get("location") or "").lower()
        # Ordered from most-specific to least-specific so cities match before countries
        _LOCATION_CC = [
            # USA cities / states / indicators ("+1" shared with Canada)
            ("san francisco", "+1"), ("los angeles", "+1"), ("new york", "+1"),
            ("chicago", "+1"), ("seattle", "+1"), ("boston", "+1"), ("austin", "+1"),
            ("dallas", "+1"), ("houston", "+1"), ("atlanta", "+1"), ("miami", "+1"),
            ("denver", "+1"), ("portland", "+1"), ("phoenix", "+1"), ("detroit", "+1"),
            ("united states", "+1"), ("usa", "+1"), (", ca", "+1"), (", ny", "+1"),
            (", tx", "+1"), (", wa", "+1"), (", fl", "+1"), (", il", "+1"),
            (", ma", "+1"), (", co", "+1"), (", or", "+1"), (", ga", "+1"),
            (", nc", "+1"), (", va", "+1"), (", oh", "+1"), (", mi", "+1"),
            (", az", "+1"), (", nj", "+1"), (", pa", "+1"), (", tn", "+1"),
            # Canada
            ("toronto", "+1"), ("vancouver", "+1"), ("montreal", "+1"),
            ("calgary", "+1"), ("ottawa", "+1"), ("canada", "+1"),
            # UK
            ("london", "+44"), ("manchester", "+44"), ("birmingham", "+44"),
            ("edinburgh", "+44"), ("glasgow", "+44"), ("bristol", "+44"),
            ("united kingdom", "+44"), ("england", "+44"), ("scotland", "+44"),
            ("wales", "+44"), (", uk", "+44"),
            # India
            ("bangalore", "+91"), ("bengaluru", "+91"), ("mumbai", "+91"),
            ("delhi", "+91"), ("hyderabad", "+91"), ("pune", "+91"),
            ("chennai", "+91"), ("kolkata", "+91"), ("india", "+91"),
            # Australia
            ("sydney", "+61"), ("melbourne", "+61"), ("brisbane", "+61"),
            ("perth", "+61"), ("adelaide", "+61"), ("australia", "+61"),
            # Germany
            ("berlin", "+49"), ("munich", "+49"), ("hamburg", "+49"),
            ("frankfurt", "+49"), ("germany", "+49"),
            # France
            ("paris", "+33"), ("lyon", "+33"), ("marseille", "+33"), ("france", "+33"),
            # Netherlands
            ("amsterdam", "+31"), ("rotterdam", "+31"), ("netherlands", "+31"),
            # Singapore
            ("singapore", "+65"),
            # Ireland
            ("dublin", "+353"), ("ireland", "+353"),
            # Sweden
            ("stockholm", "+46"), ("gothenburg", "+46"), ("sweden", "+46"),
            # Switzerland
            ("zurich", "+41"), ("geneva", "+41"), ("switzerland", "+41"),
            # New Zealand
            ("auckland", "+64"), ("wellington", "+64"), ("new zealand", "+64"),
            # Israel
            ("tel aviv", "+972"), ("jerusalem", "+972"), ("israel", "+972"),
            # UAE
            ("dubai", "+971"), ("abu dhabi", "+971"), ("uae", "+971"),
            # Pakistan
            ("karachi", "+92"), ("lahore", "+92"), ("islamabad", "+92"), ("pakistan", "+92"),
            # Philippines
            ("manila", "+63"), ("philippines", "+63"),
            # Brazil
            ("são paulo", "+55"), ("sao paulo", "+55"), ("rio de janeiro", "+55"), ("brazil", "+55"),
            # Mexico
            ("mexico city", "+52"), ("guadalajara", "+52"), ("mexico", "+52"),
            # South Africa
            ("johannesburg", "+27"), ("cape town", "+27"), ("south africa", "+27"),
            # Japan
            ("tokyo", "+81"), ("osaka", "+81"), ("japan", "+81"),
            # China
            ("beijing", "+86"), ("shanghai", "+86"), ("shenzhen", "+86"), ("china", "+86"),
            # South Korea
            ("seoul", "+82"), ("busan", "+82"), ("south korea", "+82"), ("korea", "+82"),
            # Indonesia
            ("jakarta", "+62"), ("bali", "+62"), ("indonesia", "+62"),
            # Malaysia
            ("kuala lumpur", "+60"), ("malaysia", "+60"),
            # Thailand
            ("bangkok", "+66"), ("thailand", "+66"),
            # Vietnam
            ("ho chi minh", "+84"), ("hanoi", "+84"), ("vietnam", "+84"),
            # Portugal
            ("lisbon", "+351"), ("porto", "+351"), ("portugal", "+351"),
            # Spain
            ("madrid", "+34"), ("barcelona", "+34"), ("spain", "+34"),
            # Italy
            ("rome", "+39"), ("milan", "+39"), ("italy", "+39"),
            # Poland
            ("warsaw", "+48"), ("krakow", "+48"), ("poland", "+48"),
            # Belgium
            ("brussels", "+32"), ("antwerp", "+32"), ("belgium", "+32"),
            # Argentina
            ("buenos aires", "+54"), ("argentina", "+54"),
            # Colombia
            ("bogota", "+57"), ("medellin", "+57"), ("colombia", "+57"),
            # Chile
            ("santiago", "+56"), ("chile", "+56"),
        ]
        cc = next((code for kw, code in _LOCATION_CC if kw in _loc), None)

        # For "Remote" with no city/country match, fall back to timezone hints
        if cc is None:
            _TZ_CC = [
                ("est", "+1"), ("edt", "+1"), ("cst", "+1"), ("cdt", "+1"),
                ("mst", "+1"), ("mdt", "+1"), ("pst", "+1"), ("pdt", "+1"),
                ("gmt", "+44"), ("bst", "+44"),
                ("ist", "+91"),   # India Standard Time
                ("aest", "+61"), ("aedt", "+61"),
                ("jst", "+81"),
                ("kst", "+82"),
                ("cet", "+49"), ("cest", "+49"),
                ("sgt", "+65"),   # Singapore
            ]
            tz_loc = re.sub(r'[()]', ' ', _loc)  # treat parentheses as spaces
            cc = next((code for tz, code in _TZ_CC if re.search(r'\b' + tz + r'\b', tz_loc)), "+1")

        if len(digits_only) == 10:
            # 10-digit number: apply inferred country code
            phone_raw = f"{cc} ({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
        elif len(digits_only) == 11 and digits_only[0] == '1':
            # 11-digit NANP (1 + 10): always +1
            phone_raw = f"+1 ({digits_only[1:4]}) {digits_only[4:7]}-{digits_only[7:]}"
        elif phone_raw.startswith('+'):
            # Already has country code prefix — keep as-is (international)
            pass
        else:
            # Unknown length with no country code — prefix the inferred one
            phone_raw = f"{cc} {phone_raw.strip()}"
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
    seen_skills: set = set()
    if isinstance(skills_raw, list):
        for s in skills_raw:
            if len(cleaned_skills) == 8:
                break
            if isinstance(s, dict):
                raw_name = str(s.get("name") or "").strip()
                level = str(s.get("level") or "").strip()
                level = next((v for v in _VALID_LEVELS if v.lower() == level.lower()), None)
            elif isinstance(s, str):
                raw_name = s.strip()
                level = None
            else:
                continue
            if not raw_name:
                continue
            # Drop phrase-like entries (> 3 words or > 30 chars) — these are competencies, not skills
            if len(raw_name.split()) > 3 or len(raw_name) > 30:
                continue
            name = canonicalize_skill(raw_name)
            if name.lower() in seen_skills:
                continue
            seen_skills.add(name.lower())
            cleaned_skills.append({"name": name, "level": level})
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
    x_openrouter_key: Optional[str] = Header(None),
    x_llm_model: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user),
    current_role: str = Depends(get_user_role),
):
    """Return resumes with validation metadata, with optional search/filter."""
    import json
    from datetime import datetime, timedelta
    from services.db.lancedb_client import (
        list_all_resumes_with_users, get_or_create_resume_meta_table,
        search_resumes_hybrid, get_or_create_table,
    )
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    is_recruiter = current_role in ("recruiter", "manager")

    # Load the set of filenames that actually have chunks AND exist on disk.
    # Both conditions must be true for a resume to appear in the database view.
    try:
        _chunks_df = get_or_create_table().to_pandas()[["filename"]]
        _chunks_fns = set(_chunks_df["filename"].unique()) if not _chunks_df.empty else set()
        # Intersect with files that are actually on disk
        _valid_filenames: Optional[set] = {
            fn for fn in _chunks_fns
            if os.path.exists(os.path.join(UPLOAD_DIR, fn))
        }
    except Exception:
        _valid_filenames = None  # can't determine — skip filter

    # 1. Load validation metadata once (1 row per resume, much smaller than chunk table)
    meta_table = get_or_create_resume_meta_table()
    try:
        meta_df = meta_table.to_pandas()
        # Drop dangling/orphaned rows to prevent stub cards in UI
        if _valid_filenames is not None and meta_df is not None and not meta_df.empty:
            meta_df = meta_df[meta_df["filename"].isin(_valid_filenames)]
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
                "metro_location": _str(row.get("metro_location")),
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

    # 2. Name search — fast exact/substring match on candidate_name before semantic search
    if search and search.strip():
        q_name = search.strip().lower()
        name_matched = [
            fn for fn in base_filenames
            if q_name in str(meta_lookup.get(fn, {}).get("candidate_name") or "").lower()
        ]
        if name_matched:
            print(f"DEBUG: [search] name match '{q_name}': {len(name_matched)} results")
            ranked = name_matched
            # Sort: exact full-name match first, then partial
            ranked.sort(key=lambda fn: (
                0 if str(meta_lookup.get(fn, {}).get("candidate_name") or "").lower() == q_name else 1,
                str(meta_lookup.get(fn, {}).get("candidate_name") or "")
            ))
            resumes_out = []
            for fn in ranked[skip: skip + limit]:
                rec = dict(meta_lookup.get(fn, {}))
                rec["filename"] = fn
                rec["apply_count"] = _apply_counts.get(fn, 0)
                rec["shortlist_count"] = _shortlist_counts.get(fn, 0)
                resumes_out.append(rec)
            return {"resumes": resumes_out, "total": len(ranked)}

    # 3. Semantic search — re-rank filenames by similarity
    if search and search.strip():
        import asyncio as _asyncio
        # Run intent parsing and raw-query embedding in parallel.
        # If cleanQuery == raw query (common for pure role/skill queries), the pre-computed
        # vector is reused and no second embedding call is needed.
        _raw_query = search.strip()
        _api_key   = creds["openrouter_key"]
        _llm_model = creds.get("llm_model")

        async def _embed_raw() -> Optional[list]:
            try:
                loop = _asyncio.get_event_loop()
                from services.db.lancedb_client import get_embeddings_model
                emb = get_embeddings_model(api_key=_api_key)
                return await loop.run_in_executor(None, emb.embed_query, _raw_query)
            except Exception as e:
                print(f"DEBUG: [parallel-embed] failed: {e}")
                return None

        intent, raw_vector = await _asyncio.gather(
            _parse_candidate_search_intent(_raw_query, _api_key, _llm_model),
            _embed_raw(),
        )
        loc_match_kws   = [kw.lower() for kw in intent["locationAliases"]]
        loc_excl_kws    = [kw.lower() for kw in intent.get("locationExclusions") or []]
        company_filter  = [c.lower() for c in intent["companyFilter"]]
        strict_company  = bool(intent.get("strictCompany", False))
        has_role_signal = bool(intent.get("hasRoleSignal", False))
        query_exp_level = intent["expLevel"]
        semantic_query  = intent["cleanQuery"]

        print(f"DEBUG: [search intent] loc={loc_match_kws} | excl={loc_excl_kws} | company={company_filter} | strict={strict_company} | exp={query_exp_level} | q='{semantic_query}'")

        # Pre-filter the candidate pool from metadata using extracted signals.
        def _loc_matches(fn: str) -> bool:
            rec = meta_lookup.get(fn, {})
            raw_loc = str(rec.get("location") or "")
            # Build effective location string to match against:
            # 1. metro_location (LLM-resolved at ingest, e.g. "Foothill Ranch, CA" → "Los Angeles, CA")
            # 2. _suburb_to_metro fallback for older resumes without metro_location
            # 3. raw location as last resort
            stored_metro = str(rec.get("metro_location") or "")
            if not stored_metro or stored_metro == "nan":
                stored_metro = _suburb_to_metro(raw_loc) or ""
            effective_loc = (stored_metro or raw_loc).lower()
            raw_loc_lower = raw_loc.lower()

            if loc_excl_kws and (
                any(ex in effective_loc for ex in loc_excl_kws)
                or any(ex in raw_loc_lower for ex in loc_excl_kws)
            ):
                return False
            return (
                any(kw in effective_loc for kw in loc_match_kws)
                or any(kw in raw_loc_lower for kw in loc_match_kws)
            )

        def _company_matches(fn: str) -> bool:
            stored_co = str(meta_lookup.get(fn, {}).get("current_company") or "").lower()
            return any(c in stored_co for c in company_filter)

        def _exp_matches(fn: str) -> bool:
            stored_exp = str(meta_lookup.get(fn, {}).get("exp_level") or "").strip().lower()
            return stored_exp == query_exp_level.lower()

        pre_filtered = list(base_filenames)
        company_boost_set: set = set()  # current-company matches → sorted to top of results

        if loc_match_kws:
            pre_filtered = [fn for fn in pre_filtered if _loc_matches(fn)]
            print(f"DEBUG: [search] location pre-filter: {len(pre_filtered)} resumes")
        if company_filter:
            co_filtered = [fn for fn in base_filenames if _company_matches(fn)]
            if co_filtered:
                if strict_company:
                    # Present tense ("working in X") → show ONLY current-company matches
                    pre_filtered = [fn for fn in pre_filtered if fn in set(co_filtered)]
                    print(f"DEBUG: [search] company strict-filter: {len(pre_filtered)} resumes")
                else:
                    # Past tense ("worked at X") → boost current matches to top, keep rest
                    company_boost_set = set(co_filtered)
                    print(f"DEBUG: [search] company boost set: {len(company_boost_set)} resumes (will be ranked first)")
            else:
                print(f"DEBUG: [search] company filter had 0 current-company matches — relying on semantic search")
        if query_exp_level and not exp_level:
            # Only apply query exp_level if the dropdown filter isn't already set
            exp_filtered = [fn for fn in pre_filtered if _exp_matches(fn)]
            if exp_filtered:
                pre_filtered = exp_filtered
                print(f"DEBUG: [search] exp_level pre-filter '{query_exp_level}': {len(pre_filtered)} resumes")
            else:
                print(f"DEBUG: [search] exp_level '{query_exp_level}' had 0 matches — skipping filter")

        # loc_pool restricts semantic results to the pre-filtered set.
        # Strict company filter (present tense) acts like a hard filter — only those candidates returned.
        # Past-tense company filter uses boost instead, so loc_pool stays None.
        # If location was explicitly specified but no candidates match, return empty — don't fall back to all.
        if loc_match_kws and not pre_filtered:
            print(f"DEBUG: [search] location pre-filter matched 0 resumes — returning empty")
            return {"resumes": [], "total": 0}

        if (loc_match_kws or query_exp_level or strict_company) and pre_filtered:
            loc_pool = pre_filtered
        else:
            loc_pool = None

        try:
            # Search limit: cover entire loc_pool (or full DB if no location filter)
            sem_limit = max(500, len(loc_pool) * 3) if loc_pool is not None else 500
            final_query = semantic_query or _raw_query
            # Reuse pre-computed embedding when the query wasn't modified by intent parsing
            reuse_vector = raw_vector if (final_query.strip() == _raw_query.strip()) else None
            results = search_resumes_hybrid(final_query, user_id, limit=sem_limit,
                                            api_key=creds["openrouter_key"],
                                            is_recruiter=is_recruiter,
                                            pre_computed_vector=reuse_vector)
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

                if company_boost_set and not has_role_signal:
                    # Boost only when there is no specific role/skill in the query.
                    # For role+company queries ("java developer from apple"), semantic
                    # search already ranks by role — boosting ALL company employees
                    # would promote non-Java Apple employees above Java developers.
                    # For company-only queries ("candidates from apple"), boost is the
                    # primary signal so all company matches go first.
                    boosted   = [fn for fn in ranked if fn in company_boost_set]
                    rest      = [fn for fn in ranked if fn not in company_boost_set]
                    sem_set   = set(ranked)
                    missed_co = [fn for fn in company_boost_set if fn not in sem_set]
                    ranked    = boosted + rest + missed_co
                    print(f"DEBUG: [search] company boost: {len(boosted)} boosted, {len(rest)} rest, {len(missed_co)} appended")
                elif company_boost_set and has_role_signal:
                    print(f"DEBUG: [search] role+company query — semantic order preserved, company boost skipped")

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
        loc_filter = location.strip()
        metro_substrings = _METRO_TO_SUBSTRINGS.get(loc_filter)
        if metro_substrings:
            # State-level filter (e.g. "California"): match ", CA" substring, exclude international
            subs_lower = [s.lower() for s in metro_substrings]
            resumes = [
                r for r in resumes
                if any(sub in str(r.get("location") or "").lower() for sub in subs_lower)
                and _classify_region(str(r.get("location") or "")) == "United States"
            ]
        else:
            # City-level filter: prefer metro_location field (LLM-resolved at ingest).
            # For older resumes without it, fall back to _suburb_to_metro + substring match.
            norm_filter = (_normalize_location(loc_filter) or loc_filter)
            norm_filter_lower = norm_filter.lower()
            city_only = norm_filter_lower.split(",")[0].strip()
            def _city_matches(r: dict) -> bool:
                stored_metro = str(r.get("metro_location") or "")
                if stored_metro and stored_metro != "nan":
                    return stored_metro.lower() == norm_filter_lower
                # Legacy fallback
                raw_loc = str(r.get("location") or "")
                return (
                    norm_filter_lower in (_normalize_location(raw_loc) or "").lower()
                    or city_only in raw_loc.lower()
                    or _suburb_to_metro(raw_loc) == norm_filter
                )
            resumes = [r for r in resumes if _city_matches(r)]

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


@router.post("/purge-dangling")
async def purge_dangling_metadata(
    user_id: str = Depends(get_current_user),
    role: str = Depends(get_user_role),
):
    """Remove resume_meta rows that have no corresponding chunks in the resumes table.

    Only managers may run this. Returns the list of purged filenames.
    """
    if role not in ("manager",):
        raise HTTPException(status_code=403, detail="Manager role required")

    from services.db.lancedb_client import purge_dangling_meta
    purged = purge_dangling_meta()
    return {"purged": purged, "count": len(purged)}


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
    """Update extracted text for a resume: re-index chunks/vectors AND refresh metadata."""
    creds = await resolve_credentials(user_id, x_openrouter_key, x_llm_model)
    from services.db.lancedb_client import update_resume_text as db_update

    # 1. Re-chunk, re-embed and store new vectors
    try:
        db_update(filename, user_id, body.text, api_key=creds["openrouter_key"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 2. Re-extract candidate metadata and update resume_meta table
    text = body.text.strip()
    if text:
        llm_config = build_llm_config(creds["openrouter_key"], creds.get("llm_model"))
        candidate_meta: dict = {}
        try:
            cls_result = _llm_classify_batch([(filename, text)], llm_config)
            candidate_meta = _clean_metadata(cls_result.get(filename, {}), llm_config)
            print(f"DEBUG: [update] Re-extracted metadata for '{filename}': {list(candidate_meta.keys())}")
        except Exception as e:
            print(f"DEBUG: [update] Metadata re-extraction failed for '{filename}': {e}")
        store_resume_validation(user_id, filename, {}, candidate_meta)

    return {"success": True, "filename": filename}


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
