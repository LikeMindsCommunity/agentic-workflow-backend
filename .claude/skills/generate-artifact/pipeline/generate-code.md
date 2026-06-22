# Use case: code — generate an SDK/code snippet

Produce the **code** the KB describes — an SDK integration, a function, a handler, a glue script — and verify it. **Snippets and integrations, not whole projects or codebases.** Nothing is executed.

**Follow the shared generation backbone in `SKILL.md`** (1 Learn the KB → 2 Understand the request → 3 Plan → 6 Deliver). This file defines only the two steps that are code-specific: **Generate (4)** and **Verify (5)**.

## 4. Generate (code)
Produce the code **strictly** from the KB's API surface, idioms, and the language/conventions the KB declares. Use the KB's reference snippets/examples verbatim where it provides them. Use no API surface that is not in the KB.

- **Call only real symbols.** Every class, method, function, parameter, constant, and import must exist in the KB's documented API surface. Do **not** invent a method name, guess a signature, or pattern-match a plausible-but-undocumented call from general knowledge of "how this kind of SDK usually works" — an unattested symbol compiles in your head and then fails at import/call time. When unsure between two, prefer the one **attested in a KB example**.
- **Match the KB's language and idioms** (error handling, async style, naming, config/initialization pattern). Don't introduce a dependency the KB doesn't sanction.
- **A snippet, not a scaffold.** Emit the integration/function itself, not a project skeleton, build tooling, or a generator program.

## 5. Verify and repair (code)
Run the checks the KB implies, strongest-available first:
- **It parses.** Syntactically valid in the declared language.
- **It type-checks / compiles / lints** if a toolchain is available — actually run it with Bash (`tsc`, `python -m py_compile` / a linter, `go build`, etc.). Report what you ran and the result.
- **Symbol reality:** every SDK symbol/method/parameter it calls exists in the KB's API surface (re-check against the KB, not against memory).

Loop Generate↔Verify until clean or genuinely stuck. If no toolchain exists to compile/lint, say so and fall back to a careful parse + symbol-existence pass. Surface anything unresolved with the reason — never silently ship a failing check.

## Deliverable
An SDK integration, a function, a handler, or a glue script — a **snippet/integration, not a whole project**. Validity is "parses, lints/compiles if a toolchain exists, and only calls real symbols from the KB's API surface."
