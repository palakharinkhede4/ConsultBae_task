"""
Seeds sample audio submissions into the SQLite database for initial demonstration.
"""

import os
import sqlite3
from app.audio_processor import process_audio_submission
from pipeline.merge_data import DB_PATH, setup_database
from pipeline.generate_sample_audio import create_sample_wav, SAMPLE_DIR


def seed_submissions():
    setup_database(DB_PATH)
    
    file1 = os.path.join(SAMPLE_DIR, "demo_voice_sample_1.wav")
    if not os.path.exists(file1):
        create_sample_wav("demo_voice_sample_1.wav", duration_sec=4.2, sample_rate=44100, freq_hz=320.0)
        
    file2 = os.path.join(SAMPLE_DIR, "demo_voice_sample_2.wav")
    if not os.path.exists(file2):
        create_sample_wav("demo_voice_sample_2.wav", duration_sec=2.8, sample_rate=16000, freq_hz=480.0)

    m1 = process_audio_submission(file1, "demo_voice_sample_1.wav")
    m2 = process_audio_submission(file2, "demo_voice_sample_2.wav")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM audio_submissions;")

    cursor.execute("""
    INSERT INTO audio_submissions (
        candidate_name, phone, audio_filename, audio_path,
        duration_sec, sample_rate_khz, bitrate_kbps,
        loudness_db, quality_score, submitted_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-15 minutes'));
    """, (
        "Tanvi Gupta", "9000000254", "demo_voice_sample_1.wav", file1,
        m1["duration_sec"], m1["sample_rate_khz"], m1["bitrate_kbps"],
        m1["loudness_db"], m1["quality_score"]
    ))

    cursor.execute("""
    INSERT INTO audio_submissions (
        candidate_name, phone, audio_filename, audio_path,
        duration_sec, sample_rate_khz, bitrate_kbps,
        loudness_db, quality_score, submitted_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-5 minutes'));
    """, (
        "Rohit Nair", "9000000268", "demo_voice_sample_2.wav", file2,
        m2["duration_sec"], m2["sample_rate_khz"], m2["bitrate_kbps"],
        m2["loudness_db"], m2["quality_score"]
    ))

    conn.commit()
    conn.close()
    print("[INFO] Seeded demo audio submissions successfully.")


if __name__ == "__main__":
    seed_submissions()
