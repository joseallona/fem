# **Forecasting Monitor Functional Specification**

## **1\. Purpose**

This document translates the product vision and domain model into precise system behavior.

It defines what the system must do, what inputs it accepts, what outputs it produces, what rules govern behavior, and how edge cases should be handled.

This document is intended to help product, engineering, and AI-assisted implementation align on expected functionality.

This is **not** a UI specification and **not** a low-level technical design. It is a behavior specification.

---

## **2\. System Scope**

The Forecasting Monitor MVP is a **single-theme foresight engine** that:

* lets a user create a project and assign one or more themes  
* allows setup of a theme workspace with focal question, time horizon, and scope  
* discovers and manages web sources relevant to the theme  
* crawls sources on a recurring schedule  
* extracts and ranks signals  
* maps relevant signals to scenarios  
* updates scenario confidence and momentum  
* generates a structured strategic brief weekly and on demand

The MVP emphasizes:

* daily sensing  
* system-led source discovery  
* user-led correction and curation  
* disciplined LLM usage only where deterministic methods are insufficient

---

## **3\. Functional Modules**

The MVP is divided into eight functional modules:

1. Project Management  
2. Theme Workspace Setup  
3. Source Discovery and Source Management  
4. Monitoring Run Orchestration  
5. Signal Processing  
6. Scenario Management and Scenario Updating  
7. Strategic Brief Generation  
8. User Review and Feedback

---

## **4\. Module 1: Project Management**

## **4.1 Objective**

Allow the user to create and manage a project that serves as an organizational container for foresight monitoring work.

## **4.2 Functional requirements**

### **FR-1 Create project**

The system shall allow the user to create a project with at least:

* project name  
* description (optional)  
* owner (optional in MVP)  
* status (optional default)

**Output:**

* project record created

### **FR-2 Edit project**

The system shall allow the user to update project metadata.

### **FR-3 Assign themes to project**

The system shall allow a project to be linked to one or more themes.

### **FR-4 View project-theme relationships**

The system shall allow retrieval of themes associated with a project.

## **4.3 Business rules**

* A project may exist before any theme is attached  
* A theme may exist before being linked to a project  
* In MVP, one active theme workspace is used operationally at a time even if multiple themes are structurally linked to projects

## **4.4 Edge cases**

* If a project has no themes, the system shall allow save but shall not allow monitoring runs from the project alone  
* If a theme linked to a project is archived, the relationship may remain historical but shall not be used as an active monitoring target

---

## **5\. Module 2: Theme Workspace Setup**

## **5.1 Objective**

Allow the user to define the strategic frame that governs relevance, monitoring, and synthesis.

## **5.2 Functional requirements**

### **FR-5 Create theme workspace**

The system shall allow the user to create a theme workspace with:

* theme name  
* primary subject  
* focal question  
* time horizon  
* scope and boundaries  
* stakeholders (optional in MVP)

### **FR-6 Edit theme workspace**

The system shall allow the user to edit theme metadata.

### **FR-7 Store related subjects**

The system shall support storage of related or adjacent subjects associated with a theme.

### **FR-8 Activate theme workspace**

The system shall allow one theme workspace to be marked active for monitoring and synthesis.

### **FR-9 Archive theme workspace**

The system shall allow a theme workspace to be archived, preventing future monitoring runs while preserving history.

## **5.3 Business rules**

* Theme name is required  
* Focal question is required for a production-quality workspace, but MVP may allow draft save without it  
* Time horizon is required before scenario monitoring or brief generation can run  
* Active theme state is required for automated monitoring

## **5.4 Validation rules**

* Time horizon must be a positive duration or normalized future window  
* Focal question must be non-empty before monitoring is fully enabled  
* Primary subject must not be blank if automated source discovery is enabled

## **5.5 Edge cases**

* If stakeholders are absent, the system shall still operate, but implications may be less tailored  
* If boundaries are broad or missing, relevance filtering may become noisier; system may show a warning but should not block

---

## **6\. Module 3: Source Discovery and Source Management**

## **6.1 Objective**

Build and maintain the set of web sources the system uses for monitoring.

## **6.2 Functional requirements**

### **FR-10 Suggest sources from theme context**

The system shall generate candidate sources based on:

* theme name  
* primary subject  
* related subjects  
* focal question  
* previously approved sources if applicable

### **FR-11 Score candidate sources**

The system shall score candidate sources using deterministic factors where possible, such as:

* topical relevance  
* freshness or update frequency  
* source type fit  
* domain trust or authority priors  
* expected signal density

### **FR-12 Present suggested sources**

The system shall store and expose a list of suggested sources for user review.

### **FR-13 Add manual source**

The system shall allow the user to manually add a source the cron should crawl.

### **FR-14 Approve source**

The system shall allow a suggested or manual source to be approved for active crawling.

### **FR-15 Pause source**

The system shall allow an active source to be paused.

### **FR-16 Remove or block source**

The system shall allow a source to be removed from active crawling or blocked from future suggestion/use.

### **FR-17 Edit source metadata**

The system shall allow updating crawl frequency, source type, and status.

### **FR-18 Refresh source suggestions**

The system shall allow on-demand regeneration of candidate sources for a theme.

## **6.3 Business rules**

* Only approved active sources shall be included in scheduled crawling  
* Manual sources shall not be auto-approved unless explicitly configured  
* Blocked sources shall not be reintroduced by automated suggestion without explicit override logic  
* Source discovery should prefer deterministic ranking before LLM assistance

## **6.4 Validation rules**

* Manual source requires a valid domain or URL  
* Duplicate sources should be merged or prevented at save time where reasonably detectable  
* Crawl frequency must be within allowed policy range

## **6.5 Edge cases**

* If no sources are suggested, the user shall still be able to add manual sources  
* If a source repeatedly fails crawling, the system may downgrade status or flag it for review  
* If a source is relevant to multiple related subjects, it may still appear once in the theme source set

## **6.6 LLM restrictions**

The system shall not use an LLM for routine source CRUD or source state transitions.  
An LLM may be used only if needed to infer adjacent subjects or summarize why a source is relevant, and only after deterministic methods are insufficient.

---

## **7\. Module 4: Monitoring Run Orchestration**

## **7.1 Objective**

Execute the recurring sensing workflow for the active theme.

## **7.2 Functional requirements**

### **FR-19 Schedule daily monitoring run**

The system shall support a daily automated monitoring run for each active theme workspace.

### **FR-20 Allow manual monitoring run**

The system shall allow the user to manually trigger a monitoring run.

### **FR-21 Record monitoring run metadata**

Each monitoring run shall record at minimum:

* theme  
* start time  
* end time  
* status  
* sources scanned  
* documents fetched  
* signals created or updated  
* errors and warnings

### **FR-22 Run pipeline stages in order**

The system shall execute, in sequence or safely parallelized form:

* source fetch  
* raw document storage  
* deduplication  
* relevance filtering  
* signal extraction  
* classification  
* ranking  
* scenario update preparation  
* change detection

### **FR-23 Preserve auditability**

The system shall preserve enough metadata to trace outputs back to source evidence and run context.

## **7.3 Business rules**

* A monitoring run requires at least one active approved source  
* If no active approved source exists, run shall fail gracefully with actionable status  
* Runs may be retried if failures occur in non-terminal stages

## **7.4 Edge cases**

* If one source fails, other sources may still be processed unless failure is systemic  
* If a run produces no relevant signals, the run shall complete successfully with zero-signal outcome  
* If a run is manually triggered while another is active, system shall either queue, reject, or merge according to configured concurrency policy

---

## **8\. Module 5: Signal Processing**

## **8.1 Objective**

Convert raw documents into structured, ranked, relevant signals.

## **8.2 Functional requirements**

### **FR-24 Store raw documents**

The system shall store fetched documents and provenance metadata before signal determination.

### **FR-25 Deduplicate raw documents**

The system shall detect likely duplicate or substantially overlapping documents using deterministic methods first.

### **FR-26 Filter for relevance**

The system shall evaluate whether a raw document is relevant to the active theme.

### **FR-27 Extract candidate signals**

The system shall derive one or more candidate signals from relevant raw documents when meaningful evidence exists.

### **FR-28 Classify signal**

The system shall classify a signal into at least:

* signal type  
* STEEP category  
* horizon classification

### **FR-29 Score signal**

The system shall assign deterministic or hybrid scores such as:

* relevance  
* novelty  
* importance  
* source trust contribution

### **FR-30 Rank signals**

The system shall rank signals for dashboard and brief use.

### **FR-31 Store signal-document relationship**

The system shall preserve linkage from each signal to its supporting raw document(s).

### **FR-32 Detect change over time**

The system shall compare current signal state against prior runs to identify:

* new signals  
* changed signals  
* strengthened or weakened relevance  
* newly elevated importance

## **8.3 Business rules**

* Not every raw document becomes a signal  
* One raw document may produce multiple signals only when distinct developments are present  
* A signal must remain tied to evidence  
* Ranking should be governed by transparent scoring rules, not pure generative judgment

## **8.4 Validation rules**

* Signal cannot be saved without at least one supporting document reference unless manually created by explicit product rule  
* Signal type and STEEP category should come from controlled enumerations in MVP  
* If confidence in extraction is low, the system may mark a signal as needing review

## **8.5 Edge cases**

* If a document is relevant but too thin to extract a meaningful signal, it may be stored without signal creation  
* If multiple documents reflect the same signal, system may merge evidence under one signal object  
* If classification dimensions disagree or are ambiguous, signal may enter review-needed state

## **8.6 LLM restrictions**

The system may use an LLM for semantic extraction or summarization of candidate signals when deterministic methods are insufficient.  
The system shall not rely on an LLM for deterministic scoring, ranking formulas, or state transitions.

---

## **9\. Module 6: Scenario Management, Matrix Construction, and Scenario Updating**

## **9.1 Objective**

Allow scenarios to act as an organizing layer for interpreted signals and track how evidence shifts support over time. Allow the user to trigger an algorithmic 2x2 matrix construction that derives the two best critical uncertainty axes from signal evidence and generates four quadrant scenarios.

## **9.2 Functional requirements**

### **FR-33 Create scenario**

The system shall allow the user to create a scenario with:

* name  
* narrative  
* assumptions  
* linked critical uncertainties (optional in MVP if simplified)

Scenarios may also be generated by the matrix construction pipeline (FR-59). Both origins produce first-class scenario objects subject to the same editing, linking, and updating rules.

### **FR-34 Edit scenario**

The system shall allow the user to update scenario fields.

### **FR-35 Link signal to scenario**

The system shall support storing that a signal:

* supports a scenario  
* weakens a scenario  
* is neutral or unassigned

### **FR-36 Suggest signal-scenario relationship**

The system may suggest a signal-to-scenario relationship for review.

### **FR-37 Update scenario confidence**

The system shall update each scenario’s confidence level based on accumulated evidence support rules.

### **FR-38 Update scenario momentum**

The system shall update each scenario’s momentum based on recent directional evidence change.

### **FR-39 Show scenario rationale**

The system shall preserve enough evidence to explain why a scenario gained or lost support.

## **9.3 Business rules**

* Scenario confidence shall be represented as relative support, not explicit probability  
* Scenario momentum shall represent directional change over time, not static support level  
* Not every signal must affect a scenario  
* One signal may affect multiple scenarios differently

## **9.4 Validation rules**

* Scenario must belong to a theme context  
* Confidence values shall be restricted to the approved set  
* Momentum values shall be restricted to the approved set

## **9.5 Edge cases**

* If there are too few mapped signals, scenario confidence may remain unchanged  
* If new signals both support and weaken a scenario, net effect shall be determined by deterministic update rules  
* If no scenarios exist yet, the system shall still process signals and generate dashboard output, but scenario-dependent sections may be omitted or flagged as unavailable

## **9.6 LLM restrictions**

The system may use an LLM to draft explanations for signal-scenario relationships.  
The actual confidence and momentum update logic shall be implemented with deterministic software rules.

## **9.7 2x2 Matrix Construction Requirements**

### **FR-59 Trigger matrix rebuild**

The system shall allow the user to trigger a 2x2 matrix construction on demand for the active theme. The rebuild shall execute the full pipeline defined in Decision Logic Specification Section 16.

### **FR-60 Lock and unlock a critical uncertainty axis**

The system shall allow the user to lock a critical uncertainty as a fixed matrix axis. A locked axis shall always be selected regardless of its computed scores or signal gate status. The user shall be able to unlock it to return it to normal selection.

### **FR-61 Configure signal gate threshold**

The system shall expose a frontend setting for the minimum signal count required per selected axis for matrix construction to proceed. Default value: 10. The setting shall be configurable without a code change.

### **FR-62 Configure pole opposition threshold**

The system shall expose a frontend setting for the minimum `opposition_score` a driving force must reach to be eligible as an axis candidate. Default value: 0.6. The setting shall be configurable without a code change.

### **FR-63 Display degenerate quadrant warning**

When a matrix rebuild produces a quadrant with insufficient signal coverage (fewer than `floor(signal_gate / 4)` signals supporting that pole combination), the system shall display a warning on that quadrant indicating low evidence viability. The scenario shall still be generated.

### **FR-64 Display 2x2 matrix view**

The system shall provide a view that renders the four quadrant scenarios organized by their two axes and pole labels. Each quadrant shall show the scenario name, confidence, momentum, and viability status.

## **9.8 Matrix business rules**

* Matrix rebuild runs on demand only; it does not trigger automatically  
* Scenarios generated by a prior matrix rebuild that are no longer aligned to the new axes are not modified or archived; they persist as-is  
* A user may lock both axes simultaneously, in which case pair selection is bypassed entirely  
* If a locked axis has fewer signals than the signal gate, the lock is still honored; only the unlocked axis must meet the gate  
* The matrix may not be rebuilt if no driving forces are eligible after applying the signal gate and opposition threshold

## **9.9 Matrix edge cases**

* If fewer than two eligible driving force candidates exist after scoring, rebuild shall fail with a descriptive message indicating insufficient signal evidence  
* If all four quadrants are flagged as degenerate, the rebuild shall still complete but the system shall surface a prominent warning that the matrix has low evidential grounding  
* If LLM pole label generation fails, the system shall store placeholder labels and allow the user to author them manually before proceeding

---

## **10\. Module 7: Strategic Brief Generation**

## **10.1 Objective**

Generate a structured synthesis artifact for the active theme on a weekly schedule and on demand.

## **10.2 Functional requirements**

### **FR-40 Generate weekly brief**

The system shall support scheduled generation of a strategic brief for a defined reporting period.

### **FR-41 Generate on-demand brief**

The system shall allow the user to trigger generation of a brief at any time.

### **FR-42 Build deterministic brief structure**

The system shall assemble brief sections in code using a fixed structure:

* key developments  
* what’s changing  
* why it matters  
* implications  
* recommended actions

### **FR-43 Select source material for brief**

The system shall select signals, scenario shifts, and change summaries according to deterministic selection rules.

### **FR-44 Draft brief prose**

The system may generate prose content for some sections using an LLM.

### **FR-45 Preserve evidence traceability**

The brief shall retain references to underlying signals or evidence items supporting each major section.

### **FR-46 Store generated brief**

The system shall persist both the structured payload and rendered brief content.

## **10.3 Business rules**

* Brief structure must not depend on the LLM  
* If scenario data is unavailable, the brief may still be generated with scenario references omitted or reduced  
* Brief generation should succeed even if recommendations are minimal or empty in MVP

## **10.4 Validation rules**

* A brief requires a valid theme context and reporting period  
* If insufficient data exists, the system may produce a sparse brief but shall explicitly indicate low evidence density

## **10.5 Edge cases**

* If no relevant signals exist in the period, the brief shall state that change was limited rather than hallucinating content  
* If LLM prose generation fails, the system may fall back to deterministic summaries or partial brief generation

## **10.6 LLM restrictions**

The system may use an LLM for narrative synthesis only.  
Report formatting, section ordering, payload construction, and inclusion logic shall remain deterministic.

---

## **11\. Module 8: User Review and Feedback**

## **11.1 Objective**

Allow the user to correct, enrich, and validate system outputs.

## **11.2 Functional requirements**

### **FR-47 Mark signal importance or irrelevance**

The system shall allow the user to mark a signal as important, irrelevant, or otherwise adjusted in salience.

### **FR-48 Reclassify signal**

The system shall allow the user to edit:

* signal type  
* STEEP category  
* horizon

### **FR-49 Add note to signal**

The system shall allow the user to add annotations.

### **FR-50 Link or relink signal to scenario**

The system shall allow the user to confirm, remove, or change signal-scenario relationships.

### **FR-51 Edit brief content**

The system shall allow user review and modification of generated brief content.

### **FR-52 Preserve user override state**

The system shall retain user-applied overrides so that human correction has semantic authority where applicable.

## **11.3 Business rules**

* User correction should override system suggestion for that artifact where conflict exists  
* Overrides should remain auditable  
* MVP may store feedback without full online learning, but future ranking can consume this data later

## **11.4 Edge cases**

* If a user override conflicts with prior automated classification, user override wins for the visible artifact  
* If a user removes a signal-scenario relationship, system may suggest it again later only if new evidence emerges or confidence threshold is crossed, depending on policy

---

## **12\. Cross-Cutting Functional Requirements**

### **FR-53 Explainability**

The system shall preserve enough metadata to explain:

* why a source was suggested  
* why a signal was surfaced  
* why a scenario was strengthened or weakened  
* what evidence contributed to a brief section

### **FR-54 Provenance**

The system shall retain source and document provenance for every signal and brief-supporting statement where practical.

### **FR-55 Deterministic-first implementation**

For each feature, the system shall prefer deterministic logic over LLM usage when a simpler reliable method is available.

### **FR-56 Local model compatibility**

The system architecture shall support substitution of a local LLM for eligible semantic tasks without requiring large changes to product behavior.

### **FR-57 Auditability**

The system shall log monitoring runs, major state transitions, and generation events.

### **FR-58 Graceful degradation**

If an LLM-dependent step fails, the system should degrade gracefully rather than failing the entire workflow where possible.

---

## **13\. Non-Functional Constraints with Functional Impact**

### **NFR-F1 Performance-sensitive behaviors**

* Monitoring runs should complete within an acceptable operational window for the configured source set  
* Dashboard data should be retrievable without recomputing the full pipeline on every load

### **NFR-F2 Reliability-sensitive behaviors**

* Failures in one source should not invalidate the entire run by default  
* Partial outputs should be clearly marked if completeness is affected

### **NFR-F3 Trust-sensitive behaviors**

* The system shall not present fabricated certainty  
* If evidence is sparse, it should say so  
* If a recommendation is weakly supported, it should be framed accordingly

---

## **14\. Out of Scope for MVP**

The following are not required for MVP unless later explicitly added:

* full multi-theme portfolio balancing across many active workspaces  
* fully autonomous unprompted scenario generation without user trigger or signal evidence basis  
* advanced collaboration workflows  
* deep quantitative forecasting models  
* hard-probability scenario prediction  
* unrestricted autonomous crawling of the open web without source governance

---

