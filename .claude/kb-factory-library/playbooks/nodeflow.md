---
id: nodeflow
seen-in: [exotel]
---

## Artifact description

Client artifacts are Exotel NodeFlow JSON exports — call-flow definitions from Exotel's visual IVR builder. Recognize by:

- Top-level shape: `{ "nodeflowInfo": {...}, "childNodeflows": {...} | null }`.
- `nodeflowInfo.scriptType` is the fixed string `"nodeflow.script.interpreter.js"`. This is the strongest single fingerprint.
- `nodeflowInfo.nodeflowType` ends in `NodeFlow` (`InboundNodeFlow`, `OutboundNodeFlow`).
- `nodeflowInfo` has a fixed 13-key shape: `id, name, description, nodeflowType, scriptType, startNodeID, stopNodeID, nodes, transitions, uiProps, conditions, variables, nodeflowErrors`.
- `nodes` is a list. Every node carries an `alias` in the `node.*` namespace (`node.script`, `node.play`, `node.digit.collection`, `node.acd`, ...) and a `type` (`ScriptNode`, `PlayNode`, `DigitCollectionNode`, `ACDNode`, `SQLQueryNode`, `HTTP`, `CRMNode`, `HolidayNode`, `OfficeHourNode`, `SyncChildFlowNode`, `DialNode`, `TransferToPhone`, `StartMonitorNode`, `AdditionalCallHistory`, `HangupNode`, `SleepNode`, `StopNode`).
- `transitions` is a flat UUID-keyed dict; each entry has `from.{nodeID, eventName}`, `to`, `condition`, `labels`, and `uiProps.{sourcePort, targetPort, points}`.
- Event names are dotted (`success.collect.digit`, `hungup.collect.digit`, `script.node.success`, `system.error`).
- Embedded scripts live inline in attribute `staticValue` for `script`, `preScript`, `postScript` and in `conditions[*].condition`. The language is a sandboxed JS interpreter, not Node/browser JS.
- All IDs are UUIDs; nodes carry layout coordinates in `uiProps.x/y` and transitions carry waypoints in `uiProps.points`.

This is a component-flow + artifact-generator platform with first-class embedded scripting. There is no external client API surface — the downstream agent's job is to **produce valid NodeFlow JSON**.

## Recipe

Generate `.claude/skills/{client}-kb/` with the following files:

- `00-overview.md` — Domain context (IVR / call flows). Glossary: NodeFlow, alias, transition, event, condition, port, variable, child flow. State the fixed values: `scriptType` is always `"nodeflow.script.interpreter.js"`; `nodeflowType` is one of `InboundNodeFlow` / `OutboundNodeFlow`.
- `01-building-blocks.md` — One subsection per distinct node `type` observed in the inputs. For each: `alias`, `type`, purpose, when-to-use, full attribute schema (name / type / required / default / accepts-script?), event catalog (every event the runtime can emit + whether it must be wired). Document the **universal node fields** (`id, alias, name, type, version, visible, connectedChildNodeflowId, events, attributes, uiProps`) once in a dedicated subsection, not repeated per node type.
- `02-composition-rules.md` — Transition schema (`from`, `to`, `condition`, `uiProps`). `unconditionalTransition` vs `conditionalTransitions` on each event. Condition resolution: `conditionalTransitions[*].conditionId` resolves against `nodeflowInfo.conditions`. `sourcePort` / `targetPort` semantics. Parent ↔ child flow wiring via `childNodeflows` + `connectedChildNodeflowId` on `SyncChildFlowNode`. Note: `startNodeID` must reference a real `nodes[*].id`; `stopNodeID` may be a literal sentinel (e.g. `"SuccessStop"`). Validation rule: every node typically needs a `system.error` event handler.
- `03-artifact-schema.md` — Full `{nodeflowInfo, childNodeflows}` schema. Classify each field: **fixed** (e.g. `scriptType`), **identity** (UUIDs), **configurable** (`name`, `description`, attribute `staticValue`s), **computed** (`nodeflowErrors.errors/warnings`). Minimum-valid example + a fully-featured annotated example pulled from the actual input files.
- `04-variables-and-scripting.md` — Variable system: `nodeflowInfo.variables` declares all variables; convention is to **initialize them in a `StartScript` node's `script` attribute** before they're referenced. Embedded scripting: which attribute slots accept scripts (`script`, `preScript`, `postScript`, `condition`), built-ins observed (extract from real `staticValue` bodies — do not assume Node/browser globals), how variables are read/written (bare-name assignment, e.g. `mainMenuInput = '1'`). Condition expression language: every operator and form observed in `conditions[*].condition` (e.g. `==`, `&&`, `||`, string-equality with single quotes, statement terminated with `;`). One CORRECT and one WRONG example per form.
- `05-patterns.md` — Common patterns extracted from the input flows. Examples likely to appear: welcome-play → digit-collect → branch-by-condition → ACD/transfer/dial; SQL-lookup-then-branch; holiday / office-hour gating prefix; CRM-lookup-then-personalised-greeting; SyncChildFlow invocation. Each pattern: when-to-use, step-by-step component sequence, required wirings, anti-pattern.
- `06-constraints.md` — Numbered constraints. Seed from what the artifacts enforce: (C1) all IDs are UUIDs; (C2) `transitions[*].from.nodeID` must match a `nodes[*].id`; (C3) `transitions[*].condition` (when non-null) must be a key in `nodeflowInfo.conditions`; (C4) `SyncChildFlowNode.connectedChildNodeflowId[0]` must be a key in `childNodeflows`; (C5) every node should declare a handler for `system.error`; (C6) `startNodeID` must point to a real node; (C7) `scriptType` must equal `"nodeflow.script.interpreter.js"`. For each, the rule, consequence, CORRECT, WRONG.
- `07-layout-rules.md` — Coordinates on nodes (`uiProps.x/y`) and waypoints on transitions (`uiProps.points`). No effect on execution but the visual editor relies on them. Document the directional convention observed (left-to-right? top-to-bottom?) and any spacing/swimlane pattern visible across the input files.
- `08-input-checklist.md` — Per-instance fields the downstream agent must extract before generating a flow. **Tier 1 (must halt if missing)**: flow name, intended `nodeflowType` (Inbound/Outbound), menu structure (digit → target), transfer numbers / ACD queues, voice prompt asset names, business-hour boundaries (if HolidayNode/OfficeHourNode used), CRM lookup contracts (if CRMNode used). **Tier 3 (safe defaults from this KB)**: `scriptType`, universal node attribute defaults, UUID generation strategy.
- `09-gap-log.md` — Remaining uncertainties, assumptions, areas where artifacts disagreed, node types mentioned in docs but absent from artifacts.

**Do not generate** files for: external REST API reference, authentication setup, entity data model, event/webhook contracts, configuration reference. The downstream agent's job is producing NodeFlow JSON, not calling Exotel APIs or wiring webhooks — these concepts don't apply.

## Anti-pattern

- **Do not describe the scripting layer as generic JavaScript.** It's a sandboxed interpreter (`nodeflow.script.interpreter.js`). Extract built-ins and idioms from real `staticValue` bodies; never assume `console`, `fetch`, `require`, `process`, or DOM globals exist.
- **Do not paraphrase event names.** `success.collect.digit`, `hungup.collect.digit`, `script.node.success`, `system.error`, etc. are exact dispatch strings the runtime matches on. Quote them verbatim everywhere.
- **Do not merge variables-and-scripting into the building-blocks file.** The variable system and the expression/script language are a separate subsystem and need their own focused reference; downstream agents will dereference it constantly.
- **Do not include API, auth, or webhook content even partially.** Producing NodeFlow JSON is not the same as integrating with Exotel's REST APIs. Including these sections wastes context and invites the agent to hallucinate an API surface.
- **Do not invent node types.** Only document the node `type`s actually present in the input artifacts; flag absent-but-likely types (e.g. `SmsNode` if mentioned in docs but not in artifacts) under Known Gaps instead of fabricating attribute schemas.
