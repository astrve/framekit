# Ouro — Available Agents & Skills

Use these agents and skills only when they are available in the current Claude Code environment.

Prefer the project rules in `CLAUDE.md` over generic agent behavior.

Do not claim that an agent or skill was used unless it was actually invoked.

Do not invoke agents/skills mechanically. Use them when they add clear value for the task size, risk, or uncertainty.

The main agent remains responsible for synthesizing agent/skill output, choosing scope, applying project instructions, and making the final implementation decision.

Use at most one planning/exploration subagent before implementation unless the task is explicitly broad, risky, security-sensitive, or the user asks for a multi-agent review.

---

## Connectors

| Connector | When to use |
|---|---|
| `GitHub` | Repository, issue, PR, branch, remote code, or review context |
| `Context7` | Current documentation for external libraries/frameworks |

Use project-local code before external documentation. Use Context7 only when library behavior, API usage, or version-specific docs matter.
Do not use GitHub for local-only tasks unless remote context is explicitly needed.

## Skill/agent groups

| Skill group | When to use |
|---|---|
| `Engineering` | General implementation, refactoring, debugging |
| `Ecc` | Subagents for specialized planning, review, FastAPI/TypeScript/security/debug workflows |
| `Caveman` | Small bounded tasks, read-only investigation, surgical edits |
| `Andrej Karpathy skills` | Coding discipline and behavioral guardrails |
| `UI UX Pro Max` | UI pages, components, dashboard UX, visual redesign |
| `Data` | Data/file analysis, reports, tables, transformations |
| `Code review graph main` | Structural review, dependency graph, cross-file impact analysis |

---

## Review agents

Use after meaningful modifications when the touched area matches the trigger. Prefer targeted reviewers over broad multi-agent review.

| Agent | Trigger |
|---|---|
| `ecc:python-reviewer` | Python files changed |
| `ecc:fastapi-reviewer` | FastAPI routes, request/response models, or API behavior changed |
| `ecc:typescript-reviewer` | TypeScript or TSX files changed |
| `ecc:security-reviewer` | Auth, vault, tokens, secrets, API permissions, sensitive settings, or persistence of sensitive values changed |

---

## Planning agents

Use before implementation only when the task is broad, cross-cutting, ambiguous, or risky enough to benefit from a separate planning pass.

| Agent | Trigger |
|---|---|
| `ecc:planner` | New feature or multi-step implementation |
| `ecc:code-architect` | Implementation blueprint across backend/frontend/settings |
| `ecc:architect` | Major refactor or system-level design decision |
| `ecc:code-explorer` | Read-only mapping, audit, or unfamiliar area of the codebase |

---

## Debugging and quality agents

| Agent | Trigger |
|---|---|
| `ecc:build-error-resolver` | Build, typecheck, import, or test failures |
| `ecc:silent-failure-hunter` | Swallowed errors, false success states, bad fallbacks, missing user-visible errors |
| `ecc:refactor-cleaner` | Explicit cleanup tasks, dead code removal, unused imports, half-feature removal |
| `ecc:performance-optimizer` | UI lag, slow API responses, repeated queries, bundle-size concerns |

---

## UI/UX agents and skills

| Agent/Skill | Trigger |
|---|---|
| `/ui-ux-pro-max` | Creating or redesigning a visible UI component, page, dashboard surface, empty state, loading state, or error state |
| `ecc:a11y-architect` | Accessibility review, keyboard navigation, focus states, ARIA, contrast, or WCAG concerns |

---

## Testing agents

| Agent | Trigger |
|---|---|
| `ecc:e2e-runner` | Playwright or end-to-end user-flow validation |
| `ecc:tdd-guide` | User explicitly asks for TDD, or feature is test-first |
| `ecc:pr-test-analyzer` | PR-level test coverage review |

---

## Bounded task agents

Use only for small, well-scoped tasks.

| Agent | Trigger |
|---|---|
| `caveman:cavecrew-builder` | 1–2 file surgical implementation |
| `caveman:cavecrew-investigator` | Read-only lookup: find definitions, callers, configs, or data flow |
| `caveman:cavecrew-reviewer` | Review a diff or small file set |

---

## External documentation

Prefer Context7 for official/current library documentation when available. Use `ecc:docs-lookup` when Context7 is unavailable, insufficient, or the skill provides better project-specific lookup.

| Skill | Trigger |
|---|---|
| `ecc:docs-lookup` | Need current library docs for FastAPI, TanStack Router, TanStack Query, Zod, shadcn/ui, Tailwind, Click, PyYAML, or Fernet |
| `ecc:doc-updater` | User explicitly asks to update docs, codemaps, README, or architecture notes |

---

## Trigger summary

- Python changed: consider `ecc:python-reviewer`
- FastAPI/API behavior changed: consider `ecc:fastapi-reviewer`
- TypeScript/TSX changed: consider `ecc:typescript-reviewer`
- Auth/vault/API/sensitive data changed: strongly prefer `ecc:security-reviewer`
- New cross-cutting feature: consider `ecc:planner` or `ecc:code-architect`
- UI page/component redesigned: consider `/ui-ux-pro-max`
- Build/type/test failure: use `ecc:build-error-resolver`
- Silent failure or fake success suspected: use `ecc:silent-failure-hunter`