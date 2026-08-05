# Reference: the intervention protocol (human in the loop)

Unattended browser automation meets things it cannot pass alone. Some are security controls doing their job, some are the site changing under you, some are decisions that are not yours to make. **A run that dies at one of these when a single question would have unblocked it has failed unnecessarily** — and a run that pushes through one it should have surfaced has done something worse.

## The operating constraint that shapes everything below

**You and the operator are not looking at the same browser, and they cannot reach yours.** The browser is headless, isolated, and running inside the server's container; the operator is at the other end of a text conversation. They cannot see the screen, cannot click anything, cannot complete a login for you, and cannot take over and hand back.

So there is exactly one thing the operator can do: **send you text.** Everything else has to be done by you, in your browser, using what they send.

That makes "please do this part yourself in the browser and tell me when you're done" an instruction **nobody can carry out**. Never write it. When you need something, ask for the *information* that lets **you** do it — and when no information could (a CAPTCHA, an OAuth consent screen), that is not a pause at all: it is a **hard stop and a finding**, because there is no one to hand it to. The finding still ends with a question, though: the operator, not you, decides whether the run skips that journey, resolves the gate another way, or stops.

**Never offer the operator the browser.** Not as an option, not as a preference, not as "if you can reach this session". There is no shared-session arrangement, no attach mode, no way for them to click. Presenting one as a choice sends them off to look for something that does not exist and strands the run while they try.

Every blocker therefore falls into one of just two buckets:

| Bucket | Who acts | How it resolves |
|---|---|---|
| **A — resolvable by text** | Operator sends it, **you** act | Ask in chat, wait, then perform the action yourself. Covers workflow values, decisions, **and credentials** — email, password, OTP, anything the sign-in needs |
| **B — needs a human at the browser** | **Nobody can** | Stop at the gate and record it — then **ask the operator what happens next**: skip the journey, resolve it another way, or abort. Do not wait for the impossible, and do not decide alone |

**Credentials are bucket A.** The SOW normally carries them, but when it doesn't, **ask the operator for the value in chat and type it yourself.** Do not send them looking for a secrets file, and do not treat a missing password as a dead end — it is a question. The operator is the account holder deciding to hand you their own credential for their own automation; asking plainly is the working path, and refusing to ask just deadlocks a run that one message would have unblocked.

Handle what they send with care, because chat is transcribed: **use it, never repeat it.** Never echo the value back in a later message, never write it into `run.log`, `result.json`, the displayed plan, the KB, or a screenshot, and never restate it "to confirm". Show it only as `<from operator: NAME>`.

Bucket B is not a failure to apologise for. "This journey cannot run unattended because sign-in is Google-only" is a genuine, valuable finding — it tells the client which flows need a different approach. Report it as a result, not as an error.

## The ask format

One message, four things:

1. **Where you are** — journey, step number, screen name, current URL.
2. **What is blocking** — concretely. "Sign-in wants a 6-digit code sent to the phone on the account", not "authentication issue".
3. **What you need from them** — the exact value or the exact decision. For a credential, name which one and what the field expects.
4. **What skipping costs** — which steps stay undone, and whether the run can still finish.

Then **stop and wait**. The realistic options are only ever:

> **send the value** · **skip this journey and carry on** · **abort the run**

Ask for one blocker at a time as you hit it. A speculative list of everything that *might* block is noise on a live run.

## Blocker classes

| Class | Bucket | What to do | Never |
|---|---|---|---|
| **Missing workflow value** | A | Ask: which field, which screen, expected format, and the valid options where the page constrains them | Never guess, never leave blank, never take a "reasonable" default the KB doesn't document |
| **Ambiguous target** | A | List the candidates with what distinguishes them and let them pick | Never take the first match — on a mutating step that picks a victim at random |
| **MFA / OTP code** | A | Ask for the code directly — **and you type it, not them**. Say it must be fresh, since codes expire in ~30–60s and your pause may be long | Never ask them to disable MFA; never loop the login hoping to skip the challenge |
| **Destructive action** | A | Re-confirm before acting, naming the **concrete target** — the actual record, id, recipient, amount — not the plan | Never rely on the earlier plan-level go-ahead for a destructive step |
| **Unexpected screen** | A | Screenshot it, describe exactly what is on it, and ask how to proceed | Never click an unknown button to find out what it does |
| **KB gap** (locators dead, cue absent) | A | Report it as a concrete re-map request. You may offer to re-target by the KB's *described* element (role + accessible name), with them confirming the match from your description | Never silently re-derive a selector from the page and carry on |
| **Missing credential** (email, password, API key) | A | The SOW normally carries it; when it doesn't, **ask the operator for the value in chat** — name which credential and which field it fills — then type it yourself | Never ask them to sign in for you; never guess or try a default; never echo the value back, log it, or write it into any artifact |
| **CAPTCHA / bot check / "unusual activity"** | **B** | **Stop.** Record what fired it, on which screen, and under what conditions. Report the journey as not automatable unattended | **Never** attempt to solve, script around, or evade one. Never rotate identity or retry to shake it off |
| **OAuth / SSO is the only route** | **B** | **Stop.** The provider's consent screen, account chooser and device checks cannot be driven from here, and there is no one at the browser to complete them. Record it as a human-only sign-in gate | Never enter identity-provider credentials; never accept a consent or scope-grant screen |
| **Signup / account creation** | **B** | **Stop.** Creating an account binds the client to terms and creates a real identity — not a decision you make, and not one you can take on their behalf from here | Never create an account, accept terms, or agree to a privacy policy |
| **Payment authorization** (3-D Secure, bank redirect) | **B** | **Stop.** The step-up leg happens on the bank's domain and needs the cardholder | Never enter card or bank details; never confirm a payment |
| **Native OS dialog** (file picker, print, permission prompt) | **B** unless scriptable | Use the driver's own upload/download/dialog affordance if one exists — that is bucket A. If the flow needs a true OS dialog, **stop**: there is no desktop here | Never accept a download the SOW didn't ask for; never execute a downloaded file |
| **Rate limit / lockout / maintenance** | **B** | **Stop** and report where the run reached. Suggest resuming later | Never hammer, never rotate identity, never work around the limit |

## Resuming after a pause

The browser is exactly where you left it — nobody else can have touched it. **The risk is not interference; it is elapsed time.** A pause waits on a human reading a message, and can run to the better part of an hour before the session times out. Sites do not wait that patiently.

So before acting on the answer:

1. **Re-read the current URL and screen.** Compare against the step's precondition.
2. **Assume the session may have died while you waited.** Bounced to login is the common case — re-authenticate per the KB, then resume at the step you paused at.
3. **Treat a supplied OTP as perishable.** If the pause was long, the code has almost certainly expired: say so and ask for a fresh one rather than typing a dead code and burning a retry.
4. **Watch for a page that moved on without you** — a toast that auto-dismissed, a modal that timed out, a list that refreshed. Re-assert the precondition rather than trusting the pre-pause snapshot.
5. **If you cannot tell where you are, ask** rather than clicking to find out.

## What goes in the run record

Log every intervention as a first-class event: which class and bucket, at which step, what was asked, what came back (**redacted** — never the credential value, never the OTP), and what happened next. A run that paused twice and finished is a successful run with two interventions, and the record should read that way.

**Bucket B blockers are the most valuable thing this skill discovers.** Each one is a precise statement of where the automation boundary actually falls on this product — worth reporting prominently, and worth sending back to `kb-builder` so the KB predicts the gate up front instead of the next run discovering it mid-flow.
