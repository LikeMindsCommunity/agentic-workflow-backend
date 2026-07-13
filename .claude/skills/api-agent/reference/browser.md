# Reference: what the LLD/ED must specify for a browser-agent Runner (browser mode)

This skill **designs**; it never drives a browser. This file is the checklist for a `browser`-mode LLD/ED — everything a **browser-agent Runner** needs to carry the workflow out through the product's web UI, written down so the Runner needs nothing but this document, the credential values it sources itself, and the site it's pointed at. **The KB documents the product's web flows; this file is the template for how to turn them into a self-contained, declarative runbook.** Never assume a page, field, or selector the KB doesn't document, and **never read, type, store, or embed a credential value** — the LLD/ED names credentials only.

The same boundaries as curl mode hold: **resolve the KB into the document (never "see KB"), name secrets (the Runner owns values), list environments without binding one (default non-prod), confirm before any state-changing action, ship no script.**

## Entry & session (the LLD/ED's "Authentication / sign-in" section)

- **Entry point.** The landing URL/path the flow starts from, expressed against a symbolic origin (`{base_url}`) the Runner binds when it picks the environment — never a hardcoded host.
- **Login flow (if any).** The login page, the fields to fill (username/email, password, etc.) named to the **credentials by the KB's exact name** (`<from secrets: NAME>`), the submit action, and how success is confirmed (redirect to a dashboard, a visible logged-in element). The Runner supplies the values and types them; the LLD never carries or logs them.
- **Session continuity.** How the logged-in state is carried between steps (cookie/session persists in the browser context) and how to detect a dropped session (bounced to login) so the Runner can re-authenticate.
- **Can't-run-unattended flows.** If the login needs MFA, a CAPTCHA, or an emailed/SMS code, the LLD/ED must **flag it as an open item** — the Runner cannot complete it autonomously and must surface it to the operator.

## Per-step UI action — what to specify

For each step the LLD/ED records, fully resolved from the KB:

- **action** — `navigate` / `click` / `fill` / `select` / `upload` / `hover` / `assert` (and whether it **changes state**: submits, creates, edits, deletes).
- **target element** — the **locator the KB provides**: a stable selector, a `data-testid`, or an accessible name/role + text. Prefer stable, KB-attested locators; **never invent a selector** or guess one from how the page "probably" looks. If the KB doesn't give a locator for an element the flow needs, that's a **KB gap to flag**.
- **page / precondition** — which screen the Runner must be on first, and any guard ("only click Delete if the row's status is Inactive").
- **inputs** — literal values from the SOW/prompt, or `← step N.<captured>` when chained; credential fields shown only as `<from secrets: NAME>`.
- **expected result** — the on-screen state that confirms success: a URL change, a visible toast/banner, an element appearing/disappearing, a field showing a value. This is what the Runner **asserts** before moving on.
- **capture** — any on-screen value to read for a later step (an order id shown after submit, a row's text), and whether it is **required** (missing → stop the chain, don't fabricate).
- **waits** — what to wait for (element visible / network idle / URL match) and a timeout, rather than a fixed sleep.

## Failure & edge cases the LLD/ED must hand the Runner

| Symptom | Likely cause | Runner action to specify |
|---|---|---|
| **Element not found** | page not loaded yet, wrong screen, changed UI | wait for the element per the step's wait condition; if still absent, stop — don't click blindly into the wrong place |
| **Stale element / re-render** | DOM replaced after an action | re-locate the element before acting; don't reuse a stale handle |
| **Navigation timeout** | slow load, wrong URL, network | retry the navigation per the retry policy; after the cap, stop and report |
| **Unexpected modal / popup / cookie banner** | consent dialog, interstitial | dismiss only if the KB documents it; otherwise surface — don't click unknown buttons |
| **Bounced to login** | session expired | re-authenticate (per the sign-in section), then resume; if it recurs, stop |
| **Assertion failed** (expected state absent) | the action didn't take effect | treat as a failed step — do not proceed down the chain on an unconfirmed result |
| **MFA / CAPTCHA appears** | anti-automation / step-up auth | can't run unattended — surface to the operator |

**Transient vs terminal:** element-not-yet-visible and navigation flake are **transient** — retry within the policy. A missing page, a missing KB-documented element, or a failed assertion is **terminal for that step** — stop, don't cascade.

## Safety, idempotency & observability (browser)

- **Confirm before any state-changing UI action.** Submitting a form, creating/editing/deleting a record, or paying is the browser analog of a mutating call — it goes behind the LLD/ED's confirm-before-mutate gate, and a destructive action (delete, irreversible) is re-confirmed at the moment of the click with the concrete target.
- **Environment.** List the site environments the KB documents (staging vs prod origin) as options; instruct the Runner to **default to non-prod**. Acting on the prod site is an explicit run-time choice. Never bind or hardcode the origin.
- **Idempotency.** A UI submit usually carries **no idempotency key**, so a blind re-submit can **double-create**. After a state-changing action, the Runner **verifies the effect** (the record appears, the id is shown) before treating it as done; on an ambiguous failure it reads state rather than re-submitting.
- **Broken chain.** A required captured value that isn't on screen → **stop**; never proceed with a blank/guessed value.
- **Redaction.** Never log typed secret values; redact them in any step log or screenshot. Capture evidence (screenshots/DOM) only as the run record allows, with secrets masked.
- **Cap & report.** Loops over a list/table get a sane cap; the Runner logs when it hits the cap and never presents a truncated run as complete.
