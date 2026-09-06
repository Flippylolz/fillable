# One task per pull request

Status: the user requires every task to use its own PR and requested auto-merge. Repository-level `allow_auto_merge` was enabled and verified on `Flippylolz/fillable` on 2026-09-06. P00 publishes the planning documents through a dedicated PR; application CI and required branch checks remain E01 work.

## Task boundary

- A task means an individual work item such as `E02.3`, not an entire epic. Each task has a dedicated branch and PR, including its necessary tests and documentation.
- Give new work outside the existing roadmap a task ID and clear acceptance criteria before implementation.
- Do not bundle unrelated tasks or complete an entire epic in one PR. If a task is too large, split it into named subtasks first and give each its own PR.
- Repository-setting changes are tracked with their configuration evidence in the task's documentation/PR; some effects occur through the GitHub API rather than a file diff.
- Prefer branches such as `task/e02-3-local-storage`. Start from current `origin/main` after prerequisite PRs have merged. Avoid dependent PR chains unless the task requires one and its base/dependency is documented.
- Implementation changes go through PRs, not direct pushes to `main`. Do not bypass required checks or use an administrator merge to accelerate a task.

## Delivery workflow

1. Read the task's scope, dependencies, and acceptance criteria. Check the existing branch and PR state before creating duplicates.
2. Implement one task on its branch. Include behavior-focused tests and relevant `AI/` updates.
3. Run applicable Docker checks. Application changes must meet the independent backend/frontend 90% line and branch gates in [CI and deployment](CI_CD.md).
4. Push the task branch and create a PR targeting `main`. Use a draft while work is incomplete; make it ready only when the result is reviewable.
5. Title the PR with the task ID and concrete outcome. Explain the problem/result, relevant validation, measured coverage where applicable, limitations, and dependencies. Use a body file or structured API argument to preserve formatting.
6. Inspect the actual repository rules and required CI check for this PR. Repository-level auto-merge availability does not itself enforce coverage or enable auto-merge on every PR.
7. Enable auto-merge for the ready PR with squash as the default method, subject to repository policy. Use the verified PR head commit to avoid acting on an unexpected revision. An example command contract is `gh pr merge <PR> --repo Flippylolz/fillable --auto --squash --match-head-commit <HEAD_SHA>`.
8. Follow check results, fix failures on the same branch, and verify auto-merge remains enabled after updates. Do not dismiss failures, reduce thresholds, or manually bypass the gate.
9. Verify the PR actually reached `MERGED`, record its URL and resulting merge commit, then synchronize local `main` before starting a dependent task. Record a task's own final merge evidence in its PR body first and carry it into the ledger in the next task PR; the current commit cannot contain its own final merge hash. GitHub's actual merge state is authoritative.

The user has authorized the routine branch/PR/auto-merge workflow for project tasks. Do not ask again for each ordinary task PR. This does not authorize unrelated publishing, purchasing, or moving deployment ahead of E08.

Reference: [GitHub CLI auto-merge options](https://cli.github.com/manual/gh_pr_merge).

## Merge gate and readiness

- Once CI is established in E01, `main` must require PRs and the stable `ci-required` check. Require checks against an up-to-date base, or a verified merge-queue equivalent if adopted later.
- Do not introduce a mandatory human approval solely as a substitute for automated checks; honor any review requirements actually configured by the owner.
- Auto-merge may be armed while required CI is running, but only when the actual branch rules guarantee that failing, skipped, cancelled, or missing required checks prevent merging.
- If repository checks/protection are not established, leave a code PR unmerged and record the missing prerequisite. Do not rely on `--auto` as a safety mechanism: a mergeable PR can merge immediately.
- A docs-only PR still follows the PR workflow and its applicable checks. Coverage is not fabricated for documentation; the first application source must arrive with working coverage enforcement.
- Draft/open/auto-merge-enabled does not mean done. Track the task as `in_review` until its PR merges and acceptance evidence is complete; keep its epic open until all required tasks are delivered.
- A failed or disabled auto-merge request is an unresolved delivery state. Diagnose the actual reason and continue safe work; do not report a merge that did not happen.

## Initial repository state

The remote was verified empty before P00. Empty commit `3820bff` established the base `main` branch on 2026-09-06 and contains no files. P00 delivers the planning documents on `task/p00-mvp-plan` through a PR. This minimal Git-history bootstrap must not be reused to deliver application/task changes directly to `main`.

E01 must establish minimum Docker test/coverage CI and required repository rules before the first application PR merges. Later E01 tasks may expand the checks, but the 90% requirement is not postponed until those tasks finish.

## Deployment remains separate

Merging an ordinary task PR does not deploy the application. E08 remains the final task and uses the GitHub Actions deployment workflow after all previous epics pass. Its code/configuration is also delivered through its own task PRs, with server actions and shared-nginx evidence recorded in the corresponding task record.
