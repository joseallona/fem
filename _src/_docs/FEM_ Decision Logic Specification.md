# **Forecasting Monitor Decision Logic Specification**

## **1\. Purpose**

This document defines the **deterministic decision rules** that govern how the system:

* selects sources  
* filters and ranks signals  
* maps signals to scenarios  
* updates scenario confidence and momentum  
* selects content for briefs

This document is critical to ensure that the system behavior is:

* transparent  
* explainable  
* reproducible  
* not dependent on opaque LLM decisions

LLMs may assist in semantic interpretation, but **final decisions must follow deterministic rules where possible**.

---

## **2\. Design Principles**

### **2.1 Deterministic-first**

All scoring, ranking, and state transitions must be implemented using explicit rules and formulas unless impossible.

### **2.2 Explainability**

Every decision must be traceable to:

* input data  
* scoring components  
* thresholds

### **2.3 Composability**

Scores should be built from smaller components rather than monolithic judgments.

### **2.4 Bounded heuristics**

Heuristics are allowed but must be:

* documented  
* stable  
* adjustable

---

## **3\. Source Scoring Logic**

## **3.1 Objective**

Rank candidate sources for a theme.

## **3.2 Source Score Formula**

source\_score \= w1 \* topical\_relevance  
             \+ w2 \* freshness\_score  
             \+ w3 \* authority\_score  
             \+ w4 \* signal\_density\_estimate

### **Components**

**Topical relevance (0–1)**

* keyword overlap with theme \+ related subjects  
* taxonomy match

**Freshness (0–1)**

* update frequency of source

**Authority (0–1)**

* domain-level trust heuristic (predefined list or external signals)

**Signal density estimate (0–1)**

* % of documents historically producing signals

### **Rules**

* Sources above threshold T1 → suggested  
* Sources below T2 → discarded  
* Between T1 and T2 → optional suggestion

---

## **4\. Document Deduplication Logic**

## **4.1 Objective**

Remove duplicate or near-duplicate documents.

## **4.2 Rules**

Primary:

* exact content hash match → duplicate

Secondary:

* normalized title similarity \> 0.9 → duplicate  
* canonical URL match → duplicate

Optional:

* embedding similarity \> 0.95 (if implemented)

---

## **5\. Relevance Filtering Logic**

## **5.1 Objective**

Determine if a document is relevant to a theme.

## **5.2 Relevance Score**

relevance\_score \= w1 \* keyword\_match  
                \+ w2 \* entity\_overlap  
                \+ w3 \* subject\_alignment

### **Rules**

* relevance\_score \> 0.7 → relevant  
* 0.4–0.7 → borderline (optional LLM assist)  
* \< 0.4 → discard

---

## **6\. Signal Scoring Logic**

## **6.1 Objective**

Rank signals for importance and visibility.

## **6.2 Signal Score Formula**

signal\_score \= w1 \* relevance  
             \+ w2 \* novelty  
             \+ w3 \* impact  
             \+ w4 \* source\_trust  
             \+ w5 \* recency

### **Components**

**Relevance**

* inherited from document relevance

**Novelty**

* inverse similarity to existing signals

**Impact (heuristic)**

* based on keywords (policy change, funding, breakthrough, etc.)

**Source trust**

* inherited from source score

**Recency**

* time decay function (recent signals score higher)

---

## **7\. Signal Ranking Logic**

## **7.1 Rules**

* Top N signals by score → dashboard  
* Top M signals → brief inclusion  
* Weak signals flagged by:  
  * low frequency  
  * high novelty

---

## **8\. Signal-to-Scenario Mapping Logic**

## **8.1 Objective**

Determine relationship between signal and scenario.

## **8.2 Relationship Types**

* supports  
* weakens  
* neutral

## **8.3 Determination**

Initial mapping:

* keyword/assumption overlap  
* scenario tags

Optional assist:

* LLM suggests mapping

Final rule:

* must be stored as explicit relationship

---

## **9\. Scenario Update Logic**

## **9.1 Internal Scores**

Each scenario tracks:

support\_score  
contradiction\_score  
recent\_delta

## **9.2 Update Rules**

support\_score \+= sum(weighted supporting signals)  
contradiction\_score \+= sum(weighted contradicting signals)

net\_score \= support\_score \- contradiction\_score

## **9.3 Confidence Mapping**

net\_score \< T1 → low  
T1–T2 → medium  
\> T2 → high

## **9.4 Momentum Mapping**

recent\_delta \> \+X → increasing  
recent\_delta \< \-X → decreasing  
else → stable

---

## **10\. Change Detection Logic**

## **10.1 Objective**

Identify what changed since last run.

## **10.2 Changes include**

* new signals  
* signal score increase \> threshold  
* new weak signals  
* scenario momentum shift

---

## **11\. Brief Selection Logic**

## **11.1 Objective**

Select content for brief.

## **11.2 Rules**

Key developments:

* top K signals by score

What’s changing:

* signals with highest delta

Scenario section:

* scenarios with momentum change

Implications:

* derived from clustered signals

---

## **12\. LLM Usage Constraints**

LLM MAY be used for:

* summarization  
* interpretation  
* clustering suggestions

LLM MUST NOT be used for:

* scoring  
* ranking  
* threshold decisions  
* state transitions

---

## **13\. Threshold Management**

All thresholds (T1, T2, etc.) must be:

* configurable  
* logged  
* adjustable without code rewrite

---

## **14\. Explainability Requirements**

System must expose:

* signal score breakdown  
* why a signal was selected  
* why a scenario changed  
* which signals contributed

---

## **15\. Future Extensions**

* adaptive weighting based on user feedback  
* learned ranking models  
* probabilistic scenario modeling (optional future)

---

## **16\. 2x2 Matrix Construction Logic**

## **16.1 Objective**

Algorithmically construct a 2x2 scenario matrix by selecting the two most analytically productive critical uncertainty axes from candidate driving forces and generating four quadrant scenarios.

## **16.2 Trigger**

Matrix construction runs on demand only. It does not run automatically on schedule.

## **16.3 Stage 1 — Signal Clustering into Driving Forces**

An LLM reads top-ranked signals for the active theme and outputs a structured list of candidate driving forces. Each signal is tagged with one or more driving force IDs and a pole direction (`high | low | neutral`). This is the only LLM step in this stage. Output is stored as structured data before any scoring begins.

## **16.4 Stage 2 — Score Each Driving Force**

### **Signal gate**

A driving force is eligible as an axis candidate only if it has ≥ N signals tagged to it, where N is the configurable signal gate threshold (default: 10). The gate applies per selected axis post-ranking, not per candidate.

### **Impact score (0–1)**

```
impact = mean(signal_score for all signals tagged to this force)
         weighted by source_trust
```

### **Uncertainty score (0–1)**

```
support_count    = count(signals with pole_direction = high)
contradict_count = count(signals with pole_direction = low)
total            = count(all signals tagged to this force)

uncertainty = 1 - |support_count - contradict_count| / total
```

### **Pole opposition score (0–1)**

```
pole_overlap     = count(signals tagged as both high AND low simultaneously)
opposition_score = 1 - (pole_overlap / total)
```

A driving force with `opposition_score < 0.6` (configurable) is ineligible as an axis candidate. It is flagged as poorly differentiated and excluded from pair selection.

### **Axis score**

```
axis_score = w1 * impact + w2 * uncertainty
```

## **16.5 Stage 3 — Axis Pair Selection**

Axis selection evaluates all eligible candidate pairs, not just the top two individual scorers.

### **Independence score**

```
signal_overlap(A, B) = |signals tagged to A ∩ signals tagged to B|
                       / |signals tagged to A ∪ signals tagged to B|

independence(A, B) = 1 - signal_overlap(A, B)
```

### **Pair score**

```
pair_score(A, B) = harmonic_mean(axis_score_A, axis_score_B) * independence(A, B)
```

The pair with the highest `pair_score` is selected as Axis 1 and Axis 2.

### **Locked axes**

A locked axis is always included as a selected axis regardless of `axis_score`, `opposition_score`, or signal gate. If one axis is locked, only the unlocked axis goes through normal pair selection against the locked axis. If both axes are locked, pair selection is skipped entirely.

### **Tiebreaker**

If two pairs have equal `pair_score`, prefer the pair where the combined total signal count across both axes is higher.

## **16.6 Stage 4 — Pole Definition**

An LLM drafts pole labels for each selected axis using the signal clusters for each pole direction. Labels must represent mutually exclusive, opposite resolutions of the driving force. A second LLM call scores the pole pair for opposition (0–1); this score is stored for explainability but does not override the deterministic gate or block construction.

User may override pole labels at any time after generation.

## **16.7 Stage 5 — Quadrant Viability Check**

Each of the four quadrant combinations (`axis1_pole × axis2_pole`) is checked:

```
viable = count(signals supporting axis1_pole AND axis2_pole) >= floor(signal_gate / 4)
```

A quadrant with zero viable signals is flagged as degenerate. A warning is surfaced to the user. The system still drafts a scenario for all four quadrants regardless of viability status.

## **16.8 Stage 6 — Scenario Drafting**

An LLM drafts a name and description for each quadrant scenario using the pole labels and the signals associated with that quadrant combination. Assumptions are seeded from the two contributing poles. Signal-to-scenario mapping for all four scenarios is seeded from signals already tagged to the corresponding pole combination.

## **16.9 Orphaned Scenarios**

When a matrix rebuild produces new axes, previously existing scenarios generated by a prior matrix build are not modified, archived, or deleted. They persist as-is, disconnected from the new matrix. Users may manually archive or delete them.

## **16.10 LLM Usage in Matrix Construction**

| Step | LLM? | Justification |
|---|---|---|
| Cluster signals → driving forces | Yes | Semantic interpretation — allowed |
| Tag signal pole direction | Yes | Semantic classification — allowed |
| Score impact, uncertainty, opposition | No | Pure arithmetic |
| Select axis pair | No | Sort by formula |
| Draft pole labels | Yes | Summarization — allowed |
| Validate pole label opposition | Yes | Quality check — stored only |
| Draft scenario names and descriptions | Yes | Summarization — allowed |
| Assign signals to quadrants | No | Follows from pole tags |
| Update confidence and momentum | No | Existing deterministic rules (Section 9) |

