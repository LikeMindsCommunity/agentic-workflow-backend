---
name: customer1-kb
description: >
  Builds and extends the Customer 1 knowledge base from a ServiceNow Solution Design Document (SDD).
  Archetype: document-from-template — reference DOCX consumed; downstream agent generates new
  ServiceNow SDDs for future clients matching this template's structure and style.
  Triggers: "build customer1 KB", "extend customer1 KB", "run customer1-kb", "generate customer1 KB".
---

# Customer 1 KB Skill

## Overview

**Artifacts consumed:** ServiceNow Solution Design & Architecture Documents (`SolutionDesign&Architecture_Doc v0.2.docx` and any additional reference SDDs added later).

**KB produced:** `outputs/customer1/kb/` — a structured knowledge base that lets a downstream agent generate new ServiceNow SDDs for new clients, matching Customer 1's template structure, section ordering, table schemas, and vocabulary.

**First invocation:** draft all KB files from scratch from the reference artifacts.

**Subsequent invocations:** treat existing KB files in `outputs/customer1/kb/` as the baseline; run the inventory phase as a delta (new sections, updated tables, new gap findings only); extend in place.

**Reference file (clone anchor):** `inputs/sample_artifacts/serviceIO/Customer_1_Implementation_Documentation/Solution Design Document/SolutionDesign&Architecture_Doc v0.2.docx`

---

## Inputs

- `inputs=inputs/sample_artifacts/serviceIO/Customer_1_Implementation_Documentation/Solution Design Document/` — default artifact directory
- `output=outputs/customer1/kb/` — default KB output directory

**Recognition signals** — confirm the artifact is a Customer 1 ServiceNow SDD before proceeding:

- File is a `.docx` (or `.pdf`) with "SolutionDesign" or "Solution Design" in the filename plus a version string (`v0.1`, `v0.2`, etc.)
- Document opens with a "Purpose of this Document" section listing ServiceNow modules to be implemented
- Body contains explicit `<client name>` or `<customer name>` placeholder strings
- Numbered tables throughout (`Table 5`, `Table 6`, … up to at least `Table 30+`)
- Module sections present: Incident Management, Problem Management, Change Management, Service Level Management, Knowledge Management, Service Portal / Service Catalog and Request Management, Release Management
- Integration section covering at least one of: Azure AD / SSO, Jira, GitHub, SolarWinds

If the artifact does not match these signals, halt and ask the operator to confirm this is the correct file.

---

## Phases

### Phase 1 — Recognition

1. Confirm the artifact matches recognition signals above. If not, halt.
2. Extract document metadata: filename, version string, number of pages (estimate from section count), modules listed in the Purpose section, integration systems listed in the Architecture section.
3. Note any `<client name>` or `<customer name>` placeholder strings — confirm these appear verbatim and are the per-instance swap targets.
4. If KB already exists at `outputs/customer1/kb/`, read `09-gap-log.md` first — carry forward any open BLOCKING gaps and skip re-deriving what is already resolved.

### Phase 2 — Inventory

Walk every section in order. For each module section, record:

- Exact heading text (casing, spacing, punctuation — verbatim, no paraphrase)
- Subsection list and their table numbers
- Table column headers verbatim for every table in the section
- Values that are clearly per-instance variables (placeholder strings, "Example" rows, blank approval fields, client-specific group names)
- Values that appear OOB / fixed (standard ServiceNow role names, state enums, plugin IDs)

The **internal subsection pattern** repeats across module sections. Confirm it holds for each module and note deviations:

```
Introduction paragraph (module purpose + lifecycle step list)
Roles and Permissions table
[module-specific config tables: categories, states, priorities, defaults]
Email Notifications list
Reports list (or table)
Dashboards list
```

Note which modules deviate: Problem Management shares its category list with Incident by reference; Change Management adds Change Types, Change Tasks, Close Codes, CAB Approvers, plugin IDs; Service Level Management has SLA Conditions and SLA Notifications instead of Email Notifications; Release Management has Release Phases and Release Types.

Record all embedded images (logos, diagrams, architecture diagrams, screenshots) with location in doc, apparent type, and replacement policy determination. Flag any diagram that depicts client-specific architecture.

### Phase 3 — Draft KB Files

Write to `outputs/customer1/kb/`. On first invocation, create all files. On subsequent invocations, update only sections that changed.

**KB files to produce:**

| File | Purpose |
|---|---|
| `00-overview.md` | Document genre, purpose, reference file path, defined-term glossary |
| `01-document-structure.md` | Ordered section hierarchy, exact heading text, mandatory vs. conditional, internal module subsection pattern |
| `02-module-templates.md` | Per-module subsection detail: exact table schemas, state enums, lifecycle steps, OOB vs. per-instance classification per field |
| `03-tables-and-schemas.md` | Every distinct table type with column headers verbatim, column content conventions, empty-cell rendering |
| `04-variable-vs-fixed.md` | Per-section: per-instance variable fields vs. fixed boilerplate, with BLOCKING flags where the single-reference sample leaves the split uncertain |
| `05-servicenow-vocabulary.md` | OOB ServiceNow role names, state enums, priority/impact/urgency conventions, plugin IDs, OOB catalog names, category lists |
| `06-integrations.md` | Integration modules in scope, port/protocol conventions, field mapping tables (where extracted) |
| `07-boilerplate.md` | Verbatim fixed text: Introduction paragraphs per module, lifecycle step lists, standard role descriptions, process definitions |
| `08-input-checklist.md` | Per-instance fields the downstream agent must extract before drafting (tiered: BLOCKING / IMPORTANT / NICE TO HAVE) |
| `09-gap-log.md` | Open uncertainties, BLOCKING gaps, assumptions flagged for operator confirmation |

### Phase 4 — Gap Loop

Ask BLOCKING questions first, wait for operator response before continuing. Do not batch BLOCKING and IMPORTANT questions together.

See gap-question templates below. Emit only questions that are still unresolved (check `09-gap-log.md` for already-asked questions).

### Phase 5 — Save

Write or update all KB files. Mark each resolved gap in `09-gap-log.md` with `[RESOLVED: <answer>]`. Leave unresolved gaps marked `[OPEN]`.

---

## KB File Details

### `00-overview.md`

- Genre: ServiceNow Implementation Solution Design Document
- Audience: `<client name>` ServiceNow Stakeholders
- Reference file: `SolutionDesign&Architecture_Doc v0.2.docx`
- Downstream agent's job: generate a new SDD for a new client by replacing per-instance variables, updating client-specific config tables, and retaining the module structure and OOB vocabulary
- Defined-term glossary (seed from reference, extend as new terms surface):
  - **Incident** — any disruption to a service or workflow
  - **Problem** — underlying cause of one or more incidents
  - **Change** — modification to the production environment (types: Normal, Standard, Emergency)
  - **CAB** — Change Advisory Board
  - **SLA** — Service Level Agreement (external SLA)
  - **OLA** — Operational Level Agreement (internal)
  - **UC** — Underpinning Contract (external provider)
  - **CMDB** — Configuration Management Database
  - **CI** — Configuration Item
  - **ITIL** — IT Infrastructure Library
  - **OOTB** — Out-of-the-Box (standard ServiceNow feature, no customization)

### `01-document-structure.md`

Record section ordering exactly as observed. Confirmed section list (from v0.2):

1. Purpose of this Document
2. High Level Architecture / Overall Solution Architecture
3. Incident Management
4. Problem Management
5. Change Management
6. Service Level Management
7. Knowledge Management
8. Service Portal / Service Catalog and Request Management
9. Release Management
10. [CMDB / Discovery / IT Operations Management — referenced in Purpose but content not extracted; flag as BLOCKING gap G2]
11. [Platform Encryption — referenced in Purpose but content not extracted; flag as BLOCKING gap G3]
12. Integrations (Azure AD / SSO / Jira / GitHub / SolarWinds)

**Conditional sections** — include only when the engagement includes that component:
- CMDB / Discovery — when IT Operations Management is in scope
- Platform Encryption — when encryption is in scope
- Each integration subsection — only when that system is in scope

### `02-module-templates.md`

For each ITSM module, record the subsection pattern and deviations. Key module-level specifics:

**Incident Management specific:**
- Priority = f(Impact, Urgency) — configured in ServiceNow "Priority Lookup Rules" table
- On-Hold reasons enum: Awaiting Caller, Awaiting Change, Awaiting Validation, Awaiting Vendor
- Auto-close after Resolved: 5 days
- Incident channels: Chat, Email, Phone, Self-Service, Virtual Agent, Monitoring, Walk-In

**Problem Management specific:**
- Lifecycle: Problem Detection → Logging → Investigation & Diagnosis → Workaround → Known Error Record → Resolution → Closure
- Cause Codes: Environmental disaster, Hardware issue, People / Process / Documentation, Software issue, Vendor issue, Other
- Categories: reference Incident Management (do not duplicate)

**Change Management specific:**
- Change Types: Normal (requires approval: `<customer name>` + Business + CAB), Standard (pre-approved, no deviation), Emergency (post-hoc review)
- Default form field values in table (Requested By: Logged-in User, Priority: Low, Risk: Moderate, Impact: Low, State: New)
- Default Change Tasks on Implement: "Implement" + "Post-implementation testing"
- Plugins required: `com.snc.change_management.risk_assessment`, `com.snc.change_management.cab`
- OOTB workflows used (no custom workflow — flag this per-instance if customer requires custom)

**Service Level Management specific:**
- SLA notification schedule: 50% (to Assignee), 75% (to Assignee), Breach (to Assignee + Manager)
- SLA types: SLA, OLA, UC — document which apply for this engagement
- Retroactive start option available on SLAs

**Knowledge Management specific:**
- Article states: Draft → Review → Published → Pending retirement → Retired
- Knowledge bases: IT (Service Desk KB), Knowledge (open read; Knowledge-role users can contribute)
- Feedback Task states: New, Work in progress, Awaiting information, Resolved, Closed

**Service Catalog / Request Management specific:**
- OOTB catalogs: Services, Can We Help You?, Office, Hardware, Peripherals, Software, Desktops, Mobiles
- Service Request state enum differs from Incident state enum (see Table 41)
- Catalog task states differ from service request states

**Release Management specific:**
- Release States: Draft, Scoping, Awaiting Approval, Work in Progress, Testing/QA, Deploy/Launch, Close Complete, On Hold, Cancelled
- Release Phases: Requirement Gathering, Design, Development, Build, Deployment, QA, User Acceptance
- Release Types: Major, Minor, Upgrade, Emergency, Maintenance, Patch

### `03-tables-and-schemas.md`

**Roles and Permissions table** (used by every module):
- Columns: Role Name | Action | Remark (or Description — varies by module)
- Header styling and column order may vary slightly; capture verbatim from reference

**Priority Lookup table:**
- Columns: Priority | Impact | Urgency
- Values are fixed OOB ServiceNow enums

**SLA Configuration table:**
- Columns: Name | Schedule | Duration | Start condition | Stop condition | Pause condition | Type | Target
- Per-instance: specific values; schema is fixed

**State Transition table:**
- Columns: State | Description
- Module-specific state lists (see `02-module-templates.md`)

**Auto Assignment table:**
- Columns: Sr No. | Category | Assignment Group
- Per-instance: assignment group names; "Example" rows in reference are placeholders

**Default Values table (Change Management):**
- Columns: Field | Table | Default Value

**Release Types / Phases tables:**
- Single-column lists (numbered or bulleted)

**CAB Approvers table:**
- Single-column list of names
- Per-instance: "CAB team member1 name" / "CAB team member2 name" in reference are explicit placeholders

### `04-variable-vs-fixed.md`

**Per-instance variables (confirmed — explicit placeholders in reference):**
- `<client name>` / `<customer name>` — all occurrences, including cover page, Purpose section, Change Management approvals
- CAB Approver names
- Auto Assignment group names
- Integration endpoint details (Azure AD tenant, SolarWinds host, Jira instance URL)
- SLA schedule name (e.g. "12x5 Weekdays 8:00AM–8:00PM CST" — hours and timezone are client-specific)
- User provisioning field mapping table

**Per-instance variables (guessed — single reference, BLOCKING gap G1):**
- Category and subcategory lists — may match exactly or differ per client
- SLA durations and targets — v0.2 shows specific values (30 Mins, 4 Hours, etc.); these may vary
- Resolution codes — may vary per client engagement
- Email notification event list — extensions or subsets possible
- Report and dashboard selections

**Fixed OOB (high confidence — standard ServiceNow constructs):**
- OOB role names (sn_incident_read, sn_incident_write, major_incident_manager, incident_manager, problem_admin, change_manager, etc.)
- Plugin IDs (com.snc.change_management.risk_assessment, com.snc.change_management.cab)
- Priority/Impact/Urgency enum labels (1-Critical, 2-High, 3-Moderate, 4-Low, 5-Planning; 1-High, 2-Medium, 3-Low)
- OOB catalog names (Can We Help You?, Office, Hardware, Peripherals, Software, Desktops, Mobiles)
- State enum labels per module (confirmed OOB)
- SLA type definitions (SLA, OLA, UC) and their conceptual definitions
- Change Task auto-creation on Implement (Implement + Post-implementation testing)

### `05-servicenow-vocabulary.md`

Document OOB ServiceNow role names by module, state enums by module, and priority/impact/urgency scales exactly as they appear in the reference. These must be reproduced verbatim in the generated SDD — no paraphrase.

Key verbatim forms:
- Priority labels: `1 - Critical`, `2 - High`, `3 - Moderate`, `4 - Low`, `5 - Planning`
- Impact labels: `1 – High`, `2 – Medium`, `3 – Low` (note en-dash, not hyphen)
- Urgency labels: `1 - High`, `2 - Medium`, `3 - Low`
- On-Hold reasons: `Awaiting Caller`, `Awaiting Change`, `Awaiting Validation`, `Awaiting Vendor`
- Change types: `Normal`, `Standard`, `Emergency` (capitalized)

### `06-integrations.md`

Integration modules mentioned in v0.2 (from Architecture section):

| Integration | System | Protocol/Port | Direction | Description |
|---|---|---|---|---|
| SSO + User Provisioning | Azure Active Directory | HTTPS / 443 | Inbound | Azure AD credentials for ServiceNow login; user sync |
| Ticketing Sync | Jira | HTTPS / 443 | Bi-directional | Epics and Stories synchronized between Jira and ServiceNow |
| Event Management | SolarWinds | HTTPS / 443 | Bi-directional | Events from SolarWinds create Incidents in ServiceNow |
| Source Control | GitHub | (not detailed in v0.2) | — | Referenced in scope; details not extracted |

Flag for gap log: Azure AD field mapping table (end of document, not fully extracted) — BLOCKING gap G4.

### `07-boilerplate.md`

Store verbatim introductory paragraphs for each module and the five-step incident management lifecycle definition. Mark per-instance fill-ins with `{{placeholder}}`.

Example — Incident Management Introduction (verbatim from reference):
> An incident is any disruption to a service or workflow. Incident management is the process of detecting, investigating, and responding to incidents in as little time as possible. The aim is to fix and clear issues before they become large-scale, company-wide crises.

Five steps in an incident management plan:
1. Incident identification
2. Incident categorization
3. Incident prioritization
4. Incident response
5. Incident closure

Mark each module's Introduction paragraph as fixed or per-instance-variable after G1 is resolved.

### `08-input-checklist.md`

Per-instance fields the downstream agent must extract from discovery materials before drafting:

**BLOCKING — halt if absent:**
- `client_name` — the client's formal name (populates all `<client name>` placeholders)
- `customer_name` — the customer's formal name (populates `<customer name>` placeholders; confirm if same as client_name)
- Modules in scope — which of the 9+ module sections to include
- Integrations in scope — which integration subsections to include
- CAB approver names — list of named individuals
- Assignment groups per category — for Auto Assignment table
- SLA schedules — schedule names, business hours definition, timezone
- SLA durations per priority per type (Response / Resolution)
- Azure AD tenant details (if AD integration in scope)

**IMPORTANT — proceed with documented default if absent, flag in output:**
- Category and subcategory list — default to reference values if not overridden
- Resolution codes per module — default to reference values if not overridden
- SLA notification thresholds — default to 50% / 75% / breach
- Jira / SolarWinds / GitHub connection details (if those integrations in scope)

**NICE TO HAVE:**
- Additional custom reports or dashboards beyond OOB set
- Custom email notification events beyond reference list
- Custom catalog items beyond OOB catalogs
- Version string for the new SDD (default: v1.0)

### `09-gap-log.md`

Seed with the following open gaps on first invocation:

**G1 [BLOCKING] Single reference sample — fixed-vs-variable split uncertain**
Only one reference SDD provided (v0.2). Fields marked "guessed per-instance" in `04-variable-vs-fixed.md` may actually be fixed boilerplate. Resolve: share at least one additional reference SDD from a different customer engagement. Until resolved, treat guessed-per-instance fields as per-instance and flag in generated output.

**G2 [BLOCKING] CMDB / Discovery / IT Operations Management section missing**
Referenced in the Purpose section but not present in the extracted content. The section covers Discovery, CMDB, and Schedules. Resolve: share the complete document or a supplementary CMDB design document.

**G3 [BLOCKING] Platform Encryption section missing**
Referenced in the Purpose section but content not extracted. Resolve: share the complete document or a Platform Encryption design spec.

**G4 [BLOCKING] Azure AD field mapping table not extracted**
The Azure AD integration section references a user provisioning field mapping table that was at the end of the document and was not fully captured. Resolve: manually extract and provide the field mapping table from the reference DOCX.

**G5 [IMPORTANT] GitHub integration not detailed**
GitHub is listed in the integration scope but no detail was present in the extracted content. Resolve: share the GitHub integration design section or confirm it is out of scope for the SDD template.

**G6 [IMPORTANT] Embedded images and assets not inventoried**
The reference DOCX likely contains embedded logos, architecture diagrams, and other assets. Without reading the DOCX media/ folder, replacement policies cannot be set. Resolve: open the DOCX as a zip and enumerate `word/media/` assets; determine per-asset replacement policy (vendor logo: keep; client logo: swap; architecture diagram: regenerate or carry over).

---

## Critical Rules

1. **Reproduce section headings verbatim.** Heading casing, spacing, and punctuation are exact strings — do not paraphrase. "Service Portal / Service Catalog and Request Management" is not the same as "Service Portal and Catalog Management."
2. **Quote OOB role names exactly.** `sn_incident_read`, `major_incident_manager`, `sn_change_cab.cab_manager` — no paraphrase, no abbreviation. These are ServiceNow system identifiers.
3. **Quote state enum labels exactly.** `1 - Critical`, `On-Hold`, `Fix in Progress` — copy from `05-servicenow-vocabulary.md`, not from memory.
4. **Do not invent module sections.** Only include modules explicitly listed in the engagement scope. A client not using Release Management must not receive that section.
5. **Do not treat "Example" rows as real data.** The Auto Assignment table and CAB Approver table have placeholder values. Halt and ask if real values are not provided.
6. **Do not produce a generic ServiceNow guide.** Every section must be grounded in this client's specific configuration choices. Generic "ServiceNow best practices" text is not an SDD.
7. **Do not resolve source conflicts silently.** If a discovery MOM contradicts another source, surface the conflict to the operator before choosing one.
8. **Do not copy the previous client's identifying details.** When generating a new SDD, all `<client name>` and `<customer name>` placeholders must be replaced. Any embedded screenshots or diagrams from the reference showing another client's UI must be cleansed or replaced.
9. **Do not output resolved BLOCKING gaps as confirmed facts.** If G1 through G6 are not resolved, generated SDDs must carry explicit `[GAP — see gap log]` markers in the relevant sections rather than fabricating content.
10. **Priority is a function of Impact × Urgency.** Do not set priority independently. The 5×3 lookup matrix is the source of truth; never write a priority value that isn't derivable from it.
11. **Plugins must be declared explicitly.** If a feature requires a plugin (`com.snc.change_management.risk_assessment`, `com.snc.change_management.cab`), the SDD must call it out by plugin ID. Do not describe plugin-dependent features without the plugin declaration.

---

## Gap-Question Templates

**G1 [BLOCKING]** "Only one reference SDD was provided (v0.2). I've marked `{fields}` as guessed per-instance, but without a second reference I can't confirm they're not fixed boilerplate. Please share at least one more reference SDD from a different client engagement."

**G2 [BLOCKING]** "The SDD scope lists CMDB / Discovery / IT Operations Management, but this section was absent from the extracted content. Please share the CMDB design section or a supplementary document so I can draft that KB file."

**G3 [BLOCKING]** "Platform Encryption is listed in scope but the section content was not extracted. Please share the Platform Encryption design section or confirm it is out of scope for this template."

**G4 [BLOCKING]** "The Azure AD user provisioning field mapping table was at the end of the reference DOCX and was not fully captured. Please provide the field mapping table (field names and their ServiceNow target fields)."

**G5 [IMPORTANT]** "GitHub is listed as an integration but its design detail was not present in the extracted content. Is this a separate design document, or should it be included in the SDD? If in scope, please share the connection and field mapping details."

**G6 [IMPORTANT]** "I was not able to inventory the embedded assets in the reference DOCX (logos, architecture diagrams, screenshots). To set replacement policies, I need the DOCX opened as a zip — can you list the contents of `word/media/` and tell me which assets are client-specific vs. vendor-fixed?"

**G7 [VERIFY ASSUMPTION]** "I classified the category/subcategory list as potentially per-instance because I only have one reference. Confirm: is the category list in Table 6 a standard default your firm uses for every client, or is it customized per client?"

**G8 [VERIFY ASSUMPTION]** "The SLA durations in Table 11 (e.g. P1 Resolution: 4 Hours, P2 Resolution: 8 Hours) — are these your firm's standard defaults, or are they negotiated per client?"

**G9 [NICE TO HAVE]** "The reference shows OOB reports and dashboards only. Do you configure custom reports for any standard engagement, or is the OOB set sufficient?"

---

## Skip-Entirely List

The runtime must never produce:
- External REST API reference or authentication setup instructions
- Data model / entity catalog for ServiceNow tables (e.g. incident, sys_user schema)
- Webhook contracts or event bus integration specs
- Configuration reference for ServiceNow platform settings
- Generic "how to implement ITIL in ServiceNow" advice — this KB encodes one template's identity, not industry-wide best practices

---

## Runtime Behavior

On invocation:

1. Confirm the artifact matches recognition signals. Halt if not.
2. Check `outputs/customer1/kb/09-gap-log.md`. If it exists, carry forward open BLOCKING gaps — do not re-ask resolved questions.
3. If KB exists: run inventory as a delta; update only changed sections and new gap findings.
4. If KB does not exist: run from scratch, drafting all 10 KB files.
5. After drafting, run the gap loop: present BLOCKING gaps first and wait for operator response before presenting IMPORTANT gaps.
6. Save all KB files. Mark resolved gaps `[RESOLVED: <answer>]`; leave unresolved gaps `[OPEN]`.
