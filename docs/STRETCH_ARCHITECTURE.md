# Task 5: Scaling to 5,000 Gig Workers (System Architecture Proposal)

A system design analysis evaluating potential failure modes, infrastructure bottlenecks, and production upgrades required to scale the ConsultBae Audio Collection Platform to 5,000 concurrent gig workers over a single weekend.

---

## 1. Traffic, Storage & Workload Modeling

* **Total Active Gig Workers**: 5,000 workers submitting 1–3 recordings each $\approx$ 10,000 audio submissions.
* **Average Recording Size**: 30 seconds @ 128 kbps (AAC/WebM) $\approx$ 500 KB – 2 MB per file.
* **Total Storage Footprint**: $10,000 \times 1.5\text{ MB} \approx 15\text{ GB}$ of raw audio.
* **Peak Traffic Burst**: ~600–800 submissions/hour during peak submission windows (~15–25 requests/sec peak).

---

## 2. Identified Failure Points in Single-Node Prototype

```
[ Prototype Synchronous Architecture ]
Gig Worker (Mobile Client) ---> [ Multipart Upload (2MB) ] ---> [ Web Server ]
                                                                      |
                                            +-------------------------+-------------------------+
                                            |                                                   |
                                            v                                                   v
                             [ In-Memory Signal Analysis ]                             [ SQLite DB Lock ]
                             (CPU Saturation / Timeouts)                               (Database Locked Error)
```

1. **SQLite Concurrency Locking (`database is locked` error)**:
   SQLite supports multiple concurrent readers but only **one single writer at a time**. Under 20+ concurrent write transactions, locks queue up, leading to connection timeouts and HTTP 500 responses.
2. **Synchronous Audio Processing & HTTP Worker Starvation**:
   Extracting duration, sample rate, RMS loudness, and SNR in the main FastAPI request thread blocks worker threads for 200–800ms per submission. Under burst traffic, the thread pool is exhausted, causing cascading timeouts for subsequent users.
3. **Local File Storage & Ephemeral Container Restarts**:
   Storing files in `./uploads/` on local disk causes data loss in serverless or auto-scaling container environments (e.g. AWS ECS, Render, Railway, Kubernetes) when containers restart or scale out.
4. **Mobile Network Upload Drops**:
   Gig workers submitting via mobile connections experience TCP resets on multipart HTTP uploads without chunked or resumable upload support.
5. **Duplicate Submissions from Client Retries**:
   Workers re-tapping the submit button on high-latency connections generate redundant database rows and duplicate audio files.

---

## 3. Recommended Production Architecture

```
[ Scalable Event-Driven Architecture ]

Gig Worker ---> [ 1. Request Presigned URL ] ---> [ API Gateway / FastAPI ]
    |                                                     | (Generates S3 Presigned URL & DB Pending Record)
    |                                                     v
    |                                           [ Managed PostgreSQL (PgBouncer) ]
    |                                                     ^
    +-----------> [ 2. Direct Chunked Upload (TUS) ] ---> [ AWS S3 / Cloudflare R2 ]
                                                          |
                                                 (ObjectCreated Event)
                                                          |
                                                          v
                                                 [ AWS SQS / Redis Queue ]
                                                          |
                                                          v
                                             [ Background Workers (Celery / Lambda) ]
                                             (Calculates Duration, Loudness dB, SNR)
                                                          |
                                                          v
                                             [ Update Extracted Properties in DB ]
```

### Architectural Components

1. **Direct-to-Object-Storage Uploads (Presigned S3 URLs / Cloudflare R2)**:
   - The web app never proxies raw audio binary data.
   - Flow: Client requests a pre-signed S3 upload URL $\to$ Client uploads directly to S3 via chunked, resumable protocol (e.g. **TUS.io** or S3 Multipart Upload).
   - Reduces web server compute and network egress by over 90%.

2. **Asynchronous, Event-Driven Audio Extraction**:
   - S3 Event Notifications push upload events to **AWS SQS** (or Redis Queue).
   - Containerized worker pools (Celery / AWS Lambda) consume the queue, extract audio signal properties (duration, sample rate, bitrate, loudness dB, SNR quality estimate), and update the database record.

3. **Managed PostgreSQL with Connection Pooling (PgBouncer)**:
   - Replaces SQLite with managed **PostgreSQL** (AWS RDS Aurora / Supabase).
   - Utilizes **PgBouncer** connection pooling to manage thousands of transient mobile connections without exhausting database memory limits.

4. **Deduplication, Idempotency & Rate Limiting**:
   - **Idempotency Key**: Client generates a unique UUID submission key; duplicate HTTP submissions with the same key return the existing record immediately without re-processing.
   - **Redis Rate Limiting**: Limits submissions to 5 per minute per phone number to prevent accidental duplicates or automated spam.

5. **Edge Delivery & Global CDN (Cloudflare)**:
   - Fronts the application and static assets with Cloudflare CDN.
   - Serves reviewer audio playback via Cloudflare CDN signed URLs with HTTP byte-range caching for efficient audio scrubbing.

---

## 4. Weekend Infrastructure Cost Estimation

| Infrastructure Component | Resource Specification | Estimated Weekend Cost (USD) |
|---|---|---|
| **Storage (AWS S3 / Cloudflare R2)** | 15 GB stored + 30 GB egress data transfer | **$0.80** (R2 has zero egress fee) |
| **Database (AWS RDS PostgreSQL / Supabase)** | db.t4g.small instance with 20GB SSD | **$3.50** (for 3 days) |
| **API & Worker Compute (AWS ECS / Fargate)** | 2 Fargate vCPU tasks (2 vCPU, 4GB RAM) | **$11.20** |
| **Async Queue & Redis (AWS SQS + ElastiCache)** | 10k messages + cache.t4g.micro | **$2.40** |
| **CDN & DDoS Protection (Cloudflare)** | Pro Plan / Free Plan + Edge Caching | **$0.00 - $20.00** |
| **Total Estimated Weekend Cost** | Full High-Availability Deployment | **~$18.00 - $38.00 USD** |

---

## 5. Summary Recommendation
By decoupling file ingestion from audio computation and utilizing S3 presigned direct uploads, the platform can support **5,000+ gig workers with high reliability at under $40 total cost**.
