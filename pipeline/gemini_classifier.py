"""
ConsultBae Gemini Candidate Classifier
Uses Google Gemini API to auto-classify candidate skills, seniority, and talent tags.
"""

import os
import json
import requests
from typing import Dict, Any, Optional

def get_gemini_api_key() -> Optional[str]:
    """Retrieves GEMINI_API_KEY from environment or .env file."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip("'\"")
                        break
    return api_key


def classify_candidate_with_gemini(
    name: str,
    experience_years: float,
    skills: str,
    api_key: Optional[str] = None,
    model: str = "gemini-1.5-flash"
) -> Dict[str, Any]:
    """
    Sends candidate profile to Google Gemini and returns structured JSON classification.
    """
    key = api_key or get_gemini_api_key()
    if not key:
        print("[WARN] No GEMINI_API_KEY found. Using local deterministic fallback tags.")
        # Deterministic fallback when API key is not yet set
        skills_lower = skills.lower()
        if "n8n" in skills_lower or "zapier" in skills_lower:
            category = "Automation Specialist"
        elif "langchain" in skills_lower or "pandas" in skills_lower:
            category = "Data & AI Engineer"
        elif "react" in skills_lower or "javascript" in skills_lower:
            category = "Full-Stack Web Dev"
        else:
            category = "Backend Engineer"
            
        seniority = "Senior" if experience_years >= 4.0 else ("Mid-Level" if experience_years >= 2.0 else "Junior")
        return {
            "status": "FALLBACK_MODE",
            "model_used": "deterministic-rules",
            "category": category,
            "seniority": seniority,
            "recruitment_summary": f"{name} is a {seniority} {category} with {experience_years} years of experience in {skills}."
        }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    
    prompt = f"""You are a technical recruiter. Analyze this candidate and return JSON:
Candidate Name: {name}
Experience: {experience_years} years
Skills: {skills}

Tasks:
1. Classify candidate into exactly ONE category: ["Automation Specialist", "Full-Stack Web Dev", "Data & AI Engineer", "Backend Engineer"]
2. Assign Seniority: ["Junior", "Mid-Level", "Senior", "Lead"]
3. Provide a 1-sentence recruitment summary.

Respond strictly in valid JSON with keys: category, seniority, recruitment_summary."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            data = res.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_text)
            parsed["status"] = "SUCCESS"
            parsed["model_used"] = model
            return parsed
        else:
            print(f"[WARN] Gemini API error ({res.status_code}): {res.text}")
            return {
                "status": "ERROR",
                "error": res.text,
                "category": "Automation Specialist",
                "seniority": "Mid-Level",
                "recruitment_summary": f"{name} possesses hands-on experience in {skills}."
            }
    except Exception as e:
        print(f"[ERROR] Gemini request failed: {e}")
        return {
            "status": "EXCEPTION",
            "error": str(e),
            "category": "Automation Specialist",
            "seniority": "Mid-Level",
            "recruitment_summary": f"{name} has experience with {skills}."
        }


if __name__ == "__main__":
    print("[INFO] Testing Gemini Candidate Classifier...")
    sample_candidate = {
        "name": "Tanvi Gupta",
        "experience_years": 4.2,
        "skills": "n8n, LangChain, REST APIs, MongoDB, SQL"
    }
    result = classify_candidate_with_gemini(**sample_candidate)
    print("\nResult:")
    print(json.dumps(result, indent=2))
