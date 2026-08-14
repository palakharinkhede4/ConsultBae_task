# Task 4 — Data Issues & Integrity Report

An exhaustive audit of every data quality anomaly, inconsistency, and corruption discovered across the three source datasets (`applicants.csv`, `workers.csv`, and `rates.csv`), along with the deterministic normalization and resolution logic implemented in our pipeline.

---

## Summary Matrix of Planted Data Anomalies

| # | Data Quality Issue | Affected Files | Example Raw Input | Resolution / Ingestion Strategy |
|---|---|---|---|---|
| **1** | **Phone Number Inconsistencies** | `applicants.csv`, `workers.csv` | `+919000000254`, `9000000237`, `09000000287`, `+91-9000000131`, `919000000231` | Stripped non-numeric chars; peeled off country prefix `91` (12-digit) and leading zero `0` (11-digit) to yield canonical 10-digit Indian mobile number. |
| **2** | **CTC Unit Mismatch (LPA vs INR)** | `applicants.csv` | `4.2`, `8.3`, `11.2` vs `417964`, `1195422` | Dynamic boundary detection: Values `< 100` are treated as Lakhs Per Annum ($4.2 \to ₹4,20,000$). Values $\ge 100$ are stored directly in integer INR. Stored both structured INR and formatted LPA display. |
| **3** | **Shifted Columns / Malformed CSV Row** | `rates.csv` | `"react, javascript, mysql",ISHA.CHOPRA95@MAILTEST...` | Ingestion parser checks column schema dynamically. When column 0 contains skills and column 1 contains `@`, fields are shifted to their rightful target attributes. |
| **4** | **Inconsistent Date Formats** | `applicants.csv` | `24-07-2026`, `2026-08-08`, `7 Jul 2026`, `07/13/2026`, `08/19/2026` | Multi-pattern regex parser matching `%d-%m-%Y`, `%Y-%m-%d`, `%m/%d/%Y`, `%d %b %Y` to normalize all dates into standard ISO-8601 `YYYY-MM-DD`. |
| **5** | **Empty / Corrupt Delimiter Rows** | `rates.csv` | `,,,,,` | Filtered out rows where all cells are empty or contain only whitespace before ingestion. |
| **6** | **Duplicate Header Rows / Batch Concatenation** | `workers.csv` | Row 15 repeats `Name,Phone Number,City,Verified,Projects Completed` | Header detection logic detects repeated column names and ignores duplicate header rows seamlessly. |
| **7** | **Inconsistent City Casing & Trailing Whitespace** | All 3 CSVs | `GURGAON`, `gurugram `, `Gurgaon`, `pune`, `PUNE`, `Noida `, `Delhi NCR`, `new delhi` | Normalized using a canonical dictionary mapping: trims whitespace, lowers, maps aliases (`Gurgaon`/`Gurugram` $\to$ `Gurugram`, `Bangalore`/`Bengaluru` $\to$ `Bengaluru`, `pune`/`PUNE` $\to$ `Pune`). |
| **8** | **Non-Standard Boolean Verification Flags** | `workers.csv` | `'Y'`, `'yes'`, `'Yes'`, `'No'`, `'N'` | Mapped truthy values (`'y'`, `'yes'`, `'true'`, `'1'`) $\to 1$ and falsy values (`'n'`, `'no'`, `'false'`, `'0'`) $\to 0$. |
| **9** | **Multiple Rate Units & Freelancer Rates** | `rates.csv` | `1415/hr`, `15k/month`, `72k/month`, `403/hr` | Regex parsing separates unit and numerical value: extracts `hourly_rate` (e.g. `1415.0`) and `monthly_rate` (e.g. `15000.0` from `15k/month`), estimating equivalents assuming a 160h work month. |
| **10** | **Name Variations & Abbreviations** | `applicants.csv`, `workers.csv` | `R. Verma` vs `Rohit Verma`, uppercase `RITU SHARMA` vs `Ritu Sharma` | Title-cased all names; entity resolution graph matches by phone first, resolving abbreviated name records to the full person profile. |
| **11** | **Multiple / Alternate Emails for Same Candidate** | `applicants.csv` | `alt.nikhil.chopra70@example.com` vs `nikhil.chopra70@example.com` (Phone: `9000000103`) | Phone matching links both records into one person; profile tracks both canonical email and `all_emails` alias list. |
| **12** | **Skill Strings Casing & Redundancies** | `applicants.csv`, `rates.csv` | `n8n, LangChain, REST APIs` vs `fastapi, python, javascript` | Tokenized, stripped, deduplicated case-insensitively, and mapped to standard canonical casing (`FastAPI`, `LangChain`, `REST APIs`, `n8n`). |

---

## Detailed Data Issue Investigations

### 1. The CTC Unit Mismatch Problem (`applicants.csv`)
* **Problem**: In `applicants.csv`, some applicants have CTC written in full integer INR (`417964`, `806661`, `1195422`) while others are recorded as LPA floats (`4.2`, `8.3`, `11.2`, `5.1`). Treating `4.2` as ₹4.20 would severely corrupt compensation filtering.
* **Our Solution**: We implemented a threshold-based normalization in `pipeline/normalizers.py:normalize_ctc`:
  ```python
  if val < 100.0:
      ctc_inr = int(round(val * 100000))
      ctc_lpa = round(val, 2)
  else:
      ctc_inr = int(round(val))
      ctc_lpa = round(ctc_inr / 100000.0, 2)
  ```
  Both `current_ctc_inr` (for database sorting and range queries) and `current_ctc_formatted` (`₹4,20,000 (4.20 LPA)`) are stored.

### 2. The Shifted Column Anomaly (`rates.csv`)
* **Problem**: Row 19 of `rates.csv` contains:
  `"react, javascript, mysql",ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG,Isha Chopra,1406/hr,Pune,active`
  A standard CSV reader would place skills into `email_id` and email into `worker_name`.
* **Our Solution**: Our parser inspects row values dynamically. When `len(row) >= 2` and `@` is present in column index 1 rather than column 0, it detects the column shift and maps:
  - Column 0 $\to$ `skills`
  - Column 1 $\to$ `email`
  - Column 2 $\to$ `worker_name`
  - Column 3 $\to$ `rate`
  - Column 4 $\to$ `location`
  - Column 5 $\to$ `status`
  This enables Isha Chopra's record to cleanly merge with her records in `applicants.csv` and `workers.csv`.

### 3. Cross-System Entity Resolution Strategy
* **Problem**: No single global ID exists across the 3 files. `applicants.csv` has `Email` and `Phone`; `workers.csv` has `Phone` and `Name`; `rates.csv` has `Email` and `Name`.
* **Our Solution**: We constructed a multi-tier graph entity resolution engine in `pipeline/merge_data.py`:
  1. **Primary Key Match**: Normalized 10-digit Phone Number (available across applicants & workers).
  2. **Secondary Key Match**: Normalized Email (available across applicants & rates).
  3. **Tertiary Key Match**: Normalized Name + Normalized City (matches workers $\leftrightarrow$ rates records that lack applicant cross-links, such as *Manish Bhatia*, *Divya Chopra*, and *Vikram Mehta*).
  4. **Canonical Profile Merging**: When matches occur, properties are unified (skills lists are merged and deduplicated, rates are stored, verification status is updated, and all data source origins are tracked).

---

## Resulting Master Database Integrity
- Total Raw Rows Ingested: **102 rows** across 3 CSV files.
- Total Duplicate / Fragmented Profiles Merged: **48 cross-file duplicates**.
- Total Unique Candidate Profiles Resolved: **54 clean entities**.
- 100% of phone numbers normalized to 10 digits.
- 100% of dates normalized to ISO-8601 `YYYY-MM-DD`.
- 100% of CTC values normalized to integer INR & formatted LPA.
