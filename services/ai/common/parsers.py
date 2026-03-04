"""Shared output-cleaning helpers for LLM responses."""

import json
import re


def clean_json_output(content: str) -> str:
    """Remove markdown code-block fences (```json ... ```) from a string.

    LLMs frequently wrap JSON in fences even when instructed not to.
    This helper strips them so the result can be fed to ``json.loads``.
    """
    content = content.strip()
    if content.startswith("```"):
        # Remove first line (```json or ```)
        content = content.split("\n", 1)[1]
        # Remove last line (```)
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]
    return content.strip()


def repair_json(text: str) -> str:
    """Best-effort repair of common LLM JSON mistakes.

    Handles:
    - Trailing commas before } or ]
    - JavaScript-style single-line comments (// ...)
    - Block comments (/* ... */)
    - Extracts JSON object/array from surrounding prose
    - Single-quoted strings → double-quoted (simple cases)
    - Unquoted property names
    """
    # 1. Extract the outermost JSON object or array from surrounding text
    #    (LLMs sometimes prefix with "Here is the JSON:" or similar)
    brace_start = text.find("{")
    bracket_start = text.find("[")

    if brace_start == -1 and bracket_start == -1:
        return text  # nothing to extract

    # Pick whichever comes first, preferring { for objects
    if brace_start == -1:
        start = bracket_start
        open_char, close_char = "[", "]"
    elif bracket_start == -1:
        start = brace_start
        open_char, close_char = "{", "}"
    else:
        if brace_start <= bracket_start:
            start = brace_start
            open_char, close_char = "{", "}"
        else:
            start = bracket_start
            open_char, close_char = "[", "]"

    # Find matching close by counting nesting (skip chars inside strings)
    depth = 0
    in_string = False
    escape_next = False
    end = len(text)
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    text = text[start:end]

    # 2. Remove JavaScript-style comments (only outside strings)
    #    Block comments first, then single-line
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

    # Single-line comments: remove // ... but NOT inside strings
    # Simple approach: only remove // at the start of a line or after whitespace
    text = re.sub(r'(?m)^\s*//.*$', '', text)
    # Also remove inline // comments that follow a value
    # (but avoid mangling URLs like "https://...")
    text = re.sub(r'(?<!:)//[^\n"]*$', '', text, flags=re.MULTILINE)

    # 3. Remove trailing commas before } or ]
    #    This is the most common LLM JSON error
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # 4. Handle single-quoted strings → double-quoted
    #    Only do this if the text doesn't parse and has single quotes
    #    This is tricky because of apostrophes, so we only attempt if needed
    try:
        json.loads(text)
        return text  # already valid
    except json.JSONDecodeError:
        pass

    # Try replacing single quotes with double quotes
    # First, protect escaped single quotes and apostrophes in words
    # Only do this substitution if the text looks like it uses single quotes
    # for JSON strings (heuristic: check for ': or ,' patterns)
    if re.search(r"'[^']*'\s*:", text) or re.search(r":\s*'[^']*'", text):
        # Replace single-quoted keys and values
        # This regex matches 'value' patterns and replaces quotes
        repaired = re.sub(
            r"(?<=[{,\[])\s*'([^']*?)'\s*(?=:)",  # keys
            r' "\1" ',
            text,
        )
        repaired = re.sub(
            r"(?<=:)\s*'([^']*?)'\s*(?=[,}\]])",  # string values
            r' "\1" ',
            repaired,
        )
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            pass

    # 5. Handle unquoted property names (e.g., {name: "value"})
    unquoted = re.sub(
        r'(?<=[{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:',
        r' "\1":',
        text,
    )
    try:
        json.loads(unquoted)
        return unquoted
    except json.JSONDecodeError:
        pass

    return text


# ─── Keyword-based skill extraction (deterministic fallback) ─────────────────
SKILL_PATTERNS = [
    # Languages
    "Python", "Java", "JavaScript", "TypeScript", "C\\+\\+", "C#", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "SQL", "Bash",
    # Frameworks
    "React", "Angular", "Vue", "Django", "Flask", "FastAPI", "Spring", "Express",
    "Next\\.js", "Node\\.js", "Rails", ".NET", "Laravel", "Svelte",
    # Cloud / DevOps
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Jenkins",
    "CI/CD", "GitHub Actions", "CircleCI", "Ansible",
    # Data / ML
    "TensorFlow", "PyTorch", "Spark", "Hadoop", "Kafka", "Airflow",
    "Pandas", "NumPy", "Scikit-learn", "LangChain", "OpenAI",
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "DynamoDB",
    "Cassandra", "SQLite", "Oracle",
    # Tools
    "Git", "Jira", "Figma", "Tableau", "Power BI", "Grafana", "Splunk",
    "Linux", "REST", "GraphQL", "gRPC", "Microservices", "Agile", "Scrum",
]


def extract_skills_from_text(text: str) -> list:
    """Extract technology/tool mentions from free text using keyword matching.

    Shared safety-net used by resume_generator_graph, skill_gap_graph, and
    any other module that needs deterministic skill extraction as an LLM fallback.
    """
    found = []
    seen_lower: set = set()
    for pattern in SKILL_PATTERNS:
        if re.search(r'\b' + pattern + r'\b', text, re.IGNORECASE):
            canonical = pattern.replace("\\+", "+").replace("\\.", ".")
            if canonical.lower() not in seen_lower:
                found.append(canonical)
                seen_lower.add(canonical.lower())
    return found


def safe_parse_json(raw_content: str) -> dict:
    """Parse LLM output as JSON with automatic repair.

    1. Strip markdown code fences via ``clean_json_output``.
    2. Attempt ``json.loads`` on the cleaned string.
    3. On failure, run ``repair_json`` and retry.
    4. Raises ``json.JSONDecodeError`` only if both attempts fail.
    """
    cleaned = clean_json_output(raw_content)

    # Fast path — valid JSON on first try
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Slow path — attempt repair
    repaired = repair_json(cleaned)
    return json.loads(repaired)  # let it raise if still invalid
