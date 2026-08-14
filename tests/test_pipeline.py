"""
Automated Test Suite for ConsultBae Pipeline
Validates Phone Normalization, Date Parsing, CTC Standardizing,
Entity Resolution, and Shifted Field handling.
"""

import unittest
import os
import sqlite3

from pipeline.normalizers import (
    normalize_phone,
    normalize_email,
    normalize_name,
    normalize_city,
    normalize_ctc,
    normalize_date,
    normalize_rate,
    normalize_verified,
    clean_skills
)
from pipeline.merge_data import EntityResolver, DB_PATH, run_merge_pipeline


class TestDataNormalizers(unittest.TestCase):
    def test_phone_normalization(self):
        self.assertEqual(normalize_phone("+919000000254"), "9000000254")
        self.assertEqual(normalize_phone("09000000287"), "9000000287")
        self.assertEqual(normalize_phone("9000000237"), "9000000237")
        self.assertEqual(normalize_phone("+91-9000000131"), "9000000131")
        self.assertEqual(normalize_phone("919000000231"), "9000000231")

    def test_date_normalization(self):
        self.assertEqual(normalize_date("24-07-2026"), "2026-07-24")
        self.assertEqual(normalize_date("2026-08-08"), "2026-08-08")
        self.assertEqual(normalize_date("7 Jul 2026"), "2026-07-07")
        self.assertEqual(normalize_date("07/13/2026"), "2026-07-13")
        self.assertEqual(normalize_date("19 Jul 2026"), "2026-07-19")

    def test_ctc_normalization(self):
        # LPA format
        inr1, lpa1, fmt1 = normalize_ctc("4.2")
        self.assertEqual(inr1, 420000)
        self.assertEqual(lpa1, 4.2)
        self.assertIn("4.2 LPA", fmt1)

        # Full INR format
        inr2, lpa2, fmt2 = normalize_ctc("417964")
        self.assertEqual(inr2, 417964)
        self.assertEqual(lpa2, 4.18)

    def test_city_normalization(self):
        self.assertEqual(normalize_city("GURGAON"), "Gurugram")
        self.assertEqual(normalize_city("gurugram "), "Gurugram")
        self.assertEqual(normalize_city("pune"), "Pune")
        self.assertEqual(normalize_city("NOIDA"), "Noida")
        self.assertEqual(normalize_city("bangalore"), "Bengaluru")
        self.assertEqual(normalize_city("new delhi"), "New Delhi")

    def test_rate_normalization(self):
        hr, mo, fmt = normalize_rate("1415/hr")
        self.assertEqual(hr, 1415.0)
        self.assertEqual(fmt, "₹1,415/hr")

        hr2, mo2, fmt2 = normalize_rate("15k/month")
        self.assertEqual(mo2, 15000.0)
        self.assertEqual(fmt2, "₹15,000/month")

    def test_verified_normalization(self):
        self.assertEqual(normalize_verified("Y"), 1)
        self.assertEqual(normalize_verified("yes"), 1)
        self.assertEqual(normalize_verified("Yes"), 1)
        self.assertEqual(normalize_verified("No"), 0)
        self.assertEqual(normalize_verified("N"), 0)

    def test_skills_cleaning(self):
        skills = clean_skills("n8n, LangChain, REST APIs, MongoDB, SQL")
        self.assertIn("LangChain", skills)
        self.assertIn("MongoDB", skills)
        self.assertIn("n8n", skills)
        self.assertIn("REST APIs", skills)
        self.assertIn("SQL", skills)


class TestEntityResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_merge_pipeline()

    def test_database_records_exist(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM candidates;")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertGreater(count, 40)

    def test_isha_chopra_shifted_row_merged(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT full_name, email, city, hourly_rate, verified, projects_completed, skills, data_sources FROM candidates WHERE email = 'isha.chopra95@mailtest.example.org';")
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        name, email, city, hourly_rate, verified, projects, skills, sources = row
        self.assertEqual(name, "Isha Chopra")
        self.assertEqual(city, "Pune")
        self.assertEqual(hourly_rate, 1406.0)
        self.assertEqual(verified, 0)
        self.assertEqual(projects, 7)
        self.assertIn("applicants.csv", sources)
        self.assertIn("workers.csv", sources)
        self.assertIn("rates.csv", sources)

    def test_rohit_verma_abbreviation_deduplication(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM candidates WHERE email = 'rohit.verma13@mailtest.example.org';")
        count = cursor.fetchone()[0]
        conn.close()
        # Rohit Verma and R. Verma should be resolved to exactly 1 candidate record
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
