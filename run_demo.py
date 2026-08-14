"""
ConsultBae Application Runner
Executes the data pipeline and launches the FastAPI audio web application.
"""

import sys
import uvicorn
from pipeline.merge_data import run_merge_pipeline
from pipeline.seed_demo_submissions import seed_submissions

def main():
    print("[1/3] Ingesting CSV files and generating master database...")
    run_merge_pipeline()
    
    print("[2/3] Seeding initial submissions...")
    seed_submissions()
    
    print("[3/3] Starting FastAPI server on http://127.0.0.1:8000")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
