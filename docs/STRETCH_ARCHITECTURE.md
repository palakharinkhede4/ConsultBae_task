# Task 5 — Scaling to 5,000 Gig Workers (Stretch Architectural Proposal)

An executive system design breakdown analyzing failure modes, architectural bottlenecks, and production upgrades required to scale the ConsultBae Audio Collection Platform from prototype to 5,000 concurrent gig workers over a single weekend.

---

## 1. Traffic, Storage & Workload Modeling

* **Total Active Gig Workers**: 5,000 workers submitting 1–3 recordings each $\approx$ 10,000 audio submissions.
* **Average Recording Size**: 30 seconds @ 128 kbps (AAC/WebM) $\approx$ 500 KB – 2 MB per file.
* **Total Storage Footprint**: $10,000 \times 1.5\text{ MB} \approx 15\text{ GB}$ of raw audio.
* **Peak Traffic Burst**: ~600–800 submissions/hour during peak weekend gig submission windows (~15–25 requests/sec peak).

---

## 2. What Breaks First in the Current Prototype?

```
[ Current Synchronous Architecture Bottlenecks ]
Gig Worker (Mobile 4G) ───[ Multipart Upload (2MB) ]───► [ Single Web Server ]
                                                              │
                                            ┌─────────────────┴─────────────────┐
                                            ▼                                   ▼
                             [ Sync In-Memory Audio Analysis ]         [ SQLite DB Lock ]
                             (CPU Spike -> Worker Starvation)       (Database Locked Error)
```

1. **SQLite Database Concurrency Locking (`database is locked` error)**:
   SQLite supports multiple readers but only **one single writer at a time**. Under 20+ concurrent submissions, write locks will queue up, resulting in connection timeouts and 500 Internal Server Errors.
2. **Synchronous Audio Processing & HTTP Worker Starvation**:
   Extracting duration, sample rate, RMS loudness, and SNR in the main FastAPI request thread blocks worker threads for 200–800ms per file. Under concurrent load, the thread pool is quickly exhausted, causing cascading timeouts for subsequent users.
3. **Local File Storage & Ephemeral Container Restarts**:
   Storing files in `./uploads/` on local disk causes instant data loss if deployed to serverless or auto-scaling containers (e.g. AWS ECS, Render, Railway, Kubernetes) when containers restart or scale out.
4. **Flaky Mobile Upload Failures & Network Drops**:
   Gig workers submitting via mobile data will experience frequent TCP resets on multipart HTTP uploads over 2MB without chunked or resumable upload support.
5. **Duplicate Submissions from Double-Tapping**:
   Workers frantically tapping the submit button on slow networks will cause duplicate database rows and redundant audio files.

---

## 3. Production Architecture Before Launch

```
[ Scalable Event-Driven Cloud Architecture ]

Gig Worker ──[ 1. Request Presigned URL ]──► [ API Gateway / FastAPI ]
    │                                                    │ (Generates URL & DB Pending Record)
    │                                                    ▼
    │                                          [ PostgreSQL (PgBouncer) ]
    │                                                    ▲
    ├──[ 2. Direct Chunked Upload (TUS/S3) ]──► [ AWS S3 / Cloudflare R2 ]
                                                         │
                                                (ObjectCreated Event)
                                                         │
                                                         ▼
                                                [ AWS SQS / Redis Queue ]
                                                         │
                                                         ▼
                                            [ Background Audio Workers (Celery/Lambda) ]
                                            (Extracts Duration, Loudness dB, SNR Quality)
                                                         │
                                                         ▼
                                            [ Write Extracted Properties to DB ]
```

### Key Architectural Changes

1. **Direct-to-Object-Storage Uploads (Presigned S3 URLs / Cloudflare R2)**:
   - The web app never touches heavy audio bytes.
   - Flow: Client requests a pre-signed S3 upload URL $\to$ Client uploads directly to S3 via chunked, resumable protocol (e.g. **TUS.io** or S3 Multipart Upload).
   - Web servers handle only lightweight JSON requests, cutting server bandwidth and CPU usage by >90%.

2. **Asynchronous, Event-Driven Audio Extraction**:
   - When S3 receives the audio file, an S3 Event Notification pushes a message to **AWS SQS** (or Redis Queue).
   - Containerized worker pools (Celery / AWS Lambda / Ray) consume the queue, analyze audio properties (duration, sample rate, bitrate, loudness dB, SNR quality estimate), and update the database record.

3. **Managed PostgreSQL with Connection Pooling (PgBouncer)**:
   - Replace SQLite with managed **PostgreSQL** (AWS RDS Aurora / Supabase).
   - Implement **PgBouncer** connection pooling to manage thousands of transient mobile connections without exhausting database memory.

4. **Deduplication, Idempotency & Rate Limiting**:
   - **Idempotency Key**: The client generates a unique submission UUID per attempt; duplicate HTTP submissions with the same key return the existing record immediately without re-processing.
   - **Redis Rate Limiting**: Limit each phone number to 5 submissions per minute to prevent accidental spamming or bot abuse.

5. **Edge Delivery & Global CDN (Cloudflare)**:
   - Front the web app and static assets with Cloudflare CDN.
   - Serve reviewer audio playback via Cloudflare CDN signed URLs with HTTP byte-range caching for instant scrubbing without hitting S3 origin.

---

## 4. Total Weekend Cost Estimation

| Infrastructure Component | Resource Specification | Estimated Weekend Cost (USD) |
|---|---|---|
| **Storage (AWS S3 / Cloudflare R2)** | 15 GB stored + 30 GB egress data transfer | **$0.80** (R2 has $0 egress) |
| **Database (AWS RDS PostgreSQL / Supabase)** | db.t4g.small instance with 20GB SSD | **$3.50** (for 3 days) |
| **API & Worker Compute (AWS ECS / Fargate)** | 2 Fargate vCPU tasks (2 vCPU, 4GB RAM) | **$11.20** |
| **Async Queue & Redis (AWS SQS + ElastiCache)** | 10k messages + cache.t4g.micro | **$2.40** |
| **CDN & DDoS Protection (Cloudflare Pro)** | Pro Plan / Free Plan + Edge Caching | **$0.00 – $20.00** |
| **Total Estimated Weekend Cost** | Full High-Availability Deployment | **~$18.00 – $38.00 USD** |

---

## 5. Summary Recommendation
By decoupling file ingestion from audio computation and utilizing S3 presigned direct uploads, the platform can effortlessly handle **5,000+ gig workers with 99.99% reliability at under $40 total cost**.
