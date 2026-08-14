"""
ConsultBae Gemini Candidate Classifier
Uses Google Gemini API to auto-classify candidate skills, seniority, and talent tags.
"""

import os
import re
import json
import requests
from typing import Dict, Any, Optional, Tuple


def get_gemini_config() -> Tuple[Optional[str], str]:
    """Retrieves GEMINI_API_KEY and GEMINI_MODEL from environment or .env file."""
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash"

    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY=") and not api_key:
                    api_key = line.split("=", 1)[1].strip().strip("'\"")
                elif line.startswith("GEMINI_MODEL=") and not os.getenv("GEMINI_MODEL"):
                    model = line.split("=", 1)[1].strip().strip("'\"")

    return api_key, model


def extract_json_from_text(raw_text: str) -> Dict[str, Any]:
    """
    Robust JSON parser that handles codeblocks and escaped strings.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{[\s\S]*\})", text)
        if match:
            return json.loads(match.group(1).strip())
        raise


def classify_candidate_with_gemini(
    name: str,
    experience_years: float,
    skills: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sends candidate profile to Google Gemini using structured responseSchema
    and returns guaranteed valid JSON classification.
    """
    env_key, env_model = get_gemini_config()
    key = api_key or env_key
    target_model = model or env_model

    if not key:
        print("[WARN] No GEMINI_API_KEY found in .env. Using deterministic fallback tags.")
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

    target_model = target_model.replace("models/", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={key}"
    
    prompt = f"""Analyze the candidate profile for gig project evaluation:
Candidate Name: {name}
Experience: {experience_years} years
Skills: {skills}

1. Classify candidate into primary category.
2. Assign Seniority Level.
3. Provide a 1-sentence recruitment summary."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "category": {
                        "type": "STRING",
                        "enum": ["Automation Specialist", "Full-Stack Web Dev", "Data & AI Engineer", "Backend Engineer"]
                    },
                    "seniority": {
                        "type": "STRING",
                        "enum": ["Junior", "Mid-Level", "Senior", "Lead"]
                    },
                    "recruitment_summary": {
                        "type": "STRING"
                    }
                },
                "required": ["category", "seniority", "recruitment_summary"]
            },
            "temperature": 0.2
        }
    }

    try:
        res = requests.post(url, json=payload, timeout=25)
        if res.status_code == 200:
            data = res.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = extract_json_from_text(raw_text)
            parsed["status"] = "SUCCESS"
            parsed["model_used"] = target_model
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
    _, configured_model = get_gemini_config()
    print(f"[INFO] Testing Gemini Candidate Classifier using model: {configured_model}...")
    sample_candidate = {
        "name": "Tanvi Gupta",
        "experience_years": 4.2,
        "skills": "n8n, LangChain, REST APIs, MongoDB, SQL"
    }
    result = classify_candidate_with_gemini(**sample_candidate)
    print("\nResult:")
    print(json.dumps(result, indent=2))
