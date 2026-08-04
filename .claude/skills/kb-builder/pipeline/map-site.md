# Map site

**Runs only when the operator gave a `url=`.** This is the *acquisition* phase for the `web-flow` archetype: instead of reading artifacts someone handed over, you **produce** them by driving a real browser against a live site and recording what you observe.

It slots between `scope.md` and `build.md`. Scope has already locked **which journeys** to map; this phase walks them and writes an **observation corpus** to the run's scratch/`work/` directory. `build.md` then composes the KB from that corpus exactly as it would from any other artifacts.

```
recognize ─► scope ─► MAP SITE ─► build
             (which    (drive the   (compose
              journeys) browser)     the KB)
```

Runs in the main conversation, so pausing to ask for a credential, an OTP, or permission to submit a form just works.

## Input

- `url=` — the entry origin. **Required for this phase to run at all.**
- The **locked scope** from `scope.md`: the journey list, in-scope and out-of-scope.
- The `web-flow` playbook — advice on what to look for and what makes a locator durable.
- Any credentials, non-prod origin, or mutation permission the operator supplied.

## Browser driver

Use whatever browser automation tooling the session exposes (this project ships a Playwright MCP; a Claude browser surface may also be present). You need: navigate, read the page's structure/accessibility tree, read visible text, click, fill, select, screenshot, and read the URL. Prefer reading the **accessibility tree or structured page representation** over raw HTML dumps — it surfaces roles and accessible names, which is where the durable locators live.

If no browser tooling is available in the session, **stop and say so**. Never simulate a mapping run from general knowledge of how such sites usually work: a fabricated selector is indistinguishable from a real one in the KB and fails only later, on a live click.

## Step 0 — Settle the safety posture before the first navigation

Establish all four, asking if unsettled. These are not formalities; every one of them prevents a specific, expensive failure.

1. **Which origin.** If a staging/sandbox origin exists, map there. If only production exists, say so plainly and continue — but every mutation decision below gets stricter.
2. **Read-only by default.** You may navigate, open, expand, filter and read freely. You may **not** submit, create, edit, delete, send, publish or pay **without an explicit go-ahead for that specific action**. Filling a form is not submitting it; map the fields, stop at the button.
3. **Whose account.** Confirm the credentials are the operator's to use for automated access, and which role each represents.
4. **Whether automated access is permitted.** If the site is a third party's, ask. If you meet an explicit anti-automation control, that is a finding to record and surface, not an obstacle to defeat — **never attempt to solve or bypass a CAPTCHA or bot check.**

## Step 1 — Recon the entry point

Navigate to `url=` and establish the ground truth before walking any journey:

- **The real origin and any redirect** it lands on (a marketing host that bounces to an app host is a fact the KB needs).
- **Environment tells** — a staging banner, a subdomain, a test-mode indicator.
- **The gate** — is the entry public, or does it bounce to a login? Record which.
- **Interstitials that fire on every fresh session** — cookie/consent banners, region pickers, app-download prompts, onboarding tours. These matter enormously: a runner arriving with a clean profile hits every one of them. Record the exact dismissal control, and **choose the most privacy-preserving option** on any consent dialog.
- **The persistent shell** — the nav, header, and account menu that appear on every screen, and their locators. Mapping these once saves repeating them per screen.

## Step 2 — Establish access

If the journeys live behind a login:

- Map the login screen **as a screen** first — field locators, the submit control, the validation strings — before typing anything.
- Sign in with the operator's credentials. **Record the credential's NAME, never its value** (`<from secrets: NAME>`), and never let a value reach a log, a screenshot, or the KB.
- Record the **success cue** (the redirect target, the logged-in element), where the session lives, and the **session-dropped cue** so a runner can recognise being bounced.
- If a step-up challenge fires — MFA, an emailed or SMS code, a device-trust prompt, a CAPTCHA — **pause and ask** (see Step 5). Do not attempt to defeat it.
- If no credentials were supplied, map everything public, then ask once whether to continue behind the wall or record the rest as unmapped.

## Step 3 — Walk each in-scope journey

Take the journeys in the order the scope locked. For each, walk it end to end, recording as you go rather than reconstructing afterwards from memory.

**Per screen you land on**, record:

- The **URL pattern**, parameterized (`/orders/{order_id}`, never `/orders/84213`), plus one **redacted** example.
- Whether the screen is **deep-linkable** — can a runner navigate straight here with a warm session, or must it click through? Test it. This is the single biggest robustness win available, so spend the extra navigation to find out.
- The screen's **purpose**, the **role** that reaches it, and which **state** you are seeing (populated, empty, loading, error, read-only, over quota).
- The **landmark elements** the journey touches.

**Per element you will act on**, capture a locator using the playbook's ladder — dedicated test attribute → stable semantic id → ARIA role + accessible name → label-associated control → exact visible text → structural CSS/XPath as a last resort. For each, record:

- The **primary locator** and its ladder position.
- A **fallback locator** by a different mechanism, so one rename does not kill the step.
- A **durability note** — say plainly when a class looks build-generated, when text is locale-dependent, when a position is index-based.
- Any **iframe or shadow-DOM boundary** the element sits behind. An unrecorded frame boundary makes a perfect locator resolve to nothing.

**Per action you take**, record the action, its target, the input and where the value came from, the **wait condition** (an observable cue, never a duration), the **expected on-screen result**, and anything worth capturing for a later step.

**Per cue, record the text verbatim.** Toasts, banners, validation messages, empty-state copy. These become the runner's assertions, and a paraphrase breaks the assertion that depends on it. Note explicitly when a cue is **transient** (a toast that auto-dismisses), and find a durable secondary cue alongside it — the row now exists, the URL changed, the status chip reads a new value.

**At a state-changing control, stop.** Record the form, its fields, its validation, and the button. Then either ask for the go-ahead to submit, or mark everything beyond it **inferred** and move on. Both outcomes are legitimate; silently submitting is not, and silently presenting the unmapped remainder as mapped is worse.

## Step 4 — Probe the states a happy path hides

A journey mapped once, on one account, in its best state, is the most common defective web-flow KB. Where it is cheap and safe, deliberately look at:

- The **empty state** of any list the journey depends on — "click the first row" is meaningless on a screen with no rows.
- A **validation failure** — submit-blocking client-side errors are free to observe (the form does not submit) and tell the runner how failure looks.
- The **permission-denied** path, if the journeys span roles.
- **Pagination** on any collection the journey iterates, plus how a row stays identifiable when the list re-sorts.

Where probing is not safe or not reachable, record the state as unobserved in `gaps` rather than guessing at it.

## Step 5 — Blockers: pause, ask, resume

When you hit something you cannot or must not pass alone — a login wall with no credentials, MFA, an OTP sent elsewhere, a CAPTCHA, a payment step, a signup that would create a real account, an OS file picker, an undocumented screen you did not expect — **stop and ask the operator**, in one clear message:

- **where** you are (the screen and the journey step),
- **what** is blocking,
- **what you need** to continue — a value, a decision, or for the operator to complete the step themselves in the browser and tell you to carry on,
- **the cost of skipping** — which journey steps stay unmapped if you move past it.

Then wait. When you resume, **re-establish where you are before acting** — never assume the screen is unchanged after a human touched it.

Every blocker you meet is also **KB content**: record what fired it, whether it fires always or only conditionally (a new device, a new session, a high-value action), and what a person must supply to clear it. This is what lets the downstream `browser-agent` prompt for exactly the right thing at exactly the right moment instead of failing.

## Step 6 — Write the observation corpus

Write observations to the scratch/`work/` directory as you go, not in one pass at the end — a run that hits a hard blocker halfway must still leave `build.md` something real to compose from.

Per journey, record the ordered steps with **provenance on every one**:

- **observed** — you saw it directly.
- **inferred** — read off a form's affordances or a control's label without executing it.
- **unmapped** — never reached, with the reason.

Provenance is load-bearing, not bookkeeping. It is what tells the downstream agent which steps are trustworthy and which need a human's eyes on the first live run, and it is the difference between an honest KB and a confident one.

Also record, once per site: origins and environment tells, the session model, the persistent shell, the interventions inventory, the state-changing action inventory with reversibility, conventions (URL and id patterns, pagination style, modal and date-picker patterns, new-tab behaviour), and the anti-automation posture.

## Step 7 — Hand off to build

Summarise for the operator before `build.md` runs: which journeys mapped fully, which partially and where they stopped, which blockers need a human at run time, and anything the site does that will make automation fragile. Then hand the corpus to `build.md`, which composes the KB from it under the `web-flow` playbook's guidance.

## Don't

- **Don't submit, create, edit, delete, send or pay without an explicit go-ahead** for that specific action. A destructive one is re-confirmed against the concrete target at the moment you act.
- **Don't record a credential value, a real customer record, or PII.** Names and shapes only; redact every example.
- **Don't record a live identifier in a URL** — parameterize it, or the KB encodes one account's data as the product's structure.
- **Don't record a hashed class or a positional index as a primary locator**, and never as the only one.
- **Don't record a fixed sleep as a wait.** Record the observable condition.
- **Don't attempt to solve, bypass or evade a CAPTCHA, bot check, or rate limit.** Record it and surface it.
- **Don't crawl beyond the locked scope.** The journeys plus their immediate surroundings; a full sitemap is cost without value.
- **Don't dump raw page HTML into the corpus.** Record the judged, durable locators and cues — a DOM dump is noise that rots immediately and buries the facts that matter.
- **Don't present an inferred or unmapped step as observed.** Silence about a gap becomes a runner improvising on a live site.
