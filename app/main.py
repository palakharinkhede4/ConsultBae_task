"""
ConsultBae Mini Audio Collection App - FastAPI Server
Handles browser audio recording, file uploads, automated audio property extraction,
SQLite persistence, and submissions management dashboard.
"""

import os
import sqlite3
import uuid
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from pipeline.normalizers import normalize_phone, normalize_name
from pipeline.merge_data import DB_PATH
from app.audio_processor import process_audio_submission

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI(
    title="ConsultBae Audio Collection & Recruitment Hub",
    description="Gig worker audio submission, signal analysis, and candidate matching platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serves the main application page."""
    html_file = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>ConsultBae Audio App is running!</h1>")


@app.post("/api/submit-audio")
async def submit_audio(
    name: str = Form(...),
    phone: str = Form(...),
    audio_file: UploadFile = File(...)
):
    """
    Ingests an audio recording/file from a gig worker:
    1. Normalizes candidate name and phone
    2. Stores the audio file safely in /uploads
    3. Automatically extracts: duration, sample rate, bitrate, loudness, noise quality
    4. Persists record in SQLite database
    5. Links candidate to Task 1 database
    """
    clean_name = normalize_name(name)
    clean_phone = normalize_phone(phone)

    if not clean_name:
        raise HTTPException(status_code=400, detail="Please enter a valid candidate name.")
    if not clean_phone or len(clean_phone) != 10:
        raise HTTPException(status_code=400, detail="Please enter a valid 10-digit mobile number.")

    # Generate a unique storage filename
    ext = os.path.splitext(audio_file.filename or "")[1].lower()
    if not ext or ext not in [".wav", ".mp3", ".ogg", ".webm", ".m4a", ".aac"]:
        ext = ".wav" if "wav" in (audio_file.content_type or "") else ".webm"
        
    unique_filename = f"{clean_phone}_{uuid.uuid4().hex[:8]}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, unique_filename)

    # Save audio stream
    file_bytes = await audio_file.read()
    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    # Extract audio signal properties
    metrics = process_audio_submission(saved_path, audio_file.filename or unique_filename)

    # Store into SQLite database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO audio_submissions (
        candidate_name, phone, audio_filename, audio_path,
        duration_sec, sample_rate_khz, bitrate_kbps,
        loudness_db, quality_score, submitted_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
    """, (
        clean_name,
        clean_phone,
        unique_filename,
        saved_path,
        metrics["duration_sec"],
        metrics["sample_rate_khz"],
        metrics["bitrate_kbps"],
        metrics["loudness_db"],
        metrics["quality_score"]
    ))
    submission_id = cursor.lastrowid
    
    # Check if candidate exists in Task 1 database
    cursor.execute("SELECT * FROM candidates WHERE phone = ? LIMIT 1;", (clean_phone,))
    matched_candidate = cursor.fetchone()
    candidate_info = dict(matched_candidate) if matched_candidate else None

    conn.commit()
    conn.close()

    return {
        "status": "SUCCESS",
        "message": "Audio recording submitted and analyzed successfully!",
        "submission_id": submission_id,
        "candidate": {
            "name": clean_name,
            "phone": clean_phone,
            "matched_existing_profile": candidate_info is not None,
            "profile_details": candidate_info
        },
        "audio_metrics": metrics,
        "audio_url": f"/api/audio/{unique_filename}"
    }


@app.get("/api/submissions")
async def list_submissions():
    """
    Returns list of all gig audio submissions with extracted properties
    and matched candidate metadata from Task 1.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        s.id,
        s.candidate_name,
        s.phone,
        s.audio_filename,
        s.duration_sec,
        s.sample_rate_khz,
        s.bitrate_kbps,
        s.loudness_db,
        s.quality_score,
        s.submitted_at,
        c.city,
        c.verified,
        c.skills,
        c.status as candidate_status,
        c.rate_formatted
    FROM audio_submissions s
    LEFT JOIN candidates c ON s.phone = c.phone
    ORDER BY s.id DESC;
    """)
    rows = cursor.fetchall()
    conn.close()

    submissions = []
    for r in rows:
        d = dict(r)
        d["audio_url"] = f"/api/audio/{d['audio_filename']}"
        submissions.append(d)

    return {"submissions": submissions, "total_count": len(submissions)}


@app.get("/api/candidates")
async def list_candidates():
    """Returns all merged candidate records from Task 1."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates ORDER BY id ASC;")
    rows = cursor.fetchall()
    conn.close()
    return {"candidates": [dict(r) for r in rows], "total_count": len(rows)}


@app.get("/api/stats")
async def get_dashboard_stats():
    """Returns overview platform metrics."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM candidates;")
    cand_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM candidates WHERE verified = 1;")
    verified_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM audio_submissions;")
    sub_count = cursor.fetchone()[0]
    
    conn.close()
    return {
        "total_candidates": cand_count,
        "verified_workers": verified_count,
        "audio_submissions": sub_count
    }


@app.get("/api/audio/{filename}")
async def stream_audio(filename: str):
    """Streams audio file for in-browser playback."""
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found.")
    
    ext = os.path.splitext(filename)[1].lower()
    media_type = "audio/wav" if ext == ".wav" else ("audio/webm" if ext == ".webm" else "audio/mpeg")
    return FileResponse(file_path, media_type=media_type)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
