"""
ConsultBae AI Automation - Master Runner
Executes the data pipeline and launches the FastAPI audio web application.
"""

import sys
import uvicorn
from pipeline.merge_data import run_merge_pipeline
from pipeline.seed_demo_submissions import seed_submissions

def main():
    print("=" * 70)
    print("      🚀 STARTING CONSULTBAE AI AUTOMATION & AUDIO HUB")
    print("=" * 70)
    
    # 1. Execute Merge Pipeline
    print("\n[Step 1] Ingesting CSVs and building SQLite Master Database...")
    run_merge_pipeline()
    
    # 2. Seed Demo Audio Submissions
    print("\n[Step 2] Seeding initial gig audio submissions...")
    seed_submissions()
    
    # 3. Launch Web Server
    print("\n[Step 3] Launching FastAPI Web Application...")
    print("👉 Open your browser at: http://127.0.0.1:8000")
    print("=" * 70)
    
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
