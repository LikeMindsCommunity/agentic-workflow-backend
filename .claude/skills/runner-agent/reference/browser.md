# Reference: drive the UI live (runner — browser surface)

How a **browser-agent Runner** carries the workflow out through the product's web UI **at run time**. **The LLD/ED documents every page, action, locator, and cue; this file is the playbook for executing whatever the LLD specifies.** Never invent a page, field, selector, or cue the LLD doesn't give, and never open the KB — the LLD is self-contained and is the only authority. A missing locator or cue the flow needs is a **defective LLD to surface**, not a gap to guess from how the page "probably" looks.

The same boundaries as the cURL surface hold: **read the LLD alone, source secret values yourself (never from the document), bind the LLD's symbolic origin (default non-prod), confirm before any state-changing action, and redact typed secrets.**

## Entry & session (sign-in)

- **Entry point.** Navigate the landing URL/path the LLD's flow starts from, with `{base_url}` bound to the chosen environment (default non-prod) — never a hardcoded host.
- **Login flow (if any).** Go to the LLD's login page, fill the fields it names to the credentials by the LLD's exact name (`<from secrets: NAME>`), submit, and confirm the success cue the LLD gives (redirect to a dashboard, a visible logged-in element). You supply and type the values; never log them.
- **Session continuity.** Keep the logged-in state in the browser context between steps; if a step bounces to login, re-authenticate per this section, then resume. If it recurs, stop.
- **Can't-run-unattended flows.** If sign-in needs MFA, a CAPTCHA, or an emailed/SMS code, **surface and stop** — you cannot complete it autonomously.

## Per-step UI action — execute what the LLD specifies

For each step, fully resolved from the LLD:

- **act** — `navigate` / `click` / `fill` / `select` / `upload` / `hover` / `assert`, on the **target element** the LLD gives (a stable selector, a `data-testid`, or an accessible name/role + text). Never invent or guess a locator; a missing one is a defect to flag.
- **precondition** — confirm you're on the screen the LLD requires first, and honor any guard ("only click Delete if the row's status is Inactive").
- **inputs** — literal values from the LLD, or `← step N.<captured>` when chained; credential fields typed from `<from secrets: NAME>`.
- **wait** — wait for the LLD's condition (element visible / network idle / URL match) with a timeout, rather than a fixed sleep.
- **assert** — verify the LLD's success cue (a URL change, a visible toast/banner, an element appearing/disappearing, a field value) **before moving on**. An unconfirmed result is not a success — don't chain off it.
- **capture** — read any on-screen value the LLD marks for a later step; if a **required** capture is absent, **stop the chain** — never fabricate it.

## Failure & recovery

| Symptom | Likely cause | Action |
|---|---|---|
| **Element not found** | page not loaded yet, wrong screen, changed UI | wait per the step's condition; if still absent, **stop** — don't click blindly into the wrong place |
| **Stale element / re-render** | DOM replaced after an action | re-locate the element before acting; don't reuse a stale handle |
| **Navigation timeout** | slow load, wrong URL, network | retry the navigation per the policy; after the cap, stop and report |
| **Unexpected modal / popup / cookie banner** | consent dialog, interstitial | dismiss only if the LLD documents it; otherwise **surface** — don't click unknown buttons |
| **Bounced to login** | session expired | re-authenticate (sign-in section), then resume; if it recurs, stop |
| **Assertion failed** (expected state absent) | the action didn't take effect | a failed step — do **not** proceed down the chain on an unconfirmed result |
| **MFA / CAPTCHA appears** | anti-automation / step-up auth | can't run unattended — **surface to the operator** |

**Transient vs terminal:** element-not-yet-visible and navigation flake are **transient** — retry within the policy. A missing page, a missing LLD-documented element, or a failed assertion is **terminal for that step** — stop, don't cascade.

## Safety, idempotency & observability (browser)

- **Confirm before any state-changing UI action.** Submitting a form, creating/editing/deleting a record, or paying is the browser analog of a mutating call — it goes behind the Phase 4 confirm-before-mutate gate, and a **destructive** action (delete, irreversible, money-moving) is **re-confirmed at the moment of the click** with the concrete target.
- **Environment.** Bind the LLD's symbolic origin to the chosen environment; **default to non-prod**. Acting on the prod site is an explicit, surfaced run-time choice.
- **Idempotency.** A UI submit usually carries **no idempotency key**, so a blind re-submit can **double-create**. After a state-changing action, **verify the effect** (the record appears, the id is shown) before treating it as done; on an ambiguous failure, read state rather than re-submitting.
- **Broken chain.** A required captured value that isn't on screen → **stop**; never proceed with a blank/guessed value.
- **Redaction.** Never log typed secret values; mask them in any step log or screenshot. Capture evidence only as the LLD's redaction policy allows.
- **Cap & report.** Loops over a list/table honor the LLD's cap; log when you hit it, and never present a truncated run as complete.
