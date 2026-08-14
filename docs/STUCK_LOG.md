# Stuck Log: Technical Decisions & Problem Solving

A documented breakdown of the 3 hardest technical challenges encountered during the development of this solution, the research conducted, the AI suggestions evaluated and rejected, and the final engineering implementations.

---

### Challenge 1: CTC Unit Inconsistency & Ambiguous Numeric Scale (LPA vs INR)

* **Where Stuck**:
  In `applicants.csv`, candidate CTC values were recorded in two conflicting formats:
  - Direct annual INR integers: `417964`, `806661`, `1195422`.
  - Floating-point LPA (Lakhs Per Annum): `4.2`, `8.3`, `11.2`, `2.4`, `5.1`.
  Storing these directly into a SQLite numeric column resulted in values like `4.2` being interpreted as ₹4.20 per year. Sorting by salary or filtering candidates above 5 LPA produced broken results.

* **What Was Researched**:
  - "Indian payroll compensation data formatting LPA vs full annual INR"
  - "handling mixed unit salary strings in python pandas"
  - "normalizing compensation scale discrepancies in recruitment data"

* **What Was Asked to AI**:
  > "How to reliably detect whether a number in Indian recruitment data represents Lakhs Per Annum or direct INR when no units or symbols are provided in the CSV column?"

* **Suggestions Rejected & Why**:
  1. *AI Suggestion 1: Regex matching for decimal points (`r"\.\d+"`)*:
     - **Why Rejected**: Failed for candidates with round integer LPA (e.g. `6` or `10.0`). Furthermore, some direct INR systems record paise (`417964.00`), which would have been falsely categorized as LPA.
  2. *AI Suggestion 2: String matching for keywords like 'LPA' or 'INR'*:
     - **Why Rejected**: The raw CSV data contained raw numbers with zero suffix annotations.

* **Resolution**:
  Recognizing that full-time tech salaries in India are $> 50,000$ annually, whereas LPA values range between $0.5$ and $80.0$, I implemented a deterministic numeric boundary threshold ($100.0$) in `pipeline/normalizers.py:normalize_ctc`:
  ```python
  val = float(ctc_str)
  if val < 100.0:
      ctc_inr = int(round(val * 100000))
      ctc_lpa = round(val, 2)
  else:
      ctc_inr = int(round(val))
      ctc_lpa = round(ctc_inr / 100000.0, 2)
  ```
  The database schema stores both `current_ctc_inr` (for SQL queries like `WHERE current_ctc_inr >= 600000`) and `current_ctc_formatted` (`₹4,20,000 (4.20 LPA)`) for UI display.

---

### Challenge 2: Cross-Browser Audio Codecs vs Server-Side Signal Analysis

* **Where Stuck**:
  The task requires extracting **duration**, **sample rate (kHz)**, **bitrate (kbps)**, **loudness (dB)**, and a **noise/quality estimate** from audio recorded in the browser or uploaded by users.
  When recording audio in Chrome/Firefox via `MediaRecorder`, the browser produces an `audio/webm` or `audio/ogg` Opus stream. Passing this stream to Python's standard `wave` module threw `wave.Error: file does not start with RIFF id`.

* **What Was Researched**:
  - "Python compute audio duration sample rate without external ffmpeg binary"
  - "Calculate RMS loudness in dBFS using python numpy from audio bytes"
  - "Signal to Noise Ratio SNR calculation for voice recordings python"

* **What Was Asked to AI**:
  > "How to compute duration, sample rate, bitrate, and RMS loudness in Python for both WAV and WebM browser recordings without forcing users to install external system ffmpeg executables?"

* **Suggestions Rejected & Why**:
  1. *AI Suggestion 1: Shelling out to system `ffmpeg` binary (`subprocess.run(['ffmpeg', ...])`)*:
     - **Why Rejected**: Requiring external binary dependencies on Windows creates installation friction and causes immediate runtime crashes if `ffmpeg.exe` is not configured in PATH.
  2. *AI Suggestion 2: Only allowing `.wav` file uploads*:
     - **Why Rejected**: Browser `MediaRecorder` cannot record raw uncompressed WAV natively across all modern mobile browsers without heavy client-side JavaScript encoding libraries.

* **Resolution**:
  I designed a dual-engine signal processor in `app/audio_processor.py`:
  - **Path 1 (Standard WAV)**: Leveraged Python's built-in `wave` module to extract frame count, sample width, and sample rate with sub-millisecond precision.
  - **Path 2 (General / Compressed Audio Fallback)**: Inspected container chunk headers and estimated streaming bitrates.
  - **Signal Metrics & SNR (NumPy Engine)**:
    Converted raw audio frames to float sample arrays and computed Root Mean Square (RMS) energy:
    $$\text{Loudness (dBFS)} = 20 \log_{10}\left(\frac{\text{RMS}}{\text{Max Amplitude}}\right)$$
    Segmented frames into 50ms windows to calculate the ratio between peak voice energy (90th percentile) and background noise floor (10th percentile), returning an objective **Signal-to-Noise Ratio (SNR)** quality score.

---

### Challenge 3: Shifted Columns & Multi-Tier Entity Resolution Without Shared Global IDs

* **Where Stuck**:
  1. `rates.csv` contained a corrupted row (Row 19: `"react, javascript, mysql",ISHA.CHOPRA95@...`) where the skill tags column was placed first and email was placed second.
  2. There was **no single common ID** across all three files: `applicants.csv` had `(Email, Phone)`, `workers.csv` had `(Phone, Name)`, and `rates.csv` had `(Email, Name)`.
  3. Some candidate names were identical but represented different people (e.g. `Arjun Mehta` in Noida appeared with phone `9000000131` [9 projects] and phone `9000000272` [14 projects]).

* **What Was Researched**:
  - "Entity resolution graph matching python"
  - "Handling shifted columns in CSV python DictReader"
  - "Deduplicating recruitment records with contradictory identifiers"

* **What Was Asked to AI**:
  > "What is the cleanest architecture to resolve entities across 3 CSV files when File 1 links Email-Phone, File 2 links Phone-Name, and File 3 links Email-Name, while preventing false-positive name merges?"

* **Suggestions Rejected & Why**:
  1. *AI Suggestion 1: Merging purely on normalized Name*:
     - **Why Rejected**: Would incorrectly merge different people who share common Indian names (e.g., merging the two distinct *Arjun Mehtas* in Noida who have completely different verified phone numbers).
  2. *AI Suggestion 2: Fuzzy Levenshtein matching on all fields*:
     - **Why Rejected**: Non-deterministic and fragile; slight variations in skill tags or city spelling would produce inconsistent entity IDs across runs.

* **Resolution**:
  1. **Adaptive Row Parser**: Before processing a CSV row in `rates.csv`, the parser checks if column index 1 contains `@` while column 0 contains commas. If true, it automatically remaps the shifted attributes.
  2. **Multi-Tier Graph Resolver**:
     - **Tier 1**: Normalized 10-digit Phone match (strongest unique identifier).
     - **Tier 2**: Normalized lowercase Email match.
     - **Tier 3**: Normalized Full Name + Canonical City match (only when Phone and Email are absent).
  This deterministic hierarchy correctly merged all cross-system profiles (including *Isha Chopra*, *Rohit Verma / R. Verma*, and *Nikhil Chopra*) while strictly protecting distinct individuals with the same name.
