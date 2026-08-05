---
id: web-flow
seen-in: []
fallback: false
---

# Playbook: web-flow

Analysis advice and lessons learned for clients whose subject is **a live web application that must be driven through its UI** — because the tasks they want automated have **no API surface** to call. The "artifact" here is unusual: it is not a folder of files but **the running site itself**, reached at a URL and observed by a browser.

The downstream chain is fixed: the KB this produces is read by **`api-agent`**, which detects the *web-flow* shape and designs a browser-mode **LLD/ED**; that document is then executed by **`runner-agent`** as live UI actions. So the KB's audience is not a human reader — it is a designer that must resolve every page, action, locator and cue into a runbook, and a runner that must then click exactly those things on a live site with no ability to improvise.

The consuming skill uses this playbook as guidance while mapping; the KB that gets generated is Claude's composition for *this* product, not a copy of this file.

**This archetype's distinctive stakes: the KB drives a real browser against a real site, usually a logged-in one.** A wrong fact does not yield a malformed file you can regenerate — it clicks the wrong control in someone's production account. And the failure mode is asymmetric with the API archetype: an HTTP contract is *published and versioned*, whereas a UI is **undeclared and silently mutable**. Nobody announces a redeploy that renames a CSS class. So the question a web-flow KB must answer is never merely "what does this page look like?" but **"what about this page will still be true when the runner arrives, and how does the runner know if it isn't?"** Fidelity to the durable shape, and honesty about what was never observed, are the whole game.

## When this playbook applies (recognition signals)

Structural signals at the archetype level — vendor-agnostic by design. Specific fingerprints (this product's actual URLs, its real selectors, its button labels) are NOT match conditions; they're captured from the live site during mapping.

- **The subject is a reachable web application** — an origin plus a set of screens rendered in a browser — rather than a corpus of documents. It arrives as a **URL** (optionally with credentials), not as an inputs folder.
- **The work to be automated is expressed as user journeys**: "log in, search for X, open the record, change a field, submit, read back the confirmation number." The verbs are *navigate / click / fill / select / upload / assert*, not *GET / POST*.
- **There is no usable API for the tasks in scope** — none published, none entitled to this client, or one that covers a different slice than the journeys need. This absence is the reason the archetype exists; if a documented HTTP contract covers the work, that is `api-integration` and it is almost always the better surface.
- **Access is usually gated** — a login form, a session cookie, a role/permission model — and often further gated by step-up challenges (MFA, OTP, CAPTCHA, email verification).
- **A statement of work names the journeys.** The SOW says *which* flows matter; the site says *how* they work.

Proxies for the live site fire this playbook too, and are worth asking for because they compress the mapping enormously: **HAR captures**, **Playwright/Selenium/Cypress codegen scripts or existing test suites**, **session recordings**, **screen recordings or annotated screenshots of the flow**, and **internal click-path runbooks written for human staff**.

If the signals don't match, the playbook doesn't apply:

- **Endpoint + verb + auth + request/response schema documentation** is `api-integration`, even when the product also has a web UI. The tell is what the consumer is meant to *do*: call a service, or operate a screen.
- **A branded document to reproduce** (SOW/BRD/PRD) is `document-from-template`.
- **A node-and-transition graph the consumer emits for a platform to import** is `nodeflow`.

A mixed engagement fires more than one playbook: partial API docs *plus* a UI that covers the rest hits both `api-integration` and `web-flow`. Carry both forward, and make the KB say plainly which journeys are served by which surface — the API path is cheaper, faster and far more stable, so a step that *can* be an HTTP call should not be a click.

## The analyst's real job: close the observed-to-durable gap

**What a browser shows you on one visit, on one account, at one moment is not a contract.** Six gaps separate "I saw it work" from "a runner can do this unattended next Tuesday," and a KB that closes none of them will pass review and fail in production. Each gap below must resolve to something recorded in the KB or something asked of the operator.

1. **Locator durability gap.** The DOM in front of you is full of things that will not survive a redeploy: build-hashed class names (`css-1x2y3z`, `sc-bdVaJa`), positional indices (`:nth-child(3)`), wrapper `div`s from a component library, and text that changes with locale or an A/B test. A locator's value is entirely its **durability**, and durability is *judged*, not observed. Record the ladder position and a fallback for every element — never a single brittle string.

2. **Instance-vs-shape gap.** You are looking at one account's data. `/orders/84213` is an instance; `/orders/{order_id}` is the shape. `Welcome back, Priya` is an instance; `Welcome back, {user_name}` is the shape. Record shapes with one redacted example, and never let the account you happened to map become the KB's definition of the product.

3. **State-dependence gap.** A screen is a function of role, permission, plan/tier, feature flag, locale, and whether the account has data. A journey mapped on a fully-populated owner account silently omits the **empty state** (no rows means no row to click), the **permission-denied path**, the **first-run wizard**, and the **trial/paywall interstitial**. These are precisely the states an unattended runner will hit and be unable to interpret.

4. **Async and timing gap.** What reads as instant to a human is a spinner, a debounce, a skeleton row, an optimistic update that silently rolls back, a toast that auto-dismisses in three seconds, or a job that completes minutes later by email. The KB must record **the cue to wait for**, never a duration to sleep. A success cue that vanishes on a timer is a cue the runner can miss entirely — say so, and record a durable secondary cue (the row now exists, the URL changed, the status chip reads *Active*).

5. **Mutation gap.** Some journeys simply cannot be observed to their end without changing state — you cannot see the confirmation screen without submitting the order. So every fact in the KB carries a provenance: **observed** (seen directly), **inferred** (read off a form's affordances without firing it), or **unmapped** (never reached). Inference is legitimate and often correct; presenting it as observation is not.

6. **Human-gate gap.** MFA prompts, emailed or SMS one-time codes, CAPTCHAs, identity re-verification, payment authorization, native OS file pickers, third-party SSO redirects, and "we noticed unusual activity" lockouts. These are **not obstacles to route around** — they are first-class, documentable features of the flow. The whole downstream design depends on the KB naming each one, where it fires, whether it fires always or conditionally, and what a human must supply to clear it. At mapping time a gate is also a **question**: whether to supply what clears it, work around it, or accept it as a boundary is the operator's decision, and the KB records the decision *they* made — never one the analyst made for them.

The bar this all adds up to: **a later agent, holding only the KB, must be able to execute every in-scope journey** — each screen it crosses named with a URL pattern, each element it acts on carrying a durable locator and a fallback, each action a wait condition and a verbatim cue, each human gate recorded with what clears it. Map to that bar and no further. The skip-entirely categories at the end of this playbook are not economies of effort but signal protection: cosmetic and off-journey material buries the facts the runner depends on.

## What to look for when analyzing

- **Origins and environments.** Every origin the product exposes — production, staging, sandbox, a demo tenant — and which is non-prod. This matters more here than anywhere: the runner defaults to non-prod, and a KB that documents only the prod origin quietly forces every future run against the live business. Note behavioural differences between environments (test payment instruments, seeded data, relaxed rate limits, disabled emails).

- **Entry and session.** The landing URL; whether login is required; the login page's field locators; the credentials **by name only**; the exact success cue; where the session lives (cookie, storage) and how long it lasts; the cue that the session has dropped (usually a bounce to login); and how to sign out. Also note *remember-me* behaviour and concurrent-session limits, which quietly break repeat runs.

- **Every sign-in method the page offers, ranked — and direct credentials outrank federated identity.** A login screen usually presents several routes: an email/password (or username/password) form, one or more OAuth/SSO buttons ("Continue with Google/Microsoft/Apple/GitHub"), a magic-link-by-email option, and sometimes SAML for enterprise tenants. **Record them all, and mark the direct email/password form as the preferred route whenever it exists.**

  The reason is not stylistic. An OAuth button does not log you into *this* product — it hands the session off to **a different company's identity system**, and everything downstream becomes that provider's problem: its own consent screen, its own account chooser when several are signed in, its own device-trust and risk checks, its own MFA, and a redirect chain across origins that a mapped locator cannot survive. It also widens the blast radius enormously, since the credential in play now unlocks the operator's mail, calendar and everything else that identity secures — for a run that only needed to log into one product. A magic link is weakly better than OAuth but still off-platform: it parks the flow in an inbox the automation may not be able to reach.

  So capture the direct-credential path in full detail, and capture the OAuth/SSO path as a **documented fallback** — which providers are offered, what the button says, and where the redirect goes — flagged as needing a human. When the product offers *only* federated sign-in, say so explicitly and record which provider, because that fact reshapes the whole engagement: the client must either provision a direct account or accept that every run needs someone present.

- **Deep-linkability — capture this deliberately.** For every screen, establish whether it can be reached by URL directly or only by clicking through. A stable deep link collapses four fragile clicks into one navigation, and is the single largest robustness win available in this archetype. Record the URL pattern, and note when a deep link only works with a warm session.

- **The screen catalog.** Per screen: URL pattern, what it is for, which role/permission reaches it, its landmarks, and the states it can be in (populated, empty, loading, error, read-only, over-quota).

- **The navigation graph.** What leads where, and by what control — nav items, buttons, row links, redirects after submit, breadcrumb backs. Redirect-after-submit is worth recording explicitly, because it doubles as a success cue.

- **The journeys themselves** — the ordered spine of the KB. Per step: the action, the target element, the input and where its value comes from, the precondition, the expected on-screen result, anything to capture for a later step, and the wait condition.

- **Element inventory with locator ladder.** For each interactive element the journeys touch, in preference order: `data-testid` / dedicated automation attribute → stable semantic `id` → ARIA role + accessible name → label-associated form control → exact visible text on a stable element → structural CSS/XPath **last resort, always with a fallback and a durability warning**. Record *why* a locator is trusted; a class that looks hashed is a class that will change.

- **Form semantics, not just form fields.** Required vs optional, format masks and accepted input, client-side validation messages (verbatim), dependent fields (country then state), fields that only appear after another is set, and — a classic silent failure — **typeahead/autocomplete fields where typing text is not enough and an option must be selected from the dropdown**. Also capture custom widgets: date pickers that reject typed dates, rich-text editors that are not `input`s, multi-selects, toggles that are styled `div`s.

- **Success and failure cues, verbatim.** The exact toast text, banner copy, validation strings, and empty-state wording. These are wire-exact strings for the runner's assertions — paraphrasing one breaks the assertion that depends on it.

- **Waits.** Per action, what to wait for: element visible, network idle, URL match, spinner gone, row count changed. Note anything genuinely long-running and how its completion is signalled.

- **Lists, tables, pagination.** How collections are paged (numbered, infinite scroll, load-more, cursor), how a row is identified in a way that survives re-sorting, default sort order, and a sane cap for any loop.

- **State-changing action inventory.** Every control that creates, edits, deletes, sends, pays or publishes — flagged, with its reversibility and whether the product offers any idempotency (a draft state, a confirmation step, a duplicate-detection warning). A UI submit usually carries no idempotency key, so double-submission is a live risk the KB must warn about.

- **Anti-automation posture.** Bot detection, rate limiting, device fingerprinting, "unusual activity" challenges, and any terms-of-service position on automated access. Under-recorded and expensive: a flow that maps perfectly can still fail on the tenth unattended run.

- **Structural boundaries that break naive automation.** Elements inside **iframes** (the frame must be identified or every locator fails), **shadow DOM** roots, actions that open a **new tab or window**, native browser dialogs (`confirm`/`alert`), and downloads or uploads that hand off to the OS.

## Close the gap first: what to request and decide before mapping

- **The SOW, or an explicit journey list.** Without it the mapping is unbounded — "map this website" has no completion condition. The SOW scopes the crawl to the journeys that matter.
- **Access to a non-production environment**, if one exists. Ask before mapping, not after.
- **Credentials for each role the journeys need**, supplied as values to *use* and names to *record*. A journey that spans roles needs an account per role.
- **The mutation posture.** Whether the mapper may execute state-changing steps to observe what lies past them, and if so with what test data. This is a decision only the operator can make.
- **Any existing automation** — codegen scripts, test suites, HAR captures, internal click-path runbooks. These often name the exact `data-testid`s the product's own engineers rely on, which is the best locator source that exists.
- **Whether automated access is permitted.** Terms of service, rate limits, and whether the client owns or merely uses the site.

None of these has to arrive before mapping starts, and its absence never bounds the mapping by default: each becomes a question **at the moment it is needed** — a credential at the login wall, the mutation posture at the first submit, the journey list before the first walk. The analyst can and should prompt the operator at any point of the mapping for any credential or input the exploration requires. What is never allowed is resolving one of these silently: a wall the operator never heard about is not a scope decision, it is a mapping defect.

## Questions to ask the operator

A phrasing bank, not a checklist. Ask only what the SOW and the site do not already answer, and only what would change the KB — but ask **at any point of the journey**: before the first navigation, mid-walk, or standing at a wall. Two asks are duties, not options: any credential or input the mapping needs (ask for the value in chat and type it yourself), and any decision to leave something unexplored (present it and let the operator decide — never conclude on your own that a journey stops here, and ask too when you are unsure whether a section is worth mapping at all).

- **BLOCKING** — "Which journeys from the SOW should I map? I'll map exactly these and mark everything else out of scope."
- **BLOCKING** — "The `{journey}` flow requires signing in and the SOW doesn't carry a credential for `{account}`. Send me the email and password and I'll sign in myself — I'll also need the one-time code once it arrives. If you'd rather not, I'll stop at the login wall and document everything behind it as unmapped."
- **BLOCKING** — "`{product}` only offers `Continue with {provider}` — there's no email/password route. I can't complete a provider consent flow, and nobody can do it at my browser since it runs headless on the server. Can a direct-credential account be provisioned? If not, this product needs a human present for every run, and I'll record that as the automation boundary."
- **BLOCKING** — "Completing `{journey}` means actually {submitting the order / sending the message / deleting the record} on a live site. May I execute it to map what follows, and with what test data? If not, I'll document the form and mark everything past the submit as inferred."
- **BLOCKING** — "Sign-in sent a one-time code to `{destination}`. Please paste it, or tell me to stop here and record MFA as a run-time intervention."
- **IMPORTANT** — "Is there a staging or sandbox origin? Without one, mapping and every future run target production."
- **IMPORTANT** — "The journeys span `{role A}` and `{role B}`. Do you have credentials for each, or should I map only `{role A}`'s view?"
- **IMPORTANT** — "`{screen}` is empty on this account, so I can't see a populated row or what clicking one leads to. Is there an account with data, or should I record the empty state only?"
- **VERIFY ASSUMPTION** — "I'm treating `{origin}` as production and defaulting future runs to `{other origin}`. Correct?"
- **VERIFY ASSUMPTION** — "This site's class names look build-generated, so I'm recording accessible-name locators as primary and CSS only as fallback. Flag it if your team ships stable `data-testid`s I should prefer."
- **NICE TO HAVE** — "Does your team already have Playwright/Cypress tests or a click-path runbook for these flows? Their selectors would be far more durable than anything I infer."

## Common pitfalls

Each is a "do not X because Y" the runtime can enforce on its own KB output.

1. Never record a build-hashed or generated class as a primary locator — it changes on the next deploy and every step depending on it fails at once.
2. Never record a positional index (`:nth-child`) as an element's only locator — a new row, an ad slot, or a reordered list silently retargets the click onto the wrong thing.
3. Never record a URL containing a real identifier — parameterize it, or the KB encodes one account's records as the product's structure.
4. Never record real customer data, PII, or account contents seen while mapping — capture the shape, redact the instance.
5. Never record a credential value; record its name only, matching the `<from SOW: NAME>` convention the downstream runner uses. The SOW carries the values, which makes it secret-bearing — never copy it into the KB or quote it back.
6. Never treat "the control exists" as "the action succeeded" — without a recorded success cue the runner cannot tell a submit from a silent validation failure.
7. Never record a fixed sleep as a wait — record the observable condition, or the flow is flaky by construction.
8. Never let one role's view stand for every role's — an owner account hides the permission-denied path the runner will hit.
9. Never let a populated account hide the empty state — "click the first row" has no meaning on a screen with no rows.
10. Never execute a state-changing action to satisfy curiosity — mutations happen only under an explicit operator decision, and destructive ones only with the concrete target confirmed.
11. Never present an inferred step as observed — mark provenance per step, because the runner's risk calculus depends on it.
12. Never omit an iframe or shadow-DOM boundary — an otherwise perfect locator resolves to nothing when the element lives in a frame the KB never mentioned.
13. Never use locale-dependent visible text as a primary locator on a multi-locale site — the runner may sign in to a different language than you mapped.
14. Never quietly skip a human gate because it "only appeared once" — a conditional MFA challenge that fires on a new device fires on every fresh runner.
15. Never present a partially-mapped journey as complete — an unmarked gap becomes a runner improvising on a live site, which is the exact failure this architecture exists to prevent.
16. Never abandon a journey — or settle for the public surface of a gated site — without the operator's explicit say-so. "Stuck" is a question to ask, not a scope decision to make; a gap the operator never sanctioned is a defect, not a boundary.

## Typical KB shapes that have worked

Reference only — size the file list to the journeys actually in scope. The journey files are the heart; everything else exists to make them executable.

- `overview.md` — what the product is, what the automation is for, the mapped journey index, and the scope boundary (what was deliberately not mapped).
- `environments.md` — every origin, which is non-prod, and how the environments differ behaviourally.
- `access-and-session.md` — the sign-in flow, credential **names**, the success cue, session carrier and lifetime, the session-dropped cue, sign-out, and the role matrix.
- `navigation-map.md` — the screen graph: which screens exist, what leads where, and which are deep-linkable by URL pattern.
- `screens/<screen>.md` — per screen: URL pattern, purpose, required role, landmark elements, and the states it can present.
- `journeys/<journey>.md` — one per SOW journey: the ordered steps with action, target, input, precondition, expected result, capture, wait, and per-step provenance.
- `locators.md` — the element table: primary locator, ladder position, fallback, durability note, and the frame/shadow boundary if any.
- `forms-and-inputs.md` — field semantics, validation strings, dependent and conditional fields, and custom widget handling.
- `cues.md` — verbatim success, failure, validation, and empty-state strings, plus which cues are transient.
- `waits-and-timing.md` — per-action wait conditions, long-running operations, and how completion is signalled.
- `state-changing-actions.md` — the mutation inventory with reversibility, destructive flags, and double-submission risk.
- `interventions.md` — every human gate: what fires it, when, and — the distinction downstream actually turns on — **whether a remote operator can clear it from a text channel at all**. A gate that resolves to a value someone can type into a chat message (an email, a password, an OTP, a missing input) is a pause the automation survives, because the agent supplies it to the page itself. A gate that needs a person *at the browser* (a CAPTCHA, an OAuth consent screen, a bank's 3-D Secure step, a native OS dialog) cannot be cleared by an unattended runner at all, and must be recorded as a hard automation boundary rather than a prompt. Blurring the two produces a KB that promises journeys the runner will stall on forever.
- `conventions.md` — URL and id patterns, pagination style, modal and dialog patterns, date formats, new-tab behaviour, anti-automation posture.
- `gaps.md` — what was not mapped and why, so nothing downstream mistakes silence for coverage.

## Skip-entirely categories

Things the KB should never lead the downstream agent to emit or depend on:

- **Exhaustive site crawls.** Map the journeys in scope and their immediate surroundings; a full sitemap is cost without value.
- **Marketing, blog, legal and help pages** that no journey traverses.
- **Cosmetic styling** — colours, spacing, fonts, animation. This KB drives behaviour, not rendering.
- **Analytics, tracking and consent-vendor internals**, beyond the fact that a consent banner appears and how it is dismissed.
- **Third-party widget internals** (payment iframes, chat launchers, embedded maps) — record the boundary and the handoff, not the vendor's DOM.
- **Responsive breakpoints and mobile layouts**, unless a journey's controls genuinely differ there.
- **Raw DOM dumps or full page HTML.** The KB records the durable locators and cues that were *judged* worth keeping; a dumped DOM is noise that rots immediately and buries the facts that matter.
