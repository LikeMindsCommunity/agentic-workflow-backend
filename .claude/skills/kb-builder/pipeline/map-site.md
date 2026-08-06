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

Use whatever browser automation tooling the session exposes (this project ships a Playwright MCP driver; a conversation's own browser surface may also be present). You need: navigate, read the page's **accessibility tree**, read visible text, click, type, select/fill form controls, screenshot, and read the current URL.

**The accessibility tree is the locator source; prefer it over raw HTML.** It gives roles and accessible names directly — the top of the durability ladder — whereas an HTML dump buries them under build-generated classes and wrapper elements. Where the tool hands back its own element references, treat those as a **read-time convenience, not a locator**: they are valid for that page state only. Record the durable role/name/test-id the reference resolves to, never the reference itself.

**If the tools offer no explicit wait-for-condition, poll — never sleep.** Re-read the page (or the specific text) until the cue holds or a sensible attempt cap is reached. A fixed sleep is flaky when the site is slow and wasteful when it is fast, and it is the single most common reason a recorded flow behaves differently on the next run.

If no browser tooling is available in the session, **stop and say so**. Never simulate a mapping run from general knowledge of how such sites usually work: a fabricated selector is indistinguishable from a real one in the KB and fails only later, on a live click.

### The browser is unattended — assume it always, never branch on it

Your browser runs **headless inside the server's container**, while the operator is at the other end of a text conversation. They cannot see the screen and cannot touch it. Do not reason about whether someone might be watching, and do not ask which kind of surface you have: assuming a handover is possible is the one mistake here that produces an instruction **nobody can carry out**, stranding the run at a wall while the operator waits for a browser that was never theirs. Assuming it is never possible costs nothing.

Three things follow, and they shape the whole phase:

- **Screenshot at every pause and give a path the operator can actually open.** A browser they cannot see is only usable if what it saw lands somewhere reachable — a screenshot is how they "look at" a blocker, so never describe a screen in prose and leave it at that when you could show it. **Only paths under `outputs/` exist for them.** The browser driver writes its captures there already, so cite the path it returns, **relative to the project root** (drop any leading `/app/`). Never cite a `work/` or sandbox path: those live inside the server, are discarded when the run ends, and hand the operator a file they cannot open — which is worse than no screenshot, because it reads like evidence was provided.
- **You sign in, not them.** Take the credential values from the SOW and type them yourself. When the SOW lacks one, **ask the operator for the value in chat** — the email, the password, the one-time code — and type that. A missing credential is a question, never a request for them to take over the browser, and never a reason to stall. Use what they send and never repeat it: no echo, no restating to confirm, and nothing written into a log, screenshot, the corpus or the KB.
- **A credential is an ordinary text input, not a special class of thing.** A password field is a field the sign-in screen requires, exactly like the email field next to it: ask for the value, type it, move on. Do **not** treat it as a reason for extra ceremony — no demand that it be written to a file first, no refusal to accept it in chat, no lecture about transcripts, no counter-proposal about how it "should" have been sent. The operator is the account holder handing you their own credential for their own automation, and chat is the only channel that reaches you, so refusing the value simply deadlocks a run that one message would have unblocked. The discipline that matters is what happens *after*: use it, never repeat it.
- **A gate that truly needs a person at the browser cannot be cleared here at all** — a CAPTCHA, a bot check, a device-trust prompt, an SSO consent screen. Never attempt one, never ask for a handover that cannot happen, and never wait on one. But the gate ends only the *action*, not the conversation: report it plainly, lay out the realistic ways past it (a direct-credential account, a TOTP seed, an alternate route the screen offers), and **ask the operator which to take — or whether to leave the journeys behind it unmapped. That decision is theirs, never yours.** An **OTP is different and still works**: it is a value the operator reads off their phone and pastes, so ask for it directly and type it yourself.

**Where the driver can execute arbitrary JavaScript in the page, don't reach for it to get around a hard element.** Evaluating script can read anything and click anything, which makes it a fast way to produce a locator no ordinary run could ever use — the KB would record a step that only works when driven by script. Use it, if at all, to *observe* (read an attribute, confirm a frame boundary); never as the recorded way to perform an action.

## Asking is the default; abandoning is the operator's call

These four rules govern the whole phase and outrank any impulse to be self-sufficient:

- **You can and should prompt the operator at any point of the mapping** — for a credential, a value, a decision, a go-ahead, or a scope call. An ask costs one pause; a silent assumption costs a defective KB. There is no stage of the walk where asking is out of bounds.
- **Never abandon a journey, a screen, or the run on your own authority.** Every wall — a login you hold no credential for, a step-up challenge, a hard gate, a screen that doesn't match, a section of uncertain relevance — gets a question **before** it becomes a gap. `gaps` records the operator's decision ("operator chose to skip X because Y"), never a decision you made alone. A gap the operator never heard about is a mapping defect, not a scope choice.
- **Unsure whether a section matters to a journey? Ask** — don't silently skip it and don't silently wander into it. The corollary holds too: sections plainly on no in-scope journey (marketing, blog, help, legal, cosmetic chrome) are distractions — stay off them without needing to ask.
- **Silence is not a decision.** A run that arrived with no credential, or with instructions that simply never mention signing in, has *not* decided that everything behind the wall is out of scope. The operator decides that at the wall, when you ask.

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
- **Enumerate every sign-in route the screen offers, and prefer the direct email/password form.** Most login screens present several: a credential form, OAuth/SSO buttons ("Continue with Google/Microsoft/Apple"), a magic link, sometimes enterprise SAML. Map the **direct credential path in full**, and record OAuth/SSO only as a documented **fallback** — which providers, what the button says, where the redirect goes — marked as requiring a human.

  Take the OAuth route only when the product offers no direct one. It does not sign you into *this* product; it hands off to another company's identity system, and the run inherits that provider's consent screen, account chooser, device-trust checks and MFA, across a redirect chain no mapped locator survives. It also puts a credential that unlocks the operator's mail and calendar in play for a run that needed one product. If federated sign-in is genuinely the only option, **say so plainly and stop to ask** — the operator may be able to provision a direct account, and if not, that changes the engagement, because every future run will need a person present.
- Sign in with the credential **values the SOW carries** — it is the single input document, holding the env values and credentials alongside the journey list, so there is no separate secrets file to look for. **If the SOW lacks one, ask the operator for it in chat and type it yourself.** Either way **record the credential's NAME, never its value** (`<from SOW: NAME>`), and never let a value reach a log, a screenshot, the observation corpus, or the KB.
- Record the **success cue** (the redirect target, the logged-in element), where the session lives, and the **session-dropped cue** so a runner can recognise being bounced.
- If a step-up challenge fires, split it by whether the operator can help from a text channel (Step 5). **MFA / an emailed or SMS code** → ask for the code, then type it yourself. **A CAPTCHA, a bot check, or a device-trust prompt that needs a real device** → nobody can clear it from here: stop, record the gate, and mark the journeys behind it as requiring a human. Never attempt to defeat any of them.
- If no credentials were supplied, don't treat that as a decision — it usually means nobody has been asked yet. Map the login screen and anything public, then **stop at the wall and ask**: name each credential the in-scope journeys need and ask for the values in chat (you type them yourself). Only two exits exist from that wall — the operator sends the credentials and you continue behind it, or the operator explicitly chooses to stop and you record everything behind it as unmapped **by their decision**. The run never quietly ends at a login screen.

## Step 3 — Walk each in-scope journey

Take the journeys in the order the scope locked. For each, walk it end to end, recording as you go rather than reconstructing afterwards from memory.

Stay on the journey's spine: the screens it crosses and their immediate surroundings. A control no in-scope journey touches is a distraction, however interesting the widget — and when you genuinely cannot tell whether something matters to a journey, ask the operator rather than deciding either way alone.

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

**The operator cannot reach your browser.** Yours is headless and isolated inside the server's container; they are at the other end of a text conversation and cannot see it, click in it, or take over and hand it back. The only thing they can do is **send you text**. So never ask them to "complete this step in the browser" — nobody can carry that out. Ask for the *information* that lets **you** do it.

That splits every blocker three ways:

- **Needs a value or a decision** — a login you have no credential for, which of two routes to take, an OTP, permission to submit a form, an undocumented screen. **Ask, wait, then act yourself.** Credentials belong here too: where the SOW doesn't carry one, ask the operator in chat for the email, password or code and type it. Use it and never repeat it.
- **Needs a human at the browser** — a CAPTCHA or bot check, an OAuth/SSO consent screen, a signup that would create a real account, a bank's payment step-up, a native OS file dialog. **Nobody can do these from here**, so never attempt them and never wait for a handover — but do not walk away from the journey on your own either: record the gate, present the realistic options (provision a direct-credential account, supply a TOTP seed, take an alternate route the screen offers, or leave the journey unmapped), and **let the operator choose**. The gate goes in the corpus either way; what happens to the journey is their call.
- **Needs nothing** — you simply must not pass it alone (a state-changing submit). Ask for the go-ahead as above.

When you do ask, one clear message:

- **where** you are (the screen and the journey step),
- **what** is blocking,
- **what you need from them** — the exact value or decision, and for a credential, which one and what the field expects. Ask for the value itself, in chat. Never send them off to write a file first,
- **the cost of skipping** — which journey steps stay unmapped if you move past it.

Then wait. On resume, **re-establish where you are before acting** — not because someone touched the browser (nobody can), but because a pause can run close to an hour: the session may have expired, a supplied OTP has almost certainly gone stale, and transient UI has moved on.

**A blocker nobody can pass is a finding, not a failure.** Record what fired it, on which screen, and whether it fires always or only conditionally (a new device, a new session, a high-value action). "This journey cannot run unattended because sign-in is Google-only" is one of the most useful things this whole phase produces — it tells the client exactly where the automation boundary falls, and it lets `browser-agent` warn up front instead of discovering the same wall mid-run. But it becomes a finding only after the operator has seen it and made the call — a journey abandoned without that exchange is not a finding, it is a mapping defect.

## Step 6 — Write the observation corpus

Write observations to the scratch/`work/` directory as you go, not in one pass at the end — a run that hits a hard blocker halfway must still leave `build.md` something real to compose from. (`work/` is the right place for *your own* intermediate notes, which only `build.md` reads. It is the wrong place for anything the **operator** must open — that has to be under `outputs/`, per the screenshot rule above.)

Per journey, record the ordered steps with **provenance on every one**:

- **observed** — you saw it directly.
- **inferred** — read off a form's affordances or a control's label without executing it.
- **unmapped** — never reached, with the reason.

Provenance is load-bearing, not bookkeeping. It is what tells the downstream agent which steps are trustworthy and which need a human's eyes on the first live run, and it is the difference between an honest KB and a confident one.

Also record, once per site: origins and environment tells, the session model, the persistent shell, the interventions inventory, the state-changing action inventory with reversibility, conventions (URL and id patterns, pagination style, modal and date-picker patterns, new-tab behaviour), and the anti-automation posture.

## Step 7 — Hand off to build

First run the **runner test** against every in-scope journey: could a later agent, holding only the KB this corpus will become, execute the journey unaided — every screen named with its URL pattern, every acted-on element carrying a primary locator and a fallback, every action a wait condition and a verbatim success cue, every human gate recorded with what clears it? Whatever fails the test takes one of exactly three exits: map it now, ask the operator about it now, or record it in `gaps` with the operator's explicit sanction. There is no fourth exit where a hole ships silently.

Then summarise for the operator before `build.md` runs: which journeys mapped fully, which partially and where they stopped, which blockers need a human at run time, and anything the site does that will make automation fragile. Then hand the corpus to `build.md`, which composes the KB from it under the `web-flow` playbook's guidance.

## Don't

- **Don't submit, create, edit, delete, send or pay without an explicit go-ahead** for that specific action. A destructive one is re-confirmed against the concrete target at the moment you act.
- **Don't record a credential value, a real customer record, or PII.** Names and shapes only; redact every example.
- **Don't record a live identifier in a URL** — parameterize it, or the KB encodes one account's data as the product's structure.
- **Don't record a hashed class or a positional index as a primary locator**, and never as the only one.
- **Don't record a fixed sleep as a wait.** Record the observable condition.
- **Don't attempt to solve, bypass or evade a CAPTCHA, bot check, or rate limit.** Record it and surface it.
- **Don't crawl beyond the locked scope.** The journeys plus their immediate surroundings; a full sitemap is cost without value.
- **Don't abandon a journey, a screen, or the run on your own authority.** Every wall gets a question before it becomes a gap; `gaps` records the operator's decision, never yours.
- **Don't silently include or exclude a section you're unsure about.** Relevance in doubt is a question for the operator — in both directions.
- **Don't dump raw page HTML into the corpus.** Record the judged, durable locators and cues — a DOM dump is noise that rots immediately and buries the facts that matter.
- **Don't present an inferred or unmapped step as observed.** Silence about a gap becomes a runner improvising on a live site.
