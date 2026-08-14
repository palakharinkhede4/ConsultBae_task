# Task 4: Data Issues & Integrity Report

An audit of all data quality anomalies, format discrepancies, and corruptions identified across the three source datasets (`applicants.csv`, `workers.csv`, and `rates.csv`), along with the deterministic normalization and resolution logic implemented in the pipeline.

---

## Data Quality Issue Summary Matrix

| Index | Data Quality Issue | Affected Datasets | Raw Input Example | Resolution / Normalization Logic |
|---|---|---|---|---|
| **1** | **Phone Number Inconsistencies** | `applicants.csv`, `workers.csv` | `+919000000254`, `9000000237`, `09000000287`, `+91-9000000131`, `919000000231` | Stripped all non-numeric characters; removed country prefix `91` (12 digits) and leading zero `0` (11 digits) to produce canonical 10-digit mobile numbers. |
| **2** | **CTC Unit Discrepancy (LPA vs INR)** | `applicants.csv` | `4.2`, `8.3`, `11.2` vs `417964`, `1195422` | Boundary threshold detection: values `< 100` are treated as Lakhs Per Annum ($4.2 \to 420000$). Values $\ge 100$ are stored as full integer INR. Stored both integer INR and formatted LPA display string. |
| **3** | **Shifted Columns / Malformed CSV Row** | `rates.csv` | `"react, javascript, mysql",ISHA.CHOPRA95@MAILTEST...` | Dynamic schema validator checks row structure. When column 0 contains comma-separated skills and column 1 contains an `@` sign, attributes are realigned to their proper schema columns. |
| **4** | **Inconsistent Date Formats** | `applicants.csv` | `24-07-2026`, `2026-08-08`, `7 Jul 2026`, `07/13/2026`, `08/19/2026` | Multi-pattern date parser sequentially matching `%d-%m-%Y`, `%Y-%m-%d`, `%m/%d/%Y`, `%d %b %Y` to normalize all dates into ISO-8601 `YYYY-MM-DD`. |
| **5** | **Empty / Delimiter-Only Rows** | `rates.csv` | `,,,,,` | Filtered rows where all fields are null or empty whitespace prior to ingestion. |
| **6** | **Duplicate Header Rows in Batch Exports** | `workers.csv` | Row 15 repeats `Name,Phone Number,City,Verified,Projects Completed` | Header detection logic identifies repeated column headers and skips duplicate header chunks. |
| **7** | **Inconsistent City Casing & Whitespace** | All 3 CSVs | `GURGAON`, `gurugram `, `Gurgaon`, `pune`, `PUNE`, `Noida `, `Delhi NCR`, `new delhi` | Normalized using a canonical dictionary mapping: trims whitespace, lowers, and standardizes variations (`Gurgaon`/`Gurugram` $\to$ `Gurugram`, `Bangalore`/`Bengaluru` $\to$ `Bengaluru`, `pune`/`PUNE` $\to$ `Pune`). |
| **8** | **Non-Standard Boolean Verification Flags** | `workers.csv` | `'Y'`, `'yes'`, `'Yes'`, `'No'`, `'N'` | Mapped truthy values (`'y'`, `'yes'`, `'true'`, `'1'`) $\to 1$ and falsy values (`'n'`, `'no'`, `'false'`, `'0'`) $\to 0$. |
| **9** | **Multiple Rate Units & Frequency Formats** | `rates.csv` | `1415/hr`, `15k/month`, `72k/month`, `403/hr` | Regex separation splits unit and numerical value: extracts `hourly_rate` (e.g. `1415.0`) and `monthly_rate` (e.g. `15000.0` from `15k/month`), calculating equivalent hourly rates assuming a standard 160h work month. |
| **10** | **Name Variations & Abbreviations** | `applicants.csv`, `workers.csv` | `R. Verma` vs `Rohit Verma`, uppercase `RITU SHARMA` vs `Ritu Sharma` | Title-cased all names; entity resolution graph matches by phone first, resolving abbreviated name records to the full candidate profile. |
| **11** | **Multiple Email Aliases for Single Candidate** | `applicants.csv` | `alt.nikhil.chopra70@example.com` vs `nikhil.chopra70@example.com` (Phone: `9000000103`) | Phone matching links both records into one master entity; profile tracks primary email and logs alias history. |
| **12** | **Skill String Formatting & Duplicate Tags** | `applicants.csv`, `rates.csv` | `n8n, LangChain, REST APIs` vs `fastapi, python, javascript` | Tokenized, trimmed, deduplicated case-insensitively, and mapped to canonical casing (`FastAPI`, `LangChain`, `REST APIs`, `n8n`). |

---

## Detailed Data Quality Analysis

### 1. The CTC Unit Mismatch Problem (`applicants.csv`)
* **Problem**: In `applicants.csv`, candidate compensation is recorded in two conflicting formats: direct integer INR (`417964`, `806661`, `1195422`) and LPA floats (`4.2`, `8.3`, `11.2`, `5.1`). Inserting `4.2` directly into an integer or numeric column corrupts salary range filtering and sorting.
* **Solution**: Implemented a numeric boundary threshold in `pipeline/normalizers.py:normalize_ctc`:
  ```python
  if val < 100.0:
      ctc_inr = int(round(val * 100000))
      ctc_lpa = round(val, 2)
  else:
      ctc_inr = int(round(val))
      ctc_lpa = round(ctc_inr / 100000.0, 2)
  ```
  Both `current_ctc_inr` (for database indexing and range queries) and `current_ctc_formatted` (`₹4,20,000 (4.20 LPA)`) are stored.

### 2. The Shifted Column Anomaly (`rates.csv`)
* **Problem**: Row 19 of `rates.csv` contains:
  `"react, javascript, mysql",ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG,Isha Chopra,1406/hr,Pune,active`
  A standard CSV reader maps skills to `email_id` and email to `worker_name`.
* **Solution**: The ingestion parser inspects field values dynamically. When `len(row) >= 2` and `@` is present in column index 1 rather than column 0, it detects the shift and remaps:
  - Column 0 $\to$ `skills`
  - Column 1 $\to$ `email`
  - Column 2 $\to$ `worker_name`
  - Column 3 $\to$ `rate`
  - Column 4 $\to$ `location`
  - Column 5 $\to$ `status`
  This enables Isha Chopra's record to cleanly merge with her corresponding rows in `applicants.csv` and `workers.csv`.

### 3. Cross-System Entity Resolution Strategy
* **Problem**: No single common ID exists across the 3 files. `applicants.csv` contains `Email` and `Phone`; `workers.csv` contains `Phone` and `Name`; `rates.csv` contains `Email` and `Name`.
* **Solution**: Constructed a multi-tier deterministic entity resolution graph in `pipeline/merge_data.py`:
  1. **Primary Match**: Normalized 10-digit Phone Number (connects applicants and workers).
  2. **Secondary Match**: Normalized Email (connects applicants and rates).
  3. **Tertiary Match**: Normalized Name + Normalized City (connects workers and rates records that lack applicant cross-links, such as *Manish Bhatia*, *Divya Chopra*, and *Vikram Mehta*).
  4. **Master Profile Consolidation**: Unified all skills lists, hourly/monthly compensation figures, verification status, and recorded source lineage.

---

## Resulting Master Database Integrity
- Total Raw Rows Ingested: **102 rows** across 3 CSV files.
- Total Duplicate / Fragmented Profiles Merged: **48 cross-file duplicates**.
- Total Unique Candidate Profiles Resolved: **54 clean entities**.
- 100% of phone numbers normalized to 10 digits.
- 100% of dates normalized to ISO-8601 `YYYY-MM-DD`.
- 100% of CTC values normalized to integer INR and formatted LPA.
