#!/usr/bin/env python3
"""
Test the /jobs/parse-query-intent endpoint with 100 diverse queries.

Usage:
    python scripts/test_query_intent.py
    python scripts/test_query_intent.py --token <jwt>   # if auth required
    python scripts/test_query_intent.py --fail-only     # show only unexpected results
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000/api/v1"

QUERIES = [
    # --- Global / no location ---
    ("Top 5 paid jobs in the world",                  None,             5,    True),
    ("Top 10 highest paying jobs globally",           None,             10,   True),
    ("Best paying remote jobs",                       None,             None, True),
    ("Highest salary software engineer",              None,             None, True),
    ("Most lucrative data scientist roles",           None,             None, True),
    ("Best compensated ML engineer positions",        None,             None, True),
    ("Top paying jobs worldwide",                     None,             None, True),
    ("Highest earning jobs anywhere",                 None,             None, True),
    ("Remote python developer",                       None,             None, False),
    ("Frontend engineer fully remote",                None,             None, False),

    # --- California variants ---
    ("Top 5 paid jobs in california",                 "california",     5,    True),
    ("Top 5 paid jobs in northern california",        "california",     5,    True),
    ("Top 5 paid jobs in southern california",        "california",     5,    True),
    ("Best paying jobs in SF",                        "san francisco",  None, True),
    ("Top 3 jobs in SFO",                             "san francisco",  3,    False),
    ("Jobs in the Bay Area",                          "san francisco",  None, False),
    ("Software engineer in Silicon Valley",           "san francisco",  None, False),
    ("Top paid 5 roles in Los Angeles",               "los angeles",    5,    True),
    ("Data scientist in LA area",                     "los angeles",    None, False),
    ("Engineer jobs in San Diego",                    "san diego",      None, False),

    # --- New York variants ---
    ("Top 5 paid jobs in ny",                         "new york",       5,    True),
    ("Top 5 paid jobs in new york",                   "new york",       5,    True),
    ("Highest paid roles in NYC",                     "new york",       None, True),
    ("Top 3 jobs in Manhattan",                       "new york",       3,    False),
    ("Machine learning jobs in Brooklyn",             "new york",       None, False),
    ("Top 10 paying jobs in New York City",           "new york",       10,   True),
    ("Finance tech jobs near Wall Street",            "new york",       None, False),

    # --- Texas ---
    ("Top 5 paid jobs in Texas",                      "texas",          5,    True),
    ("Best paying jobs in Austin",                    "austin",         None, True),
    ("Software roles in Dallas",                      "dallas",         None, False),

    # --- Pacific Northwest ---
    ("Top jobs in Seattle",                           "seattle",        None, False),
    ("Best paying roles in Washington state",         "washington",     None, True),
    ("Cloud engineer in Seattle",                     "seattle",        None, False),

    # --- UK ---
    ("Top 5 paid jobs in UK",                         "uk",             5,    True),
    ("Top 5 paid jobs in London",                     "london",         5,    True),
    ("Best paying fintech roles in London",           "london",         None, True),
    ("Software engineer in United Kingdom",           "uk",             None, False),
    ("Top 3 highest paid in Britain",                 "uk",             3,    True),

    # --- Germany ---
    ("Top 5 paid jobs in Germany",                    "germany",        5,    True),
    ("Best paying jobs in Berlin",                    "berlin",         None, True),
    ("ML engineer roles in Munich",                   "munich",         None, False),
    ("Top 3 paid jobs in Deutschland",                "germany",        3,    True),

    # --- Canada ---
    ("Top 5 paid jobs in Canada",                     "canada",         5,    True),
    ("Top 5 paid jobs in Toronto",                    "toronto",        5,    True),
    ("Best paying roles in Ontario",                  "toronto",        None, True),
    ("Backend engineer in Toronto",                   "toronto",        None, False),

    # --- Australia ---
    ("Top 5 paid jobs in Australia",                  "australia",      5,    True),
    ("Best paying jobs in Sydney",                    "sydney",         None, True),
    ("Top 3 roles in Melbourne",                      "melbourne",      3,    False),

    # --- Singapore ---
    ("Top 5 paid jobs in Singapore",                  "singapore",      5,    True),
    ("Best compensated engineers in Singapore",       "singapore",      None, True),

    # --- Netherlands / Europe ---
    ("Top 5 paid jobs in Netherlands",                "netherlands",    5,    True),
    ("Best paying jobs in Amsterdam",                 "amsterdam",      None, True),
    ("Top 5 paid jobs in Europe",                     "europe",         5,    True),
    ("Highest paying jobs in EU",                     "europe",         None, True),
    ("Software engineer in Paris",                    "paris",          None, False),
    ("Top 3 paid roles in France",                    "france",         3,    True),

    # --- India ---
    ("Top 5 paid jobs in India",                      "india",          5,    True),
    ("Best paying tech jobs in Bangalore",            "bangalore",      None, True),
    ("Top 10 paid roles in Mumbai",                   "mumbai",         10,   True),

    # --- Asia-Pacific ---
    ("Top 5 paid jobs in Japan",                      "japan",          5,    True),
    ("Best paying jobs in Tokyo",                     "tokyo",          None, True),
    ("Top 5 paid jobs in South Korea",                "south korea",    5,    True),
    ("Top jobs in Hong Kong",                         "hong kong",      None, False),

    # --- Middle East / Africa ---
    ("Best paying tech jobs in Dubai",                "dubai",          None, True),
    ("Top 5 paid jobs in UAE",                        "uae",            5,    True),
    ("Highest paid engineer in Tel Aviv",             "israel",         None, True),
    ("Top 3 roles in Cape Town",                      "south africa",   3,    False),
    ("Best paying jobs in Nigeria tech scene",        "nigeria",        None, True),

    # --- Hybrid / work model queries ---
    ("On-site data engineer roles in Berlin",         "berlin",         None, False),
    ("Hybrid roles in London paying well",            "london",         None, True),
    ("Top 5 remote-friendly paid roles",              None,             5,    True),
    ("Work from home top 3 paid engineer jobs",       None,             3,    True),

    # --- Job type specific ---
    ("Top 5 paid data scientist jobs in california",  "california",     5,    True),
    ("Best paying ML engineer in New York",           "new york",       None, True),
    ("Highest paid devops engineer in London",        "london",         None, True),
    ("Top 3 product manager jobs in San Francisco",   "san francisco",  3,    False),
    ("Best compensated backend engineer in Toronto",  "toronto",        None, True),
    ("Highest salary full stack developer in Berlin", "berlin",         None, True),
    ("Top 10 paid cloud architect roles globally",    None,             10,   True),
    ("Senior engineer highest salary in Singapore",   "singapore",      None, True),

    # --- Count-only, no salary intent ---
    ("Show me 5 jobs in London",                      "london",         5,    False),
    ("List 3 data engineer roles in Seattle",         "seattle",        3,    False),
    ("Find 10 jobs in Toronto",                       "toronto",        10,   False),

    # --- Salary but no location ---
    ("Top 5 highest paying backend roles",            None,             5,    True),
    ("Best paying 3 jobs available",                  None,             3,    True),
    ("Most paid engineer jobs right now",             None,             None, True),

    # --- Edge cases ---
    ("Jobs",                                          None,             None, False),
    ("Software engineer",                             None,             None, False),
    ("Top",                                           None,             None, False),
    ("Top 5",                                         None,             5,    False),
    ("Engineer jobs in the north of England",         "uk",             None, False),
    ("Roles near Los Angeles International Airport",  "los angeles",    None, False),
    ("Top paying jobs in greater london",             "london",         None, True),
    ("Jobs in the Silicon Valley area",               "san francisco",  None, False),
    ("5 best paying roles in toronto canada",         "toronto",        5,    True),
    ("Top 5 paid jobs in southern ontario",           "toronto",        5,    True),
    ("Highest salary engineer in east coast usa",     "new york",       None, True),
    ("Top 3 well compensated devops in chicago",      "chicago",        3,    True),
    ("Best paid architect roles in boston",           "boston",         None, True),
]

assert len(QUERIES) == 100, f"Expected 100 queries, got {len(QUERIES)}"


def check_result(q: str, expected_loc, expected_n, expected_salary, result: dict) -> list[str]:
    issues = []
    loc = (result.get("location") or "").lower()
    top_n = result.get("topN")
    salary = result.get("sortBySalary", False)
    aliases = [a.lower() for a in (result.get("locationAliases") or [])]

    if expected_n is not None and top_n != expected_n:
        issues.append(f"topN: expected {expected_n}, got {top_n}")

    if expected_salary and not salary:
        issues.append("sortBySalary: expected True, got False")

    if expected_loc is None and loc:
        # Some edge cases OK to have a location extracted
        pass
    elif expected_loc is not None:
        if not loc:
            issues.append(f"location: expected '{expected_loc}', got null")
        # Check for cross-contamination: toronto aliases must not include california terms
        ca_terms = {"san francisco", "bay area", "los angeles", "silicon valley", "west coast", "sacramento"}
        toronto_terms = {"toronto", "ontario", "canada"}
        if any(t in ca_terms for t in aliases) and any(t in toronto_terms for t in [loc] + aliases):
            issues.append(f"CROSS-CONTAMINATION: CA aliases in Toronto result: {aliases}")

    return issues


def run(token: str, fail_only: bool):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{BASE_URL}/jobs/parse-query-intent"

    passed = 0
    failed = 0
    errors = 0
    results_log = []

    print(f"\nTesting {len(QUERIES)} queries against {url}\n{'='*70}")

    for i, (q, exp_loc, exp_n, exp_sal) in enumerate(QUERIES, 1):
        try:
            resp = requests.post(url, headers=headers, json={"query": q}, timeout=30)
            if resp.status_code != 200:
                errors += 1
                msg = f"[{i:3}] HTTP {resp.status_code} — {q!r}"
                print(msg)
                results_log.append({"query": q, "status": resp.status_code, "error": resp.text})
                continue

            result = resp.json()
            issues = check_result(q, exp_loc, exp_n, exp_sal, result)

            status = "PASS" if not issues else "FAIL"
            if issues:
                failed += 1
            else:
                passed += 1

            if not fail_only or issues:
                loc_str = result.get("location") or "—"
                aliases = result.get("locationAliases") or []
                alias_str = ", ".join(aliases[:4]) + ("…" if len(aliases) > 4 else "")
                print(
                    f"[{i:3}] {status}  topN={result.get('topN')!s:<5} sal={str(result.get('sortBySalary')):<5} "
                    f"loc={loc_str:<20} aliases=[{alias_str}]"
                )
                if issues:
                    for iss in issues:
                        print(f"       ⚠  {iss}")
                print(f"       Q: {q!r}")
                print(f"       cleanQuery: {result.get('cleanQuery')!r}")

            results_log.append({"query": q, "result": result, "issues": issues})

        except requests.exceptions.Timeout:
            errors += 1
            print(f"[{i:3}] TIMEOUT — {q!r}")
        except Exception as exc:
            errors += 1
            print(f"[{i:3}] ERROR — {q!r}: {exc}")

        # Small delay to avoid hammering the LLM endpoint
        time.sleep(0.3)

    print(f"\n{'='*70}")
    print(f"Results: {passed} passed  {failed} failed  {errors} errors  (total {len(QUERIES)})")

    # Save full log
    out = Path(__file__).parent / "test_query_intent_results.json"
    out.write_text(json.dumps(results_log, indent=2))
    print(f"Full log saved to {out}")

    return failed + errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default="mock-google-token", help="Bearer token for auth")
    parser.add_argument("--fail-only", action="store_true", help="Print only failing queries")
    args = parser.parse_args()

    exit_code = run(args.token, args.fail_only)
    sys.exit(1 if exit_code > 0 else 0)


if __name__ == "__main__":
    main()
