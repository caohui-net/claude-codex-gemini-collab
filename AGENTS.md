# AGENTS.md instructions

@/home/caohui/.codex/RTK.md

## Project Context

- Follow the repository's existing agent context files when they apply.
- `CLAUDE.md` points Claude-family agents to `.wolf/OPENWOLF.md`; do not remove or bypass that project convention when updating shared guidance.

<!-- CODEGRAPH_START -->
## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tools** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them. `codegraph_node` returns one symbol's source + callers, or reads a whole file with line numbers. If the tools are listed but deferred, load them by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` and `codegraph node <symbol-or-file>` print the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
<!-- CODEGRAPH_END -->

## Karpathy-Inspired Coding Guidelines

These guidelines are adapted from `multica-ai/andrej-karpathy-skills`. They are intended to reduce common coding-agent mistakes: hidden assumptions, overbuilt abstractions, unrelated edits, and work that stops before it is verified.

### 1. Think Before Coding

Do not silently guess when the request, code shape, or success criteria are unclear.

- State important assumptions before making non-trivial changes.
- If multiple interpretations are plausible, surface them instead of picking one silently.
- If a simpler path exists, say so and prefer it unless the user asks for more.
- If uncertainty would make the change risky, stop and ask a focused question.

### 2. Simplicity First

Write the minimum code that solves the requested problem.

- Do not add features, configuration, extension points, or abstractions that were not requested.
- Do not create a reusable abstraction for a single use unless it clearly matches an existing local pattern.
- Do not add defensive handling for impossible or irrelevant scenarios.
- If the solution is much larger than the problem, simplify before finalizing.

### 3. Surgical Changes

Touch only what the request requires.

- Match the surrounding style, naming, and architecture even if you would choose differently in a new project.
- Do not refactor adjacent code, rewrite comments, or reformat files as a side effect.
- If you notice unrelated dead code or design issues, mention them instead of changing them.
- Clean up imports, variables, helpers, and tests that your own change makes obsolete.
- Every changed line should trace back to the user's request.

### 4. Goal-Driven Execution

Convert work into verifiable outcomes and keep going until the outcome is checked.

- For bug fixes, reproduce the failure when feasible, then make the check pass.
- For behavior changes, add or update focused tests when the risk justifies it.
- For refactors, verify behavior before and after using the repo's existing test or lint commands.
- For multi-step work, keep a short plan with each step tied to a verification action.
- If verification cannot be run, explain exactly what was not run and why.

### Tradeoff

These rules bias toward caution over speed. For trivial one-line or documentation-only changes, use judgment and keep the process lightweight.
