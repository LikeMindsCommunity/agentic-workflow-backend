# Reference: driving a UI that drifts

A web UI is an **undeclared, silently mutable** interface. Nobody publishes a changelog for a renamed CSS class, and the KB was accurate the day it was mapped. This file is how to stay correct anyway: fail over the way the KB sanctions, tell transient flake apart from a real break, and never let recovery become improvisation.

**The governing distinction:** *following the KB's own fallback* is not adaptation and needs no permission. *Anything the KB doesn't sanction* is a stop, not a workaround.

## The locator ladder at run time

The KB records, per element, a primary locator, a fallback by a **different mechanism**, and a durability note. At run time:

1. **Try the primary.** Resolve it inside the frame the KB names — an unrecorded iframe or shadow boundary is the most common reason a perfect locator finds nothing.
2. **Exactly one match → act.** Several matches is **ambiguity, not success**: stop and ask (see `interventions.md`). On a mutating step, taking the first match picks a victim at random.
3. **No match → wait first.** Most "missing" elements are simply not rendered yet. Wait for the step's condition before concluding anything.
4. **Still nothing → try the KB's documented fallback.** This is following the KB, so continue normally — but **log the fallback**, because a primary that stopped working is a re-map signal even when the run succeeds.
5. **Both dead → stop.** Report it as a KB gap with what you actually see on screen. You may offer to re-target by the KB's *described* element (its role and accessible name), but only with the operator confirming the match — never silently.

Never substitute a selector you derived by reading the page. It will often be right, and that is exactly the problem: the failures it causes are indistinguishable from success until something irreversible happens.

## Transient vs terminal

| Symptom | Read it as | Action |
|---|---|---|
| Element not yet visible | **Transient** | Wait for the step's condition, then retry within the cap |
| Navigation timeout, slow load | **Transient** | Retry the navigation within the cap; then stop and report |
| Stale element after a re-render | **Transient** | **Re-locate before acting** — never reuse a handle across a DOM replacement |
| Spinner or skeleton still showing | **Transient** | Wait for it to clear; never act over a loading state |
| Bounced to login | **Recoverable once** | Re-authenticate per the KB, resume. **Recurs → stop** (a login loop means something is wrong) |
| Locator dead, fallback works | **Recoverable** | Continue, and log it as a re-map signal |
| Both locators dead | **Terminal for the step** | Stop and ask — report the KB gap; the operator decides: confirm a re-target, skip, or abort |
| Success cue never appears | **Terminal for the step** | The action did **not** succeed. Do not chain off it — report and ask before moving on |
| Failure cue appears | **Terminal for the step** | Read it verbatim into the report — the site is telling you why — then ask how to proceed |
| Required capture absent | **Terminal for the run** | Stop and ask. Never continue with a blank or an inferred value |
| Screen contradicts the KB | **Terminal** | Stop and ask — do not explore to work out where you are |

**Retries are for transport and timing only.** Retrying a click whose *cue* never appeared is not a retry — it is doing the action twice, and on a mutating step that double-creates.

**Terminal never means silent.** A terminal verdict ends the *step*, not the conversation: report what happened and ask the operator whether to skip the journey, resolve it another way, or abort. Ending the run without that exchange is abandoning it, and that decision belongs to the operator.

## Waiting

Wait on **observable conditions the KB records** — element visible, spinner gone, URL matches, row count changed, network idle — never on a duration. A fixed sleep is flaky when the site is slow and wasteful when it is fast.

Where the KB marks a cue **transient** (a toast that auto-dismisses), assert the durable secondary cue it records alongside — the row now exists, the status chip changed, the URL moved. Missing a toast is not evidence that the action failed, and treating it as failure triggers exactly the wrong recovery.

For genuinely long-running operations the KB flags, wait on the completion signal it names, with a cap. On timeout, **report the operation as still in flight** rather than as failed — those are different facts with different consequences for the operator.

## Mutations, verified not retried

A UI submit usually carries **no idempotency key**, so the safe pattern is inverted from HTTP: **verify, don't retry.**

- After a state-changing action, confirm the effect the KB describes — the record appears, the id is shown, the status changed.
- On an **ambiguous** outcome (timeout, connection drop, cue never rendered), **read the state**: navigate to where the record would be and look. Only act on what you find.
- Never re-submit to "make sure." If state can't be determined, stop and surface it — a duplicate order is worse than a stalled run.
- Where the KB records a duplicate-detection warning or a draft state, use it; that is the site's own idempotency and it beats guessing.

## Iteration and caps

Loops over lists and tables honor a cap. Identify rows by the stable key the KB names, not by position — a list that re-sorts between page loads silently retargets a position-based loop onto the wrong row.

Follow the KB's pagination style (numbered, infinite scroll, load-more, cursor) and stop when its stop condition is met or the cap is hit. **Log the cap when you hit it, and say so in the report** — a truncated sweep presented as a complete one is a false negative the operator has no way to detect.

## Session

Keep the logged-in session across steps. Watch for the KB's session-dropped cue rather than waiting for a confusing failure downstream. Re-authenticate once on a drop, resume, and stop if it recurs. If the site enforces a concurrent-session limit the KB records, respect it — signing in again can silently invalidate the session the run is using.
