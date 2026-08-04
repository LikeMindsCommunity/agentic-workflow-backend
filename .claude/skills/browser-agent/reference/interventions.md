# Reference: the intervention protocol (human in the loop)

Unattended browser automation meets things it must not pass alone. Some are security controls doing their job, some are the site changing under you, some are decisions that are not yours to make. **A run that dies at one of these when a single question would have unblocked it has failed unnecessarily** — and a run that pushes through one it should have surfaced has done something worse.

The rule is the same for all of them: **pause, ask precisely, wait, re-establish reality, resume.**

## The ask format

Whenever you pause, one message, four things:

1. **Where you are** — journey, step number, screen name, current URL.
2. **What is blocking** — concretely. "Sign-in sent a 6-digit code to a phone ending 4417", not "authentication issue".
3. **What you need** — the specific value, the specific decision, or the specific thing for them to do in the browser.
4. **What skipping costs** — which steps stay undone, and whether the run can still finish.

Then offer the realistic options and **stop**:

> **supply it** · **do it yourself in the browser and tell me to continue** · **skip this journey and carry on** · **abort the run**

Ask for one blocker at a time as you hit it — this is a live run, not a planning phase, and a speculative list of everything that *might* block is noise.

## Blocker classes

| Class | What you see | What to do | Never |
|---|---|---|---|
| **Missing credential** | The secret source has no value for a name the KB lists | Name it exactly as the KB does, say which source you read, ask them to add it there — **or** to sign in themselves and hand back | Never ask for a password or API key in chat; never try a guess or a default |
| **MFA / OTP / device trust** | A code field after a correct password; "we sent a code to…" | Ask for the code directly — it is single-use and short-lived, so this one is fine to receive in chat | Never ask them to disable MFA; never retry the login loop hoping to skip it |
| **CAPTCHA / bot check / "unusual activity"** | A challenge widget, a slider, an interstitial, a lockout notice | Stop. Explain what fired, that you will not attempt it, and offer to let them clear it in the browser and hand back | **Never** attempt to solve, script around, or evade one. Never rotate identity to avoid detection |
| **Signup / account creation** | The journey needs an account that doesn't exist | Stop and ask. Account creation binds the client to terms and creates a real identity — it is their decision, not yours | Never create an account, accept terms, or agree to a privacy policy on your own |
| **Payment authorization** | A card form, a 3-D Secure step, a bank redirect | Stop. Present the exact amount, payee and method, and require explicit confirmation. Any bank/OTP leg is theirs to complete | Never enter card or bank details; never confirm a payment on an implied go-ahead |
| **OS-level handoff** | A native file picker, a download prompt, a print dialog | Say which file is expected and where. Use the driver's upload/download affordance if the KB documents one; otherwise hand over | Never accept a download the SOW didn't ask for; never execute a downloaded file |
| **Third-party SSO redirect** | Bounced to an identity provider | Continue only if the KB documents that leg and the credential exists; otherwise hand over so they can complete it | Never grant OAuth scopes or accept a consent screen on your own |
| **Unexpected screen** | A page the KB doesn't describe — an interstitial, a survey, a plan-upgrade wall, a maintenance notice | Stop, screenshot, describe what's on screen, ask how to proceed | Never click an unknown button to find out what it does |
| **Ambiguous target** | The locator matches several elements, or the SOW's value matches several rows | Stop and list the candidates with what distinguishes them; let them pick | Never take the first match. On a mutating step this picks a victim at random |
| **KB gap** | Primary and fallback locators both dead; the cue never appears; the screen contradicts the KB | Stop, report it as a concrete re-map request. Offer to re-target by the KB's *described* element — role and accessible name — with them confirming the match | Never silently re-derive a selector from the page and carry on |
| **Destructive action** | The next step deletes, cancels, sends, publishes or pays | Re-confirm at the moment of the click, naming the **concrete target** — the actual record, id, recipient, amount — not the plan | Never rely on the earlier plan-level go-ahead for a destructive step |
| **Rate limit / lockout / maintenance** | Throttling, a temporary block, a scheduled-downtime page | Stop and report. Suggest resuming later; note where the run reached | Never hammer, never rotate identity, never work around the limit |

## Resuming safely

**After any pause, and especially after a human has touched the browser, re-establish reality before acting.** They may have navigated elsewhere, dismissed a dialog, completed extra steps, signed in as a different user, or opened a new tab.

1. Read the **current URL and screen**, and compare against the step's precondition from the KB.
2. If it matches → continue from the step you paused at.
3. If they completed the step for you → **verify its effect** by the KB's cue, mark it done, and continue from the next one. Do not redo it — on a mutating step that double-creates.
4. If you are somewhere else entirely → navigate back by the KB's documented route (a deep link if the KB records one), re-assert, and only then continue.
5. If you cannot tell where you are → stop and ask rather than clicking to find out.

Never resume on the assumption that the browser is where you left it.

## What goes in the run record

Log every intervention as a first-class event: which class, at which step, what was asked, what came back (**redacted** — never the credential value, never the OTP), and what happened next. A run that paused three times and finished is a successful run with three interventions, and the record should read that way.

**Interventions are also product feedback.** A gate that fires every run is something the KB should predict rather than discover — report it so `kb-builder` can record it, and the next run can warn the operator up front instead of stalling mid-flow.
