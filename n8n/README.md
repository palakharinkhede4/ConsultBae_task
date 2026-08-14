# ConsultBae n8n Workflow Automation (Task 2)

This directory contains the exportable **n8n automation workflow** for candidate deduplication, database synchronization, and LLM skill auto-tagging.

---

## Workflow Architecture Diagram

```
[ Webhook Trigger (Incoming Profile / CSV Row) ]
                       |
                       v
            [ Data Normalizer Code Node ]
    (Standardizes Phone: 10-digits, Lowercases Email)
                       |
                       v
        [ SQLite Database Lookup Node ]
       (SELECT * FROM candidates WHERE phone/email)
                       |
                       v
          [ IF Node: Is Duplicate? ]
              /                  \
      (YES: Duplicate)     (NO: New Candidate)
            |                      |
            v                      v
  [ Slack/Webhook Alert ]   [ LLM Auto-Tag Skill Category ]
  "Duplicate Detected"      (Classifies: Automation/Web/Data)
            |                      |
            v                      v
  [ Respond HTTP 200 ]     [ Save Profile to SQLite DB ]
  (Status: DUPLICATE)              |
                                   v
                           [ Respond HTTP 200 ]
                           (Status: SUCCESS + AI Tags)
```

---

## Features Implemented

1. **Webhook Ingestion**: Accepts JSON payload from recruitment forms, webhooks, or new CSV entries.
2. **Deterministic Data Normalization**: Cleans phone numbers (handles `+91`, `0`, spaces) and lowercases emails.
3. **Database Deduplication**: Looks up the candidate in the SQLite database created in Task 1.
4. **Duplicate Alerting Branch**: If the person already exists, dispatches an immediate alert payload (Slack/Webhook/Email) with their existing status and data sources.
5. **Skill Categorization Branch**: If new, prompts an LLM agent to classify their skill set into `Automation Specialist`, `Full-Stack Web Dev`, `Data & AI Engineer`, or `Backend Engineer`, then writes back the enriched profile to the database.

---

## How to Import & Run in n8n

### Option A: Using Free n8n Cloud Trial (Fastest, No Install)
1. Sign up for a free trial at [n8n.io](https://n8n.io).
2. Click **Add Workflow** -> Click the **3 dots (top right)** -> Select **Import from File**.
3. Choose `n8n/consultbae_candidate_automation.json`.
4. Click **Save** and **Activate / Test step**.

### Option B: Running Locally via n8n Desktop or Docker
Run this command in terminal:
```bash
npx n8n
```
Or with Docker:
```bash
docker run -it --rm --name n8n -p 5678:5678 -v ~/.n8n:/home/node/.n8n docker.n8n.io/n8nio/n8n
```
Open `http://localhost:5678` in your browser, import the `consultbae_candidate_automation.json` file, and test.

---

## Test Payloads

### Test 1: Testing Duplicate Detection
Send a candidate that already exists in Task 1 DB (e.g. Tanvi Gupta):
```bash
curl -X POST http://localhost:5678/webhook-test/candidate-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tanvi Gupta",
    "phone": "+91-9000000254",
    "email": "tanvi.gupta31@example.com",
    "skills": "n8n, LangChain, REST APIs, MongoDB, SQL"
  }'
```
**Expected Outcome**: Trigger fires -> Normalizer cleans phone -> SQLite finds existing record -> IF branch takes TRUE -> Sends Duplicate Alert.

### Test 2: Testing New Candidate + LLM Auto-Tagging
Send a new candidate:
```bash
curl -X POST http://localhost:5678/webhook-test/candidate-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Aarav Sharma",
    "phone": "9876543210",
    "email": "aarav.sharma@example.com",
    "city": "Bengaluru",
    "experience_years": 4.5,
    "skills": "FastAPI, PyTorch, LangChain, Vector DBs, Python"
  }'
```
**Expected Outcome**: Trigger fires -> SQLite finds no duplicate -> IF branch takes FALSE -> LLM node auto-tags as `"Data & AI Engineer"` (Senior) -> Inserts record into database.
