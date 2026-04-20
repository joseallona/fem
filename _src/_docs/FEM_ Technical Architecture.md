# **Technical Architecture**

## **1\. Architecture goal**

Build a system that can:

* let a user define a project and theme  
* discover and manage sources  
* run a daily crawl  
* extract and rank signals  
* map signals to scenarios  
* generate a dashboard and strategic brief  
* use LLMs only where deterministic methods are insufficient

---

## **2\. High-level system design**

Use a modular architecture with 6 services/layers:

1. **Frontend App**  
2. **Application API**  
3. **Source Discovery \+ Crawling Pipeline**  
4. **Signal Processing Pipeline**  
5. **Scenario \+ Brief Engine**  
6. **Data Layer**

A simple MVP deployment can keep most of this in one backend codebase, but logically these should stay separate.

---

## **3\. Recommended stack**

## **Frontend**

* **Next.js / React**  
* TypeScript  
* Shadcn/Tailwind for UI  
* Shadcn chart library for dashboard visuals

Why:

* fast to build  
* good for authenticated app flows  
* easy dashboard \+ forms

---

## **Backend API**

* **Python \+ FastAPI**  
* REST API first  
* background jobs via Celery or a simpler queue/scheduler

Why:

* strong ecosystem for crawling, NLP, ranking, pipelines  
* easier integration with ML/LLM components

---

## **Database**

* **PostgreSQL**

Use it for:

* projects  
* themes  
* sources  
* signals  
* scenarios  
* monitoring runs  
* user feedback  
* briefs

Why:

* structured, reliable, enough for MVP  
* supports JSONB when you need flexible metadata

---

## **Search / retrieval**

For MVP:

* PostgreSQL full-text \+ indexed fields

Later:

* OpenSearch / Elasticsearch for advanced signal search  
* vector store only if genuinely needed

Do not add a vector DB on day one unless similarity retrieval becomes a bottleneck.

---

## **Queue / scheduler**

* **Celery \+ Redis** or **RQ \+ Redis**  
* Daily cron triggers pipeline jobs

Why:

* easy async job control  
* retries  
* separation between UI/API and crawling jobs

---

## **Crawling / scraping**

* Python crawling layer using:  
  * RSS parsing first  
  * sitemap/news feeds  
  * HTTP fetchers  
  * selective scraping for approved domains

Possible tools:

* feedparser  
* newspaper3k or trafilatura  
* BeautifulSoup  
* Playwright only when necessary

Use the simplest source-specific method first.

---

## **LLM layer**

Use LLMs only for:

* ambiguous summarization  
* signal interpretation  
* scenario impact drafting  
* brief writing

Possible approach:

* remote LLM API initially  
* optionally local LLM for selected workloads

---

## **Local model option**

Consider a local LLM for:

* first-pass classification assistance  
* summarization on sensitive data  
* cost-heavy recurring tasks

Practical local options:

* Ollama-hosted model  
* vLLM if you later need throughput  
* small/medium instruct models for cheap internal inference

Recommendation:

* start with a remote model for quality  
* design the system so model providers are swappable  
* later route certain jobs to local inference

---

# **4\. Logical architecture**

## **A. Frontend App**

Main screens:

* Project Setup  
* Theme Setup  
* Source Management  
* Theme Dashboard  
* Signal Explorer  
* Scenario View  
* Strategic Brief View

Frontend responsibilities:

* forms and workflow orchestration  
* filtering and browsing  
* dashboard rendering  
* review/edit flows  
* feedback capture

Frontend should not do:

* crawling  
* classification logic  
* scenario updates  
* document synthesis logic

---

## **B. API Layer**

FastAPI app handles:

* auth/session integration  
* CRUD for projects, themes, sources, scenarios  
* dashboard data aggregation  
* signal review actions  
* brief generation triggers  
* job status endpoints

Example domains:

* `/projects`  
* `/themes`  
* `/sources`  
* `/signals`  
* `/scenarios`  
* `/briefs`  
* `/runs`

---

## **C. Source Discovery Service**

Purpose:  
Given a theme, discover candidate sources worth monitoring.

Inputs:

* theme name  
* primary subject  
* related subjects  
* user-provided seed sources

Outputs:

* suggested sources with metadata

Deterministic logic first:

* keyword expansion  
* subject ontology / synonym lists  
* source scoring rules  
* domain-type classification  
* freshness checks

Possible source scoring dimensions:

* topical relevance  
* authority / trust  
* update frequency  
* signal density  
* uniqueness

LLM only where needed:

* infer related subtopics if rule-based taxonomy is insufficient  
* summarize why a source is relevant

This should be a separate module, even if in same codebase.

---

## **D. Crawling Service**

Purpose:  
Fetch content from approved sources daily.

Pipeline:

1. get active sources for theme  
2. fetch latest entries  
3. normalize content  
4. store raw documents  
5. emit candidate documents for signal extraction

Best-practice order:

1. RSS/API  
2. structured HTML extraction  
3. browser automation only if unavoidable

Store raw crawl metadata:

* fetch timestamp  
* URL  
* title  
* source ID  
* raw text  
* extraction success/failure  
* fingerprint/hash

This makes dedupe and debugging much easier.

---

## **E. Signal Processing Pipeline**

This is the core engine.

### **Step 1: Deduplication**

Use deterministic methods first:

* content hash  
* normalized title similarity  
* URL canonicalization  
* cosine similarity on embeddings only if needed later

### **Step 2: Relevance filtering**

Prefer deterministic/ranked methods first:

* keyword overlap with theme  
* taxonomy matches  
* source relevance priors  
* recency  
* rule-based exclusions

LLM only if a document is ambiguous.

### **Step 3: Signal extraction**

Possible outputs:

* title  
* concise summary  
* signal type candidate  
* quoted evidence  
* entities  
* subject tags

This is a valid LLM use case, because semantic compression is hard to do deterministically at high quality.

### **Step 4: Classification**

Classify into:

* STEEP  
* signal type  
* horizon  
* novelty/importance candidates

Recommended architecture:

* deterministic rules where easy  
* model assistance for ambiguous cases  
* human override always available

### **Step 5: Ranking**

Use a weighted scoring model, not an LLM.

Example signal score:

* relevance score  
* novelty score  
* source trust score  
* recency score  
* cross-source confirmation score  
* user feedback prior

This should be traditional software.

### **Step 6: Clustering**

Group related signals.

MVP approach:

* topic/entity overlap  
* keyword similarity  
* time proximity

Later:

* embedding clustering if needed

Again, do not default to LLMs here.

---

## **F. Scenario Engine**

Purpose:  
Map signals to scenarios and update scenario state.

### **Scenario state model**

Each scenario has:

* confidence: low / medium / high  
* momentum: increasing / stable / decreasing

### **Inputs**

* relevant new signals  
* signal strength  
* signal direction  
* source diversity  
* recency  
* user-confirmed mappings

### **Update mechanism**

Do this with a scoring engine, not an LLM.

Example:

* each signal contributes support or contradiction  
* weighted by relevance and quality  
* rolling time window updates scenario score  
* thresholds map score bands into confidence/momentum states

Illustrative internal model:

* scenario\_support\_score  
* scenario\_contradiction\_score  
* recent\_delta\_7d  
* recent\_delta\_30d

User-facing result:

* “gaining support”  
* “stable”  
* “weakening”

This is exactly the kind of logic that should be deterministic.

LLM may assist only in:

* drafting explanation of why a scenario is strengthening  
* suggesting initial mapping of signal → scenario

Final update logic should be code.

---

## **G. Brief Generation Engine**

Purpose:  
Produce weekly and on-demand strategic briefs.

This should be split into 2 layers:

### **Layer 1: Deterministic brief assembly**

Build the structure in code:

* section order  
* heading rules  
* data inclusion rules  
* top N signal selection  
* scenario delta section  
* formatting and export structure

### **Layer 2: LLM content generation**

Use model only for:

* prose summaries  
* “why it matters”  
* implications draft  
* recommendation draft

This matches your principle exactly:

* **content may use LLM**  
* **format and structure should use traditional software**

---

# **5\. Suggested data architecture**

## **Core tables**

### **projects**

* id  
* name  
* description  
* owner  
* status  
* created\_at  
* updated\_at

### **themes**

* id  
* name  
* description  
* primary\_subject  
* focal\_question  
* time\_horizon  
* stakeholders\_json  
* scope\_text  
* created\_at  
* updated\_at

### **project\_themes**

* project\_id  
* theme\_id

### **sources**

* id  
* theme\_id  
* name  
* domain  
* url  
* source\_type  
* discovery\_mode  
* relevance\_score  
* trust\_score  
* crawl\_frequency  
* status  
* last\_crawled\_at

### **crawl\_runs**

* id  
* theme\_id  
* started\_at  
* completed\_at  
* status  
* sources\_scanned  
* documents\_fetched  
* signals\_created  
* notes

### **raw\_documents**

* id  
* source\_id  
* crawl\_run\_id  
* url  
* title  
* published\_at  
* fetched\_at  
* raw\_text  
* content\_hash  
* canonical\_url  
* metadata\_json

### **signals**

* id  
* theme\_id  
* source\_id  
* raw\_document\_id  
* title  
* summary  
* signal\_type  
* steep\_category  
* horizon  
* importance\_score  
* novelty\_score  
* relevance\_score  
* status  
* created\_at

### **scenarios**

* id  
* theme\_id  
* name  
* narrative  
* confidence\_level  
* momentum\_state  
* internal\_score  
* created\_at  
* updated\_at

### **signal\_scenarios**

* signal\_id  
* scenario\_id  
* relationship\_type  
* relationship\_score  
* user\_confirmed  
* explanation\_text

### **briefs**

* id  
* theme\_id  
* period\_start  
* period\_end  
* generation\_mode  
* status  
* structured\_payload\_json  
* rendered\_text  
* created\_at

### **user\_feedback**

* id  
* signal\_id  
* feedback\_type  
* old\_value  
* new\_value  
* note  
* created\_at

---

# **6\. API design outline**

## **Project endpoints**

* `POST /projects`  
* `GET /projects/:id`  
* `PATCH /projects/:id`

## **Theme endpoints**

* `POST /themes`  
* `GET /themes/:id`  
* `PATCH /themes/:id`

## **Source endpoints**

* `GET /themes/:id/sources`  
* `POST /themes/:id/sources`  
* `PATCH /sources/:id`  
* `POST /themes/:id/source-discovery`

## **Signal endpoints**

* `GET /themes/:id/signals`  
* `GET /signals/:id`  
* `PATCH /signals/:id`  
* `POST /signals/:id/feedback`

## **Scenario endpoints**

* `GET /themes/:id/scenarios`  
* `POST /themes/:id/scenarios`  
* `PATCH /scenarios/:id`

## **Brief endpoints**

* `POST /themes/:id/briefs/generate`  
* `GET /themes/:id/briefs/latest`  
* `GET /briefs/:id`

## **Run endpoints**

* `POST /themes/:id/runs/trigger`  
* `GET /themes/:id/runs`  
* `GET /runs/:id`

---

# **7\. Job architecture**

## **Scheduled jobs**

### **Daily crawl job**

For each active theme:

1. refresh source set  
2. crawl active sources  
3. store raw docs  
4. run dedupe  
5. run extraction/classification  
6. update signals  
7. update scenarios  
8. refresh dashboard materializations

### **Weekly brief job**

1. collect last 7-day deltas  
2. select top changes  
3. assemble structured brief  
4. call LLM for prose sections  
5. persist brief  
6. notify UI

### **On-demand brief job**

Same as weekly but user-triggered.

---

# **8\. LLM governance layer**

Since you want explicit discipline around model usage, include a dedicated policy layer.

## **Principle**

Every pipeline stage should declare:

* deterministic path available?  
* model required?  
* fallback behavior?  
* local-model eligible?

## **Example decision table**

### **Use deterministic code**

* report formatting  
* score calculations  
* scenario thresholds  
* dedupe by hash  
* cron orchestration  
* source activation rules

### **Use LLM**

* extract concise signal from messy article  
* summarize cluster meaning  
* draft brief prose  
* explain possible scenario implications

### **Optional local LLM candidates**

* first-pass summarization  
* thematic relevance triage  
* internal sensitive-data workflows

This should be in the engineering spec, not just the PRD.

---

# **9\. Local LLM architecture option**

If you want local-model support, design an abstraction:

## **Model gateway**

A single service interface like:

* `summarize_document()`  
* `extract_signal()`  
* `draft_brief_section()`  
* `classify_ambiguous_signal()`

Then plug providers behind it:

* OpenAI API  
* local Ollama  
* vLLM-hosted model  
* fallback provider

This avoids hard-coding one provider into the app.

## **Routing idea**

* high-quality final brief generation → remote model  
* cheap bulk triage → local model  
* sensitive internal processing → local model

That is a strong long-term design.

---

# **10\. Security and compliance basics**

Even for MVP, include:

* source allowlist / crawl controls  
* respect robots / rate limits where applicable  
* audit log for generated briefs and user edits  
* traceability from brief section back to source signals  
* provenance metadata for every signal  
* model usage logs

That last point is especially important for strategist trust.

---

# **11\. Observability**

Track:

* crawl success rate  
* extraction success rate  
* duplicate rate  
* relevant-signal yield  
* scenario update frequency  
* brief generation latency  
* user override rate  
* model call volume and cost

This will tell you very quickly where the product is working or failing.

---

# **12\. Recommended MVP implementation order**

## **Phase 1**

* frontend setup screens  
* API CRUD  
* source management  
* manual signal ingest  
* deterministic brief structure  
* LLM-written brief content

## **Phase 2**

* scheduled crawling  
* raw document storage  
* filtering/ranking pipeline  
* dashboard

## **Phase 3**

* scenario engine  
* signal-scenario mapping  
* confidence/momentum updates

## **Phase 4**

* source discovery automation  
* local LLM routing  
* clustering improvements  
* explainability layer

---

# **13\. Architecture principle in one sentence**

Build the system so that deterministic software handles structure, scoring, orchestration, and formatting; use LLMs only for genuinely semantic tasks like synthesis, interpretation, and prose generation.