# **Product Requirements Document (PRD)**

## **1\. Product Summary**

**Working Title:** Forecasting Engine Monitor (FEM)

**One-line concept:**  
A strategist-facing application that continuously scans the world for signals within a thematic area and produces structured strategic intelligence through dashboards and briefs.

---

## **2\. Product Positioning**

### **2.1 What this product is**

A **strategic portfolio monitor \+ foresight engine**, not a project tracker.

It enables:

* continuous sensing of signals  
* structured futures analysis  
* scenario monitoring  
* strategic synthesis

---

### **2.2 Core value proposition**

Instead of manually scanning and synthesizing information, the system:

* discovers relevant sources  
* extracts signals  
* interprets changes  
* updates scenarios  
* produces strategic briefs

---

### **2.3 Product thesis**

A strategist should not manually rescan the world every time.

The product becomes:

a **continuous sensing \+ interpretation layer for foresight**

---

## **3\. Problem Statement**

* Forecasting work is fragmented  
* Signals are scattered across sources  
* Scenario updates are manual and infrequent  
* Strategic synthesis is time-consuming

Result:  
👉 Too much time gathering, not enough time thinking

---

## **4\. Core Product Model**

### **Core entities:**

* **Theme** → monitoring lens  
* **Signals** → live evidence  
* **Scenarios** → structured futures  
* **Projects** → strategic containers

---

## **5\. Core Workflow**

### **Setup Loop (User)**

1. Define focal question \+ time horizon  
2. Define theme  
3. Configure sources (manual \+ system suggested)

---

### **Monitoring Loop (System)**

Daily cron job:

1. Scan sources (web crawling)  
2. Extract signals  
3. Filter \+ rank  
4. Classify (STEEP, weak signals, etc.)  
5. Interpret patterns  
6. Map to scenarios  
7. Update scenario confidence \+ momentum  
8. Detect changes

---

### **Output Loop**

Weekly \+ on-demand:

* Generate **Strategic Brief**  
* Update dashboard  
* Highlight changes

---

## **6\. Strategic Brief (Core Output)**

Structure:

1. Key developments  
2. What’s changing  
3. Why it matters  
4. Implications  
5. Recommended actions

---

## **7\. MVP Definition**

### **7.1 User Promise**

User defines a theme → system monitors → outputs intelligence.

---

### **7.2 MVP Features**

* Project creation  
* Theme assignment  
* Focal question \+ time horizon  
* **System-discovered sources**  
* **Manual source management**  
* Daily crawling \+ ingestion  
* Signal extraction \+ classification  
* Scenario tracking (confidence \+ momentum)  
* Dashboard  
* Weekly \+ on-demand brief generation

---

### **7.3 Non-goals (MVP)**

* Full automation of scenarios  
* Deep collaboration tools  
* Predictive modeling  
* Multi-theme portfolio optimization

---

## **8\. Data Model**

### **Project**

* name, owner, themes

### **Theme**

* primary subject  
* related subjects  
* focal question  
* time horizon

### **Source**

* system-suggested or user-added  
* relevance \+ trust score  
* crawl frequency

### **Signal**

* content, source  
* STEEP classification  
* type (trend / weak signal / wildcard)  
* horizon (H1/H2/H3)  
* importance \+ novelty

### **Scenario**

* narrative  
* linked uncertainties  
* **confidence (low/medium/high)**  
* **momentum (↑ / ↓ / \~)**

### **Monitoring Run**

* crawl execution log

---

## **9\. Core System Pipeline**

Daily cron:

Sources → Signals → Filter → Classify → Interpret → Map to Scenarios → Detect Change → Generate Brief → Feedback Loop

---

## **10\. Source Discovery Logic**

System should:

* identify primary subject  
* infer adjacent themes  
* discover relevant sources  
* rank sources  
* suggest to user

Example (Longevity):

* biotech  
* healthcare  
* insurance  
* labor  
* wellness  
* regulation

---

## **11\. Front-End Scope**

### **1\. Project Setup**

* create project  
* assign themes  
* define framing

---

### **2\. Source Management**

* view suggested sources  
* add manual sources  
* activate / pause sources

---

### **3\. Theme Dashboard (Main Screen)**

* what changed  
* key signals  
* signal trends  
* scenario momentum  
* access to brief

---

### **4\. Signal Explorer**

* browse signals  
* light curation  
* deep analysis mode

---

### **5\. Strategic Brief View**

* generated output  
* editable  
* regeneratable

---

## **12\. Scenario Logic**

Each signal:

* supports / weakens scenarios  
* updates:  
  * **confidence**  
  * **momentum**

⚠️ No explicit probabilities (avoid false precision)

---

## **13\. LLM Usage Principles (IMPORTANT)**

### **Guiding Rule:**

Use LLMs only when no simpler deterministic method exists.

---

### **Use LLMs for:**

* signal extraction  
* summarization  
* interpretation  
* brief generation

---

### **Do NOT use LLMs for:**

* formatting reports  
* UI logic  
* structured transformations  
* deterministic workflows

---

### **Architecture principle:**

* **LLMs \= intelligence layer**  
* **Traditional code \= structure \+ control**

---

### **Additional recommendation:**

* Consider **local LLM deployment** for:  
  * privacy  
  * cost control  
  * performance

---

## **14\. Build Plan**

### **Phase 1 — Setup \+ Manual Signals**

* project \+ theme creation  
* manual sources  
* basic signal extraction  
* basic brief generation

---

### **Phase 2 — Automated Sensing**

* cron crawling  
* ingestion pipeline  
* filtering \+ ranking  
* dashboard

---

### **Phase 3 — Scenario Engine**

* scenario setup  
* signal → scenario mapping  
* confidence \+ momentum tracking

---

## **15\. Core Product Principle**

Combine **system-led discovery** with **user-led control**

* system finds signals \+ sources  
* user shapes interpretation \+ scope

---

# **🔥 Final Product Definition**

A **single-theme foresight engine** that continuously scans the world, interprets signals, updates scenarios, and generates strategic intelligence briefs.

---

