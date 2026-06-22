# Use case: config — generate a structured config

Produce the **config** the KB describes (JSON / XML / YAML / a NodeFlow JSON / any structured file a platform ingests) and verify it. Nothing is executed.

**Follow the shared generation backbone in `SKILL.md`** (1 Learn the KB → 2 Understand the request → 3 Plan → 6 Deliver). This file defines only the two steps that are config-specific: **Generate (4)** and **Verify (5)**.

## 4. Generate (config)
Produce the artifact **strictly** from the KB's grammar / schema / templates / idioms. Use the KB's reference structures verbatim where it provides them (an alias→JSON map, a template snippet, a canonical example). Use no platform knowledge that is not in the KB.

**Fixed per-type constants — copy, never choose or coin.** For any value the KB marks fixed-per-type (data-provider ids, port ids, engine/interpreter identifiers, class discriminators, etc.), copy the **exact value the KB's reference/template gives for that exact type** — including when it is `null`. Do **not** pick an alternative from a documentation "options"/prose list, and do **not** synthesize one by pattern-matching the type's name (e.g. coining `<type>.data.provider`). A documentation "option" attested in **no** known-good example is unverified: a plausible-but-unregistered constant passes structural checks and then crashes the platform at import (a null-registry lookup). When in doubt, prefer the value **attested in a known-good reference flow** over anything that appears only in a comment.

## 5. Verify and repair (config)
Run the validity checks the KB implies:
- Structural / schema validity; required fields present; references resolve; enums and values legal; naming conventions honored.
- **Validate every fixed-per-type constant and enumerated value against the KB's allowed set for that type** — and when the KB ships known-good reference flows, the value must match one **attested** there, not merely something a comment lists as possible. A value that is documented-but-unattested is a failed check: replace it with the attested value or flag it. (This is the silent-invalid class — structurally fine, rejected by the platform.)

Loop Generate↔Verify until clean or genuinely stuck. Surface anything unresolved with the reason — never silently ship a failing check.

## Deliverable
A structured config file: JSON / XML / YAML / a visual-flow JSON (e.g. NodeFlow `.anfx`) / any file a platform ingests. Validity is structural + schema + reference integrity, graded against the KB (and a known-good reference if the KB names one).
