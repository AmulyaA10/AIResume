#!/usr/bin/env python3
"""Generate synthetic resumes, job descriptions, and edge-case documents.

Usage:
    python scripts/generate_synthetic_data.py            # defaults: 20 resumes, 5 JDs
    python scripts/generate_synthetic_data.py --resumes 100 --jds 50
    python scripts/generate_synthetic_data.py --output data/synthetic

Output structure:
    <output>/
        resumes/
            strong/          (classification: resume_valid_strong)
            good/            (classification: resume_valid_good)
            weak/            (classification: resume_valid_but_weak)
            invalid/         (classification: resume_invalid_or_incomplete)
            not_resume/      (classification: not_resume)
        job_descriptions/
        manifest.json        (metadata for all generated files)
"""

import argparse
import json
import os
import random
import string
import sys
from datetime import datetime

try:
    from faker import Faker
except ImportError:
    print("ERROR: faker is required.  pip install faker")
    sys.exit(1)

fake = Faker()
Faker.seed(42)
random.seed(42)

# ---------------------------------------------------------------------------
# Locale configs — add a new entry here to support a new region
# ---------------------------------------------------------------------------
LOCALE_CONFIGS = {
    "india": {
        "faker_locale": "en_IN",
        "phone": lambda: f"+91 {random.choice(['6','7','8','9'])}{random.randint(100000000,999999999):09d}",
        "locations": {
            "bangalore": ["Bangalore, India"],
            "hyderabad": ["Hyderabad, India"],
            "mumbai":    ["Mumbai, India", "Pune, India", "Thane, India"],
            "chennai":   ["Chennai, India"],
            "delhi":     ["New Delhi, India", "Gurugram, India", "Noida, India"],
            "other":     ["Kolkata, India", "Ahmedabad, India", "Kochi, India", "Jaipur, India"],
            "remote":    ["Remote"],
        },
        "weights": {"bangalore": 0.50, "hyderabad": 0.15, "mumbai": 0.12,
                    "chennai": 0.08, "delhi": 0.08, "other": 0.04, "remote": 0.03},
        "label": "Bangalore-heavy",
    },
    "uk": {
        "faker_locale": "en_GB",
        "phone": lambda: f"+44 07{random.randint(700,999)} {random.randint(100000,999999)}",
        "locations": {
            "london":     ["London, UK"],
            "manchester": ["Manchester, UK"],
            "edinburgh":  ["Edinburgh, Scotland"],
            "birmingham": ["Birmingham, UK"],
            "bristol":    ["Bristol, UK"],
            "cambridge":  ["Cambridge, UK"],
            "leeds":      ["Leeds, UK"],
            "glasgow":    ["Glasgow, Scotland"],
            "remote":     ["Remote (UK)"],
        },
        "weights": {"london": 0.50, "manchester": 0.12, "edinburgh": 0.08,
                    "birmingham": 0.08, "bristol": 0.07, "cambridge": 0.05,
                    "leeds": 0.05, "glasgow": 0.03, "remote": 0.02},
        "label": "London-heavy",
    },
    "us": {
        "faker_locale": "en_US",
        "phone": None,
        "locations": {
            "sf":      ["San Francisco, CA", "San Jose, CA", "Oakland, CA"],
            "ny":      ["New York, NY", "Brooklyn, NY"],
            "seattle": ["Seattle, WA", "Bellevue, WA"],
            "austin":  ["Austin, TX"],
            "boston":  ["Boston, MA"],
            "chicago": ["Chicago, IL"],
            "la":      ["Los Angeles, CA"],
            "denver":  ["Denver, CO"],
            "atlanta": ["Atlanta, GA"],
            "remote":  ["Remote (US)"],
        },
        "weights": {"sf": 0.22, "ny": 0.18, "seattle": 0.14, "austin": 0.10,
                    "boston": 0.09, "chicago": 0.08, "la": 0.07, "denver": 0.06,
                    "atlanta": 0.04, "remote": 0.02},
        "label": "SF/NY-heavy",
    },
    "eu": {
        "faker_locale": "en_US",
        "phone": lambda: f"+{random.randint(30,49)} {random.randint(10,99)} {random.randint(1000000,9999999)}",
        "locations": {
            "berlin":    ["Berlin, Germany"],
            "paris":     ["Paris, France"],
            "amsterdam": ["Amsterdam, Netherlands"],
            "stockholm": ["Stockholm, Sweden"],
            "madrid":    ["Madrid, Spain"],
            "dublin":    ["Dublin, Ireland"],
            "zurich":    ["Zurich, Switzerland"],
            "munich":    ["Munich, Germany"],
            "remote":    ["Remote (EU)"],
        },
        "weights": {"berlin": 0.22, "paris": 0.18, "amsterdam": 0.14, "stockholm": 0.10,
                    "madrid": 0.09, "dublin": 0.09, "zurich": 0.08, "munich": 0.07, "remote": 0.03},
        "label": "Berlin/Paris-heavy",
    },
    "canada": {
        "faker_locale": "en_CA",
        "phone": None,
        "locations": {
            "toronto":   ["Toronto, ON", "Mississauga, ON"],
            "vancouver": ["Vancouver, BC", "Burnaby, BC"],
            "montreal":  ["Montreal, QC"],
            "calgary":   ["Calgary, AB"],
            "ottawa":    ["Ottawa, ON"],
            "remote":    ["Remote (Canada)"],
        },
        "weights": {"toronto": 0.40, "vancouver": 0.25, "montreal": 0.15,
                    "calgary": 0.10, "ottawa": 0.05, "remote": 0.05},
        "label": "Toronto-heavy",
    },
    "australia": {
        "faker_locale": "en_AU",
        "phone": lambda: f"+61 0{random.randint(4,5)}{random.randint(10000000,99999999)}",
        "locations": {
            "sydney":    ["Sydney, NSW"],
            "melbourne": ["Melbourne, VIC"],
            "brisbane":  ["Brisbane, QLD"],
            "perth":     ["Perth, WA"],
            "remote":    ["Remote (Australia)"],
        },
        "weights": {"sydney": 0.40, "melbourne": 0.30, "brisbane": 0.15,
                    "perth": 0.10, "remote": 0.05},
        "label": "Sydney-heavy",
    },
    "singapore": {
        "faker_locale": "en_US",
        "phone": lambda: f"+65 {random.randint(81000000,99999999)}",
        "locations": {
            "central":  ["Singapore (Central)"],
            "east":     ["Singapore (East)"],
            "west":     ["Singapore (West)"],
            "remote":   ["Remote (Singapore)"],
        },
        "weights": {"central": 0.50, "east": 0.20, "west": 0.20, "remote": 0.10},
        "label": "Singapore",
    },
}

# Aliases: make demo UK=5 → 'uk', IN=5 → 'india', etc.
LOCALE_ALIASES = {
    "in": "india", "gb": "uk", "au": "australia", "sg": "singapore",
    "ca": "canada", "us": "us", "eu": "eu",
}

# Lazy-initialised Faker instances per locale
_faker_cache: dict = {}

def _get_faker(locale_key: str) -> Faker:
    cfg = LOCALE_CONFIGS.get(locale_key, {})
    fl  = cfg.get("faker_locale", "en_US")
    if fl not in _faker_cache:
        _faker_cache[fl] = Faker(fl)
    return _faker_cache[fl]


# Current locale being generated (None = global default)
_CURRENT_LOCALE: str | None = None


def _gen_name() -> str:
    if _CURRENT_LOCALE:
        return _get_faker(_CURRENT_LOCALE).name()
    return fake.name()


def _gen_phone() -> str:
    if _CURRENT_LOCALE:
        phone_fn = LOCALE_CONFIGS[_CURRENT_LOCALE].get("phone")
        if phone_fn:
            return phone_fn()
        return _get_faker(_CURRENT_LOCALE).phone_number()
    return fake.phone_number()

# ---------------------------------------------------------------------------
# Core Tech Pools
# ---------------------------------------------------------------------------

TECH_SKILLS = [
    "Python", "Java", "TypeScript", "JavaScript", "Go", "Rust", "C++", "C#",
    "React", "Angular", "Vue.js", "Next.js", "Node.js", "FastAPI", "Django",
    "Flask", "Spring Boot", "PostgreSQL", "MySQL", "MongoDB", "Redis",
    "Elasticsearch", "Docker", "Kubernetes", "Terraform", "AWS", "GCP", "Azure",
    "CI/CD", "GitHub Actions", "GraphQL", "REST", "Apache Kafka",
    "TensorFlow", "PyTorch", "Scikit-learn", "Pandas", "NumPy",
    "Linux", "Git", "Agile", "Scrum",
]

SOFT_SKILLS = [
    "Leadership", "Team collaboration", "Communication", "Problem-solving",
    "Mentoring", "Cross-functional teamwork", "Strategic planning",
    "Stakeholder management", "Technical writing", "Project management",
]

TITLES = [
    "Software Engineer", "Senior Software Engineer", "Staff Engineer",
    "Full-Stack Developer", "Frontend Engineer", "Backend Engineer",
    "DevOps Engineer", "Site Reliability Engineer", "Data Engineer",
    "Machine Learning Engineer", "Cloud Architect", "Engineering Manager",
    "Platform Engineer", "Security Engineer",
]

COMPANIES = [
    "Google", "Amazon", "Meta", "Apple", "Microsoft", "Netflix", "Stripe",
    "Uber", "Airbnb", "Shopify", "Salesforce", "Adobe", "Atlassian",
    "Datadog", "Snowflake", "Coinbase", "Acme Corp", "TechStart Inc",
    "DataFlow Systems", "CloudNine Solutions", "ByteForge", "QuantumLeap AI",
]

UNIVERSITIES = [
    ("MIT", "Computer Science"),
    ("Stanford University", "Computer Science"),
    ("UC Berkeley", "Electrical Engineering & CS"),
    ("Carnegie Mellon University", "Software Engineering"),
    ("Georgia Tech", "Computer Science"),
    ("University of Washington", "Information Systems"),
    ("University of Michigan", "Computer Engineering"),
    ("University of Texas at Austin", "Computer Science"),
    ("Purdue University", "Computer Science"),
    ("University of Illinois", "Computer Science"),
    ("State University", "Information Technology"),
    ("Community College", "Computer Science"),
]

DEGREES = ["B.S.", "B.A.", "M.S.", "M.Eng.", "Ph.D."]

# ---------------------------------------------------------------------------
# Industry-specific Pools (for diverse semantic search personas)
# ---------------------------------------------------------------------------

INDUSTRIES = [
    "software_engineering",
    "data_science",
    "devops_cloud",
    "healthcare_tech",
    "fintech",
    "climate_tech",
    "media_advertising",
    "cybersecurity",
    "machine_learning",
    "product_management",
    "startup_generalist",
    "enterprise_consulting",
]

INDUSTRY_SKILLS = {
    "software_engineering": [
        "Python", "TypeScript", "React", "Node.js", "PostgreSQL", "Docker",
        "Kubernetes", "AWS", "REST APIs", "CI/CD", "Git", "Agile",
    ],
    "data_science": [
        "Python", "Pandas", "NumPy", "Scikit-learn", "TensorFlow", "PyTorch",
        "SQL", "Spark", "Tableau", "dbt", "Airflow", "Databricks",
        "A/B testing", "statistical modeling", "feature engineering",
    ],
    "devops_cloud": [
        "Kubernetes", "Terraform", "AWS", "GCP", "Azure", "Docker",
        "Ansible", "Prometheus", "Grafana", "GitHub Actions", "Jenkins",
        "Linux", "Bash scripting", "Site Reliability Engineering",
    ],
    "healthcare_tech": [
        "HL7 FHIR", "Epic EHR integration", "HIPAA compliance",
        "clinical data pipelines", "Python", "SQL", "AWS",
        "FDA 21 CFR Part 11", "medical device software", "ICD-10 coding",
        "telehealth platforms", "EHR systems", "DICOM imaging",
    ],
    "fintech": [
        "Python", "Java", "PostgreSQL", "Kafka", "FCA compliance",
        "PCI-DSS", "PSD2", "GDPR for fintech", "trading systems",
        "risk modeling", "fraud detection", "blockchain", "Swift messaging",
        "payment gateways", "regulatory reporting",
    ],
    "climate_tech": [
        "Python", "geospatial analysis", "carbon accounting software",
        "IoT sensor data", "energy modeling", "grid optimization",
        "GIS tools", "SCADA systems", "renewable energy forecasting",
        "ESG reporting", "Spark", "AWS", "sustainability metrics",
    ],
    "media_advertising": [
        "programmatic advertising", "DSP/SSP platforms", "Google DV360",
        "The Trade Desk", "ad tech stack", "audience segmentation",
        "upfront advertising sales", "CRM", "campaign attribution",
        "Madison Avenue agency experience", "content management systems",
        "digital media buying", "Nielsen ratings",
    ],
    "cybersecurity": [
        "penetration testing", "SOC operations", "SIEM (Splunk, QRadar)",
        "incident response", "threat intelligence", "zero-trust architecture",
        "OWASP Top 10", "ISO 27001", "NIST framework",
        "cloud security (AWS/GCP)", "PKI", "vulnerability management",
        "network forensics", "malware analysis",
    ],
    "machine_learning": [
        "PyTorch", "TensorFlow", "transformer models", "LLMs",
        "RAG pipelines", "recommendation systems", "collaborative filtering",
        "ranking algorithms", "user personalization", "MLOps",
        "feature stores", "model serving", "A/B testing", "Kubeflow",
    ],
    "product_management": [
        "product roadmap", "OKRs", "user research", "Figma",
        "stakeholder alignment", "go-to-market strategy",
        "Agile/Scrum", "JIRA", "data-driven product decisions",
        "0 to 1 product development", "cross-functional leadership",
        "competitive analysis", "product analytics",
    ],
    "startup_generalist": [
        "full-stack development", "React", "Node.js", "Python", "AWS",
        "wore multiple hats", "early-stage startup", "Series A",
        "built team from 3 to 20", "owned end-to-end delivery",
        "product and engineering overlap", "rapid prototyping",
        "zero to one", "technical co-founder experience",
    ],
    "enterprise_consulting": [
        "SAP", "Salesforce CRM", "enterprise architecture",
        "digital transformation", "change management",
        "stakeholder management", "executive presentations",
        "business process optimization", "ERP implementation",
        "Big 4 consulting", "cloud migration strategy",
    ],
}

INDUSTRY_TITLES = {
    "software_engineering": [
        "Software Engineer", "Senior Software Engineer", "Staff Engineer",
        "Full-Stack Developer", "Backend Engineer", "Frontend Engineer",
    ],
    "data_science": [
        "Data Scientist", "Senior Data Scientist", "Analytics Engineer",
        "Data Analyst", "Research Scientist", "Applied Scientist",
    ],
    "devops_cloud": [
        "DevOps Engineer", "Site Reliability Engineer", "Cloud Engineer",
        "Infrastructure Engineer", "Platform Engineer",
    ],
    "healthcare_tech": [
        "Healthcare Software Engineer", "Clinical Data Engineer",
        "Health Informatics Specialist", "EHR Integration Developer",
        "Digital Health Product Manager",
    ],
    "fintech": [
        "Fintech Software Engineer", "Quantitative Developer",
        "Payments Engineer", "Risk Systems Engineer",
        "Regulatory Technology Engineer",
    ],
    "climate_tech": [
        "Climate Tech Engineer", "Energy Systems Software Engineer",
        "Sustainability Data Analyst", "Grid Technology Developer",
        "Carbon Accounting Platform Engineer",
    ],
    "media_advertising": [
        "Ad Tech Engineer", "Programmatic Advertising Manager",
        "Digital Media Strategist", "Campaign Analytics Lead",
        "Publisher Technology Manager",
    ],
    "cybersecurity": [
        "Security Engineer", "Penetration Tester", "SOC Analyst",
        "Security Architect", "Threat Intelligence Analyst",
        "Cloud Security Engineer",
    ],
    "machine_learning": [
        "Machine Learning Engineer", "Applied ML Scientist",
        "MLOps Engineer", "Recommendation Systems Engineer",
        "NLP Engineer", "Computer Vision Engineer",
    ],
    "product_management": [
        "Product Manager", "Senior Product Manager", "Group Product Manager",
        "Technical Product Manager", "Principal PM",
    ],
    "startup_generalist": [
        "Software Engineer", "Technical Lead", "Engineering Manager",
        "CTO (early-stage)", "Full-Stack Engineer",
    ],
    "enterprise_consulting": [
        "Technology Consultant", "Solutions Architect",
        "Senior Consultant", "Digital Transformation Lead",
        "Enterprise Architect",
    ],
}

INDUSTRY_COMPANIES = {
    "healthcare_tech": [
        "Epic Systems", "Cerner Health", "Veeva Systems", "Meditech",
        "Teladoc Health", "23andMe", "Tempus AI", "Flatiron Health",
        "Nuvation Bio", "Wellpath", "Athenahealth",
    ],
    "fintech": [
        "Stripe", "Plaid", "Robinhood", "Chime", "Affirm", "Klarna",
        "Revolut", "Monzo", "Square (Block)", "Wise", "Adyen",
        "Goldman Sachs Engineering", "JPMorgan Chase Tech",
    ],
    "climate_tech": [
        "Tesla Energy", "Sunrun", "Enphase Energy", "Commonwealth Fusion",
        "Form Energy", "Watershed", "Pachama", "Xcel Energy",
        "Aurora Solar", "Arcadia Power", "WattTime",
    ],
    "media_advertising": [
        "NBCUniversal", "WPP", "Omnicom Group", "Publicis Groupe",
        "The Trade Desk", "DoubleVerify", "IAS", "Spotify Advertising",
        "BuzzFeed", "Condé Nast", "Hearst Media",
    ],
    "cybersecurity": [
        "CrowdStrike", "Palo Alto Networks", "SentinelOne", "Mandiant",
        "Rapid7", "Qualys", "Tenable", "Darktrace",
        "FireEye", "Okta", "CyberArk",
    ],
    "default": COMPANIES,
}

# ---------------------------------------------------------------------------
# Location Pools (for geo semantic search)
# ---------------------------------------------------------------------------

LOCATIONS = {
    "sf_bay_area": [
        "San Francisco, CA", "San Jose, CA", "Palo Alto, CA",
        "Mountain View, CA", "Sunnyvale, CA", "Oakland, CA",
    ],
    "nyc": [
        "New York, NY", "Brooklyn, NY", "Manhattan, NY",
        "Jersey City, NJ",
    ],
    "seattle": [
        "Seattle, WA", "Bellevue, WA", "Redmond, WA",
    ],
    "austin": [
        "Austin, TX", "Round Rock, TX",
    ],
    "london": [
        "London, UK", "London, England",
    ],
    "berlin": [
        "Berlin, Germany",
    ],
    "remote": [
        "Remote (US)", "Remote (EST)", "Remote (PST)", "Remote (CET)",
        "Remote — willing to overlap with US Pacific hours",
        "Fully remote, based in Austin TX",
        "Remote-first, located in New York",
    ],
    "other_us": [
        "Boston, MA", "Chicago, IL", "Denver, CO", "Atlanta, GA",
        "Miami, FL", "Los Angeles, CA", "Portland, OR",
    ],
}

LOCATION_WEIGHTS = {
    "sf_bay_area": 0.20, "nyc": 0.18, "seattle": 0.10,
    "austin": 0.08, "london": 0.10, "berlin": 0.06,
    "remote": 0.18, "other_us": 0.10,
}

# India locations — Bangalore-heavy as requested
def _random_location():
    if _CURRENT_LOCALE:
        cfg    = LOCALE_CONFIGS[_CURRENT_LOCALE]
        locs   = cfg["locations"]
        wts    = cfg["weights"]
        region = random.choices(list(wts.keys()), weights=list(wts.values()))[0]
        return random.choice(locs[region]), _CURRENT_LOCALE
    region = random.choices(
        list(LOCATION_WEIGHTS.keys()),
        weights=list(LOCATION_WEIGHTS.values())
    )[0]
    return random.choice(LOCATIONS[region]), region


# ---------------------------------------------------------------------------
# Work culture / relocation signals
# ---------------------------------------------------------------------------

CULTURE_PHRASES = {
    "startup": [
        "thrives in fast-paced startup environments",
        "comfortable with ambiguity and rapidly shifting priorities",
        "experience scaling teams from 5 to 50 engineers",
        "built the product from zero to first 10K users",
        "wore multiple hats across engineering and product",
        "joined as employee #8 at Series A",
    ],
    "enterprise": [
        "led enterprise-wide digital transformation initiatives",
        "managed stakeholder alignment across 6 business units",
        "delivered multi-million dollar consulting engagements",
        "experience in Fortune 500 environments",
        "worked within structured Agile/SAFe delivery frameworks",
    ],
    "remote": [
        "fully remote for 4+ years, async-first mindset",
        "experienced working across distributed global teams",
        "strong written communication for remote collaboration",
        "results-oriented — no fixed hours, focused on outcomes",
        "overlap with US Pacific timezone preferred",
    ],
    "relocation": [
        "open to relocation to San Francisco Bay Area",
        "willing to relocate — currently based in Austin",
        "previously lived in California, considering return",
        "open to on-site roles in Seattle or NYC",
    ],
}


def _culture_phrase(n=1):
    all_phrases = [p for phrases in CULTURE_PHRASES.values() for p in phrases]
    return random.sample(all_phrases, k=min(n, len(all_phrases)))


# ---------------------------------------------------------------------------
# Shared generators
# ---------------------------------------------------------------------------

def _random_skills_for_industry(industry, n=(5, 12)):
    pool = INDUSTRY_SKILLS.get(industry, TECH_SKILLS)
    k = min(random.randint(*n), len(pool))
    return random.sample(pool, k=k)


def _random_title_for_industry(industry):
    pool = INDUSTRY_TITLES.get(industry, TITLES)
    return random.choice(pool)


def _random_company_for_industry(industry):
    pool = INDUSTRY_COMPANIES.get(industry, INDUSTRY_COMPANIES["default"])
    return random.choice(pool)


def _random_bullet(quantified=True, industry=None):
    actions = [
        "Designed and built", "Led migration of", "Implemented", "Architected",
        "Optimized", "Reduced", "Increased", "Automated", "Scaled",
        "Developed", "Launched", "Refactored", "Deployed", "Mentored",
        "Spearheaded", "Owned end-to-end delivery of", "Rebuilt",
    ]
    objects_by_industry = {
        "healthcare_tech": [
            "FHIR-based patient data pipeline", "EHR integration layer",
            "clinical decision support tool", "HIPAA-compliant data warehouse",
            "telehealth scheduling platform", "medical imaging workflow",
        ],
        "fintech": [
            "real-time fraud detection system", "payment reconciliation engine",
            "regulatory reporting pipeline", "risk scoring model",
            "PCI-DSS compliant infrastructure", "trading execution platform",
        ],
        "climate_tech": [
            "carbon footprint tracking dashboard", "EV charging optimization system",
            "solar energy forecasting model", "grid load balancing algorithm",
            "ESG reporting pipeline", "renewable energy marketplace",
        ],
        "media_advertising": [
            "programmatic ad auction engine", "audience segmentation platform",
            "campaign attribution dashboard", "ad delivery optimization system",
            "publisher revenue analytics tool", "real-time bidding infrastructure",
        ],
        "machine_learning": [
            "recommendation system serving 50M+ users",
            "collaborative filtering pipeline",
            "real-time ranking algorithm",
            "LLM fine-tuning pipeline", "RAG-based search system",
            "user personalization engine",
        ],
        "default": [
            "microservices architecture", "CI/CD pipeline", "data pipeline",
            "customer-facing dashboard", "real-time notification system",
            "authentication system", "search infrastructure", "monitoring stack",
            "API gateway", "ETL workflow", "distributed cache layer",
        ],
    }
    objects = objects_by_industry.get(industry, objects_by_industry["default"])
    metrics = [
        "reducing deploy time by {n}%", "improving throughput by {n}x",
        "serving {n}K+ daily active users", "processing {n}M+ events daily",
        "cutting latency from {a}ms to {b}ms", "saving ${n}K annually",
        "increasing test coverage to {n}%", "reducing error rate by {n}%",
        "supporting {n}+ enterprise clients", "reducing manual effort by {n}%",
    ]
    bullet = f"{random.choice(actions)} {random.choice(objects)}"
    if quantified and random.random() > 0.3:
        metric = random.choice(metrics)
        metric = metric.format(
            n=random.randint(10, 95),
            a=random.randint(200, 800),
            b=random.randint(20, 100)
        )
        bullet += f", {metric}"
    return bullet


def _random_experience(n_roles=(1, 4), industry="software_engineering"):
    entries = []
    current_year = 2026
    for i in range(random.randint(*n_roles)):
        end_year = current_year - i * random.randint(1, 3)
        start_year = end_year - random.randint(1, 4)
        period = f"{start_year} – {'Present' if i == 0 else end_year}"
        n_bullets = random.randint(2, 5)
        entries.append({
            "title": _random_title_for_industry(industry),
            "company": _random_company_for_industry(industry),
            "period": period,
            "bullets": [
                _random_bullet(quantified=(random.random() > 0.2), industry=industry)
                for _ in range(n_bullets)
            ],
        })
    return entries


def _random_education(level="good"):
    uni, field = random.choice(UNIVERSITIES)
    degree = random.choice(DEGREES[:3])
    if level == "strong":
        degree = random.choice(DEGREES)
        uni, field = random.choice(UNIVERSITIES[:6])
    year = random.randint(2010, 2024)
    return [{"degree": f"{degree} {field}", "school": uni, "year": str(year)}]


# ---------------------------------------------------------------------------
# Strong Resume
# ---------------------------------------------------------------------------

def generate_strong_resume():
    industry = random.choice(INDUSTRIES)
    name = _gen_name()
    email = fake.email()
    phone = _gen_phone()
    location, region = _random_location()
    linkedin = f"linkedin.com/in/{name.lower().replace(' ', '-')}"
    github = f"github.com/{fake.user_name()}"

    skills = _random_skills_for_industry(industry, n=(8, 14))
    experience = _random_experience(n_roles=(2, 4), industry=industry)
    education = _random_education(level="strong")
    culture = _culture_phrase(n=2)

    title = _random_title_for_industry(industry)
    summary = (
        f"Results-driven {title.lower()} with {random.randint(6, 15)}+ years of experience. "
        f"{culture[0].capitalize()}. Proven track record of leading cross-functional teams and "
        f"delivering high-impact projects. {culture[1].capitalize()}."
    )

    certifications = random.sample([
        "AWS Solutions Architect Professional",
        "Google Cloud Professional Engineer",
        "Certified Kubernetes Administrator (CKA)",
        "HashiCorp Certified Terraform Associate",
        "Certified Information Systems Security Professional (CISSP)",
        "Certified Scrum Master (CSM)",
        "PMI Project Management Professional (PMP)",
    ], k=random.randint(1, 3))

    text = f"""{name}
{email} | {phone} | {location}
LinkedIn: {linkedin} | GitHub: {github}

PROFESSIONAL SUMMARY
{summary}

TECHNICAL SKILLS
{', '.join(skills)}

EXPERIENCE
"""
    for exp in experience:
        text += f"\n{exp['title']} | {exp['company']} | {exp['period']}\n"
        for b in exp["bullets"]:
            text += f"- {b}\n"

    text += "\nEDUCATION\n"
    for edu in education:
        text += f"{edu['degree']} | {edu['school']} | {edu['year']}\n"

    text += "\nCERTIFICATIONS\n"
    for cert in certifications:
        text += f"- {cert}\n"

    return {
        "text": text,
        "json": {
            "contact": {"name": name, "email": email, "phone": phone, "location": location,
                        "linkedin": linkedin, "github": github},
            "summary": summary,
            "skills": skills,
            "experience": experience,
            "education": education,
            "certifications": certifications,
            "industry": industry,
            "region": region,
        },
        "classification": "resume_valid_strong",
        "expected_score_range": (25, 30),
    }


# ---------------------------------------------------------------------------
# Good Resume
# ---------------------------------------------------------------------------

def generate_good_resume():
    industry = random.choice(INDUSTRIES)
    name = _gen_name()
    email = fake.email()
    phone = _gen_phone()
    location, region = _random_location()

    skills = _random_skills_for_industry(industry, n=(5, 10))
    experience = _random_experience(n_roles=(1, 3), industry=industry)
    education = _random_education(level="good")
    culture = _culture_phrase(n=1)

    title = _random_title_for_industry(industry)
    summary = (
        f"{title} with {random.randint(3, 8)} years of experience. "
        f"{culture[0].capitalize()}. "
        f"Skilled in {', '.join(random.sample(skills[:5], min(3, len(skills))))}."
    )

    text = f"""{name}
{email} | {phone} | {location}

SUMMARY
{summary}

SKILLS
{', '.join(skills)}

EXPERIENCE
"""
    for exp in experience:
        text += f"\n{exp['title']} | {exp['company']} | {exp['period']}\n"
        for b in exp["bullets"]:
            text += f"- {b}\n"

    text += "\nEDUCATION\n"
    for edu in education:
        text += f"{edu['degree']} | {edu['school']} | {edu['year']}\n"

    return {
        "text": text,
        "json": {
            "contact": {"name": name, "email": email, "phone": phone, "location": location},
            "summary": summary,
            "skills": skills,
            "experience": experience,
            "education": education,
            "industry": industry,
            "region": region,
        },
        "classification": "resume_valid_good",
        "expected_score_range": (18, 24),
    }


# ---------------------------------------------------------------------------
# Weak Resume
# ---------------------------------------------------------------------------

def generate_weak_resume():
    industry = random.choice(INDUSTRIES)
    name = _gen_name()
    email = fake.email()
    location, _ = _random_location()

    skills = _random_skills_for_industry(industry, n=(2, 5))

    text = f"""{name}
{email} | {location}

Skills: {', '.join(skills)}

Work Experience:
{_random_title_for_industry(industry)} at {_random_company_for_industry(industry)}
- Worked on various projects
- Helped with development tasks
- Attended team meetings and sprint planning
- Fixed bugs and resolved issues

Education:
{random.choice(DEGREES[:2])} in Computer Science
"""

    return {
        "text": text,
        "json": {"contact": {"name": name, "email": email}, "skills": skills},
        "classification": "resume_valid_but_weak",
        "expected_score_range": (11, 17),
    }


# ---------------------------------------------------------------------------
# Invalid Resume
# ---------------------------------------------------------------------------

def generate_invalid_resume():
    def _garbled():
        chars = string.ascii_letters + " \n"
        garble = "".join(random.choices(chars, k=200))
        return f"{fake.name()}\n\n{garble}"

    variants = [
        lambda: f"{fake.name()}\n{fake.email()}\n\nLooking for a job in tech.",
        lambda: "Resume\n\nI am a developer.\nSkills: coding\nExperience: some",
        _garbled,
        lambda: (
            f"Hi my name is {fake.name()} and I want to work at your company. "
            f"I know {random.choice(TECH_SKILLS)} and {random.choice(TECH_SKILLS)}. "
            f"Please hire me. I am very good at what I do. Thank you."
        ),
    ]

    text = random.choice(variants)()
    return {
        "text": text,
        "json": None,
        "classification": "resume_invalid_or_incomplete",
        "expected_score_range": (1, 10),
    }


# ---------------------------------------------------------------------------
# Not a Resume
# ---------------------------------------------------------------------------

def generate_not_resume():
    variants = [
        lambda: (
            "Chocolate Chip Cookies\n\nIngredients:\n- 2 cups flour\n- 1 cup butter\n"
            "- 1 cup sugar\n- 2 eggs\n- 1 tsp vanilla\n\nInstructions:\n"
            "Preheat oven to 350F. Mix ingredients. Bake for 12 minutes."
        ),
        lambda: (
            "TERMS OF SERVICE\n\nLast updated: January 2026\n\n"
            "By accessing this website, you agree to these terms. "
            "The company reserves the right to modify these terms at any time."
        ),
        lambda: (
            f"Meeting Notes - {fake.date()}\n\nAttendees: {fake.name()}, {fake.name()}\n\n"
            "Agenda:\n1. Q1 budget review\n2. Product roadmap\n3. Hiring pipeline\n\n"
            "Action items:\n- Review proposal by Friday\n- Schedule follow-up with marketing"
        ),
        lambda: f"The Impact of AI on Modern Society\n\n{'  '.join(fake.paragraphs(nb=3))}",
        lambda: (
            "INVOICE #2026-0042\n\nBill To: Acme Corp\nDate: March 2026\n\n"
            "Services:\n- Software consulting: $12,000\n- Infrastructure setup: $4,500\n\n"
            "Total Due: $16,500\nPayment due within 30 days."
        ),
    ]

    text = random.choice(variants)()
    return {
        "text": text,
        "json": None,
        "classification": "not_resume",
        "expected_score_range": (0, 0),
    }


# ---------------------------------------------------------------------------
# Job Descriptions — industry-aware, diverse, geo-rich
# ---------------------------------------------------------------------------

JD_TEMPLATES = {
    "software_engineering": {
        "titles": ["Senior Full-Stack Engineer", "Backend Engineer (Python/Go)",
                   "Frontend Engineer (React/TypeScript)", "Staff Software Engineer"],
        "about_snippets": [
            "We are a fast-growing Series B startup disrupting the {sector} space.",
            "Join our engineering team building the next generation of {sector} infrastructure.",
            "We are a remote-first company with hubs in San Francisco and New York.",
        ],
        "sectors": ["e-commerce", "SaaS", "developer tooling", "API infrastructure", "productivity"],
        "responsibilities": [
            "Design and own critical backend services handling {n}M+ requests per day",
            "Lead architecture decisions for our microservices migration",
            "Collaborate with product and design to ship customer-facing features end-to-end",
            "Mentor junior engineers and contribute to technical culture",
            "Drive improvements to CI/CD pipeline and developer productivity",
        ],
        "requirements_extra": [
            "Experience building distributed systems at scale",
            "Track record of 0 to 1 product delivery in a startup environment",
            "Comfortable owning features end-to-end across the stack",
        ],
    },
    "data_science": {
        "titles": ["Senior Data Scientist", "Applied Scientist", "Analytics Engineer",
                   "Staff Data Scientist (Recommendations)"],
        "about_snippets": [
            "Our data team builds models that power decisions for {n}M+ users.",
            "We are an ML-first company where data science drives every product decision.",
        ],
        "sectors": ["personalization", "pricing", "fraud", "supply chain", "growth"],
        "responsibilities": [
            "Build and deploy ML models for {sector} optimization",
            "Run A/B tests and analyze experiment results to guide product strategy",
            "Collaborate with engineering to take models from notebook to production",
            "Develop recommendation and ranking algorithms serving millions of users",
        ],
        "requirements_extra": [
            "Strong statistical modeling and A/B testing experience",
            "Experience with recommendation systems or collaborative filtering a plus",
            "Proficiency in Python, SQL, and distributed computing (Spark/Databricks)",
        ],
    },
    "healthcare_tech": {
        "titles": ["Healthcare Software Engineer", "Clinical Data Engineer",
                   "Senior Engineer — EHR Integration", "Digital Health PM"],
        "about_snippets": [
            "We are building the operating system for modern healthcare, used in {n}+ hospitals.",
            "Our platform helps clinicians spend more time with patients and less time on paperwork.",
        ],
        "sectors": ["EHR", "telehealth", "clinical decision support", "prior authorization"],
        "responsibilities": [
            "Build FHIR-based APIs to integrate with Epic, Cerner, and Athenahealth",
            "Design HIPAA-compliant data pipelines for clinical analytics",
            "Work closely with clinicians to translate medical workflows into software",
            "Ensure FDA 21 CFR Part 11 compliance for regulated modules",
        ],
        "requirements_extra": [
            "Experience with HL7 FHIR or EHR system integrations required",
            "HIPAA compliance and healthcare data security knowledge",
            "Background in clinical workflows or medical device software a strong plus",
        ],
    },
    "fintech": {
        "titles": ["Payments Engineer", "Risk Systems Engineer",
                   "Senior Fintech Engineer (Python)", "Regulatory Technology Engineer"],
        "about_snippets": [
            "We process ${n}B in transactions annually and are expanding to {n} new markets.",
            "We are a London-headquartered fintech licensed under FCA regulations.",
            "Our mission is to make financial services accessible to everyone.",
        ],
        "sectors": ["payments", "lending", "trading", "compliance", "fraud detection"],
        "responsibilities": [
            "Build high-throughput payment processing systems with 99.99% uptime",
            "Implement PCI-DSS compliant infrastructure for card data handling",
            "Develop regulatory reporting pipelines for FCA and PSD2 compliance",
            "Build real-time fraud detection models processing millions of transactions",
        ],
        "requirements_extra": [
            "Experience with payment systems, PCI-DSS, or financial regulations",
            "Knowledge of FCA/PSD2 compliance or similar regulatory frameworks",
            "Experience in London-based banking or fintech operations a plus",
        ],
    },
    "climate_tech": {
        "titles": ["Climate Tech Engineer", "Energy Systems Software Engineer",
                   "Senior Engineer — Grid Technology", "Carbon Platform Developer"],
        "about_snippets": [
            "We are on a mission to accelerate the transition to clean energy.",
            "Our software manages {n}GW of renewable energy capacity across {n} grid operators.",
            "We are a Series C climate tech company backed by leading impact investors.",
        ],
        "sectors": ["solar", "EV charging", "grid optimization", "carbon accounting", "ESG reporting"],
        "responsibilities": [
            "Build grid optimization algorithms for renewable energy dispatch",
            "Develop carbon accounting and ESG reporting pipelines",
            "Work with IoT sensor data from solar panels and EV charging stations",
            "Implement energy forecasting models using geospatial and weather data",
        ],
        "requirements_extra": [
            "Passion for climate change and renewable energy required",
            "Experience with geospatial data, IoT, or energy systems a plus",
            "Familiarity with ESG reporting standards (GHG Protocol, TCFD)",
        ],
    },
    "cybersecurity": {
        "titles": ["Senior Security Engineer", "Cloud Security Architect",
                   "Penetration Tester", "Threat Intelligence Analyst", "SOC Engineer"],
        "about_snippets": [
            "We protect {n}K+ enterprises from advanced persistent threats.",
            "Our security platform ingests {n}B+ security events per day.",
        ],
        "sectors": ["endpoint security", "cloud security", "identity", "threat intel", "GRC"],
        "responsibilities": [
            "Design zero-trust architecture for cloud infrastructure",
            "Lead penetration testing engagements and red team exercises",
            "Build SIEM rules and detection engineering for emerging threats",
            "Develop incident response playbooks and lead security investigations",
        ],
        "requirements_extra": [
            "CISSP, CEH, OSCP, or equivalent certification preferred",
            "Experience with SIEM platforms (Splunk, QRadar, Chronicle)",
            "Knowledge of OWASP Top 10, NIST, or ISO 27001 frameworks",
        ],
    },
    "machine_learning": {
        "titles": ["Machine Learning Engineer", "Senior ML Engineer — Recommendations",
                   "MLOps Engineer", "NLP Engineer", "LLM Platform Engineer"],
        "about_snippets": [
            "Our ML platform serves {n}M+ personalized recommendations per second.",
            "We are building the next generation of AI-powered {sector} tools.",
        ],
        "sectors": ["search", "recommendations", "LLMs", "computer vision", "NLP"],
        "responsibilities": [
            "Build and maintain recommendation systems serving {n}M+ daily active users",
            "Develop LLM fine-tuning and RAG pipelines for production use cases",
            "Own the full ML lifecycle from experimentation to production serving",
            "Collaborate with product teams to define ML-powered features",
        ],
        "requirements_extra": [
            "Experience with recommendation systems or collaborative filtering",
            "Production ML experience with PyTorch or TensorFlow required",
            "Familiarity with LLMs, RAG, or transformer fine-tuning a strong plus",
        ],
    },
    "media_advertising": {
        "titles": ["Ad Tech Engineer", "Programmatic Advertising Manager",
                   "Campaign Analytics Lead", "Publisher Revenue Engineer"],
        "about_snippets": [
            "We operate one of the largest programmatic advertising platforms in North America.",
            "Our Madison Avenue-based team manages ${n}M in annual ad spend.",
            "We are a New York City-headquartered digital media company.",
        ],
        "sectors": ["programmatic", "display advertising", "connected TV", "publisher tech"],
        "responsibilities": [
            "Build real-time bidding infrastructure processing {n}B+ ad auctions daily",
            "Develop audience segmentation and targeting algorithms",
            "Build campaign attribution dashboards for advertiser clients",
            "Integrate with DSP/SSP platforms including Google DV360 and The Trade Desk",
        ],
        "requirements_extra": [
            "Experience with programmatic advertising, DSPs, or SSPs required",
            "Familiarity with ad tech ecosystem (DV360, TTD, OpenRTB protocol)",
            "New York City media or advertising industry experience a plus",
        ],
    },
    "remote_first": {
        "titles": ["Senior Software Engineer (Remote)", "Remote Full-Stack Engineer",
                   "Remote Platform Engineer", "Distributed Systems Engineer (Remote)"],
        "about_snippets": [
            "We are a fully remote-first company with team members in {n} countries.",
            "We operate async-first and believe results matter more than hours online.",
            "No offices. No required hours. Pure output focus.",
        ],
        "sectors": ["SaaS", "developer tools", "productivity", "collaboration"],
        "responsibilities": [
            "Own and ship features autonomously with minimal hand-holding",
            "Collaborate asynchronously across a globally distributed team",
            "Document your work thoroughly for async review",
            "Participate in optional video syncs during overlapping hours",
        ],
        "requirements_extra": [
            "4+ years of experience working fully remote required",
            "Strong written communication skills — async-first mindset essential",
            "Overlap with US Pacific timezone preferred (PST hours)",
            "Self-directed and comfortable with high autonomy",
        ],
    },
    "startup_engineering": {
        "titles": ["Software Engineer (Early Stage Startup)", "Founding Engineer",
                   "Technical Lead — Series A", "Engineer #3"],
        "about_snippets": [
            "We are a {funding}-funded startup and looking for our {n}th engineer.",
            "If you want to build from zero, own everything, and grow fast — this is it.",
            "Small team. Big impact. No bureaucracy.",
        ],
        "funding": ["Seed", "Pre-Series A", "Series A"],
        "sectors": ["SaaS", "marketplace", "fintech", "developer tools"],
        "responsibilities": [
            "Build the core product from the ground up — you own the stack",
            "Work directly with the founders and first customers",
            "Make architectural decisions that will scale to millions of users",
            "Wear multiple hats: backend, frontend, infra — whatever it takes",
        ],
        "requirements_extra": [
            "Previous startup experience strongly preferred — ideally 0 to 1",
            "Comfortable with ambiguity, changing priorities, and moving fast",
            "Ability to build from scratch and take full ownership",
            "Experience at Series A or earlier company a strong signal",
        ],
    },
}

GEO_PREFERENCES = [
    "Remote (US-based candidates only)",
    "Hybrid — San Francisco Bay Area preferred",
    "On-site — New York City (Manhattan)",
    "Remote-friendly — West Coast timezone preferred (PST)",
    "Hybrid — Seattle, WA",
    "On-site or Hybrid — Austin, TX",
    "Remote (EU/UK candidates welcome — CET timezone)",
    "London, UK (hybrid — 2 days in office)",
    "Berlin, Germany (on-site or hybrid)",
    "Fully remote — anywhere in the world",
    "US-based remote — EST/CST preferred",
    "Toronto, Canada (hybrid)",
    "Sydney, Australia (on-site or hybrid)",
    "Singapore (on-site)",
    "Amsterdam, Netherlands (hybrid)",
    "Paris, France (hybrid)",
]

# Maps geo keywords → (currency_symbol, salary_low_range, salary_high_delta, retirement_benefit, leave_benefit)
_GEO_CURRENCY = [
    ("UK",          "£",    (70,  130), (30, 60),  "pension scheme",                        "28 days annual leave + bank holidays"),
    ("London",      "£",    (75,  140), (30, 60),  "pension scheme",                        "28 days annual leave + bank holidays"),
    ("Berlin",      "€",    (65,  110), (25, 50),  "betriebliche Altersvorsorge (pension)", "30 days annual leave"),
    ("Germany",     "€",    (65,  110), (25, 50),  "betriebliche Altersvorsorge (pension)", "30 days annual leave"),
    ("Amsterdam",   "€",    (65,  110), (25, 50),  "company pension scheme",                "25 days annual leave"),
    ("Netherlands", "€",    (65,  110), (25, 50),  "company pension scheme",                "25 days annual leave"),
    ("Paris",       "€",    (55,   95), (20, 45),  "plan d'épargne entreprise (PEE)",       "25 days annual leave (RTT included)"),
    ("France",      "€",    (55,   95), (20, 45),  "plan d'épargne entreprise (PEE)",       "25 days annual leave (RTT included)"),
    ("EU",          "€",    (65,  110), (25, 50),  "company pension scheme",                "25 days annual leave"),
    ("Canada",      "CAD$", (100, 160), (35, 70),  "RRSP matching",                         "3 weeks PTO + statutory holidays"),
    ("Toronto",     "CAD$", (100, 160), (35, 70),  "RRSP matching",                         "3 weeks PTO + statutory holidays"),
    ("Australia",   "AUD$", (110, 170), (35, 70),  "superannuation (11% employer)",         "20 days annual leave"),
    ("Sydney",      "AUD$", (110, 170), (35, 70),  "superannuation (11% employer)",         "20 days annual leave"),
    ("Singapore",   "SGD$", (90,  150), (30, 60),  "CPF contributions",                     "14 days annual leave"),
]


def _salary_for_geo(geo: str):
    """Return (symbol, low, high, retirement_benefit, leave_benefit) based on geo string."""
    for keyword, symbol, (lo_min, lo_max), (hi_min, hi_max), retirement, leave in _GEO_CURRENCY:
        if keyword.lower() in geo.lower():
            low = random.randint(lo_min, lo_max)
            high = low + random.randint(hi_min, hi_max)
            return symbol, low, high, retirement, leave
    low = random.randint(120, 200)
    high = low + random.randint(40, 120)
    return "$", low, high, "401(k) matching", ("Unlimited PTO" if random.random() > 0.4 else "20 days PTO + holidays")


def generate_job_description():
    template_key = random.choice(list(JD_TEMPLATES.keys()))
    template = JD_TEMPLATES[template_key]

    title = random.choice(template["titles"])
    geo = random.choice(GEO_PREFERENCES)
    currency, salary_low, salary_high, retirement_benefit, leave_benefit = _salary_for_geo(geo)

    about_raw = random.choice(template["about_snippets"])
    sector = random.choice(template.get("sectors", ["technology"]))
    funding = random.choice(template.get("funding", ["Series B"]))
    about = about_raw.format(
        n=random.randint(10, 500),
        sector=sector,
        funding=funding,
    )

    responsibilities = random.sample(template["responsibilities"], k=min(4, len(template["responsibilities"])))
    responsibilities_fmt = [
        r.format(n=random.randint(10, 500), sector=sector)
        for r in responsibilities
    ]

    required_skills = _random_skills_for_industry(
        template_key.replace("_engineering", "_tech").replace("remote_first", "software_engineering")
        .replace("startup_engineering", "startup_generalist"),
        n=(4, 8)
    )
    nice_to_have = random.sample(
        [s for s in TECH_SKILLS if s not in required_skills],
        k=random.randint(2, 4),
    )
    yoe = random.randint(3, 10)
    extra_reqs = template.get("requirements_extra", [])

    text = f"""{title}
Location: {geo}

ABOUT US
{about}

THE ROLE
As a {title}, you will be a key contributor to our engineering team, working on
systems that {random.choice(['scale to millions of users', 'power our core product', 'drive business-critical decisions', 'serve enterprise clients globally'])}.

RESPONSIBILITIES
"""
    for r in responsibilities_fmt:
        text += f"- {r}\n"

    text += f"""
REQUIREMENTS
- {yoe}+ years of professional software development experience
"""
    for skill in required_skills:
        text += f"- Strong proficiency in {skill}\n"
    for req in extra_reqs:
        text += f"- {req}\n"

    text += "\nNICE TO HAVE\n"
    for skill in nice_to_have:
        text += f"- Experience with {skill}\n"

    is_remote = 'Remote' in geo or 'remote' in geo
    home_office = f"Home office stipend ({currency}1,500/year)" if is_remote else "Commuter benefits"

    text += f"""
COMPENSATION & BENEFITS
- Salary: {currency}{salary_low}K – {currency}{salary_high}K + equity
- {'Remote-friendly' if is_remote else 'Flexible work arrangements'}
- Health, dental, and vision insurance
- {retirement_benefit}
- {leave_benefit}
- {home_office}
"""

    company_name = random.choice(COMPANIES)
    return {
        "text": text,
        "json": {
            "title": title,
            "company_name": company_name,
            "location": geo,
            "industry": template_key,
            "required_skills": required_skills,
            "nice_to_have": nice_to_have,
            "min_years": yoe,
            "salary_range": f"{currency}{salary_low}K-{currency}{salary_high}K",
        },
        "type": "job_description",
    }


# ---------------------------------------------------------------------------
# Level-aware bullet generator
# ---------------------------------------------------------------------------

_BULLET_VERBS = {
    "junior": [
        "Assisted in building", "Helped implement", "Contributed to",
        "Wrote unit tests for", "Fixed bugs in", "Supported the team on",
        "Participated in developing", "Learned and applied",
    ],
    "mid": [
        "Built and maintained", "Implemented", "Designed and developed",
        "Improved", "Refactored", "Collaborated to deliver",
        "Owned the development of", "Shipped",
    ],
    "senior": [
        "Led the design and implementation of", "Architected",
        "Drove adoption of", "Mentored junior engineers on",
        "Reduced latency of", "Scaled", "Delivered", "Spearheaded",
    ],
    "architect": [
        "Defined the technical strategy for", "Established org-wide standards for",
        "Championed migration from", "Evangelized best practices around",
        "Influenced engineering direction for", "Authored the RFC for",
        "Collaborated with C-suite to prioritize", "Led a cross-functional initiative to",
    ],
}


def _leveled_bullet(level: str, quantified: bool = True, industry: str = "software_engineering") -> str:
    verb = random.choice(_BULLET_VERBS.get(level, _BULLET_VERBS["mid"]))
    base = _random_bullet(quantified=quantified, industry=industry)
    # Strip any existing verb at the start and prepend the level-appropriate one
    words = base.split()
    if len(words) > 4:
        base = " ".join(words[2:])
    return f"{verb} {base}"


# ---------------------------------------------------------------------------
# Tiered resume generators
# ---------------------------------------------------------------------------

def generate_junior_resume():
    industry = random.choice(INDUSTRIES)
    name = _gen_name()
    email = fake.email()
    phone = _gen_phone()
    location, region = _random_location()
    github = f"github.com/{fake.user_name()}"

    skills = _random_skills_for_industry(industry, n=(4, 7))
    yoe = random.randint(0, 2)
    experience = _random_experience(n_roles=(1, 2), industry=industry)
    for exp in experience:
        exp["bullets"] = [_leveled_bullet("junior", quantified=False, industry=industry)
                          for _ in range(random.randint(2, 3))]

    education = [{"degree": f"B.S. {random.choice(['Computer Science', 'Information Technology', 'Software Engineering'])}",
                  "school": random.choice(UNIVERSITIES)[0],
                  "year": str(random.randint(2020, 2025))}]
    title = _random_title_for_industry(industry)
    summary = (f"Recent graduate and aspiring {title.lower()} with {yoe} year(s) of hands-on experience. "
               f"Eager to grow skills in {', '.join(skills[:3])}.")

    text = f"""{name}
{email} | {phone} | {location}
GitHub: {github}

PROFESSIONAL SUMMARY
{summary}

TECHNICAL SKILLS
{', '.join(skills)}

EXPERIENCE
"""
    for exp in experience:
        text += f"\n{exp['title']} | {exp['company']} | {exp['period']}\n"
        for b in exp["bullets"]:
            text += f"- {b}\n"
    text += "\nEDUCATION\n"
    for edu in education:
        text += f"{edu['degree']} | {edu['school']} | {edu['year']}\n"

    return {
        "text": text,
        "json": {"contact": {"name": name, "email": email, "phone": phone,
                              "location": location, "github": github},
                 "summary": summary, "skills": skills, "experience": experience,
                 "education": education, "certifications": [], "projects": [],
                 "industry": industry, "region": region},
        "classification": "resume_valid_good",
        "expected_score_range": (10, 18),
    }


def generate_mid_resume():
    industry = random.choice(INDUSTRIES)
    name = _gen_name()
    email = fake.email()
    phone = _gen_phone()
    location, region = _random_location()
    linkedin = f"linkedin.com/in/{name.lower().replace(' ', '-')}"

    skills = _random_skills_for_industry(industry, n=(8, 12))
    yoe = random.randint(3, 6)
    experience = _random_experience(n_roles=(2, 4), industry=industry)
    for exp in experience:
        exp["bullets"] = [_leveled_bullet("mid", quantified=True, industry=industry)
                          for _ in range(random.randint(3, 5))]

    certs = random.sample([
        "AWS Certified Developer – Associate",
        "Google Associate Cloud Engineer",
        "Certified Kubernetes Application Developer (CKAD)",
        "Microsoft Azure Developer Associate",
        "HashiCorp Terraform Associate",
    ], k=random.randint(0, 2))

    education = [{"degree": f"B.S. {random.choice(['Computer Science', 'Mathematics', 'Engineering'])}",
                  "school": random.choice(UNIVERSITIES)[0],
                  "year": str(random.randint(2015, 2021))}]
    title = _random_title_for_industry(industry)
    culture = _culture_phrase(n=2)
    summary = (f"{title} with {yoe}+ years building and maintaining production systems. "
               f"Proficient in {', '.join(skills[:4])}. {culture[0].capitalize()}. "
               f"Track record of delivering features end-to-end. {culture[1].capitalize()}.")

    text = f"""{name}
{email} | {phone} | {location}
LinkedIn: {linkedin}

PROFESSIONAL SUMMARY
{summary}

TECHNICAL SKILLS
{', '.join(skills)}

EXPERIENCE
"""
    for exp in experience:
        text += f"\n{exp['title']} | {exp['company']} | {exp['period']}\n"
        for b in exp["bullets"]:
            text += f"- {b}\n"
    text += "\nEDUCATION\n"
    for edu in education:
        text += f"{edu['degree']} | {edu['school']} | {edu['year']}\n"
    if certs:
        text += "\nCERTIFICATIONS\n"
        for c in certs:
            text += f"- {c}\n"

    return {
        "text": text,
        "json": {"contact": {"name": name, "email": email, "phone": phone,
                              "location": location, "linkedin": linkedin},
                 "summary": summary, "skills": skills, "experience": experience,
                 "education": education, "certifications": certs, "projects": [],
                 "industry": industry, "region": region},
        "classification": "resume_valid_strong",
        "expected_score_range": (18, 25),
    }


def generate_senior_resume():
    industry = random.choice(INDUSTRIES)
    name = _gen_name()
    email = fake.email()
    phone = _gen_phone()
    location, region = _random_location()
    linkedin = f"linkedin.com/in/{name.lower().replace(' ', '-')}"
    github = f"github.com/{fake.user_name()}"

    skills = _random_skills_for_industry(industry, n=(12, 18))
    yoe = random.randint(7, 12)
    experience = _random_experience(n_roles=(3, 5), industry=industry)
    for exp in experience:
        exp["bullets"] = [_leveled_bullet("senior", quantified=True, industry=industry)
                          for _ in range(random.randint(4, 6))]

    education = [
        {"degree": random.choice(["M.S.", "MBA"]) + f" {random.choice(['Computer Science', 'Engineering Management'])}",
         "school": random.choice(UNIVERSITIES[:10])[0], "year": str(random.randint(2010, 2018))},
        {"degree": f"B.S. {random.choice(['Computer Science', 'Electrical Engineering'])}",
         "school": random.choice(UNIVERSITIES[:15])[0], "year": str(random.randint(2005, 2013))},
    ]
    certs = random.sample([
        "AWS Solutions Architect Professional", "Google Cloud Professional Engineer",
        "Certified Kubernetes Administrator (CKA)", "HashiCorp Certified Terraform Associate",
        "Certified Scrum Master (CSM)",
    ], k=random.randint(2, 4))

    projects = []
    for _ in range(random.randint(2, 3)):
        proj_skills = random.sample(skills, min(4, len(skills)))
        projects.append({
            "name": f"{fake.word().capitalize()} {random.choice(['Platform', 'Service', 'Engine', 'Framework'])}",
            "description": f"Built a {random.choice(['distributed', 'scalable', 'real-time'])} system for {fake.bs()}.",
            "tech_stack": proj_skills,
            "outcomes": [_leveled_bullet("senior", quantified=True, industry=industry),
                         _leveled_bullet("senior", quantified=True, industry=industry)],
        })

    title = _random_title_for_industry(industry)
    culture = _culture_phrase(n=2)
    summary = (f"Senior {title.lower()} with {yoe}+ years designing and scaling complex systems. "
               f"Deep expertise in {', '.join(random.sample(skills[:8], 4))}. "
               f"{culture[0].capitalize()}. Experienced in leading teams and driving technical decisions. "
               f"{culture[1].capitalize()}.")

    text = f"""{name}
{email} | {phone} | {location}
LinkedIn: {linkedin} | GitHub: {github}

PROFESSIONAL SUMMARY
{summary}

TECHNICAL SKILLS
{', '.join(skills)}

EXPERIENCE
"""
    for exp in experience:
        text += f"\n{exp['title']} | {exp['company']} | {exp['period']}\n"
        for b in exp["bullets"]:
            text += f"- {b}\n"
    text += "\nPROJECTS\n"
    for proj in projects:
        text += f"\n{proj['name']}\n{proj['description']}\n"
        text += f"Tech: {', '.join(proj['tech_stack'])}\n"
        for o in proj["outcomes"]:
            text += f"- {o}\n"
    text += "\nEDUCATION\n"
    for edu in education:
        text += f"{edu['degree']} | {edu['school']} | {edu['year']}\n"
    text += "\nCERTIFICATIONS\n"
    for cert in certs:
        text += f"- {cert}\n"

    return {
        "text": text,
        "json": {"contact": {"name": name, "email": email, "phone": phone, "location": location,
                              "linkedin": linkedin, "github": github},
                 "summary": summary, "skills": skills, "experience": experience,
                 "education": education, "certifications": certs, "projects": projects,
                 "industry": industry, "region": region},
        "classification": "resume_valid_strong",
        "expected_score_range": (24, 28),
    }


def generate_architect_resume():
    industry = random.choice(INDUSTRIES)
    name = _gen_name()
    email = fake.email()
    phone = _gen_phone()
    location, region = _random_location()
    linkedin = f"linkedin.com/in/{name.lower().replace(' ', '-')}"
    github = f"github.com/{fake.user_name()}"

    skills = _random_skills_for_industry(industry, n=(16, 22))
    yoe = random.randint(15, 22)
    experience = _random_experience(n_roles=(5, 7), industry=industry)
    for exp in experience:
        exp["bullets"] = [_leveled_bullet("architect", quantified=True, industry=industry)
                          for _ in range(random.randint(5, 8))]

    education = [
        {"degree": random.choice(["Ph.D.", "M.S."]) + f" {random.choice(['Computer Science', 'Data Science', 'Engineering Management'])}",
         "school": random.choice(UNIVERSITIES[:6])[0], "year": str(random.randint(2000, 2010))},
        {"degree": f"B.S. {random.choice(['Computer Science', 'Mathematics', 'Electrical Engineering'])}",
         "school": random.choice(UNIVERSITIES[:10])[0], "year": str(random.randint(1998, 2006))},
    ]
    certs = random.sample([
        "AWS Solutions Architect Professional", "Google Cloud Professional Engineer",
        "Certified Kubernetes Administrator (CKA)", "HashiCorp Certified Terraform Associate",
        "Certified Information Systems Security Professional (CISSP)",
        "PMI Project Management Professional (PMP)", "Azure Solutions Architect Expert",
        "Databricks Certified Associate Developer",
    ], k=random.randint(4, 6))

    projects = []
    for _ in range(random.randint(3, 5)):
        proj_skills = random.sample(skills, min(5, len(skills)))
        projects.append({
            "name": f"{random.choice(['Open-Source', 'Internal', 'Research'])} {fake.word().capitalize()} Platform",
            "description": f"Architected a {random.choice(['distributed', 'scalable', 'real-time', 'ML-powered'])} system for {fake.bs()}.",
            "tech_stack": proj_skills,
            "outcomes": [_leveled_bullet("architect", quantified=True, industry=industry),
                         _leveled_bullet("senior", quantified=True, industry=industry)],
        })

    _venues = ["NeurIPS", "ICML", "IEEE", "ACM SIGMOD", "USENIX", "O'Reilly"]
    publications = [
        f'"{fake.sentence(nb_words=8).rstrip(".")}" — {random.choice(_venues)} {random.randint(2012, 2024)}'
        for _ in range(random.randint(2, 4))
    ]

    title = random.choice(["Principal Engineer", "Staff Engineer", "Distinguished Engineer",
                            "VP of Engineering", "Chief Architect", "Technical Fellow"])
    culture = _culture_phrase(n=3)
    summary = (
        f"{title} with {yoe}+ years driving large-scale technical strategy across multiple organizations. "
        f"Deep expertise in {', '.join(random.sample(skills[:10], 5))}. "
        f"{culture[0].capitalize()}. Published author and conference speaker. "
        f"Mentored 20+ engineers to senior and staff levels. {culture[1].capitalize()}."
    )

    text = f"""{name}
{email} | {phone} | {location}
LinkedIn: {linkedin} | GitHub: {github}

PROFESSIONAL SUMMARY
{summary}

TECHNICAL SKILLS
{', '.join(skills)}

EXPERIENCE
"""
    for exp in experience:
        text += f"\n{exp['title']} | {exp['company']} | {exp['period']}\n"
        for b in exp["bullets"]:
            text += f"- {b}\n"
    text += "\nPROJECTS\n"
    for proj in projects:
        text += f"\n{proj['name']}\n{proj['description']}\n"
        text += f"Tech: {', '.join(proj['tech_stack'])}\n"
        for o in proj["outcomes"]:
            text += f"- {o}\n"
    text += "\nEDUCATION\n"
    for edu in education:
        text += f"{edu['degree']} | {edu['school']} | {edu['year']}\n"
    text += "\nCERTIFICATIONS\n"
    for cert in certs:
        text += f"- {cert}\n"
    text += "\nPUBLICATIONS & TALKS\n"
    for pub in publications:
        text += f"- {pub}\n"

    return {
        "text": text,
        "json": {"contact": {"name": name, "email": email, "phone": phone, "location": location,
                              "linkedin": linkedin, "github": github},
                 "summary": summary, "skills": skills, "experience": experience,
                 "education": education, "certifications": certs, "projects": projects,
                 "publications": publications, "industry": industry, "region": region},
        "classification": "resume_valid_strong",
        "expected_score_range": (28, 30),
    }


# ---------------------------------------------------------------------------
# Main — write files
# ---------------------------------------------------------------------------

GENERATORS = {
    "junior": generate_junior_resume,
    "mid": generate_mid_resume,
    "senior": generate_senior_resume,
    "architect": generate_architect_resume,
    "strong": generate_strong_resume,
    "good": generate_good_resume,
    "weak": generate_weak_resume,
    "invalid": generate_invalid_resume,
    "not_resume": generate_not_resume,
}

# Distribution: rich mix of tiers for realistic demo data
DISTRIBUTION = {
    "junior": 0.15, "mid": 0.20, "senior": 0.20, "architect": 0.10,
    "strong": 0.10, "good": 0.10, "weak": 0.075, "invalid": 0.05, "not_resume": 0.025,
}

# Only quality tiers — used when generating demo data (no edge-case files)
DISTRIBUTION_QUALITY = {
    "junior": 0.25, "mid": 0.30, "senior": 0.25,
    "architect": 0.10, "strong": 0.05, "good": 0.05,
}


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic test data for Resume Intelligence")
    parser.add_argument("--resumes", type=int, default=20, help="Number of resumes (default: 20)")
    parser.add_argument("--jds", type=int, default=5, help="Number of job descriptions (default: 5)")
    parser.add_argument("--locale", metavar="KEY=N", action="append", default=[],
                        help="Locale-specific resumes, e.g. --locale uk=18 --locale eu=10. "
                             "Supported: " + ", ".join(LOCALE_CONFIGS.keys()))
    parser.add_argument("--india", type=int, default=0,
                        help="Shorthand for --locale india=N (backward compat)")
    parser.add_argument("--quality-only", action="store_true",
                        help="Only generate quality tiers (junior/mid/senior/architect/strong/good), skip weak/invalid/not_resume")
    parser.add_argument("--output", type=str, default="data/synthetic", help="Output directory")
    args = parser.parse_args()

    global _CURRENT_LOCALE

    out_dir = os.path.abspath(args.output)
    manifest = {"generated_at": datetime.now().isoformat(), "resumes": [], "job_descriptions": []}

    for cat in GENERATORS:
        os.makedirs(os.path.join(out_dir, "resumes", cat), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "job_descriptions"), exist_ok=True)

    # --- Compute how many resumes to generate in each tier ---
    # India resumes are distributed proportionally across the same tiers
    # Parse --locale KEY=N pairs + backward-compat --india
    locale_counts: dict = {}
    if args.india > 0:
        locale_counts["india"] = args.india
    for pair in args.locale:
        key, _, val = pair.partition("=")
        key = LOCALE_ALIASES.get(key.lower(), key.lower())
        if key not in LOCALE_CONFIGS:
            print(f"  WARNING: Unknown locale '{key}'. Supported: {', '.join(LOCALE_CONFIGS)}")
            continue
        locale_counts[key] = locale_counts.get(key, 0) + int(val)

    # Cap locale counts so they never exceed total --resumes
    remaining = args.resumes
    for key in list(locale_counts):
        locale_counts[key] = min(locale_counts[key], remaining)
        remaining -= locale_counts[key]
    regular_n = remaining

    dist = DISTRIBUTION_QUALITY if args.quality_only else DISTRIBUTION

    def _build_counts(total_n: int) -> dict:
        if total_n <= 0:
            return {}
        counts: dict = {}
        for cat, weight in dist.items():
            counts[cat] = max(1, round(total_n * weight))
        diff = total_n - sum(counts.values())
        if diff > 0:
            counts["good"] += diff
        elif diff < 0:
            for cat in ["not_resume", "invalid", "weak"]:
                take = min(-diff, counts[cat] - 1)
                counts[cat] -= take
                diff += take
                if diff >= 0:
                    break
        return counts

    regular_counts = _build_counts(regular_n)

    # --- Generate resumes ---
    total = 0

    def _gen_batch(counts: dict, suffix: str = ""):
        nonlocal total
        for cat, n in counts.items():
            gen_fn = GENERATORS[cat]
            for i in range(n):
                total += 1
                data = gen_fn()
                slug = f"{cat}{suffix}_{i+1:03d}"

                txt_path = os.path.join(out_dir, "resumes", cat, f"{slug}.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(data["text"])

                json_path = None
                if data.get("json"):
                    json_path = os.path.join(out_dir, "resumes", cat, f"{slug}.json")
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data["json"], f, indent=2)

                manifest["resumes"].append({
                    "file": os.path.relpath(txt_path, out_dir),
                    "json_file": os.path.relpath(json_path, out_dir) if json_path else None,
                    "classification": data["classification"],
                    "expected_score_range": data["expected_score_range"],
                    "category": cat,
                })

    # Regular (global) resumes
    _CURRENT_LOCALE = None
    _gen_batch(regular_counts)

    # Locale-specific resumes
    for locale_key, locale_n in locale_counts.items():
        lc_counts = _build_counts(locale_n)
        _CURRENT_LOCALE = locale_key
        _gen_batch(lc_counts, suffix=f"_{locale_key[:2]}")
        _CURRENT_LOCALE = None
        label = LOCALE_CONFIGS[locale_key].get("label", locale_key)
        print(f"  {locale_key.title()} resumes: {locale_n} ({label})")

    print(f"  Resumes: {total} ({', '.join(f'{cat}={n}' for cat, n in regular_counts.items())})")

    # --- Generate JDs ---
    for i in range(args.jds):
        data = generate_job_description()
        slug = f"jd_{i+1:03d}"

        txt_path = os.path.join(out_dir, "job_descriptions", f"{slug}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(data["text"])

        json_path = os.path.join(out_dir, "job_descriptions", f"{slug}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data["json"], f, indent=2)

        manifest["job_descriptions"].append({
            "file": os.path.relpath(txt_path, out_dir),
            "json_file": os.path.relpath(json_path, out_dir),
            "title": data["json"]["title"],
            "location": data["json"]["location"],
            "industry": data["json"]["industry"],
        })

    print(f"  Job Descriptions: {args.jds}")

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"  Manifest: {manifest_path}")
    print(f"\nAll files written to: {out_dir}")


if __name__ == "__main__":
    main()
