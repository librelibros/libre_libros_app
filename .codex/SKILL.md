---
name: developing-features
description: Orchestrates end-to-end feature development through a multi-agent pipeline. Product Manager defines requirements, Codebase Analyst gathers project context, UX Experience defines the UI/UX baseline, Technical Product Manager breaks requirements into atomic tasks, parallel Development agents implement changes, a Validator ensures code quality with up to 2 review iterations, UX Refinement modernizes the shipped interface based on executed test evidence, and the workflow finishes by re-running the relevant tests and creating a final commit. Use when requesting new functionality, implementing features, or developing new capabilities.
---

# Developing Features

## Artifacts Directory

All generated markdown artifacts are stored in `generated/` within the working directory. Create this directory at the start of execution if it does not exist.

If `generated/project-context.md` exists, treat it as the shared cross-agent orientation file for this repository. Read it early in each phase to accelerate understanding, but always verify implementation details against the current codebase.

## Pipeline Overview

```
User Request
     |
     v
[PRODUCT-MANAGER] --> generated/feature-spec.md
     |
     v
[CODEBASE-ANALYST] --> generated/codebase-context.md
     |
     v
[UX-EXPERIENCE] --> generated/ux-spec.md
     |
     v
[TECHNICAL-PRODUCT-MANAGER] --> generated/technical-plan.md
     |                          (per-task context included)
     v
[DEVELOPER x N] (parallel) --> generated/task-report-XXX.md + code
     |
     v
[TECHNICAL-PRODUCT-MANAGER] (verification)
     |
     v
[VALIDATOR] --> reviews + WebSearch best practices
     |              + updates CODEBASE-ANALYST.md guardrails
     |
     +--> CRITICAL/MAJOR? --> [DEVELOPER fixes] (max 2 iterations)
     |
     v
[UX-REFINEMENT] --> evidence-led UI improvements
     |               + refreshed screenshots/logs
     v
 [FINALIZE] --> final test pass + intentional commit
     |
     v
   Done --> generated/validation-report.md
            generated/codebase-context-updates.md
            generated/ux-refinement-report.md
```

**Every agent in this pipeline runs as a subagent via the Task tool.** The orchestrator (this file) ONLY coordinates — it reads artifacts from `generated/`, passes them to the next subagent, and handles user interaction. This preserves the main context window and keeps each agent's work isolated.

## Agents

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| Product Manager | Define and clarify feature requirements | User request (text, examples, images, files) | `generated/feature-spec.md` |
| Codebase Analyst | Gather project technologies, libraries, conventions | Project codebase | `generated/codebase-context.md` |
| UX Experience | Define UI/UX baseline and interaction guidance | `generated/feature-spec.md` + `generated/codebase-context.md` + codebase | `generated/ux-spec.md` |
| Technical Product Manager | Break feature into atomic tasks with project context | `generated/feature-spec.md` + `generated/codebase-context.md` + `generated/ux-spec.md` + codebase | `generated/technical-plan.md` |
| Developer (x N) | Implement atomic tasks in parallel | Single task from `generated/technical-plan.md` | Code changes + `generated/task-report-XXX.md` |
| Validator | Review code quality (never modifies code), research best practices online, update CODEBASE-ANALYST.md with guardrails | All changes + all artifacts in `generated/` | `generated/validation-report.md` + `generated/codebase-context-updates.md` |
| UX Refinement | Use executed test evidence and screenshots to modernize and polish the UI | `generated/ux-spec.md` + `generated/validation-report.md` + latest `test_plan/` evidence + codebase | Code changes + `generated/ux-refinement-report.md` + refreshed `test_plan/` evidence |
| Finalize | Re-run relevant tests after all fixes and refinements, review git scope, and create the final commit | Latest code + generated artifacts + latest `test_plan/` evidence | Passed verification commands + git commit |

## Execution Rules

1. **Every phase runs as a subagent** using the Task tool — never execute agent logic in the main orchestrator context
2. Execute agents **sequentially** in pipeline order (except Developers which run in parallel)
3. Each phase MUST complete before the next one starts
4. Pass artifacts between agents via structured markdown files in `generated/` — the orchestrator reads these files to verify completion and pass context to the next subagent
5. Never skip an agent phase
6. The user MUST confirm `generated/feature-spec.md` before development begins
7. If there are ambiguities in the user request, ask clarifying questions during the Product Manager phase before finalizing the spec
8. Create the `generated/` directory at the start if it does not exist
9. Unless the user explicitly opts out, the workflow must end with a git commit that captures the delivered changes
10. Validation is not complete until the relevant automated tests and browser-based flows have been executed after the last code change

## Subagent Launch Pattern

For each phase, the orchestrator must:

1. **Read** the agent definition file (e.g., `PRODUCT-MANAGER.md`)
2. **Launch** a subagent via the Task tool, including:
   - The full agent definition content in the prompt
   - References to input artifacts the subagent must read from `generated/`
   - The working directory path
3. **Wait** for the subagent to complete
4. **Verify** the expected output artifact exists in `generated/`
5. **Proceed** to the next phase

```
# Subagent launch template (per phase):

Task tool call:
  subagent_type: "general-purpose"
  description: "[Phase name] - [3-5 word summary]"
  prompt: |
    [Full content of the agent .md file]

    Working directory: [path]
    Input artifacts to read: [list of generated/*.md files]
    Output artifact to write: [generated/output-file.md]
```

**IMPORTANT**: The orchestrator must NEVER attempt to do the agent's work itself. Each agent's logic, tools usage, and decision-making happens entirely within its subagent context.

## Phase 1: Product Manager

Launch a subagent with the contents of [PRODUCT-MANAGER.md](PRODUCT-MANAGER.md).

**Input**: The user's feature request (text, examples, images, files) — include the full user request in the subagent prompt
**Output**: `generated/feature-spec.md`

After the subagent completes, read `generated/feature-spec.md` and present it to the user for confirmation. If the user wants changes, launch the Product Manager subagent again with the feedback.

## Phase 2: Codebase Analysis

Launch a subagent with the contents of [CODEBASE-ANALYST.md](CODEBASE-ANALYST.md).

**Input**: Project codebase (the subagent explores using Read, Grep, Glob tools)
**Output**: `generated/codebase-context.md`

This phase runs automatically after the feature spec is confirmed. No user interaction needed.

## Phase 3: UX Experience

Launch a subagent with the contents of [UX-EXPERIENCE.md](UX-EXPERIENCE.md).

**Input**: Tell the subagent to read `generated/feature-spec.md` + `generated/codebase-context.md` and inspect the codebase only as needed to understand existing UI patterns
**Output**: `generated/ux-spec.md`

This phase runs automatically after codebase analysis. It should default to simple Material Design-based guidance for new projects or new UI surfaces unless the codebase already has an established UI system or the user requested a different direction.

## Phase 4: Technical Planning

Launch a subagent with the contents of [TECHNICAL-PRODUCT-MANAGER.md](TECHNICAL-PRODUCT-MANAGER.md).

**Input**: Tell the subagent to read `generated/feature-spec.md` + `generated/codebase-context.md` + `generated/ux-spec.md` and explore the project codebase
**Output**: `generated/technical-plan.md`

The TPM produces an ordered list of atomic tasks, each enriched with relevant project context from `generated/codebase-context.md` and UX constraints from `generated/ux-spec.md`.

## Phase 5: Parallel Development

Read [DEVELOPER.md](DEVELOPER.md) to get the Developer agent definition.

For each task in `generated/technical-plan.md`, launch a Developer subagent via the Task tool. Include the task description and the full Developer agent instructions in the prompt. **Tasks without dependencies launch in parallel** (multiple Task tool calls in a single message).

**Input per subagent**: Single task description from `generated/technical-plan.md` + Developer agent definition
**Output per subagent**: Code changes + `generated/task-report-XXX.md` (where XXX is the task ID)

After all Developer subagents complete, launch a Technical Product Manager subagent to verify all tasks match the plan.

## Phase 6: Validation (max 2 iterations)

Launch a subagent with the contents of [VALIDATOR.md](VALIDATOR.md).

**Input**: Tell the subagent to read all artifacts in `generated/` and review all code changes
**Output**: `generated/validation-report.md` + `generated/codebase-context-updates.md`

The Validator:
1. Researches best practices online (WebSearch) for the project's language and framework
2. Reviews all code but **never modifies it** — all fixes are delegated to Developer agents
3. Returns CRITICAL and MAJOR issues to Developer agents for immediate fix
4. Updates [CODEBASE-ANALYST.md](CODEBASE-ANALYST.md) with guardrails so the agent includes them in future outputs
5. Produces `generated/codebase-context-updates.md` summarizing what was added to `CODEBASE-ANALYST.md`

### Feedback Loop

```
Iteration 1:
  Validator subagent reviews (no code changes)
  -> Zero CRITICAL and MAJOR? -> APPROVED -> Done
  -> Any CRITICAL or MAJOR? -> CHANGES_REQUESTED -> Launch Developer subagents for fixes -> Iteration 2

Iteration 2:
  Validator subagent re-reviews (no code changes)
  -> Zero CRITICAL and MAJOR? -> APPROVED -> Done
  -> Still CRITICAL or MAJOR? -> Escalate to user
```

**On CHANGES_REQUESTED**: Read `generated/validation-report.md`, extract CRITICAL and MAJOR findings, and launch Developer subagents with specific fix instructions. After Developer subagents complete, launch the Validator subagent again for re-review.

**On escalation**: Present unresolved issues to the user with options to approve as-is, provide guidance, or adjust requirements.

## Phase 7: UX Refinement

Launch a subagent with the contents of [UX-REFINEMENT.md](UX-REFINEMENT.md).

This phase runs only after the Validator has reached `APPROVED`.

**Input**: Tell the subagent to read `generated/feature-spec.md`, `generated/ux-spec.md`, `generated/validation-report.md`, and the latest relevant evidence under `test_plan/`, including screenshots and `run-log.md`
**Output**: Code changes + `generated/ux-refinement-report.md` + a fresh evidence folder such as `test_plan/<date>-ux-refinement/`

The UX Refinement agent:
1. Reviews the executed user journeys and screenshots from a UX expert perspective instead of relying on abstract guidelines alone
2. Identifies friction in hierarchy, spacing, readability, responsiveness, feedback states, and visual consistency
3. Explicitly checks whether the primary workflow fits well in a common laptop viewport such as 1366x768 or 1280x720 without excessive scrolling
4. Applies the necessary user-facing code changes to move the UI toward a modern, usable, visually pleasant front end without changing product scope
5. Re-runs the relevant flow after refinement and stores updated screenshots and logs so the improvements are traceable

## Phase 8: Finalize and Commit

After UX Refinement completes, the orchestrator must do a final close-out pass:

1. Re-run the relevant automated test commands for the delivered scope
2. Re-run any browser-based validation flow affected by the latest changes when the change is user-facing
3. Review `git status` and ensure only the intended files are included
4. Create one or more intentional commits with clear messages that reflect the delivered work
5. Report the verification commands executed and the resulting commit hash(es) in the final response

Do not skip this phase unless the user explicitly asks for no commit or no git interaction.

## Workflow Checklist

```
Feature Development Progress:
- [ ] Phase 1: Product Manager subagent defines feature requirements
- [ ] User confirms feature specification
- [ ] Phase 2: Codebase Analyst subagent gathers project context
- [ ] Phase 3: UX Experience subagent defines the UX baseline and UI guidance
- [ ] Phase 4: Technical Product Manager subagent creates atomic task breakdown
- [ ] Phase 5: Developer subagents implement tasks in parallel
- [ ] Phase 5b: Technical Product Manager subagent verifies task completion
- [ ] Phase 6: Validator subagent reviews code quality + researches best practices online
- [ ] Phase 6a: Validator subagent updates CODEBASE-ANALYST.md with guardrails
- [ ] Phase 6b: Developer subagents fix CRITICAL/MAJOR issues (if any, max 2 iterations)
- [ ] Phase 7: UX Refinement subagent reviews `test_plan/` evidence and applies UI improvements
- [ ] Phase 7a: UX Refinement subagent refreshes screenshots and run logs after the UI changes
- [ ] Phase 8: Final verification commands are executed after the last code change
- [ ] Phase 8a: A final git commit is created for the delivered work
- [ ] Feature delivered
```
