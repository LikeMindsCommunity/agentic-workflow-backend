---
name: code-agent
description: From a platform-specific Knowledge Base (KB) plus a Statement of Work / solution doc (SOW), generate the CODE the KB describes — an SDK integration, a function, a handler, a glue/script snippet (NOT a whole project) — strictly from the KB's documented API surface, verify it (parse / compile / lint), and INTEGRATE it into the user's target codebase. If the operator names a target directory, integrate there; if none is given, ASK for the integration path before writing — never guess where to land code. The skill is platform-agnostic: every symbol, signature, idiom, and language fact comes from the KB; the SOW (and any inline prompt) says only WHAT to build. Use when an operator points at a KB + SOW and wants the integration code wired into a project. Triggers: "write the SDK code from this KB + SOW", "integrate the {platform} code into <dir>", "code-agent", "build and wire in the {client} integration from the KB and solution doc".
---

# code-agent

Turn a **platform-specific KB** + a **SOW** (the client's statement of work / solution doc, in any form) into the **integration code** that KB describes, verify it, and **wire it into the user's codebase**. **Snippets and integrations, not whole projects.** Nothing is executed.

```
   KB  (the platform's API surface + idioms) ─┐
                                              ├─► generate ─► verify ─► integrate into the target dir
   SOW (what to build, in any form)          ─┘
```

The skill is a **generic engine**. It knows nothing about any platform or SDK and hardcodes nothing — no method name, no signature, no import. It learns the platform entirely from the KB at runtime. Point it at a different KB and it produces a different platform's integration, with no change to the skill.

## Inputs

| Input | Meaning | Required |
|---|---|---|
| `kb=<dir>` | The platform-specific KB directory. The single source of truth for **how** this platform's API/SDK is called (symbols, signatures, idioms, language, conventions). | **Yes** |
| `sow=<path>` | The Statement of Work / solution doc — **what** to build. Any form: prose, `.md`, `.txt`, JSON, YAML, **PDF**, or **DOCX**. The skill extracts and reads it. | **Yes\*** |
| `prompt` / `$ARGUMENTS` | Free-text intent and/or per-build values that refine or override the SOW. | No\* |
| `target=<dir>` / `output=<dir>` | The **directory in the user's codebase** to integrate the code into. **No default — if absent, ASK** (see below). | No (but resolved before writing) |

\*At least one of `sow` or `prompt` must be present. If both are given, the SOW carries the requirements and the prompt carries refinements/values; reconcile them and **ask if they conflict**.

**Beyond these, assume nothing exists.** No sample artifacts, no reference snippet, no hidden config. If you want one, either (a) read it from the KB, (b) take it from the SOW/prompt, (c) read it from the target codebase, or (d) ask.

### The integration directory — ask, don't guess
This skill **lands code inside the user's project**, so the location matters. Resolve it in this order:
1. `target=` / `output=` if the operator gave one → use it.
2. Otherwise the SOW/prompt clearly names a path → use it, and **state which path you picked**.
3. Otherwise **ask the operator for the integration directory before writing anything.** Do not default to `outputs/...`, do not drop code into the repo root, do not guess. Wrong placement is harmful — it can collide with, shadow, or overwrite real source.

Before writing into the chosen directory, **read enough of what's already there** to match its conventions and avoid clobbering existing files.

## Core principles

1. **Platform-agnostic, always.** Every platform fact — class/method/function names, parameters, constants, imports, the SDK's idioms, the declared language — comes from the **KB**. The SOW/prompt supplies only *intent and per-build values*. If a symbol you need isn't in the KB, you do not know it: ask or flag it, **even if the SOW appears to state it**. **Never invent a method name, guess a signature, or pattern-match a plausible-but-undocumented call from general knowledge of "how this kind of SDK usually works."** An unattested symbol compiles in your head and fails at import/call time.
2. **KB is *how*, the SOW is *what*.** The KB carries the API surface; the SOW carries the specific integration to build, expressed using only the KB's real symbols. If the SOW inlines a call that conflicts with the KB, the **KB wins** — surface the conflict rather than silently following the SOW.
3. **Verify before you trust.** Parse, then compile/lint with a real toolchain if one exists (step 5). Code that doesn't parse, or calls a nonexistent symbol, is broken.
4. **Integrate cleanly, don't trample.** Match the target codebase's structure, style, and dependency set. Wire the new code in (imports/exports/registration) the way that codebase already does it. Never overwrite an unrelated file; if a change touches existing code, make the smallest correct edit and say what you changed.
5. **Ask as you go — never force a batch.** See below.

## Asking questions

Ask **only** when the answer would **materially change the code or where it lands** AND it is **not already answered by the KB, the SOW/prompt, or the target codebase**.

- If a reasonable default exists (a KB idiom, a convention visible in the target repo), **take it, state the assumption, and keep going.** Reserve real questions for genuine forks where guessing wrong is costly.
- The **integration directory** is a legitimate blocker — if you cannot resolve it from inputs/SOW, ask for it (see above) before writing.
- Ask **one or a few tightly-scoped questions at a time**, in the flow of the work — never a wall of speculative questions.
- Never ask the operator for platform knowledge that belongs in the KB. If the KB is missing it, say the KB is missing it.

You run **in the main conversation**, so asking mid-flow just works.

## Pipeline

### 1. Learn the platform from the KB
Read the **entire** KB. Determine, from its content alone:
- **What code it enables** (an SDK integration, a function, a handler, a glue script) and in **what language**, with what idioms (error handling, async style, naming, init/config pattern). An explicit KB declaration of its target governs.
- **The API surface** — every class, method, function, parameter, constant, and import you are allowed to call, plus any **reference snippets/examples** the KB ships, to be used **faithfully, not approximated**.
- **What "valid" means** — the checks step 5 will run (parses; compiles/lints; only calls real symbols).

If the KB doesn't document a symbol you need, **say the KB is missing it** — don't guess it from general SDK knowledge.

### 2. Read the SOW and fix the deliverable
Ingest the SOW in whatever form it arrives — prose/`.md`/`.txt` read directly; JSON/YAML parsed; **PDF** via the `pdf` skill; **DOCX** via the `docx` skill — and reduce it to plain requirements. Reconcile with what the KB can produce:
- One clear integration → proceed.
- KB supports several and the SOW is ambiguous → ask one quick question.
- SOW asks for something the KB doesn't cover → say so plainly; don't fabricate API surface.

### 3. Resolve the integration target & plan
Resolve the integration directory (see "The integration directory" above — **ask if unresolved**). Read the target codebase enough to learn its conventions and dependency set. Form an internal, platform-neutral spec of what's being built and how it wires into that project.

### 4. Generate
Produce the code **strictly** from the KB's API surface, idioms, and declared language. Use the KB's reference snippets **verbatim** where it provides them.
- **Call only real symbols.** Every class, method, function, parameter, constant, and import must exist in the KB's documented API surface. When unsure between two, prefer the one **attested in a KB example**.
- **Match the KB's language and idioms** *and* the target codebase's conventions (style, error handling, config). Don't introduce a dependency neither the KB sanctions nor the project already has.
- **A snippet, not a scaffold.** Emit the integration/function itself, not a project skeleton, build tooling, or a generator program.

### 5. Verify and repair
Run the checks the KB implies, strongest-available first:
- **It parses.** Syntactically valid in the declared language.
- **It type-checks / compiles / lints** if a toolchain is available — actually run it with Bash (`tsc`, `python -m py_compile` / a linter, `go build`, etc.). Report what you ran and the result.
- **Symbol reality:** every SDK symbol/method/parameter it calls exists in the KB's API surface (re-check against the KB, not against memory).

Loop **Generate ↔ Verify** until clean or genuinely stuck. If no toolchain exists, say so and fall back to a careful parse + symbol-existence pass. Surface anything unresolved with the reason — **never silently ship a failing check.**

### 6. Integrate and report
Place/edit files in the **resolved target directory**, wiring the code in the way that codebase already does it. Then a short report: **what** was produced, **which files** you created or edited (and the exact edits to existing files), the **key assumptions** you made, any **open questions or checks you couldn't satisfy**, and **how to run/verify** the integration in their project (the build/lint command you ran, or the one they should run if no toolchain was available here).

## Deliverable
An SDK integration, a function, a handler, or a glue script — a **snippet/integration, not a whole project** — written into the user's target directory. Validity is "parses, lints/compiles if a toolchain exists, only calls real symbols from the KB's API surface, and fits the target codebase's conventions without clobbering it."

## Never do this
- Never hardcode a platform fact in the skill, or carry one over from a previous run / general knowledge. The KB is the only authority.
- Never invent a method, signature, parameter, constant, or import to make something fit. If the KB lacks it, say so.
- Never write code into a guessed location — resolve the integration directory or **ask**. Never overwrite an unrelated file.
- Never emit a generator program or scaffold a whole project — the deliverable is the **integration code itself**.
- Never dump a forced wall of clarifying questions. Ask narrowly, when it matters, as you go.

## Folder layout
```
.claude/skills/code-agent/
└── SKILL.md                 ← this file (router + full code pipeline)

outputs/<client>/
└── kb/         ← the KB (input — produced by kb-builder)

<target dir>    ← the user's codebase: the integration is written HERE (asked for if not given)
```
