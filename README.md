# FEM — Forecasting Engine Monitor

A self-hosted strategic intelligence platform that monitors sources, extracts signals, synthesizes trends, and generates scenario narratives for foresight and decision-making.

FEM runs entirely on your machine. No cloud LLM APIs are required — it uses local models via [Ollama](https://ollama.com) by default, with optional cloud provider fallbacks.

---

## What it does

FEM automates the core workflow of a foresight analyst:

1. **Crawls sources** — RSS feeds and web pages you designate per theme
2. **Filters for relevance** — deterministic keyword scoring against your theme's focal question
3. **Extracts signals** — an LLM reads each relevant document and extracts a structured signal (title, summary, type, STEEP category, time horizon, importance/novelty scores)
4. **Clusters signals** — Jaccard token overlap groups related signals together
5. **Links signals** — a three-layer knowledge graph connects signals across clusters using shared clusters, semantic embeddings, and LLM-confirmed relationships (reinforcing or tensioning)
6. **Synthesizes trends** — LLM synthesizes each cluster into a named trend with direction, counterpole, and S-curve position, enriched with cross-cluster signal context
7. **Extracts drivers** — identifies the underlying forces driving each trend, scored by impact and uncertainty
8. **Proposes scenario axes** — selects the two most critical uncertainties and defines extreme poles for a 2×2 scenario matrix
9. **Generates scenarios** — produces four vivid, divergent scenario narratives with early indicators, opportunities, and threats
10. **Monitors live scenarios** — matches incoming signals against scenario indicators and raises alerts

---

## Requirements

| Dependency | Version | Notes |
|---|---|---|
| Docker & Docker Compose | v2+ | Runs all services |
| Ollama | latest | Local LLM inference |
| Node.js | 18+ | Only needed for local frontend dev outside Docker |

---

## LLM models

FEM uses three Ollama models. Pull them before starting:

```bash
ollama pull llama3.1          # signal extraction, trend synthesis, driver extraction
ollama pull deepseek-r1:14b   # scenario generation and axis reasoning
ollama pull nomic-embed-text  # signal embeddings for the knowledge graph
```

Minimum VRAM requirements depend on which models you load simultaneously. `llama3.1` and `nomic-embed-text` are lightweight. `deepseek-r1:14b` requires ~10GB VRAM (Q4).

### Optional: cloud providers

FEM supports DeepSeek API as a fallback for higher-quality outputs. Set `DEEPSEEK_API_KEY` in your `.env` to enable it. The routing table is fully configurable — see [LLM routing](#llm-routing) below.

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/joseallona/fem.git
cd fem
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and review the defaults. Most values work out of the box. The key ones:

```env
# Points to Ollama running on your host machine (not inside Docker)
OLLAMA_BASE_URL=http://host.docker.internal:11434

# The main chat model for extraction and synthesis
OLLAMA_MODEL=llama3.1

# The reasoning model for scenario generation and axis selection
OLLAMA_MODEL_REASONING=deepseek-r1:14b

# The embedding model for signal linking
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Change this to a random string in any shared environment
SECRET_KEY=change-me-in-production
```

### 3. Start services

```bash
docker compose up --build
```

This starts:
- **PostgreSQL 16** on port `5432`
- **Redis 7** on port `6379`
- **Backend API** (FastAPI) on port `8000`
- **Worker** (RQ) — processes pipeline jobs from the queue
- **Frontend** (Next.js) on port `3000`

### 4. Run database migrations

```bash
docker exec fem-backend-1 alembic upgrade head
```

### 5. Open the app

Navigate to [http://localhost:3000](http://localhost:3000).

---

## Getting started

### Create a theme

A **theme** is the strategic question you want to monitor. Examples:
- *"How will the energy transition reshape industrial competitiveness in Europe over the next 10 years?"*
- *"What forces will determine AI adoption in enterprise software by 2030?"*

Each theme has a name, primary subject, related subjects, focal question, and time horizon. These fields define the relevance filter — only sources that match your theme vocabulary pass through.

### Add sources

Sources are RSS feeds or web pages assigned to a theme. FEM crawls them automatically on each pipeline run. Approved sources are crawled; blocked sources are skipped.

### Run the pipeline

Trigger a run manually from the theme view, or let the daily scheduler run it automatically. The pipeline processes all approved sources and produces signals, trends, drivers, and scenarios in a single pass.

### Review signals

Signals are the atomic unit of intelligence. Each signal has a STEEP category (Social, Technological, Economic, Environmental, Political), a time horizon (H1/H2/H3), and importance/novelty scores. Signals marked `active` feed into trend synthesis.

### Read the report

The report view assembles all trends, drivers, scenarios, and briefs into a single narrative document ready for stakeholder consumption.

---

## Pipeline stages

| Stage | Name | Method |
|---|---|---|
| 1 | Source discovery | Manual / auto-discovery |
| 2 | Source selection | Approved sources filter |
| 3 | Crawling | RSS + HTML (trafilatura) |
| 4 | Raw document storage | Hash-deduplicated |
| 5 | Deduplication | Content hash + title similarity |
| 6 | Relevance filtering | Deterministic keyword scoring |
| 7–8 | Signal extraction + classification | LLM (llama3.1) |
| 9 | Scoring & ranking | Deterministic rules |
| 10–11 | Scenario mapping + update | Keyword overlap + scoring engine |
| 11b | Signal clustering | Jaccard + Union-Find |
| **11c** | **Signal linking** | **3-layer knowledge graph (new)** |
| 12 | Change detection | Diff vs previous run |
| 13 | Trend synthesis | LLM over signal clusters + link context |
| 14 | Driver extraction | LLM from trends |
| 15 | Axis proposal | LLM pole labels for top-2 drivers |
| 16 | Scenario monitoring | Deterministic indicator matching |

---

## Signal knowledge graph (Stage 11c)

FEM builds a semantic knowledge graph linking signals that share underlying forces, enabling the trend synthesizer to see cross-cluster patterns instead of just flat signal lists.

Three layers run synchronously before trend synthesis:

**Layer 1 — Cluster links** (free)
Signals already grouped by the clustering stage are formally linked with strength 1.0. No LLM call needed.

**Layer 2 — Embedding similarity** (semantic)
Each signal is embedded using `nomic-embed-text`. Pairs with cosine similarity ≥ 0.78 are linked with strength = cosine score, scoped to signals within the same theme.

**Layer 3 — LLM reasoning** (selective)
Pairs scoring ≥ 0.82 that aren't already cluster-linked get an LLM call to confirm the connection and classify the relationship:
- **reinforcing** — both signals push in the same direction or amplify the same trend
- **tensioning** — the signals point in opposing directions or represent competing forces

Capped at 30 LLM calls per run. All layers are idempotent.

The trend synthesizer uses these links to inject cross-cluster reinforcing and tensioning context into each trend synthesis prompt, giving the LLM a wider view than the current cluster boundary.

---

## LLM routing

FEM routes different job types to different providers. The default table:

| Job type | Default provider | Used for |
|---|---|---|
| `extraction` | `ollama` | Signal extraction from documents |
| `classification` | `ollama` | Signal type/STEEP/horizon classification |
| `summary` | `ollama` | Trend synthesis, driver extraction, signal linking |
| `scenario` | `ollama-r1` | Scenario narrative generation |
| `axis` | `ollama-r1` | Axis selection and divergence scoring |
| `brief` | `ollama` | Final report prose |

Override the routing at runtime via the Settings page or via `.env`:

```env
# Example: use DeepSeek for summaries, keep local R1 for scenarios
LLM_ROUTING=summary:deepseek,scenario:ollama-r1
```

Fallback chains ensure the pipeline never hard-fails due to a missing API key:
- `ollama-r1` → `ollama`
- `deepseek-r1` → `deepseek` → `ollama-r1` → `ollama`

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Frontend (Next.js 14 + Tailwind + Radix)   │  :3000
└────────────────────┬────────────────────────┘
                     │ HTTP
┌────────────────────▼────────────────────────┐
│  Backend API (FastAPI + SQLAlchemy)          │  :8000
│  Routers: themes, signals, scenarios,        │
│           trends, sources, briefs, runs      │
└──────────┬──────────────────┬───────────────┘
           │                  │
    ┌──────▼──────┐    ┌──────▼──────┐
    │ PostgreSQL  │    │    Redis    │
    │     16      │    │      7      │
    └─────────────┘    └──────┬──────┘
                              │ job queue
                       ┌──────▼──────┐
                       │  RQ Worker  │
                       │  (pipeline) │
                       └──────┬──────┘
                              │
                       ┌──────▼──────┐
                       │   Ollama    │  host machine
                       │ llama3.1   │
                       │ deepseek-r1│
                       │ nomic-embed│
                       └─────────────┘
```

---

## Tech stack

**Backend**
- Python 3.12, FastAPI, SQLAlchemy 2, Alembic
- RQ + RQ Scheduler (job queue)
- trafilatura + feedparser (crawling)
- httpx (Ollama/DeepSeek API calls)

**Frontend**
- Next.js 14, React 18, TypeScript
- Tailwind CSS, Radix UI
- Recharts + D3 (scenario matrix, report charts)

**Infrastructure**
- PostgreSQL 16 (primary store)
- Redis 7 (job queue + scheduler)
- Docker Compose (all services)

---

## Updating

```bash
git pull
docker compose up --build
docker exec fem-backend-1 alembic upgrade head
```

---

## Troubleshooting

**Pipeline fails with "Ollama connection refused"**
Make sure Ollama is running on your host machine (`ollama serve`) and that `OLLAMA_BASE_URL=http://host.docker.internal:11434` is set in `.env`. On Linux, `host.docker.internal` may not resolve automatically — use your host's IP instead.

**Embeddings not working**
Verify `nomic-embed-text` is pulled: `ollama list`. If missing, run `ollama pull nomic-embed-text`.

**No signals after a run**
Check that your sources are marked as `approved` in the Sources view. Also review the relevance threshold in Settings — a threshold that's too high will filter everything out.

**Frontend shows no data**
Confirm the backend is healthy: `curl http://localhost:8000/health`. Check that `NEXT_PUBLIC_API_URL=http://localhost:8000` is set in `.env`.

**Worker not processing jobs**
Confirm the worker container is running: `docker compose ps`. Check worker logs: `docker compose logs worker`.
