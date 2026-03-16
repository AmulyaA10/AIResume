"""Canonical skill name lookup shared across job and resume routes."""

# Maps lowercase skill variants → canonical display name.
# Used in _normalize_job_fields (jobs.py) and _clean_metadata (resumes.py).
SKILL_CANONICAL: dict[str, str] = {
    # Languages
    "python": "Python", "java": "Java", "javascript": "JavaScript", "js": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript", "golang": "Go", "go": "Go",
    "rust": "Rust", "c++": "C++", "cpp": "C++", "c#": "C#", "csharp": "C#",
    "ruby": "Ruby", "php": "PHP", "swift": "Swift", "kotlin": "Kotlin",
    "scala": "Scala", "r": "R",
    # Frontend
    "react": "React", "reactjs": "React", "react.js": "React",
    "angular": "Angular", "angularjs": "Angular",
    "vue": "Vue.js", "vuejs": "Vue.js", "vue.js": "Vue.js",
    "nextjs": "Next.js", "next.js": "Next.js",
    "nuxtjs": "Nuxt.js", "nuxt.js": "Nuxt.js",
    "svelte": "Svelte", "html": "HTML", "css": "CSS", "sass": "Sass",
    "tailwind": "Tailwind CSS", "tailwindcss": "Tailwind CSS",
    "webpack": "Webpack", "vite": "Vite",
    # Backend / Frameworks
    "nodejs": "Node.js", "node.js": "Node.js", "node": "Node.js",
    "expressjs": "Express.js", "express.js": "Express.js", "express": "Express.js",
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask",
    "spring": "Spring Boot", "springboot": "Spring Boot", "spring boot": "Spring Boot",
    "rails": "Ruby on Rails", "laravel": "Laravel", "nestjs": "NestJS",
    "graphql": "GraphQL", "rest": "REST", "grpc": "gRPC",
    # Databases
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "mysql": "MySQL", "mongodb": "MongoDB", "mongo": "MongoDB",
    "redis": "Redis", "elasticsearch": "Elasticsearch",
    "cassandra": "Cassandra", "dynamodb": "DynamoDB",
    "sqlite": "SQLite", "mssql": "SQL Server", "sql server": "SQL Server",
    "sql": "SQL", "nosql": "NoSQL", "neo4j": "Neo4j",
    # Cloud / DevOps
    "aws": "AWS", "gcp": "GCP", "azure": "Azure",
    "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "terraform": "Terraform", "ansible": "Ansible", "helm": "Helm",
    "jenkins": "Jenkins", "github actions": "GitHub Actions",
    "gitlab ci": "GitLab CI", "circleci": "CircleCI",
    "ci/cd": "CI/CD", "cicd": "CI/CD",
    "linux": "Linux", "unix": "Unix", "bash": "Bash",
    # AI / Data
    "tensorflow": "TensorFlow", "pytorch": "PyTorch",
    "scikit-learn": "Scikit-learn", "sklearn": "Scikit-learn",
    "pandas": "Pandas", "numpy": "NumPy", "spark": "Apache Spark",
    "kafka": "Apache Kafka", "airflow": "Apache Airflow",
    "dbt": "dbt", "snowflake": "Snowflake", "databricks": "Databricks",
    "mlflow": "MLflow", "openai": "OpenAI API",
    # Tools / Process
    "git": "Git", "github": "GitHub", "gitlab": "GitLab",
    "jira": "Jira", "confluence": "Confluence",
    "agile": "Agile", "scrum": "Scrum", "kanban": "Kanban",
    "microservices": "Microservices", "api": "API",
}


def canonicalize_skill(s: str) -> str:
    """Return canonical display name for a skill string.

    Known skills → exact canonical name (e.g. 'reactjs' → 'React').
    Unknown skills → title-case if all-lowercase, otherwise kept as-is.
    """
    s = s.strip()
    canonical = SKILL_CANONICAL.get(s.lower())
    if canonical:
        return canonical
    # Title-case purely lowercase strings (e.g. 'stakeholder management' → 'Stakeholder Management')
    return s.title() if s == s.lower() else s
