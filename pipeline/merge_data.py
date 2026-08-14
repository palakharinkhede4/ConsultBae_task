"""
ConsultBae Data Pipeline & Entity Resolution Engine
Merges three disparate CSV data sources into a unified, high-integrity SQLite database
and exports a clean master dataset.
"""

import os
import csv
import sqlite3
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

from pipeline.normalizers import (
    normalize_phone,
    normalize_email,
    normalize_name,
    normalize_city,
    normalize_ctc,
    normalize_date,
    normalize_rate,
    normalize_verified,
    normalize_status,
    clean_skills,
    merge_skills_lists,
    get_name_match_key
)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "consultbae.db")
PROCESSED_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "processed", "merged_candidates.csv")
RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")


class CandidateProfile:
    """
    Unified Candidate Profile representing a single resolved person across all systems.
    """
    def __init__(self, full_name: str, phone: Optional[str] = None, email: Optional[str] = None):
        self.full_name = full_name
        self.phone = phone
        self.email = email
        self.emails: Set[str] = {email} if email else set()
        self.city: Optional[str] = None
        self.experience_years: Optional[float] = None
        self.current_ctc_inr: Optional[int] = None
        self.current_ctc_lpa: Optional[float] = None
        self.current_ctc_formatted: Optional[str] = None
        self.applied_date: Optional[str] = None
        self.verified: Optional[int] = None
        self.projects_completed: Optional[int] = None
        self.hourly_rate: Optional[float] = None
        self.monthly_rate: Optional[float] = None
        self.rate_formatted: Optional[str] = None
        self.status: Optional[str] = None
        self.skills: List[str] = []
        self.data_sources: Set[str] = set()

    def merge_with(self, other: "CandidateProfile"):
        """Merges another candidate profile into this profile."""
        # Merge names (prefer non-abbreviated full names)
        if len(other.full_name) > len(self.full_name) and not self.full_name.endswith("."):
            self.full_name = other.full_name
        elif self.full_name.endswith(".") and not other.full_name.endswith("."):
            self.full_name = other.full_name
            
        if not self.phone and other.phone:
            self.phone = other.phone
            
        if not self.email and other.email:
            self.email = other.email
            
        self.emails.update(other.emails)
        
        if not self.city and other.city:
            self.city = other.city
            
        if self.experience_years is None and other.experience_years is not None:
            self.experience_years = other.experience_years
            
        if self.current_ctc_inr is None and other.current_ctc_inr is not None:
            self.current_ctc_inr = other.current_ctc_inr
            self.current_ctc_lpa = other.current_ctc_lpa
            self.current_ctc_formatted = other.current_ctc_formatted
            
        if not self.applied_date and other.applied_date:
            self.applied_date = other.applied_date
            
        if self.verified is None and other.verified is not None:
            self.verified = other.verified
            
        if self.projects_completed is None and other.projects_completed is not None:
            self.projects_completed = other.projects_completed
            
        if self.hourly_rate is None and other.hourly_rate is not None:
            self.hourly_rate = other.hourly_rate
            self.monthly_rate = other.monthly_rate
            self.rate_formatted = other.rate_formatted
            
        if not self.status and other.status:
            self.status = other.status
            
        self.skills = merge_skills_lists(self.skills, other.skills)
        self.data_sources.update(other.data_sources)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "full_name": self.full_name,
            "email": self.email,
            "all_emails": "; ".join(sorted(list(self.emails))) if self.emails else None,
            "phone": self.phone,
            "city": self.city,
            "experience_years": self.experience_years,
            "current_ctc_inr": self.current_ctc_inr,
            "current_ctc_formatted": self.current_ctc_formatted,
            "applied_date": self.applied_date,
            "verified": self.verified,
            "projects_completed": self.projects_completed,
            "hourly_rate": self.hourly_rate,
            "monthly_rate": self.monthly_rate,
            "rate_formatted": self.rate_formatted,
            "status": self.status or "Active",
            "skills": ", ".join(self.skills) if self.skills else None,
            "data_sources": ", ".join(sorted(list(self.data_sources)))
        }


class EntityResolver:
    """
    Graph-based multi-tier entity resolution engine.
    Matches candidates across multiple incomplete and contradictory identifiers.
    """
    def __init__(self):
        self.candidates: List[CandidateProfile] = []
        self.phone_index: Dict[str, CandidateProfile] = {}
        self.email_index: Dict[str, CandidateProfile] = {}
        self.name_city_index: Dict[str, CandidateProfile] = {}

    def _get_or_create(self, name: str, phone: Optional[str] = None, email: Optional[str] = None, city: Optional[str] = None) -> CandidateProfile:
        matched_profile: Optional[CandidateProfile] = None

        # Priority 1: Match by Phone Number (Strongest Personal Identifier)
        if phone and phone in self.phone_index:
            matched_profile = self.phone_index[phone]

        # Priority 2: Match by Email Address
        if not matched_profile and email and email in self.email_index:
            matched_profile = self.email_index[email]

        # Priority 3: Match by Normalized (Name + City)
        if not matched_profile and name and city:
            name_key = f"{get_name_match_key(name)}|{city.lower()}"
            if name_key in self.name_city_index:
                matched_profile = self.name_city_index[name_key]

        # Priority 4: Match by Abbreviated Name + Email match or Name only if strong
        if not matched_profile and email:
            # Check if username part of email matches person's name
            email_user = email.split("@")[0].lower()
            name_parts = name.lower().split()
            if len(name_parts) >= 2 and all(part in email_user for part in name_parts):
                for cand in self.candidates:
                    if cand.email and cand.email.split("@")[0].lower() == email_user:
                        matched_profile = cand
                        break

        if not matched_profile:
            matched_profile = CandidateProfile(full_name=name, phone=phone, email=email)
            self.candidates.append(matched_profile)

        # Update lookup indices
        if phone:
            self.phone_index[phone] = matched_profile
        if email:
            self.email_index[email] = matched_profile
            matched_profile.emails.add(email)
        if name and city:
            name_key = f"{get_name_match_key(name)}|{city.lower()}"
            self.name_city_index[name_key] = matched_profile

        return matched_profile

    def ingest_applicants(self, file_path: str):
        """Ingests File 1: applicants.csv"""
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} not found.")
            return

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = normalize_name(row.get("Full Name"))
                if not name:
                    continue
                phone = normalize_phone(row.get("Phone"))
                email = normalize_email(row.get("Email"))
                city = normalize_city(row.get("City"))
                
                profile = self._get_or_create(name=name, phone=phone, email=email, city=city)
                
                if city and not profile.city:
                    profile.city = city
                
                exp_raw = row.get("Experience (Years)")
                if exp_raw:
                    try:
                        profile.experience_years = float(exp_raw.strip())
                    except ValueError:
                        pass
                        
                ctc_inr, ctc_lpa, ctc_fmt = normalize_ctc(row.get("Current CTC"))
                if ctc_inr is not None:
                    profile.current_ctc_inr = ctc_inr
                    profile.current_ctc_lpa = ctc_lpa
                    profile.current_ctc_formatted = ctc_fmt
                    
                app_date = normalize_date(row.get("Applied Date"))
                if app_date:
                    profile.applied_date = app_date
                    
                skills = clean_skills(row.get("Skills"))
                profile.skills = merge_skills_lists(profile.skills, skills)
                profile.data_sources.add("applicants.csv")

    def ingest_workers(self, file_path: str):
        """Ingests File 2: workers.csv (handling duplicate header rows)"""
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} not found.")
            return

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = None
            for row_idx, row in enumerate(reader):
                if not row or not any(cell.strip() for cell in row):
                    continue
                # Handle header detection or duplicate header
                if "Name" in row and "Phone Number" in row:
                    header = [c.strip() for c in row]
                    continue
                
                if not header:
                    continue
                
                row_dict = dict(zip(header, [c.strip() for c in row]))
                name = normalize_name(row_dict.get("Name"))
                if not name or name.lower() == "name":
                    continue
                
                phone = normalize_phone(row_dict.get("Phone Number"))
                city = normalize_city(row_dict.get("City"))
                
                profile = self._get_or_create(name=name, phone=phone, email=None, city=city)
                
                if city and not profile.city:
                    profile.city = city
                    
                verified_val = normalize_verified(row_dict.get("Verified"))
                if verified_val is not None:
                    profile.verified = verified_val
                    
                proj_raw = row_dict.get("Projects Completed")
                if proj_raw:
                    try:
                        profile.projects_completed = int(proj_raw.strip())
                    except ValueError:
                        pass
                        
                profile.data_sources.add("workers.csv")

    def ingest_rates(self, file_path: str):
        """Ingests File 3: rates.csv (handling shifted columns and empty rows)"""
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} not found.")
            return

        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            
            for row in reader:
                if not row or not any(cell.strip() for cell in row):
                    continue  # Skip empty rows like ,,,,,
                
                # Check for shifted column anomaly:
                # e.g., ["react, javascript, mysql", "ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG", "Isha Chopra", "1406/hr", "Pune", "active"]
                if len(row) >= 2 and "@" in row[1] and "@" not in row[0]:
                    skills_raw = row[0]
                    email_raw = row[1]
                    name_raw = row[2] if len(row) > 2 else None
                    rate_raw = row[3] if len(row) > 3 else None
                    city_raw = row[4] if len(row) > 4 else None
                    status_raw = row[5] if len(row) > 5 else None
                else:
                    email_raw = row[0] if len(row) > 0 else None
                    name_raw = row[1] if len(row) > 1 else None
                    rate_raw = row[2] if len(row) > 2 else None
                    city_raw = row[3] if len(row) > 3 else None
                    status_raw = row[4] if len(row) > 4 else None
                    skills_raw = row[5] if len(row) > 5 else None

                name = normalize_name(name_raw)
                email = normalize_email(email_raw)
                city = normalize_city(city_raw)
                
                if not name and not email:
                    continue

                profile = self._get_or_create(name=name or "", phone=None, email=email, city=city)
                
                if not profile.full_name and name:
                    profile.full_name = name
                if city and not profile.city:
                    profile.city = city
                    
                hourly, monthly, rate_fmt = normalize_rate(rate_raw)
                if hourly is not None or monthly is not None:
                    profile.hourly_rate = hourly
                    profile.monthly_rate = monthly
                    profile.rate_formatted = rate_fmt
                    
                status = normalize_status(status_raw)
                if status:
                    profile.status = status
                    
                skills = clean_skills(skills_raw)
                profile.skills = merge_skills_lists(profile.skills, skills)
                profile.data_sources.add("rates.csv")


def setup_database(db_path: str):
    """Initializes the SQLite database schema with indexes."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create unified candidates table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT,
        all_emails TEXT,
        phone TEXT,
        city TEXT,
        experience_years REAL,
        current_ctc_inr INTEGER,
        current_ctc_formatted TEXT,
        applied_date TEXT,
        verified INTEGER,
        projects_completed INTEGER,
        hourly_rate REAL,
        monthly_rate REAL,
        rate_formatted TEXT,
        status TEXT DEFAULT 'Active',
        skills TEXT,
        data_sources TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create audio submissions table for Task 3
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audio_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        audio_filename TEXT NOT NULL,
        audio_path TEXT NOT NULL,
        duration_sec REAL,
        sample_rate_khz REAL,
        bitrate_kbps REAL,
        loudness_db REAL,
        quality_score TEXT,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create indexes for fast lookup and deduplication
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_phone ON candidates(phone);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidates(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_name ON candidates(full_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audio_phone ON audio_submissions(phone);")

    conn.commit()
    conn.close()


def run_merge_pipeline(db_path: str = DB_PATH, processed_csv_path: str = PROCESSED_CSV_PATH) -> List[Dict[str, Any]]:
    """
    Main orchestration routine for data ingestion, resolution, SQLite persistence, and CSV export.
    """
    print("=" * 60)
    print("ConsultBae AI Automation - Unified Data Pipeline")
    print("=" * 60)

    # 1. Initialize SQLite Database Schema
    setup_database(db_path)
    print(f"[1/4] SQLite Database schema initialized at: {db_path}")

    # 2. Run Entity Resolution Ingestion
    resolver = EntityResolver()
    
    app_file = os.path.join(RAW_DIR, "applicants.csv")
    worker_file = os.path.join(RAW_DIR, "workers.csv")
    rate_file = os.path.join(RAW_DIR, "rates.csv")

    print(f"[2/4] Ingesting & normalizing raw files...")
    resolver.ingest_applicants(app_file)
    print(f"      - Ingested applicants.csv -> {len(resolver.candidates)} unified entities tracked.")
    
    resolver.ingest_workers(worker_file)
    print(f"      - Ingested workers.csv    -> {len(resolver.candidates)} unified entities tracked.")
    
    resolver.ingest_rates(rate_file)
    print(f"      - Ingested rates.csv      -> {len(resolver.candidates)} unified entities tracked.")

    # 3. Save to SQLite Database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Clear existing candidates table before reload
    cursor.execute("DELETE FROM candidates;")
    
    records = []
    for cand in resolver.candidates:
        d = cand.to_dict()
        records.append(d)
        cursor.execute("""
        INSERT INTO candidates (
            full_name, email, all_emails, phone, city,
            experience_years, current_ctc_inr, current_ctc_formatted,
            applied_date, verified, projects_completed,
            hourly_rate, monthly_rate, rate_formatted,
            status, skills, data_sources, updated_at
        ) VALUES (
            :full_name, :email, :all_emails, :phone, :city,
            :experience_years, :current_ctc_inr, :current_ctc_formatted,
            :applied_date, :verified, :projects_completed,
            :hourly_rate, :monthly_rate, :rate_formatted,
            :status, :skills, :data_sources, CURRENT_TIMESTAMP
        )
        """, d)

    conn.commit()
    conn.close()
    print(f"[3/4] Persisted {len(records)} clean unified records to SQLite `candidates` table.")

    # 4. Export Clean Master CSV
    os.makedirs(os.path.dirname(processed_csv_path), exist_ok=True)
    if records:
        fieldnames = list(records[0].keys())
        with open(processed_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        print(f"[4/4] Exported master dataset to: {processed_csv_path}")

    print("=" * 60)
    print("Pipeline Execution Completed Successfully!")
    print("=" * 60)
    return records


if __name__ == "__main__":
    run_merge_pipeline()
