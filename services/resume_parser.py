from pypdf import PdfReader
import docx
import re

_SECTION_ALIASES = {
    "PROFESSIONAL SUMMARY": {
        "summary",
        "professional summary",
        "profile",
        "career summary",
        "objective",
    },
    "CORE COMPETENCIES": {
        "skills",
        "technical skills",
        "key skills",
        "core competencies",
        "competencies",
    },
    "PROFESSIONAL EXPERIENCE": {
        "experience",
        "professional experience",
        "work experience",
        "employment history",
        "work history",
    },
    "EDUCATION": {
        "education",
        "academic background",
        "academic history",
    },
    "PROJECTS": {
        "projects",
        "personal projects",
    },
    "CERTIFICATIONS": {
        "certifications",
        "licenses",
        "licenses and certifications",
    },
}


def _trim_blank_edges(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and not lines[start]:
        start += 1
    while end > start and not lines[end - 1]:
        end -= 1
    return lines[start:end]


def _clean_lines(text: str) -> list[str]:
    cleaned = []
    for raw in text.splitlines():
        line = raw.replace("\t", " ").strip()
        if not line:
            cleaned.append("")
            continue
        line = re.sub(r"\s+", " ", line)
        # Normalize common unicode bullets to ASCII bullet marker.
        line = re.sub(r"^[•●▪◦·]\s*", "- ", line)
        cleaned.append(line)

    collapsed = []
    prev_blank = True
    for line in cleaned:
        if not line:
            if not prev_blank:
                collapsed.append("")
            prev_blank = True
            continue
        collapsed.append(line)
        prev_blank = False
    return _trim_blank_edges(collapsed)


def _detect_section_header(line: str) -> str | None:
    candidate = re.sub(r"[^A-Za-z ]", "", line).strip().lower()
    candidate = " ".join(candidate.split())
    if not candidate:
        return None

    for canonical, aliases in _SECTION_ALIASES.items():
        if candidate == canonical.lower() or candidate in aliases:
            return canonical
    return None


def to_ats_text(raw_text: str) -> str:
    """Normalize extracted resume text into ATS-friendly section structure."""
    lines = _clean_lines(raw_text or "")
    if not lines:
        return ""

    section_order = list(_SECTION_ALIASES.keys())
    sections: dict[str, list[str]] = {k: [] for k in section_order}
    contact: list[str] = []
    current_section: str | None = None
    saw_section = False

    for line in lines:
        if not line:
            target = sections[current_section] if current_section else contact
            if target and target[-1] != "":
                target.append("")
            continue

        detected = _detect_section_header(line)
        if detected:
            current_section = detected
            saw_section = True
            continue

        if current_section:
            sections[current_section].append(line)
        else:
            contact.append(line)

    if not saw_section:
        return "\n".join(lines)

    output = _trim_blank_edges(contact)
    for sec in section_order:
        body = _trim_blank_edges(sections[sec])
        if not body:
            continue
        if output and output[-1] != "":
            output.append("")
        output.append(sec)
        output.extend(body)

    return "\n".join(_trim_blank_edges(output))

def extract_text(file_path):
    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        return "\n".join(p.extract_text() for p in reader.pages)

    if file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)

    if file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    return ""
