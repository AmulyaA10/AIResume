#!/usr/bin/env python3
"""Generate synthetic resumes, job descriptions, and edge-case documents.

Usage:
    python scripts/generate_synthetic_data.py            # defaults: 20 resumes, 5 JDs
    python scripts/generate_synthetic_data.py --resumes 50 --jds 10
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
from datetime import datetime, timedelta

try:
    from faker import Faker
except ImportError:
    print("ERROR: faker is required.  pip install faker")
    sys.exit(1)

fake = Faker()
Faker.seed(42)
random.seed(42)

# ---------------------------------------------------------------------------
# Constants & Pools
# ---------------------------------------------------------------------------

TECH_SKILLS = [
    "Python", "Java", "TypeScript", "JavaScript", "Go", "Rust", "C++", "C#",
    "React", "Angular", "Vue.js", "Svelte", "Next.js", "Node.js", "Express",
    "FastAPI", "Django", "Flask", "Spring Boot", "Ruby on Rails",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "DynamoDB", "Elasticsearch",
    "Docker", "Kubernetes", "Terraform", "AWS", "GCP", "Azure",
    "CI/CD", "Jenkins", "GitHub Actions", "GitLab CI",
    "GraphQL", "REST", "gRPC", "Apache Kafka", "RabbitMQ",
    "TensorFlow", "PyTorch", "Scikit-learn", "Pandas", "NumPy",
    "Linux", "Git", "Agile", "Scrum", "JIRA",
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
    "Product Engineer", "Platform Engineer", "Security Engineer",
]

COMPANIES = [
    "Google", "Amazon", "Meta", "Apple", "Microsoft", "Netflix", "Stripe",
    "Uber", "Airbnb", "Shopify", "Salesforce", "Adobe", "Oracle",
    "Atlassian", "Datadog", "Snowflake", "Palantir", "Coinbase",
    "Acme Corp", "TechStart Inc", "DataFlow Systems", "CloudNine Solutions",
    "ByteForge", "QuantumLeap AI", "NovaTech", "Pixel Perfect Studios",
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

JD_TITLES = [
    "Senior Full-Stack Engineer", "Backend Engineer (Python)",
    "Frontend Engineer (React)", "DevOps Engineer", "Staff Engineer",
    "Machine Learning Engineer", "Data Engineer", "Cloud Architect",
    "Engineering Manager", "Site Reliability Engineer",
    "Platform Engineer", "Security Engineer", "Mobile Developer (React Native)",
]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def _random_skills(n_tech=(4, 12), n_soft=(0, 4)):
    tech = random.sample(TECH_SKILLS, k=random.randint(*n_tech))
    soft = random.sample(SOFT_SKILLS, k=random.randint(*n_soft))
    return tech + soft


def _random_bullet(quantified=True):
    """Generate a realistic achievement bullet."""
    actions = [
        "Designed and built", "Led migration of", "Implemented", "Architected",
        "Optimized", "Reduced", "Increased", "Automated", "Scaled",
        "Developed", "Launched", "Refactored", "Deployed", "Mentored",
    ]
    objects = [
        "microservices architecture", "CI/CD pipeline", "data pipeline",
        "customer-facing dashboard", "real-time notification system",
        "authentication system", "search infrastructure", "monitoring stack",
        "API gateway", "machine learning model", "ETL workflow",
        "distributed cache layer", "event-driven system", "mobile application",
    ]
    metrics = [
        "reducing deploy time by {n}%", "improving throughput by {n}x",
        "serving {n}K+ daily active users", "processing {n}M+ events daily",
        "cutting latency from {a}ms to {b}ms", "saving ${n}K annually",
        "increasing test coverage to {n}%", "reducing error rate by {n}%",
    ]

    bullet = f"{random.choice(actions)} {random.choice(objects)}"
    if quantified and random.random() > 0.3:
        metric = random.choice(metrics)
        metric = metric.format(n=random.randint(10, 95), a=random.randint(200, 800), b=random.randint(20, 100))
        bullet += f", {metric}"
    return bullet


def _random_experience(n_roles=(1, 4)):
    """Generate work experience entries."""
    entries = []
    current_year = 2026
    for i in range(random.randint(*n_roles)):
        end_year = current_year - i * random.randint(1, 4)
        start_year = end_year - random.randint(1, 5)
        period = f"{start_year} - {'Present' if i == 0 else end_year}"
        n_bullets = random.randint(2, 5)
        entries.append({
            "title": random.choice(TITLES),
            "company": random.choice(COMPANIES),
            "period": period,
            "bullets": [_random_bullet(quantified=(random.random() > 0.2)) for _ in range(n_bullets)],
        })
    return entries


def _random_education(level="good"):
    """Generate education entries."""
    uni, field = random.choice(UNIVERSITIES)
    degree = random.choice(DEGREES[:3])  # BS/BA/MS most common
    if level == "strong":
        degree = random.choice(DEGREES)
        uni, field = random.choice(UNIVERSITIES[:6])  # top schools
    year = random.randint(2010, 2024)
    return [{"degree": f"{degree} {field}", "school": uni, "year": str(year)}]


# ── Strong Resume ───────────────────────────────────────────────────────────

def generate_strong_resume():
    """Score 25-30: comprehensive, quantified, well-structured."""
    name = fake.name()
    email = fake.email()
    phone = fake.phone_number()
    city = f"{fake.city()}, {fake.state_abbr()}"
    linkedin = f"linkedin.com/in/{name.lower().replace(' ', '-')}"
    github = f"github.com/{fake.user_name()}"

    skills = _random_skills(n_tech=(8, 14), n_soft=(2, 4))
    experience = _random_experience(n_roles=(2, 4))
    education = _random_education(level="strong")

    summary = (
        f"Results-driven {random.choice(TITLES).lower()} with {random.randint(5, 15)}+ years "
        f"of experience building scalable distributed systems. Proven track record of leading "
        f"cross-functional teams, mentoring engineers, and delivering high-impact projects "
        f"in fast-paced environments. Passionate about {random.choice(['cloud-native architectures', 'developer experience', 'system reliability', 'data-intensive applications'])}."
    )

    certifications = random.sample([
        "AWS Solutions Architect Professional",
        "Google Cloud Professional Engineer",
        "Certified Kubernetes Administrator (CKA)",
        "HashiCorp Certified Terraform Associate",
    ], k=random.randint(1, 3))

    text = f"""{name}
{email} | {phone} | {city}
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

    text += f"\nEDUCATION\n"
    for edu in education:
        text += f"{edu['degree']} | {edu['school']} | {edu['year']}\n"

    text += f"\nCERTIFICATIONS\n"
    for cert in certifications:
        text += f"- {cert}\n"

    return {
        "text": text,
        "json": {
            "contact": {"name": name, "email": email, "phone": phone, "location": city, "linkedin": linkedin, "github": github},
            "summary": summary,
            "skills": skills,
            "experience": experience,
            "education": education,
            "certifications": certifications,
        },
        "classification": "resume_valid_strong",
        "expected_score_range": (25, 30),
    }


# ── Good Resume ─────────────────────────────────────────────────────────────

def generate_good_resume():
    """Score 18-24: solid but missing some elements."""
    name = fake.name()
    email = fake.email()
    phone = fake.phone_number()

    skills = _random_skills(n_tech=(5, 10), n_soft=(1, 3))
    experience = _random_experience(n_roles=(1, 3))
    education = _random_education(level="good")

    summary = (
        f"{random.choice(TITLES)} with {random.randint(3, 8)} years of experience "
        f"in software development. Skilled in {', '.join(random.sample(skills[:5], min(3, len(skills))))}."
    )

    text = f"""{name}
{email} | {phone}

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

    text += f"\nEDUCATION\n"
    for edu in education:
        text += f"{edu['degree']} | {edu['school']} | {edu['year']}\n"

    return {
        "text": text,
        "json": {
            "contact": {"name": name, "email": email, "phone": phone},
            "summary": summary,
            "skills": skills,
            "experience": experience,
            "education": education,
        },
        "classification": "resume_valid_good",
        "expected_score_range": (18, 24),
    }


# ── Weak Resume ─────────────────────────────────────────────────────────────

def generate_weak_resume():
    """Score 11-17: bare-bones, vague, no metrics."""
    name = fake.name()
    email = fake.email()

    skills = random.sample(TECH_SKILLS, k=random.randint(2, 5))

    text = f"""{name}
{email}

Skills: {', '.join(skills)}

Work Experience:
{random.choice(TITLES)} at {random.choice(COMPANIES)}
- Worked on various projects
- Helped with development tasks
- Attended team meetings and sprint planning
- Fixed bugs and resolved issues

Education:
{random.choice(DEGREES[:2])} in Computer Science
"""

    return {
        "text": text,
        "json": {
            "contact": {"name": name, "email": email},
            "skills": skills,
        },
        "classification": "resume_valid_but_weak",
        "expected_score_range": (11, 17),
    }


# ── Invalid Resume ──────────────────────────────────────────────────────────

def generate_invalid_resume():
    """Score 1-10: barely recognizable as a resume."""
    def _garbled():
        chars = string.ascii_letters + " \n"
        garble = "".join(random.choices(chars, k=200))
        return f"{fake.name()}\n\n{garble}"

    variants = [
        # Just a name and email
        lambda: f"{fake.name()}\n{fake.email()}\n\nLooking for a job in tech.",
        # Extremely short
        lambda: "Resume\n\nI am a developer.\nSkills: coding\nExperience: some",
        # Garbled / corrupt
        _garbled,
        # Missing all structure
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


# ── Not a Resume ────────────────────────────────────────────────────────────

def generate_not_resume():
    """Score 0: document that is clearly not a resume."""
    variants = [
        # Recipe
        lambda: (
            "Chocolate Chip Cookies\n\nIngredients:\n- 2 cups flour\n- 1 cup butter\n"
            "- 1 cup sugar\n- 2 eggs\n- 1 tsp vanilla\n\nInstructions:\n"
            "Preheat oven to 350F. Mix ingredients. Bake for 12 minutes."
        ),
        # Legal document
        lambda: (
            "TERMS OF SERVICE\n\nLast updated: January 2026\n\n"
            "By accessing this website, you agree to these terms. "
            "The company reserves the right to modify these terms at any time. "
            "Users must be 18 years or older to use this service."
        ),
        # Meeting notes
        lambda: (
            f"Meeting Notes - {fake.date()}\n\nAttendees: {fake.name()}, {fake.name()}\n\n"
            "Agenda:\n1. Q1 budget review\n2. Product roadmap update\n"
            "3. Hiring pipeline\n\nAction items:\n- Review proposal by Friday\n"
            "- Schedule follow-up with marketing"
        ),
        # Random essay
        lambda: (
            f"The Impact of Artificial Intelligence on Modern Society\n\n"
            f"{'  '.join(fake.paragraphs(nb=3))}"
        ),
    ]

    text = random.choice(variants)()
    return {
        "text": text,
        "json": None,
        "classification": "not_resume",
        "expected_score_range": (0, 0),
    }


# ── Job Descriptions ────────────────────────────────────────────────────────

def generate_job_description():
    """Generate a realistic job description."""
    title = random.choice(JD_TITLES)
    company = random.choice(COMPANIES)
    required_skills = random.sample(TECH_SKILLS, k=random.randint(4, 8))
    nice_to_have = random.sample(
        [s for s in TECH_SKILLS if s not in required_skills],
        k=random.randint(2, 4),
    )
    yoe = random.randint(3, 10)

    text = f"""{title} at {company}

About Us:
{company} is a leading technology company focused on building innovative solutions.
We are looking for talented engineers to join our growing team.

Role:
As a {title}, you will be responsible for designing, building, and maintaining
scalable software systems that serve millions of users.

Requirements:
- {yoe}+ years of professional software development experience
"""
    for skill in required_skills:
        text += f"- Strong proficiency in {skill}\n"
    text += f"- Excellent problem-solving and communication skills\n"
    text += f"- Experience working in an Agile environment\n"

    text += f"\nNice to Have:\n"
    for skill in nice_to_have:
        text += f"- Experience with {skill}\n"

    text += f"""
Benefits:
- Competitive salary ({random.randint(120, 250)}K - {random.randint(250, 400)}K)
- Remote-friendly
- Health, dental, and vision insurance
- 401(k) matching
- Unlimited PTO
"""

    return {
        "text": text,
        "json": {
            "title": title,
            "company": company,
            "required_skills": required_skills,
            "nice_to_have": nice_to_have,
            "min_years": yoe,
        },
        "type": "job_description",
    }


# ---------------------------------------------------------------------------
# Main — write files
# ---------------------------------------------------------------------------

GENERATORS = {
    "strong": generate_strong_resume,
    "good": generate_good_resume,
    "weak": generate_weak_resume,
    "invalid": generate_invalid_resume,
    "not_resume": generate_not_resume,
}

# Distribution weights (% of total)
DISTRIBUTION = {"strong": 0.2, "good": 0.3, "weak": 0.2, "invalid": 0.15, "not_resume": 0.15}


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic test data for Resume Intelligence")
    parser.add_argument("--resumes", type=int, default=20, help="Number of resumes to generate (default: 20)")
    parser.add_argument("--jds", type=int, default=5, help="Number of job descriptions (default: 5)")
    parser.add_argument("--output", type=str, default="data/synthetic", help="Output directory (default: data/synthetic)")
    args = parser.parse_args()

    out_dir = os.path.abspath(args.output)
    manifest = {"generated_at": datetime.now().isoformat(), "resumes": [], "job_descriptions": []}

    # Create directories
    for cat in GENERATORS:
        os.makedirs(os.path.join(out_dir, "resumes", cat), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "job_descriptions"), exist_ok=True)

    # --- Generate resumes ---
    counts = {}
    for cat, weight in DISTRIBUTION.items():
        counts[cat] = max(1, round(args.resumes * weight))

    # Adjust to hit exact total
    diff = args.resumes - sum(counts.values())
    if diff > 0:
        counts["good"] += diff
    elif diff < 0:
        for cat in ["not_resume", "invalid", "weak"]:
            take = min(-diff, counts[cat] - 1)
            counts[cat] -= take
            diff += take
            if diff >= 0:
                break

    total = 0
    for cat, n in counts.items():
        gen_fn = GENERATORS[cat]
        for i in range(n):
            total += 1
            data = gen_fn()
            slug = f"{cat}_{i+1:03d}"

            # Write .txt
            txt_path = os.path.join(out_dir, "resumes", cat, f"{slug}.txt")
            with open(txt_path, "w") as f:
                f.write(data["text"])

            # Write .json (if structured data available)
            json_path = None
            if data.get("json"):
                json_path = os.path.join(out_dir, "resumes", cat, f"{slug}.json")
                with open(json_path, "w") as f:
                    json.dump(data["json"], f, indent=2)

            manifest["resumes"].append({
                "file": os.path.relpath(txt_path, out_dir),
                "json_file": os.path.relpath(json_path, out_dir) if json_path else None,
                "classification": data["classification"],
                "expected_score_range": data["expected_score_range"],
                "category": cat,
            })

    print(f"  Resumes: {total} ({', '.join(f'{cat}={n}' for cat, n in counts.items())})")

    # --- Generate JDs ---
    for i in range(args.jds):
        data = generate_job_description()
        slug = f"jd_{i+1:03d}"

        txt_path = os.path.join(out_dir, "job_descriptions", f"{slug}.txt")
        with open(txt_path, "w") as f:
            f.write(data["text"])

        json_path = os.path.join(out_dir, "job_descriptions", f"{slug}.json")
        with open(json_path, "w") as f:
            json.dump(data["json"], f, indent=2)

        manifest["job_descriptions"].append({
            "file": os.path.relpath(txt_path, out_dir),
            "json_file": os.path.relpath(json_path, out_dir),
            "title": data["json"]["title"],
            "company": data["json"]["company"],
        })

    print(f"  Job Descriptions: {args.jds}")

    # --- Write manifest ---
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"  Manifest: {manifest_path}")
    print(f"\nAll files written to: {out_dir}")


if __name__ == "__main__":
    main()
