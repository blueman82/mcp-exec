# Ketchup Documentation Update Plan (Structure-Aware)

## 1. Preparation: Read and Map Document Structure

- **Walkthrough Doc (`ketchup_code_walkthrough_documentation.md`):**
  - Read the Table of Contents and all Phase sections (especially Phase 2: Factories/DI, Phase 3: Module-by-Module).
  - Identify where each relevant module (e.g., `home.py`) is currently documented or needs to be added.
  - Note the structure for each factory (Slack, DB, AI, etc.) under Phase 2.
  - For each module, check if it has a dedicated section under Phase 3; if not, plan to add one.

- **High-Level Doc (`ketchup_high_level.md`):**
  - Read the Table of Contents and all module summaries (Core, Slack, etc.).
  - Identify where HomeTabHandler, product filtering, and dynamic prompts are described or need to be added.
  - Note the summary style and ensure new content fits the concise, practical format.

## 2. Update Plan by Document Section

### A. Walkthrough Doc (`ketchup_code_walkthrough_documentation.md`)

- **Phase 2: Dependency Injection and Factory System**
  - Update each factory subsection (e.g., `slack_factory.py`, `db_factory.py`) to reflect new/changed client initialisation, especially for HomeTabHandler and its dependencies.
  - Clearly document which clients are initialised, their purpose, and any changes in DI/factory logic.
  - Add/refresh Mermaid diagrams to show updated dependency flows.

- **Phase 3: Module-by-Module Intensive Code Walkthrough**
  - For each relevant module:
    - If `home.py` (HomeTabHandler) is not present, add a new detailed section following the Phase 1 template.
    - For existing modules (e.g., command handlers, prompts), update the logic, error handling, and interactions to reflect product filtering and dynamic prompt changes.
    - For each function/class, provide code-driven explanations, edge cases, and cross-references as per the walkthrough standard.

- **Other Phases**
  - Update any command/event flow diagrams (Phase 4) if the flow of HomeTabHandler, list/archive, or prompt logic has changed.
  - Add new best practices or patterns if relevant.

- **Table of Contents**
  - Update the Table of Contents to reflect any new or reorganized sections.

### B. High-Level Doc (`ketchup_high_level.md`)

- **Module Summaries**
  - Update the Core, Slack, and AI module sections to mention new/changed dependencies, product filtering, and dynamic prompt logic.
  - Add a brief, user-friendly summary of HomeTabHandler and its role if not already present.

- **How a Slack Command Works / Common Code Patterns**
  - Add/refresh explanations for product filtering in list/archive commands and dynamic prompt adaptation.
  - Ensure all new logic is described in a concise, practical way.

- **Table of Contents**
  - Update the Table of Contents if new sections are added.

## 3. Edge Cases & Learnings

- For each update, explicitly document any edge cases, legacy data handling, or confusing scenarios discovered during testing or review.

## 4. Documentation Standards

- Walkthrough doc: Maintain highly detailed, code-driven, step-by-step explanations.
- High-level doc: Keep concise, practical, and user-focused.

## 5. Cross-References & TOC

- Link to relevant plans and code files.
- Update Table of Contents in both docs if new sections are added.

---

**Next Steps:**
- Read both documentation files in full.
- Map out where each update belongs.
- Apply updates section-by-section, following the above structure. 