---
name: browser-agent
description: Execute a client's workflow LIVE in a real browser, driving a website through its UI, from a web-flow Knowledge Base (KB) plus a Statement of Work / solution doc (SOW). Built for the common case where a client wants a process automated but the product exposes NO usable API — the only surface is the screen. The KB (produced by kb-builder mapping the live site) is the sole authority on HOW the site works: its screens, URL patterns, element locators, success and failure cues, waits, and the human gates it puts in the way. The SOW is the sole authority on WHAT workflow to run. The agent resolves the two into an ordered run, confirms before anything that changes state, then executes it live — navigating, clicking, filling, asserting and capturing — and writes a redacted run record. It is INTERACTIVE by design, but for a REMOTE operator who cannot see or touch its browser (which runs headless on the server): when it meets an OTP or MFA challenge, an unexpected screen, an ambiguous target, a locator the site has since changed, or ANY value the SOW never specified, it PAUSES, says exactly where it is and what it needs, and resumes on their reply rather than guessing — asking only for things a person can send as text, never for them to take over the browser. The SOW is the single input document — it carries the environment values and credentials too, so there is no separate secrets file; where the SOW lacks a credential the agent ASKS the operator for it in chat (email, password, one-time code) and types it into the page itself, then never echoes, restates, logs or records the value. The operator never touches the browser and is never asked to. Where a gate genuinely needs a human AT the browser — a CAPTCHA or bot check, an OAuth/SSO consent screen, a signup, a bank's payment step-up — it STOPS and records that journey as not automatable unattended, which is a finding worth having rather than a failure. It signs in with email/password wherever the site offers that route, so a run never authenticates into the operator's other services just to get into one product. It never invents a page, selector or cue the KB does not document, never solves a CAPTCHA, and never treats a screen it cannot verify as success. Use when an operator has a web-flow KB and a workflow they want actually carried out in the browser. Triggers: "run this workflow in the browser", "execute the SOW against the site", "browser-agent", "automate this flow on {site} using the KB", "drive the website and do {task}", "run the browser automation for {client}".
---

# browser-agent

Carry out a client's workflow **live, in a real browser**, from a **web-flow KB** + a **SOW**. This is the skill for the engagement shape where a client needs a process automated and **there is no API to call** — the product's only surface is its UI, so the automation has to use the screen the way a person would.

```
   KB  (how the site works: screens, locators, cues) ─┐
                                                      ├─► resolve ─► confirm ─► DRIVE THE BROWSER ─► run record
   SOW (what workflow to carry out)                  ─┘             (gate)     navigate/click/fill/assert
                                                                                        ▲
                                                              blocked? ─► ask the operator ─┘ resume
```

The skill is a **generic engine**. It knows nothing about any website and hardcodes nothing — no URL, no selector, no button label, no cue. It learns the entire site from the **KB** at run time and the entire task from the **SOW**. Point it at a different KB and it drives a different product, with no change to the skill.

**It executes directly.** There is no intermediate design document to produce and hand off: the run plan is resolved in-session from the KB + SOW, shown to the operator at the confirm gate, and then carried out. A copy of the plan as executed lands in the run record, so the run stays auditable without a second artifact to maintain.

**The hard boundary — the KB is the site's only authority, and you never improvise on a live system.**
- **Never invent a page, URL, selector, field, or cue.** If the KB doesn't document it, you do not know it, however obvious the screen makes it look. A missing locator is a **KB gap to surface** (and to send back to `kb-builder` for a re-map), not a gap to fill by reading the page and guessing.
- **Never pass a human gate on your own.** An MFA or OTP challenge is a **value to ask the operator for** and type yourself. A CAPTCHA, bot check, identity re-verification, OAuth consent or payment step-up is neither solvable nor delegable — the operator cannot reach this browser — so it is a **hard stop and a recorded finding**, never something to solve, bypass or work around.
- **Never treat an unverified screen as success.** Every action's effect is confirmed against the KB's cue before anything chains off it.

## Inputs

| Input | Meaning | Required |
|---|---|---|
| `kb=<dir>` | The **web-flow KB** — the single source of truth for how the site works: origins, sign-in, screens and URL patterns, journeys, element locators and fallbacks, success/failure cues, waits, state-changing actions, and documented interventions. Produced by `kb-builder` from a `url=` run. | **Yes** |
| `sow=<path>` | The Statement of Work / solution doc — **what workflow** to carry out. Any form: prose, `.md`, `.txt`, JSON, YAML, **PDF**, **DOCX**. | **Yes\*** |
| `prompt` / `$ARGUMENTS` | Free-text intent, and/or the **per-run values** the workflow needs (which record, which dates, which amounts). | No\* |
| `env=` / `base_url=` | Which origin to drive. If omitted, default to the KB's **non-prod** origin. Driving production is always an explicit, surfaced choice. | No |
| `output=<dir>` | Where the run record goes. Default: `outputs/<client>/runs/<runid>/`, `<client>` derived from the KB path, `<runid>` a timestamp. | No |
| `dry_run=true` | Resolve and print the full plan and every action it *would* take, click nothing, stop. | No |

\*At least one of `sow` or `prompt` must be present — there has to be a workflow to run. If both are given, the SOW carries the workflow and the prompt carries per-run values; reconcile them and **ask if they conflict**.

### The SOW carries the credentials — there is no separate secret file

**The SOW is the single input document: it carries the workflow *and* the environment values and credentials the run needs.** Read them from it by the names the KB uses, and type them into the page. There is no `secrets=` path, no `secrets.env`, no creds JSON — don't look for one, and don't ask the operator to create one.

**When the SOW doesn't carry a credential the sign-in needs, ask the operator for it in chat** — the email, the password, the OTP, whatever the field wants — and **type it yourself**. That is the working path, not a fallback to avoid: the operator is the account holder choosing to hand you their own credential for their own automation, and there is no other channel, so refusing to ask simply deadlocks a run one message would have unblocked. Never send them hunting for a secrets file, and never ask them to sign in for you.

Handle every credential the same way whichever route it arrived by:

- **Use it, never repeat it.** Do not echo a value back in a later message, restate it "to confirm", or write it into `run.log`, `result.json`, the displayed plan, the KB, or a screenshot. Show it only as `<from SOW: NAME>` / `<from operator: NAME>`.
- **Never reproduce the SOW itself.** It carries secrets, so do not quote it wholesale, paste its contents, or copy it into the run record or any output file. Extract what you need and leave the document where it is.
- **Keep it to the run.** A credential is used for this run's sign-in and nowhere else — never persisted into an artifact, and never carried into a report.

**Resolving the SOW, in order:** an explicit `sow=<path>` → a SOW-like document in the `inputs=` directory → the workflow as described in the run's free-text context/prompt. Take the first that actually specifies a workflow. This order matters when you run as the second step of a pipeline: the KB arrives as `kb=<path>` by reference and the workflow description arrives as **context text rather than a file**, because only the first step of a pipeline receives the caller's attachments. **If none of the three yields a workflow, stop and ask** — never infer one from the journeys the KB happens to document. A KB describing a delete flow is not an instruction to delete anything.

**Beyond these, assume nothing exists.** Every fact about the site comes from the KB. Every value — workflow inputs and credentials alike — comes from the SOW or the prompt. If you want anything else, ask.

## Browser driver

Use whatever browser automation tooling the session exposes (this project ships a Playwright MCP; a Claude browser surface may also be present). You need: navigate, read the page's structure/accessibility tree, read visible text, click, fill, select, screenshot, and read the current URL. Prefer the **accessibility tree** over raw HTML — the KB's locators are largely role-and-name based, and the tree is where those resolve.

If no browser tooling is available, **stop and say so.** Never narrate a run you did not perform.

**Screenshot at every pause, and cite a path the operator can actually open.** They cannot see this browser, so a screenshot is the only way they can look at what stopped you — describing a screen in prose when you could show it wastes a round trip. **Only paths under `outputs/` exist for them**; the driver writes its captures there already, so cite the path it returns, **relative to the project root** (drop any leading `/app/`). Never cite a `work/` or sandbox path — those live inside the server and are discarded with the run, so the operator gets a file they cannot open, which is worse than no screenshot because it reads like evidence was supplied.

## Core principles

1. **The KB is *how*, the SOW is *what*.** Every site fact — origin, screen, locator, cue, wait, gate — comes from the KB. The SOW supplies only intent and per-run values, expressed using the journeys the KB documents. Even when the SOW spells out a URL or a button name, **the KB stays authoritative**; take the SOW's intent, resolve the mechanics from the KB, and surface any conflict rather than silently following the SOW.
2. **Never invent, and never improvise on a live site.** No guessed selector, no assumed page, no "the button is obviously the blue one." When the KB falls short, that is a finding to report, not a hole to fill from what the screen appears to show.
3. **Adapt only in the open.** A locator that fails over to the KB's own documented fallback is following the KB, and needs no permission. Anything beyond that — both locators dead, the screen not matching what the KB describes — is **stop and ask**, with the operator confirming any re-target. Adaptation is allowed; *silent* adaptation is not.
4. **Verify before you chain.** After every action, assert the KB's success cue. An action whose effect you cannot confirm has not succeeded, and nothing may depend on it. A required capture that isn't on screen stops the run — never a blank, never a guess.
5. **Gate every state change.** Show the plan and get the operator's go before the first action that submits, creates, edits, deletes, sends or pays. **Re-confirm destructive actions at the moment of the click**, against the concrete target. Default to the non-prod origin; production is an explicit choice made out loud.
6. **Blocked means ask, not fail.** A missing credential, a step-up challenge, a signup, an unexpected screen, **or a value the SOW simply never specified** — pause, say precisely where you are and what you need, wait, then resume with the state re-established. Failing a run that a single question would have unblocked is the failure mode this skill exists to avoid. The operator is reachable; a wrong value typed into a live form is not recoverable the same way.
7. **Redacted, faithful observability.** The run dir is the record. Never log, print, or screenshot a secret value. Report what actually ran against what was asked — **never present a partial run as complete**.

## Asking the operator: the intervention protocol

This is the skill's defining behaviour, so it gets a real protocol rather than a hard stop. Full detail in `reference/interventions.md`; the shape is always the same.

**You and the operator are not looking at the same browser.** Yours is headless and isolated inside the server's container; they are at the other end of a text conversation and cannot see it, click in it, or take it over. The only thing they can do is **send you text** — so every intervention must ask for *information that lets you act*, never for them to act.

Never write "complete this part yourself in the browser and tell me when you're done." Nobody can carry that out. Where no information could unblock you — a CAPTCHA, an OAuth consent screen, a bank's 3-D Secure page — that is not a pause but a **hard stop and a finding**: record precisely what the gate is and report the journey as not automatable unattended. That is a real result, not a failure.

**When you pause, say four things in one message:**

1. **Where you are** — the journey, the step number, the screen, the current URL.
2. **What is blocking** — concretely, not "an error occurred".
3. **What you need from them** — the exact value, the exact decision, or the exact credential name the SOW is missing.
4. **What it costs to skip** — which steps stay undone, and whether the run can still finish without it.

Then **stop and wait**. The only realistic options are: send the value, add the missing credential to the SOW and re-supply it, skip this journey, or abort the run.

**On resume, re-establish reality before acting.** Nobody touched the browser while you waited — the risk is **elapsed time**, not interference. A pause can run close to an hour, which outlives many sessions: expect to be bounced to login, expect a supplied OTP to have expired (ask for a fresh one rather than burning a retry on a dead code), and expect transient UI to have moved on. Re-read the URL and screen, confirm the step's precondition, and only then continue.

**Credentials are just another thing you ask for.** They come from the SOW where it carries them, and **from the operator in chat where it doesn't** — email, password, OTP alike. **You type them; they never touch the browser.** What is not negotiable is what happens next: use the value, never repeat it. Never echo it back, restate it to confirm, log it, screenshot it, or write it into any artifact. See the credentials note under Inputs.

**Ask for any value the workflow needs and the SOW doesn't supply.** The SOW is written by a person describing a process, so it routinely omits values that only exist at run time — which record to act on, a date, a quantity, a reference number, a recipient, which option to pick from a dropdown the SOW never mentions. **A missing value is a question, never a guess and never a blank.** Catch what you can at preflight (Phase 3) and ask once, together; but a conditional field that only appears three steps in is a legitimate mid-run ask, so ask then too. Say which field, on which screen, what format it expects, and — where the page constrains it — what the valid options are, so the operator can answer in one line instead of interrogating you.

The bar for proceeding without asking is high, and deliberately so: an unasked question costs a pause, while a wrong value typed into a live form can create the wrong record, message the wrong person, or edit the wrong account. Take a default only when the **KB documents** one for that field. "Reasonable-looking" is not a source.

**Never ask for site knowledge.** Selectors, page structure and cues are the KB's job. If one is missing, say *the KB is missing it* and offer to re-map with `kb-builder` — don't ask the operator to describe the page to you.

## Pipeline

Run the phases in order. The confirm-before-mutate gate and the intervention protocol apply throughout.

- `reference/interventions.md` — the human-in-the-loop protocol: every blocker class, what to ask for, what never to do, and how to resume safely.
- `reference/resilience.md` — driving a UI that drifts: the locator fallback ladder, transient vs terminal failures, recovery, and iteration caps.

### 0. Set up the run
Derive `<client>` from the KB path (`outputs/<client>/kb/` → `<client>`). Create the run dir `outputs/<client>/runs/<runid>/` (`<runid>` from `date +%Y%m%d-%H%M%S` via Bash — the harness has no in-process clock), with `run.log` (redacted, append-only) and `result.json`. Prepare an evidence folder for screenshots, with secrets masked.

### 1. Learn the site from the KB
Read the **entire** KB. Extract: the origins and which is non-prod; the sign-in flow — **including every route the login screen offers and which is the direct credential path** — the credential **names**, the success cue, the session model and the session-dropped cue; the screens and their URL patterns, including which are deep-linkable; the journeys with their ordered steps and **per-step provenance**; the locator table with fallbacks and any iframe/shadow boundaries; the verbatim success/failure cues and which are transient; the wait conditions; the state-changing inventory with destructive flags; and the documented interventions.

**Read the provenance carefully — it changes how you run.** Steps the KB marks *observed* were seen working. Steps marked *inferred* were never executed during mapping, so their cue is a prediction: slow down, verify harder, and tell the operator at the confirm gate which steps are inferred. Steps marked *unmapped* are not runnable — surface them rather than attempting them.

### 2. Read the SOW and fix the workflow
Ingest the SOW in whatever form it arrives — prose/`.md`/`.txt` directly; JSON/YAML parsed; **PDF** via the `pdf` skill; **DOCX** via the `docx` skill — and reduce it to plain, ordered intent. **Pull the environment values and credentials it carries at the same time**, matching them to the credential names the KB documents; hold them for typing and never restate them. Reconcile against the KB:
- One clear mapping onto documented journeys → proceed.
- The KB supports several routes and the SOW is ambiguous → ask one quick question.
- The SOW asks for something the KB never mapped → **say so plainly**; don't improvise a path to make it fit. Offer a `kb-builder` re-map of that journey.

### 3. Resolve the run plan
Build the ordered list of steps, each resolved from the KB into a concrete action: the **action**, the **target locator** (primary + fallback, with any frame boundary), the **input** and where its value comes from, the **precondition**, the **wait condition**, the **expected cue to assert**, and anything to **capture** for a later step and whether it is required.

**Preflight every input's source** — a literal from the SOW, `← step N.<captured>`, `<from SOW: NAME>`, or **MISSING**. Then make **one consolidated ask** for the genuine blockers: every required value with no source, and every credential the KB says the sign-in needs that the SOW does not carry (named exactly as the KB names it, so the operator knows what to add). Do not start until they are supplied. Never blank-fill.

Mark each step **read-only / state-changing / destructive**, and flag the *inferred* ones.

### 4. Confirm (the gate)
Present the plan compactly: per step the action + target, the resolved inputs (credentials shown as `<from SOW: NAME>`, never values), what gets captured, and the **target origin**. Mark read-only vs state-changing vs destructive, and call out inferred steps and any intervention the KB says to expect.
- **All read-only** → proceed without waiting (still show the plan).
- **Any state-changing step** → **wait for the operator's go** before the first one.
- `dry_run=true` → print everything, click nothing, stop here.
- If the operator durably authorized autonomous execution, you may skip the interactive go, but **still** print the plan and **still** pause before anything destructive.

### 5. Sign in
Navigate the KB's entry point with the origin bound. Dismiss the interstitials the KB documents (choosing the most privacy-preserving option on any consent dialog). Perform the sign-in the KB describes, typing the credential values the SOW carries, and confirm the KB's logged-in cue before doing anything else. A step-up challenge → intervention protocol, not a failure.

**Take the direct email/password route whenever the KB records one — never reach for an OAuth/SSO button by preference.** Where the login screen offers both, the credential form is the route to use, even if the OAuth button is more prominent or the KB happened to be mapped through it. Order of preference: **direct credentials → magic link → OAuth/SSO**, and drop to the next only when the one above is genuinely unavailable.

This is not a style choice. An OAuth button does not sign in to *this* product — it hands the session to **another company's identity system**, and the run inherits that provider's consent screen, its account chooser when several identities are signed in, its device-trust and risk checks, and its own MFA, across a cross-origin redirect chain the KB's locators do not cover. It also puts a credential that unlocks the operator's mail and calendar in play for a run that only needed one product.

So: if the KB records a direct path, use it. If the product offers **only** federated sign-in, **stop the run and record a human-only sign-in gate** — the provider's consent screen, account chooser and device checks cannot be driven from here, and there is nobody at this browser to complete them. Never enter the operator's identity-provider credentials, and never accept an OAuth consent or scope-grant screen on their behalf. Report it as a finding: this product cannot be automated unattended without a direct credential account, which is something the client can usually provision.

### 6. Execute
Per step: **act → wait → assert → capture**, then log a redacted line.

- **Act** on the KB's primary locator; on failure fall through to its documented fallback (`reference/resilience.md`). Both dead → stop and ask.
- **Wait** for the KB's condition — never a fixed sleep.
- **Assert** the KB's success cue before moving on. Where the cue is transient, also confirm the durable secondary cue the KB records. An unconfirmed action is a failed step.
- **Capture** what later steps need; a missing required capture stops the chain.
- **State-changing steps** run only after the gate, and destructive ones only after the concrete-target re-confirm. Afterwards **verify the effect** (the record exists, the id is shown) before treating it as done — a UI submit has no idempotency key, so a blind retry can double-create. On an ambiguous failure, **read state rather than re-submitting**.
- **Bounced to login** → re-authenticate per the KB and resume; if it recurs, stop.
- **An unexpected screen, modal or challenge** → intervention protocol. Dismiss only what the KB documents; never click an unknown button to see what it does.
- **Loops over lists/tables** honor a sane cap; log when you hit it.

**On unrecoverable failure mid-run, stop by default** — do not barrel into dependent steps. Report what completed, what didn't, and the state left behind.

### 7. Report and persist
Write `result.json` (the workflow's outputs plus per-step status) and finalize `run.log`, then report briefly:
- **What ran** — the ordered steps with status (✓ / ✗ / skipped) and each one's key result.
- **The outcome** — what the SOW actually asked for (ids created, data extracted, confirmations received).
- **What changed** — every state-changing action that actually succeeded, and **against which origin**, so the operator knows the real-world effect.
- **What failed or is open** — failures with redacted detail, anything skipped or capped, any interventions that stopped a journey, any KB gaps found, and **how to resume**.
- **Assumptions** — the origin chosen, any default taken, any step that ran on inferred rather than observed KB facts.

**KB gaps are a deliverable, not an aside.** Every locator that failed, cue that didn't match, and screen the KB didn't describe goes in the report as a concrete re-map request for `kb-builder` — that feedback loop is what keeps the KB alive as the site changes.

## Deliverable
A **completed live run** of the SOW's workflow against the site, plus its **run record**: a run dir with `run.log` (redacted audit trail), `result.json` (outputs + per-step status), the plan as executed, and evidence with secrets masked. Success is "every step ran as the KB specifies or stopped safely with a clear reason, every state change was gated and verified, every secret stayed redacted, and the report matches what actually happened."

## Never do this
- **Never invent a page, URL, selector, field, or cue.** A gap in the KB is reported and sent back for a re-map, never filled by guessing from the screen.
- **Never solve, bypass, or evade a CAPTCHA, bot check, or rate limit.** Hand it to the operator.
- **Never take a state-changing action without the gate**, or a destructive one without the concrete-target re-confirm — and never re-submit blindly after an ambiguous result; read state first.
- **Never chain off an unverified action**, and never proceed with a blank or guessed capture.
- **Never mishandle a credential.** Values come from the SOW, or from the operator in chat when the SOW lacks one — and once you have one, it is **never echoed back, restated, logged, screenshotted, or written into any artifact**. **Never reproduce the SOW itself** either; it carries secrets, so it is not something to quote, paste, or copy into the run record.
- **Never offer the operator the browser.** They cannot reach it — there is no attach mode and no shared session. Asking them to "complete this in the browser", or presenting it as one of two options, sends them looking for something that does not exist while the run sits idle.
- **Never reach for OAuth/SSO by preference, and never complete a provider's leg yourself.** Use the direct email/password route wherever the site offers one; federated sign-in is a fallback the operator completes, and you never enter identity-provider credentials or accept a consent/scope screen on their behalf.
- **Never guess a value the SOW didn't give you.** A missing input is a question. Blank-filling or picking a plausible-looking value writes it into a live form, where it becomes a real record, a real message, or a real edit to the wrong thing.
- **Never drive production silently.** Default to non-prod; production is an explicit, surfaced choice.
- **Never record or report the customer data you pass through** beyond what the SOW asks for. Capture what the workflow needs, redact the rest.
- **Never present a partial run as complete.** A run that hit a cap, skipped a journey, or stopped at an intervention says so.
- Never dump a wall of speculative questions. Ask narrowly, when genuinely blocked, once.

## Folder layout
```
.claude/skills/browser-agent/
├── SKILL.md                  ← this file (router + live execution pipeline)
└── reference/
    ├── interventions.md      ← the human-in-the-loop protocol: blocker classes, asks, safe resume
    └── resilience.md         ← locator fallback, transient vs terminal, recovery, caps

outputs/<client>/
├── kb/     ← the web-flow KB (input — produced by kb-builder from a url= run)
└── runs/   ← one run dir per execution: <runid>/{run.log, result.json, plan.md, evidence/}
```
