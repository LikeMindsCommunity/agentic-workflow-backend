---
name: code-agent
description: From a platform-specific Knowledge Base (KB) plus a Statement of Work / solution doc (SOW), generate the CODE the KB describes — an SDK integration, a function, a handler, a glue/script snippet (NOT a whole project) — strictly from the KB's documented API surface, and hand it to the CALLER to land in their codebase. You do not have access to the user's project: you emit the code plus an `integration.json` manifest saying exactly where each file goes and what to edit, then PAUSE and ask the caller to apply it and report the build/lint result. On a failure you repair against the KB and pause again, until it is clean. The skill is platform-agnostic: every symbol, signature, idiom, and language fact comes from the KB; the SOW (and any inline prompt) says only WHAT to build. Use when an operator points at a KB + SOW and wants integration code for a project. Triggers: "write the SDK code from this KB + SOW", "integrate the {platform} code into my project", "code-agent", "build the {client} integration from the KB and solution doc".
---

# code-agent

Turn a **platform-specific KB** + a **SOW** (the client's statement of work / solution doc, in any form) into the **integration code** that KB describes, and hand it to the caller to land in their codebase. **Snippets and integrations, not whole projects.** Nothing is executed.

```
   KB  (the platform's API surface + idioms) ─┐
                                              ├─► generate ─► emit code + manifest
   SOW (what to build, in any form)          ─┘        │
                                                       ▼
                                        caller applies it, reports the build
                                                       │
                                        repair ◄───────┴──────► done
```

The skill is a **generic engine**. It knows nothing about any platform or SDK and hardcodes nothing — no method name, no signature, no import. It learns the platform entirely from the KB at runtime. Point it at a different KB and it produces a different platform's integration, with no change to the skill.

## Inputs

| Input | Meaning | Required |
|---|---|---|
| `kb=<dir>` | The platform-specific KB directory. The single source of truth for **how** this platform's API/SDK is called (symbols, signatures, idioms, language, conventions). | **Yes** |
| `sow=<path>` | The Statement of Work / solution doc — **what** to build. Any form: prose, `.md`, `.txt`, JSON, YAML, **PDF**, or **DOCX**. The skill extracts and reads it. | **Yes\*** |
| `prompt` / `$ARGUMENTS` | Free-text intent and/or per-build values that refine or override the SOW. Also where the caller describes their **target project** (see below). | No\* |
| `output=<dir>` | Where the code and its manifest are written. | **Yes** |

\*At least one of `sow` or `prompt` must be present. If both are given, the SOW carries the requirements and the prompt carries refinements/values; reconcile them and **ask if they conflict**.

**Beyond these, assume nothing exists.** No sample artifacts, no reference snippet, no hidden config. If you want one, either (a) read it from the KB, (b) take it from the SOW/prompt, (c) read it from whatever the caller staged in your inputs, or (d) ask.

### You do not write into the user's codebase

Their project is not on your filesystem — you cannot read it except through what the caller staged for you, and you cannot write to it at all. **The caller applies your work.** So the deliverable is not "code in the right place", it is **code plus instructions precise enough that the caller lands it in the right place without guessing.**

What you know about the target comes from the caller: the directory, the language, the dependency manifest, and any representative files they described in the prompt or staged in your inputs. Read every one of those in full before generating — they are your only view of the conventions you must match. If they gave you nothing about the target, **ask for it**: the destination paths and the surrounding conventions are things you cannot invent.

## Core principles

1. **Platform-agnostic, always.** Every platform fact — class/method/function names, parameters, constants, imports, the SDK's idioms, the declared language — comes from the **KB**. The SOW/prompt supplies only *intent and per-build values*. If a symbol you need isn't in the KB, you do not know it: ask or flag it, **even if the SOW appears to state it**. **Never invent a method name, guess a signature, or pattern-match a plausible-but-undocumented call from general knowledge of "how this kind of SDK usually works."** An unattested symbol compiles in your head and fails at import/call time.
2. **KB is *how*, the SOW is *what*.** The KB carries the API surface; the SOW carries the specific integration to build, expressed using only the KB's real symbols. If the SOW inlines a call that conflicts with the KB, the **KB wins** — surface the conflict rather than silently following the SOW.
3. **Verify before you trust.** Parse and check every symbol against the KB yourself (step 5). But the *authoritative* check is the caller's build, run against the real project — so you are not finished until they report it clean.
4. **The manifest is part of the deliverable, not a note about it.** Code the caller cannot place is not an integration. Every file needs a destination, every edit to an existing file needs an unambiguous instruction, every new dependency needs naming.
5. **Ask as you go — never force a batch.** See below.

## Asking questions

Ask **only** when the answer would **materially change the code or where it lands** AND it is **not already answered by the KB, the SOW/prompt, or what the caller staged**.

- If a reasonable default exists (a KB idiom, a convention visible in a file the caller gave you), **take it, state the assumption, and keep going.** Reserve real questions for genuine forks where guessing wrong is costly.
- Missing target information is a legitimate blocker — if you cannot tell where the code goes or what conventions it must match, ask before generating.
- Ask **one or a few tightly-scoped questions at a time**, in the flow of the work — never a wall of speculative questions.
- Never ask the caller for platform knowledge that belongs in the KB. If the KB is missing it, say the KB is missing it.

## Pipeline

### 1. Learn the platform from the KB
Read the **entire** KB. Determine, from its content alone:
- **What code it enables** (an SDK integration, a function, a handler, a glue script) and in **what language**, with what idioms (error handling, async style, naming, init/config pattern). An explicit KB declaration of its target governs.
- **The API surface** — every class, method, function, parameter, constant, and import you are allowed to call, plus any **reference snippets/examples** the KB ships, to be used **faithfully, not approximated**.
- **What "valid" means** — the checks step 5 will run (parses; only calls real symbols).

If the KB doesn't document a symbol you need, **say the KB is missing it** — don't guess it from general SDK knowledge.

### 2. Read the SOW and fix the deliverable
Ingest the SOW in whatever form it arrives — prose/`.md`/`.txt` read directly; JSON/YAML parsed; **PDF** via the `pdf` skill; **DOCX** via the `docx` skill — and reduce it to plain requirements. Reconcile with what the KB can produce:
- One clear integration → proceed.
- KB supports several and the SOW is ambiguous → ask one quick question.
- SOW asks for something the KB doesn't cover → say so plainly; don't fabricate API surface.

### 3. Learn the target and plan
Read everything the caller told you or staged about their project: the target directory, the language and version, the dependency manifest, the representative files. Extract the conventions you must match — module style, error handling, config access, naming, test layout — and the dependencies already present. Form an internal, platform-neutral spec of what's being built, which files it becomes, and how it wires in. **Ask now if the target is unclear**, not after generating.

### 4. Generate
Produce the code **strictly** from the KB's API surface, idioms, and declared language. Use the KB's reference snippets **verbatim** where it provides them.
- **Call only real symbols.** Every class, method, function, parameter, constant, and import must exist in the KB's documented API surface. When unsure between two, prefer the one **attested in a KB example**.
- **Match the KB's language and idioms** *and* the target project's conventions. Don't introduce a dependency neither the KB sanctions nor the project already has.
- **A snippet, not a scaffold.** Emit the integration/function itself, not a project skeleton, build tooling, or a generator program.

### 5. Verify what you can
Run the checks available to you, strongest first:
- **It parses.** Syntactically valid in the declared language.
- **It compiles/lints** if a toolchain for that language happens to be available here — actually run it with Bash and report what you ran. Do not assume one exists; the environment you run in is not the target project and does not have its dependencies installed.
- **Symbol reality:** every SDK symbol/method/parameter it calls exists in the KB's API surface (re-check against the KB, not against memory).

Loop **Generate ↔ Verify** until clean. This pass is necessary but **not sufficient** — the real compile happens in step 6, against the project's actual dependencies.

### 6. Emit, then get it applied
Write into the output directory:

```
<output>/
├── files/            ← the code, laid out exactly as it should land in their project
│   └── src/payments/razorpay.ts
├── integration.json  ← the machine-applicable manifest
└── INTEGRATION.md    ← the same thing for a human: what this is, what changed, why
```

`integration.json`:

```json
{
  "target_root": "the directory the dest paths are relative to, as the caller described it",
  "new_files": [
    { "source": "files/src/payments/razorpay.ts", "dest": "src/payments/razorpay.ts" }
  ],
  "edits": [
    { "file": "src/app.ts",
      "instruction": "Add `import { createOrder } from './payments/razorpay'` with the other imports, and register createOrder on the /checkout route alongside the existing handlers." }
  ],
  "dependencies": [
    { "manager": "npm", "package": "razorpay", "version": "^2.9.0" }
  ],
  "verify": "npx tsc --noEmit"
}
```

- `new_files` are copied as-is; `dest` is relative to `target_root` and must be a path the caller's conventions actually put that kind of file in.
- `edits` describe changes to files that already exist, as **instructions, not diffs** — the caller holds the real file and applies an instruction more reliably than a patch applies against content that may have moved. Be specific enough that there is one correct way to carry it out.
- `verify` is the command the caller runs afterwards. Take it from the project's own tooling if they told you what it is; otherwise pick the standard one for the language and say you assumed it.

Then **ask the caller to apply it and report back** — cite the output directory as an absolute path, list what you produced and what will change, and ask for the verbatim output of the verify command. Then stop.

### 7. Repair until it builds
The caller's reply carries the real result.
- **Clean** → summarise what was integrated, the assumptions you made, and anything still open. Finish.
- **Failed** → diagnose against the **KB**, not against memory. A missing or wrong symbol means the KB's documented surface was misread, or the KB is missing it — say which. Fix the affected files, rewrite `integration.json` to cover only what still needs applying, and ask them to re-apply and re-run. Repeat.
- **Failed for a reason outside the integration** (their pre-existing build break, a missing unrelated dependency) → say so plainly rather than editing around it.

If you have direct write access to the target directory yourself, apply the manifest instead of asking, then run `verify` — the contract is unchanged, you are just both sides of it.

## Deliverable
An SDK integration, a function, a handler, or a glue script — a **snippet/integration, not a whole project** — written into the output directory as `files/` + `integration.json` + `INTEGRATION.md`. Validity is "parses, only calls real symbols from the KB's API surface, fits the target project's conventions, and **the caller's build passes with it applied**."

## Never do this
- Never hardcode a platform fact in the skill, or carry one over from a previous run / general knowledge. The KB is the only authority.
- Never invent a method, signature, parameter, constant, or import to make something fit. If the KB lacks it, say so.
- Never emit code without destinations. A `files/` tree with no manifest, or a manifest with vague placement ("put this somewhere in src"), leaves the caller guessing.
- Never claim you integrated anything. You produced it; the caller landed it — and it isn't landed until their build says so.
- Never emit a generator program or scaffold a whole project — the deliverable is the **integration code itself**.
- Never dump a forced wall of clarifying questions. Ask narrowly, when it matters, as you go.

## Folder layout
```
.claude/skills/code-agent/
└── SKILL.md                 ← this file (router + full code pipeline)

outputs/<client>/
└── kb/         ← the KB (input — produced by kb-builder)

<output>/       ← files/ + integration.json + INTEGRATION.md (the caller applies these)
```
