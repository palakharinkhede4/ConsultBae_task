"""
Batch Test Gemini Candidate Classifier
"""

import json
from pipeline.gemini_classifier import classify_candidate_with_gemini

test_candidates = [
    {
        "name": "Aarav Sharma",
        "experience_years": 4.5,
        "skills": "FastAPI, PyTorch, LangChain, Vector DBs, Python"
    },
    {
        "name": "Isha Chopra",
        "experience_years": 5.4,
        "skills": "React, JavaScript, MySQL"
    },
    {
        "name": "Manish Reddy",
        "experience_years": 3.5,
        "skills": "Docker, Zapier, JavaScript"
    }
]

def run_batch():
    for cand in test_candidates:
        print(f"\n==================================================")
        print(f"Testing Candidate: {cand['name']}")
        print(f"Skills: {cand['skills']} ({cand['experience_years']} years exp)")
        print(f"==================================================")
        res = classify_candidate_with_gemini(**cand)
        print(json.dumps(res, indent=2))

if __name__ == "__main__":
    run_batch()
