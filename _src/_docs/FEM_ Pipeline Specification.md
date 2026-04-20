# **Forecasting Monitor Pipeline Specification**

## **1\. Purpose**

This document defines the **end-to-end execution pipeline** of the Forecasting Monitor system.

It specifies:

* ordered processing stages  
* inputs and outputs per stage  
* deterministic vs LLM responsibilities  
* failure handling and retries  
* data persistence points

This document is the operational blueprint for the daily cron job and on-demand runs.

---

## **2\. Pipeline Overview**

The system executes the following pipeline for each active theme:

Source Discovery → Source Selection → Crawl → Raw Document Store → Deduplication → Relevance Filtering → Signal Extraction → Classification → Scoring & Ranking → Scenario Mapping → Scenario Update → Change Detection → Brief Assembly → Brief Generation

Each stage must:

* be independently testable  
* log inputs and outputs  
* fail gracefully when possible

---

## **3\. Execution Modes**

### **3.1 Scheduled Run (Daily)**

* triggered by cron  
* runs full pipeline except brief generation (optional)

### **3.2 Weekly Run**

* includes full pipeline \+ automatic brief generation

### **3.3 On-Demand Run**

* user-triggered  
* may skip crawl if recent data exists  
* always allows brief generation

---

## **4\. Stage-by-Stage Specification**

---

## **4.1 Stage 1: Source Discovery**

### **Input**

* theme  
* primary subject  
* related subjects

### **Process**

* generate candidate sources  
* score sources deterministically

### **Output**

* candidate source list

### **LLM usage**

* OPTIONAL (only for subject expansion if needed)

### **Failure handling**

* if discovery fails → fallback to existing sources

---

## **4.2 Stage 2: Source Selection**

### **Input**

* candidate sources  
* user-approved sources

### **Process**

* filter to active approved sources

### **Output**

* crawl-ready source list

### **Rules**

* only approved sources proceed

---

## **4.3 Stage 3: Crawling**

### **Input**

* source list

### **Process**

* fetch latest content  
* normalize structure

### **Output**

* raw documents

### **Persistence**

* store documents with metadata

### **Failure handling**

* per-source retry  
* continue on partial failure

---

## **4.4 Stage 4: Raw Document Storage**

### **Input**

* crawled documents

### **Process**

* store text, metadata, hashes

### **Output**

* stored documents with IDs

---

## **4.5 Stage 5: Deduplication**

### **Input**

* raw documents

### **Process**

* hash match  
* title similarity

### **Output**

* unique document set

### **Rules**

* duplicates removed or merged

---

## **4.6 Stage 6: Relevance Filtering**

### **Input**

* documents

### **Process**

* compute relevance score  
* filter by thresholds

### **Output**

* relevant documents

### **LLM usage**

* only for borderline cases

---

## **4.7 Stage 7: Signal Extraction**

### **Input**

* relevant documents

### **Process**

* extract candidate signals  
* summarize content

### **Output**

* candidate signals

### **LLM usage**

* YES (semantic extraction)

---

## **4.8 Stage 8: Classification**

### **Input**

* signals

### **Process**

* assign:  
  * STEEP  
  * type  
  * horizon

### **Output**

* classified signals

### **LLM usage**

* optional for ambiguous classification

---

## **4.9 Stage 9: Scoring & Ranking**

### **Input**

* classified signals

### **Process**

* compute signal scores  
* rank signals

### **Output**

* ranked signal set

### **LLM usage**

* NOT allowed

---

## **4.10 Stage 10: Scenario Mapping**

### **Input**

* signals  
* scenarios

### **Process**

* determine relationship:  
  * supports  
  * weakens

### **Output**

* signal-scenario mappings

### **LLM usage**

* optional suggestion only

---

## **4.11 Stage 11: Scenario Update**

### **Input**

* mappings

### **Process**

* update:  
  * support score  
  * contradiction score  
  * momentum

### **Output**

* updated scenario state

### **LLM usage**

* NOT allowed

---

## **4.12 Stage 12: Change Detection**

### **Input**

* previous state  
* current state

### **Process**

* detect:  
  * new signals  
  * score changes  
  * scenario changes

### **Output**

* change set

---

## **4.13 Stage 13: Brief Assembly (Deterministic)**

### **Input**

* signals  
* change set  
* scenarios

### **Process**

* select content  
* structure sections

### **Output**

* structured brief payload

### **LLM usage**

* NOT allowed

---

## **4.14 Stage 14: Brief Generation (LLM)**

### **Input**

* structured payload

### **Process**

* generate narrative sections

### **Output**

* final brief text

### **LLM usage**

* YES (controlled)

---

## **5\. Data Persistence Points**

The system must persist at:

* raw documents  
* signals  
* scenario state  
* monitoring runs  
* brief outputs

---

## **6\. Error Handling Strategy**

### **Principles**

* fail per stage, not globally  
* retry where safe  
* log all failures

### **Examples**

* crawl failure → retry source  
* LLM failure → fallback partial output  
* classification failure → mark for review

---

## **7\. Retry Logic**

* crawl retries: exponential backoff  
* LLM retries: limited attempts  
* pipeline retries: stage-level

---

## **8\. Observability**

Track per run:

* documents fetched  
* signals created  
* duplicates removed  
* relevance filter rate  
* scenario changes  
* LLM usage and latency

---

## **9\. LLM Usage Enforcement**

Each stage must declare:

* allowed: yes/no  
* purpose

LLM calls must be:

* logged  
* bounded  
* replaceable (local model option)

---

## **10\. Concurrency Rules**

* one active run per theme  
* additional runs queued or rejected

---

## **11\. Performance Constraints**

* daily run must complete within defined time window  
* pipeline must support incremental scaling

---

## **12\. Future Extensions**

* streaming ingestion  
* real-time signals  
* adaptive pipelines  
* distributed crawling

