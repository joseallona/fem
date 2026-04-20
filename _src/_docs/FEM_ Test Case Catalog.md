# **Forecasting Monitor Test Case Catalog**

## **1\. Purpose**

This document defines concrete test cases to validate that the system behaves correctly end-to-end.

Each test case includes:

* setup  
* input  
* expected behavior  
* expected output

This is used for:

* QA  
* AI-assisted implementation  
* regression testing

---

## **2\. Test Case Structure**

Each test case includes:

* ID  
* Description  
* Setup  
* Input  
* Expected System Behavior  
* Expected Output

---

## **3\. Core Test Cases**

### **TC-001: Basic Theme Setup**

**Description:** Create a theme and ensure it is valid for monitoring.

**Setup:**

* No existing themes

**Input:**

* Theme: Longevity  
* Focal question: "How will longevity impact labor markets in 15 years?"  
* Time horizon: 15 years

**Expected Behavior:**

* Theme is created  
* Theme is marked valid for monitoring

**Expected Output:**

* Theme stored with all required fields

---

### **TC-002: Source Discovery**

**Description:** System generates relevant sources for a theme.

**Setup:**

* Theme: Longevity

**Input:**

* Trigger source discovery

**Expected Behavior:**

* System identifies primary \+ adjacent domains  
* Generates list of sources

**Expected Output:**

* Sources include biotech, healthcare, policy, etc.

---

### **TC-003: Manual Source Addition**

**Description:** User adds a custom source.

**Input:**

* URL: [https://example-health-news.com](https://example-health-news.com/)

**Expected Behavior:**

* Source added  
* Not auto-approved unless configured

**Expected Output:**

* Source appears in source list

---

### **TC-004: Crawling and Document Ingestion**

**Description:** System crawls sources and stores documents.

**Setup:**

* Approved sources exist

**Input:**

* Trigger monitoring run

**Expected Behavior:**

* Documents fetched and stored

**Expected Output:**

* Raw documents saved with metadata

---

### **TC-005: Deduplication**

**Description:** Duplicate articles are removed.

**Input:**

* Two identical articles from different sources

**Expected Behavior:**

* One is removed or merged

**Expected Output:**

* Only one document retained

---

### **TC-006: Relevance Filtering**

**Description:** Irrelevant documents are filtered out.

**Input:**

* Article unrelated to theme

**Expected Behavior:**

* Relevance score below threshold

**Expected Output:**

* Document discarded

---

### **TC-007: Signal Extraction**

**Description:** Relevant document produces signal.

**Input:**

* Article about new longevity drug breakthrough

**Expected Behavior:**

* Signal extracted

**Expected Output:**

* Signal with summary and classification

---

### **TC-008: Signal Classification**

**Description:** Signal is categorized correctly.

**Input:**

* Extracted signal

**Expected Behavior:**

* Assigned STEEP: Technological  
* Type: Weak signal or trend

**Expected Output:**

* Classified signal stored

---

### **TC-009: Signal Ranking**

**Description:** Signals are ranked by importance.

**Input:**

* Multiple signals

**Expected Behavior:**

* Higher-impact signals ranked higher

**Expected Output:**

* Sorted signal list

---

### **TC-010: Scenario Mapping**

**Description:** Signal mapped to scenario.

**Setup:**

* Scenario exists

**Input:**

* Signal relevant to scenario

**Expected Behavior:**

* Relationship created (supports/weakens)

**Expected Output:**

* Mapping stored

---

### **TC-011: Scenario Update**

**Description:** Scenario confidence and momentum update.

**Input:**

* New supporting signals

**Expected Behavior:**

* Confidence increases  
* Momentum becomes increasing

**Expected Output:**

* Updated scenario state

---

### **TC-012: Change Detection**

**Description:** System detects new developments.

**Input:**

* New signals compared to previous run

**Expected Behavior:**

* New signals flagged

**Expected Output:**

* Change set generated

---

### **TC-013: Brief Generation**

**Description:** System generates structured brief.

**Input:**

* Signals \+ scenarios

**Expected Behavior:**

* Sections created deterministically  
* Content generated where needed

**Expected Output:**

* Complete brief

---

### **TC-014: Empty Signal Case**

**Description:** No relevant signals found.

**Input:**

* Monitoring run with no signals

**Expected Behavior:**

* No hallucination

**Expected Output:**

* Brief states limited change

---

### **TC-015: LLM Failure Handling**

**Description:** LLM fails during brief generation.

**Input:**

* Simulated LLM failure

**Expected Behavior:**

* Partial fallback output

**Expected Output:**

* Structured brief without full prose

---

## **4\. Edge Case Tests**

### **TC-016: Conflicting Signals**

* Signals both support and weaken scenario  
* Expect net effect calculation

### **TC-017: Low Data Density**

* Few signals available  
* Expect reduced confidence and explicit messaging

### **TC-018: Duplicate Signals Across Runs**

* Same signal appears again  
* Expect merge or update, not duplication

---

## **5\. 2x2 Matrix Construction Tests**

### **TC-019: Successful Matrix Rebuild**

**Description:** Full happy-path matrix construction produces two axes and four scenarios.

**Setup:**

* Active theme with ≥ 10 signals tagged to each of at least two driving forces  
* Both driving forces have `opposition_score ≥ 0.6`  
* No axes locked

**Input:**

* User triggers matrix rebuild

**Expected Behavior:**

* LLM clusters signals into driving forces and tags pole directions  
* System scores each force and selects the highest-scoring independent pair  
* LLM drafts pole labels and scenario names/descriptions  
* Four quadrant scenarios are created and linked to the two axes

**Expected Output:**

* Two `CriticalUncertainty` records with `axis_rank = 1` and `axis_rank = 2`  
* Four `Scenario` records with `matrix_generated = true` and distinct `quadrant_id` values  
* Each scenario has pole labels, assumptions, and seeded signal-to-scenario mappings

---

### **TC-020: Independent Pair Preferred Over Top-Two Scorers**

**Description:** Pair selection favors independence over raw axis scores.

**Setup:**

* Three driving forces: A (axis_score 0.9), B (axis_score 0.85), C (axis_score 0.7)  
* A and B are highly correlated (`signal_overlap = 0.8`); A and C are independent (`signal_overlap = 0.1`)

**Input:**

* Trigger matrix rebuild

**Expected Behavior:**

* `pair_score(A, B) = harmonic_mean(0.9, 0.85) * (1 - 0.8) = low`  
* `pair_score(A, C) = harmonic_mean(0.9, 0.7) * (1 - 0.1) = higher`  
* A and C selected as the axis pair despite B having a higher individual score than C

**Expected Output:**

* Axis 1 = A, Axis 2 = C  
* B not selected

---

### **TC-021: Rebuild Blocked by Signal Gate**

**Description:** Matrix rebuild fails when unlocked axis candidate has too few signals.

**Setup:**

* Two candidate driving forces, each with 8 signals  
* Signal gate threshold = 10  
* No axes locked

**Input:**

* Trigger matrix rebuild

**Expected Behavior:**

* No candidate driving force meets the gate threshold  
* Rebuild fails gracefully

**Expected Output:**

* Error message indicating insufficient signal evidence  
* No scenarios created or modified

---

### **TC-022: Locked Axis Bypasses Gate**

**Description:** A locked axis is selected even when below the signal gate; the unlocked axis still must meet the gate.

**Setup:**

* Driving force A locked, 5 signals (below gate of 10)  
* Driving force B not locked, 12 signals (above gate)  
* Signal gate threshold = 10

**Input:**

* Trigger matrix rebuild

**Expected Behavior:**

* A is selected as Axis 1 (locked, gate bypassed)  
* B is evaluated normally and meets gate; selected as Axis 2  
* Rebuild proceeds

**Expected Output:**

* Matrix generated with A and B as axes  
* No gate error for A

---

### **TC-023: Low Opposition Score Excludes Driving Force**

**Description:** A driving force with poles that are not genuinely opposite is excluded from axis candidacy.

**Setup:**

* Driving force with 15 signals  
* 6 signals tagged as both `high` and `low` simultaneously (`pole_overlap = 6`)  
* `opposition_score = 1 - (6/15) = 0.6` — at threshold, not below  
* Second force with `opposition_score = 0.55` — below threshold

**Input:**

* Trigger matrix rebuild

**Expected Behavior:**

* Force with `opposition_score = 0.55` is flagged as poorly differentiated and excluded  
* Force at exactly 0.6 remains eligible (threshold is exclusive lower bound)

**Expected Output:**

* Ineligible force absent from pair selection candidates  
* System selects next best eligible pair

---

### **TC-024: One Axis Locked — Other Axis Rebuilt**

**Description:** When one axis is locked, pair selection runs only for the unlocked slot against the locked axis.

**Setup:**

* Axis 1 locked to driving force A  
* Driving forces B (axis_score 0.8, independent of A) and C (axis_score 0.9, correlated with A) both eligible

**Input:**

* Trigger matrix rebuild

**Expected Behavior:**

* A is fixed as Axis 1  
* System evaluates `pair_score(A, B)` and `pair_score(A, C)`  
* B selected because its independence from A produces a higher pair_score despite lower individual score

**Expected Output:**

* Axis 1 = A (locked), Axis 2 = B

---

### **TC-025: Both Axes Locked — Pair Selection Skipped**

**Description:** When both axes are locked, the system uses them directly without scoring.

**Setup:**

* Axis 1 locked to driving force A  
* Axis 2 locked to driving force B  
* Driving force C has a higher axis_score than B

**Input:**

* Trigger matrix rebuild

**Expected Behavior:**

* No pair selection logic runs  
* A and B used as axes regardless of C's higher score

**Expected Output:**

* Axis 1 = A, Axis 2 = B  
* Four scenarios generated using A and B poles

---

### **TC-026: Degenerate Quadrant Warning**

**Description:** A quadrant with insufficient signal coverage is flagged but still gets a scenario.

**Setup:**

* Axis 1 high pole: 12 signals; Axis 1 low pole: 11 signals  
* Axis 2 high pole: 10 signals; Axis 2 low pole: 0 signals  
* Signal gate = 10; floor(10 / 4) = 2  
* Quadrant (Axis 1 high, Axis 2 low): 0 supporting signals → degenerate

**Input:**

* Trigger matrix rebuild

**Expected Behavior:**

* Three quadrants generate normally  
* Degenerate quadrant is flagged with `quadrant_viable = false`  
* Warning surfaced on that quadrant in the UI  
* LLM still drafts a scenario for the degenerate quadrant

**Expected Output:**

* Four scenarios created  
* One has `quadrant_viable = false` and a visible warning

---

### **TC-027: All Quadrants Degenerate**

**Description:** Rebuild completes but surfaces a prominent warning when no quadrant has viable signal coverage.

**Setup:**

* All four quadrant pole combinations have zero supporting signals

**Input:**

* Trigger matrix rebuild

**Expected Behavior:**

* Rebuild completes  
* All four scenarios created with `quadrant_viable = false`  
* System surfaces a prominent warning that the matrix has low evidential grounding

**Expected Output:**

* Four scenarios present  
* Global matrix warning displayed

---

### **TC-028: Orphaned Scenarios Persist After Rebuild**

**Description:** Scenarios from a prior matrix build are not deleted when a new rebuild changes the axes.

**Setup:**

* Prior rebuild produced four scenarios linked to axes A and B  
* New rebuild selects axes C and D

**Input:**

* Trigger matrix rebuild

**Expected Behavior:**

* Four new scenarios generated for axes C and D  
* Prior four scenarios remain in the database, not linked to the new axes  
* No automated archiving or deletion occurs

**Expected Output:**

* Eight total scenarios visible  
* Prior four have no `axis1_id` / `axis2_id` matching the new matrix axes

---

### **TC-029: Rebuild Fails — Fewer Than Two Eligible Candidates**

**Description:** System fails gracefully when signal evidence is insufficient to form any axis pair.

**Setup:**

* Only one driving force meets the signal gate and opposition threshold

**Input:**

* Trigger matrix rebuild

**Expected Behavior:**

* System cannot form a pair from one eligible candidate  
* Rebuild fails with a descriptive message

**Expected Output:**

* Error: "Insufficient eligible driving forces to construct a matrix. At least two are required."  
* No scenarios created or modified

---

### **TC-030: LLM Pole Label Generation Fails**

**Description:** System stores placeholder pole labels and prompts the user to author them when LLM fails.

**Setup:**

* Axes selected successfully  
* LLM call for pole label drafting returns an error

**Input:**

* Trigger matrix rebuild

**Expected Behavior:**

* Rebuild does not abort  
* Placeholder labels stored (e.g., "Pole A — unlabeled", "Pole B — unlabeled")  
* User is shown a prompt to enter pole labels manually before scenario drafting proceeds  
* Scenario drafting is deferred until labels are provided

**Expected Output:**

* Axes created with placeholder labels  
* Scenario drafting blocked pending user input

---

### **TC-031: Signal Gate Setting Updated**

**Description:** Changing the signal gate threshold in frontend settings takes effect on the next rebuild.

**Setup:**

* Signal gate currently set to 10  
* Driving force with 8 signals (previously ineligible)

**Input:**

* User changes signal gate to 7 in settings  
* Trigger matrix rebuild

**Expected Behavior:**

* Driving force with 8 signals now meets the gate  
* It is included in axis candidacy

**Expected Output:**

* Driving force with 8 signals participates in pair selection

---

### **TC-032: Opposition Threshold Setting Updated**

**Description:** Changing the opposition threshold in frontend settings takes effect on the next rebuild.

**Setup:**

* Opposition threshold currently 0.6  
* Driving force with `opposition_score = 0.55` (previously excluded)

**Input:**

* User changes opposition threshold to 0.5 in settings  
* Trigger matrix rebuild

**Expected Behavior:**

* Driving force with `opposition_score = 0.55` now meets the threshold  
* It is included in axis candidacy

**Expected Output:**

* Previously excluded driving force participates in pair selection

---

## **6\. Matrix Edge Case Tests**

### **TC-033: Tiebreaker on Equal Pair Score**

* Two axis pairs have identical `pair_score`  
* Expect the pair with higher combined signal count to be selected

### **TC-034: Pole Overlap Lowers Opposition Score**

* Signal tagged as both `high` and `low` for the same driving force  
* Expect `opposition_score` to decrease proportionally  
* Expect force to be excluded if score falls below threshold

### **TC-035: Locked Axis Below Signal Gate — Other Axis Cannot Meet Gate**

* Locked axis has 3 signals; only remaining candidate also has 3 signals (below gate of 10)  
* Expect rebuild to fail — locked axis proceeds but unlocked axis fails gate check  
* Expect descriptive error message

---

## **7\. Validation Criteria**

System passes if:

* outputs match expected behavior  
* no hallucinated content  
* decisions are explainable  
* pipeline completes successfully

---

## **8\. Future Test Expansion**

* multi-theme tests  
* scaling tests  
* user feedback learning tests  
* local LLM substitution tests  
* matrix rebuild performance tests with large signal sets  
* axis re-selection stability tests across sequential rebuilds

