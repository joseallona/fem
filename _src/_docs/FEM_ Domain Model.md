# **Forecasting Monitor Domain Model**

## **1\. Purpose**

This document defines the core concepts, relationships, and semantic rules of the Forecasting Monitor system.

Its purpose is to remove ambiguity for product, engineering, and AI-assisted implementation by making the system vocabulary precise.

This is **not** a database schema and **not** a UI specification. It defines what the system's objects mean, how they relate, and what constraints shape their behavior.

---

## **2\. Modeling Principles**

### **2.1 System purpose**

The system is a **single-theme foresight engine** that continuously monitors external sources, detects signals, organizes them into a foresight workflow, and produces strategic intelligence outputs.

### **2.2 Core design principle**

The product is organized around three layers:

* **Strategic framing layer**: defines what the user is trying to understand  
* **Evidence layer**: collects and organizes incoming signals  
* **Interpretation layer**: connects evidence to scenarios, implications, and recommendations

### **2.3 Semantic discipline**

The same term must always mean the same thing throughout the product.

Examples:

* a **theme** is not just a tag  
* a **signal** is not just any article  
* a **scenario** is not a prediction  
* **confidence** is not probability

### **2.4 AI usage principle**

Concept definitions should not depend on LLM judgment. LLMs may help populate or summarize these entities, but the entities themselves must be defined in deterministic product language.

---

## **3\. Core Domain Concepts**

## **3.1 Project**

### **Definition**

A **project** is a strategic workstream, client engagement, internal research effort, or analysis initiative within which foresight work is performed or applied.

### **Purpose in the system**

Projects are organizational containers that help connect foresight monitoring to real strategic work.

### **What a project is not**

A project is not the main intelligence object of the system.  
It does not define the evidence structure.  
It does not replace themes or scenarios.

### **Key semantic properties**

* A project may have one or more themes  
* A project may consume signals without owning them  
* A project may reference one or more scenarios  
* A project gives context to why monitoring is being done

### **Examples**

* Longevity market scan for a client  
* Internal strategic futures work on future of work  
* Sector opportunity forecasting initiative

---

## **3.2 Theme**

### **Definition**

A **theme** is the primary monitoring lens of the system: a strategic subject area defined by the user around which sensing, interpretation, and foresight analysis are organized.

### **Purpose in the system**

The theme defines what the system should pay attention to.  
It anchors source discovery, signal relevance, scenario construction, and brief generation.

### **What a theme is not**

A theme is not a generic label.  
A theme is not merely a category attached to a project.  
A theme is not a scenario.

### **Key semantic properties**

* A theme has a primary subject  
* A theme may have related or adjacent subjects  
* A theme has a focal question  
* A theme has a time horizon  
* A theme has stakeholders, scope, and boundaries  
* A theme is the default unit of monitoring in the MVP

### **Examples**

* Longevity  
* Future of work  
* AI adoption in healthcare  
* Climate migration

### **Modeling note**

In MVP, one active theme workspace is the center of the system. Multiple themes may exist structurally, but the core operating experience is optimized for one theme at a time.

---

## **3.3 Primary Subject**

### **Definition**

The **primary subject** is the central topic or domain that best describes what the theme is fundamentally about.

### **Purpose in the system**

It serves as the starting point for:

* source discovery  
* keyword expansion  
* adjacent subject inference  
* relevance filtering

### **Example**

If the theme is **longevity**, the primary subject may be human longevity, aging, or lifespan extension depending on framing.

---

## **3.4 Related Subject / Adjacent Subject**

### **Definition**

A **related subject** or **adjacent subject** is a neighboring domain that is not identical to the theme, but may generate meaningful signals that influence the theme.

### **Purpose in the system**

This concept prevents monitoring from being too narrow.  
It enables the system to discover second-order developments that matter strategically.

### **Examples for longevity**

* biotech  
* preventive health  
* regulation  
* labor and retirement  
* insurance  
* consumer wellness  
* healthcare delivery

### **Modeling note**

Related subjects are part of the source discovery logic, not separate top-level user-facing objects in MVP.

---

## **3.5 Focal Question**

### **Definition**

The **focal question** is the primary strategic question the user wants the system to help monitor and inform.

### **Purpose in the system**

It defines what “relevant” means.  
It gives the system a decision-oriented frame.

### **What it is not**

It is not a broad topic statement.  
It is not a scenario title.

### **Example**

* How might advances in longevity reshape consumer behavior and economic participation over the next 15 years?

---

## **3.6 Time Horizon**

### **Definition**

The **time horizon** is the future time window within which the focal question is being considered.

### **Purpose in the system**

The time horizon shapes:

* which signals matter  
* how scenarios are framed  
* whether a signal is near-term or long-range  
* how three horizons classification may be interpreted

### **Examples**

* 5 years  
* 10 years  
* 20 years

---

## **3.7 Stakeholder**

### **Definition**

A **stakeholder** is a person, group, institution, or decision-making actor whose interests, exposure, or agency are relevant to the focal question.

### **Purpose in the system**

Stakeholders help interpret implications and recommendations.  
They shape what counts as material change.

### **Examples**

* employers  
* consumers  
* regulators  
* insurers  
* healthcare providers  
* investors

---

## **3.8 Scope and Boundaries**

### **Definition**

**Scope and boundaries** define what is intentionally included and excluded from the theme workspace.

### **Purpose in the system**

They constrain source discovery, relevance ranking, and synthesis.  
They reduce drift and noise.

### **Example**

A longevity theme may explicitly include healthspan economics and exclude purely philosophical debate about immortality.

---

## **3.9 Source**

### **Definition**

A **source** is a web-accessible origin from which the system retrieves content that may contain relevant evidence.

### **Purpose in the system**

Sources are the monitored inputs to the sensing pipeline.

### **Source types**

Examples may include:

* news publication  
* academic journal or repository  
* government or policy body  
* company blog or report site  
* patent database  
* specialist community publication  
* newsletter archive

### **What a source is not**

A source is not a signal.  
A source is not a document.  
A source is not inherently trustworthy just because it is monitored.

### **Key semantic properties**

* A source may be system-discovered or user-added  
* A source may be approved, paused, or blocked  
* A source has topical relevance and trust characteristics  
* A source may produce zero useful signals for long periods

---

## **3.10 Raw Document**

### **Definition**

A **raw document** is a fetched content item from a source before the system has determined whether it contains a meaningful signal.

### **Purpose in the system**

It is the basic unit of ingestion.  
It preserves provenance and supports debugging.

### **Examples**

* one article  
* one report page  
* one publication entry  
* one policy release

### **What it is not**

A raw document is not yet a signal.  
Many raw documents may be irrelevant, duplicate, or low value.

---

## **3.11 Signal**

### **Definition**

A **signal** is a structured representation of a potentially meaningful development, pattern, anomaly, or indicator extracted from one or more raw documents and determined to be relevant to the theme.

### **Purpose in the system**

Signals are the live evidence layer of the product.  
They are the core units used for monitoring change.

### **What a signal is not**

A signal is not the same as a source article.  
A signal is not any interesting fact.  
A signal is not automatically true just because it was extracted.

### **Key semantic properties**

* A signal must be relevant to the active theme  
* A signal may be linked to one or more raw documents  
* A signal may be linked to one or more scenarios  
* A signal may be reviewed, curated, tracked, or archived  
* Signals are expected to be high-volume relative to other entities  
* A signal may be tagged to one or more driving forces (critical uncertainties) with a pole direction, used by the matrix construction pipeline

### **Matrix tagging fields**

* `driving_force_ids[]` (FK → CriticalUncertainty): driving forces this signal provides evidence for  
* `pole_direction` per driving force (`high | low | neutral`): which pole direction the signal supports for each tagged driving force

### **Examples**

* increased investment activity in age-tech startups  
* a regulatory change affecting anti-aging treatments  
* emerging social acceptance of longer working lives  
* a niche scientific breakthrough suggesting future viability of a therapy

---

## **3.12 Signal Type**

### **Definition**

**Signal type** is the system’s categorization of the role a signal plays in foresight analysis.

### **Candidate types**

* trend  
* weak signal  
* wildcard  
* driver  
* indicator

### **Modeling note**

These types are not interchangeable. The same signal should not casually shift types without rationale.

---

## **3.13 Trend**

### **Definition**

A **trend** is a pattern of change that is already visible with some degree of persistence, repetition, or directional consistency.

### **Meaning in the system**

Trends represent stronger and more established developments than weak signals.

---

## **3.14 Weak Signal**

### **Definition**

A **weak signal** is an early, ambiguous, low-frequency, or edge development that may indicate a more important future shift but is not yet established.

### **Meaning in the system**

Weak signals are valuable because they may foreshadow larger changes.  
They should not be treated as strong evidence without caution.

---

## **3.15 Wildcard**

### **Definition**

A **wildcard** is a low-probability, high-impact event or development that could significantly alter the strategic landscape if it occurs.

### **Meaning in the system**

Wildcards are important for resilience and contingency thinking.  
They are not expected to be common.

---

## **3.16 Driver of Change**

### **Definition**

A **driver of change** is an underlying force that shapes the direction or conditions of future developments.

### **Meaning in the system**

Drivers are more structural than individual signals.  
A signal may provide evidence of a driver.  
A driver is often inferred from multiple signals.

### **Examples**

* demographic aging  
* falling biotech costs  
* healthcare regulation shifts  
* macroeconomic pressure on retirement systems

---

## **3.17 Indicator**

### **Definition**

An **indicator** is a measurable or observable sign that helps show whether a trend, driver, or scenario is strengthening, weakening, or materializing.

### **Meaning in the system**

Indicators are monitoring tools, not narratives.  
They help operationalize scenario tracking.

---

## **3.18 STEEP Category**

### **Definition**

A **STEEP category** is one of the five macro lenses used to organize signals and drivers:

* Social  
* Technological  
* Economic  
* Environmental  
* Political

### **Purpose in the system**

STEEP classification structures scanning and supports balanced interpretation.

### **Modeling note**

A signal may have one primary STEEP category in MVP, even if it touches multiple domains.

---

## **3.19 Three Horizons Classification**

### **Definition**

**Three horizons classification** places a signal into one of three temporal/systemic layers:

* **Horizon 1 (H1):** current dominant system  
* **Horizon 2 (H2):** transitional and disruptive space  
* **Horizon 3 (H3):** emerging future system

### **Purpose in the system**

It helps the user understand whether a signal reflects continuity, transition, or emergence.

---

## **3.20 Critical Uncertainty**

### **Definition**

A **critical uncertainty** is a factor that is both highly impactful to the focal question and highly uncertain in its future direction or outcome.

### **Purpose in the system**

Critical uncertainties are used to build scenarios. In the 2x2 matrix construction pipeline, they serve as the axes of the matrix. Each axis has two poles representing opposite resolutions of the uncertainty.

### **What it is not**

A critical uncertainty is not just any important topic.  
It must satisfy both:

* high impact  
* high uncertainty

### **Key semantic properties**

* A critical uncertainty may be system-derived from signal clustering or user-authored  
* A critical uncertainty has two poles: `pole_low` and `pole_high`, which must be mutually exclusive and opposite  
* A critical uncertainty may be locked by the user to fix it as a matrix axis regardless of its computed scores  
* A critical uncertainty carries computed scores used for axis selection

### **Computed fields**

* `impact_score` (0–1): mean signal score of signals tagged to this force, weighted by source trust  
* `uncertainty_score` (0–1): degree of signal disagreement on pole direction  
* `opposition_score` (0–1): degree to which pole signal sets are mutually exclusive  
* `axis_score`: composite of impact and uncertainty used for pair ranking  
* `pole_opposition_validation_score` (0–1): LLM-assessed opposition quality of the pole label pair, stored for explainability only

### **State fields**

* `axis_locked` (bool): if true, this axis is always selected for the matrix regardless of scores  
* `axis_rank` (1 | 2 | null): rank in the selected axis pair; null if not selected  
* `pole_low_label`: user-editable label for the low pole  
* `pole_high_label`: user-editable label for the high pole

### **Example**

* pace of regulatory approval for lifespan-extending therapies  
* public adoption of longevity interventions

---

## **3.21 Scenario**

### **Definition**

A **scenario** is a coherent, plausible, internally consistent description of a possible future world shaped by combinations of critical uncertainties.

### **Purpose in the system**

Scenarios organize interpretation.  
They provide structured futures against which signals can be evaluated.

### **What a scenario is not**

A scenario is not a forecast.  
A scenario is not a preferred future.  
A scenario is not a probability statement.

### **Key semantic properties**

* A scenario belongs to a theme context  
* A scenario has assumptions  
* A scenario may gain or lose support from incoming signals  
* Scenarios are organizing structures for analysis in the product  
* A scenario may be user-authored or matrix-generated; both are first-class objects

### **Matrix-specific fields**

When a scenario is generated by the 2x2 matrix construction:

* `matrix_generated` (bool): true if generated by the matrix construction pipeline  
* `axis1_id` (FK → CriticalUncertainty): the first selected axis  
* `axis1_pole` (`low | high`): which pole of Axis 1 this scenario represents  
* `axis2_id` (FK → CriticalUncertainty): the second selected axis  
* `axis2_pole` (`low | high`): which pole of Axis 2 this scenario represents  
* `quadrant_id` (derived): composite of `axis1_pole × axis2_pole`  
* `quadrant_viable` (bool): false if the quadrant had insufficient signal coverage at generation time

---

## **3.22 Scenario Confidence**

### **Definition**

**Scenario confidence** is a relative assessment of how much current evidence supports continued attention to a scenario as an analytically meaningful possibility.

### **Important constraint**

Scenario confidence is **not** the same as probability.  
It does not mean “chance this future will happen.”

### **Purpose in the system**

It is used to express the strength of current evidence alignment.

### **Suggested values**

* low  
* medium  
* high

---

## **3.23 Scenario Momentum**

### **Definition**

**Scenario momentum** is a directional assessment of whether recent evidence is making a scenario more supported, less supported, or relatively unchanged over time.

### **Suggested values**

* increasing  
* stable  
* decreasing

### **Purpose in the system**

Momentum communicates trend direction without pretending to quantify exact likelihood.

---

## **3.24 Assumption**

### **Definition**

An **assumption** is a condition or proposition embedded in a scenario, interpretation, or strategic view that may be reinforced or challenged by signals.

### **Purpose in the system**

Assumptions help connect raw evidence to higher-level reasoning.

---

## **3.25 Implication**

### **Definition**

An **implication** is a meaningful consequence that follows if a signal pattern, scenario shift, or driver of change matters for the focal question or stakeholders.

### **Purpose in the system**

Implications are how monitoring becomes strategically useful.

---

## **3.26 Recommendation**

### **Definition**

A **recommendation** is a suggested strategic response derived from interpreted evidence, scenario movement, and stakeholder context.

### **Purpose in the system**

Recommendations translate foresight into action.

### **Modeling note**

In MVP, recommendations may be lightly drafted and human-reviewed rather than fully formalized.

---

## **3.27 Strategic Brief**

### **Definition**

A **strategic brief** is a structured synthesis produced by the system for a defined period that summarizes key developments, changes, meaning, implications, and recommended actions for the active theme.

### **Purpose in the system**

The brief is the primary synthesis output of the MVP.

### **Required structure**

* key developments  
* what’s changing  
* why it matters  
* implications  
* recommended actions

### **Important note**

The brief is built in two layers:

* deterministic structural assembly  
* semantic content generation where needed

---

## **3.28 Monitoring Run**

### **Definition**

A **monitoring run** is one execution of the system’s recurring pipeline for a theme.

### **Purpose in the system**

It provides operational traceability for what the system scanned, processed, and changed.

### **Typical contents**

* sources scanned  
* documents fetched  
* signals extracted  
* scenarios updated  
* errors or warnings

---

## **3.29 User Feedback**

### **Definition**

**User feedback** is an explicit correction, confirmation, or annotation applied by the user to a system-generated artifact.

### **Purpose in the system**

It improves quality, trust, and future ranking or classification behavior.

### **Examples**

* mark signal as irrelevant  
* reclassify STEEP category  
* confirm scenario mapping  
* edit summary

---

## **4\. Relationship Model**

### **4.1 Project-to-Theme**

* A project may have multiple themes  
* A theme may relate to multiple projects  
* In MVP, monitoring is still centered on one active theme workspace at a time

### **4.2 Theme-to-Source**

* A theme may have many sources  
* A source may support one or more themes conceptually, but in MVP source assignment may be stored per theme workspace for simplicity

### **4.3 Source-to-Raw Document**

* A source produces many raw documents over time  
* A raw document originates from one source

### **4.4 Raw Document-to-Signal**

* One raw document may produce zero, one, or multiple candidate signals  
* One signal may be supported by one or more raw documents

### **4.5 Signal-to-Scenario**

* A signal may support, weaken, or have no meaningful effect on a scenario  
* A scenario may be influenced by many signals

### **4.6 Scenario-to-Critical Uncertainty**

* A scenario is typically built from combinations of critical uncertainties  
* A critical uncertainty may participate in multiple scenarios  
* In the 2x2 matrix, exactly two critical uncertainties serve as axes; each scenario is defined by one pole from each axis  
* A critical uncertainty may exist as a candidate driving force without yet being an active matrix axis

### **4.7 Signal-to-Implication**

* Signals do not directly equal implications  
* Implications are derived from interpreting signal patterns, scenario shifts, and stakeholder context

---

## **5\. Semantic Rules and Constraints**

### **5.1 Not every document becomes a signal**

The system must distinguish between raw input and meaningful evidence.

### **5.2 Not every signal should affect a scenario**

Signals may be relevant to the theme but irrelevant to scenario movement.

### **5.3 Scenario confidence must not be shown as explicit probability in MVP**

This avoids false precision.

### **5.4 Signal relevance is theme-dependent**

The same document may be highly relevant in one theme and irrelevant in another.

### **5.5 Drivers are more structural than signals**

Drivers should not be treated as interchangeable with individual events or documents.

### **5.6 A brief is not a dump of top signals**

A brief is a synthesis artifact, not a feed summary.

### **5.7 User feedback overrides system suggestions where applicable**

Human correction should have semantic authority in the MVP.

### **5.8 Axis poles must be genuine opposites**

A critical uncertainty used as a matrix axis must have poles that are mutually exclusive and collectively exhaustive for that dimension. Two labels that differ only in degree (e.g., "fast" vs "slow") are acceptable; two labels that do not cover the full outcome space are not. The system enforces this via the `opposition_score` gate and the LLM validation score.

### **5.9 Axis independence is required for scenario distinctiveness**

The two selected matrix axes must be sufficiently independent so that each of the four quadrant scenarios describes a genuinely different world. Correlated axes produce degenerate quadrants. The system enforces independence through pair selection scoring.

---

## **6\. Ambiguities to Avoid**

The following confusions should be explicitly avoided in implementation:

* **Theme vs tag**  
  * A theme is a strategic monitoring lens, not a freeform label  
* **Signal vs article**  
  * A signal is interpreted evidence, not the raw source item itself  
* **Scenario vs forecast**  
  * A scenario is a plausible future, not a prediction  
* **Confidence vs probability**  
  * Confidence indicates support level, not statistical likelihood  
* **Momentum vs confidence**  
  * Momentum is directional change over time; confidence is current support level  
* **Driver vs trend**  
  * A driver is a structural force; a trend is a visible pattern of change  
* **Weak signal vs wildcard**  
  * A weak signal is early evidence of change; a wildcard is a low-probability, high-impact discontinuity

---

## **7\. Example Domain Walkthrough: Longevity**

### **Theme**

Longevity

### **Focal question**

How might advances in longevity reshape consumer behavior, labor participation, and healthcare systems over the next 15 years?

### **Related subjects**

* biotech  
* insurance  
* retirement systems  
* preventive health  
* regulation  
* healthcare delivery

### **Example signals**

* increased funding into senolytic therapies  
* government consultations on retirement age policy  
* consumer growth in preventive health spending  
* employer experiments around later-life workforce design

### **Example critical uncertainties**

* pace of clinical efficacy and approval for longevity therapies  
* affordability and accessibility of interventions  
* public willingness to adopt longevity-enhancing treatments

### **Example scenarios**

* longevity as elite health privilege  
* regulated mainstream longevity adoption  
* stalled promise and public skepticism  
* preventive longevity integrated into daily life

### **Example brief implication**

If affordability remains low while efficacy rises, market and policy effects may diverge sharply across income groups.

---

## **8\. Implementation Guidance**

This domain model should be used as the reference language for:

* PRDs  
* architecture docs  
* functional specs  
* database naming  
* API naming  
* prompts and model outputs  
* test cases

If future documents use conflicting definitions, this document should be treated as the semantic source of truth unless explicitly revised.

---

