# MVP acceptance evidence

E07.1b verifies the four-page user workflow on the synthetic Ukrainian corpus.
Its browser run and PR must pass before this record is marked complete. E07.2–E07.6
and final deployment remain separate, unfinished tasks in [Epics](EPICS.md).

| Contract | Executable evidence |
| --- | --- |
| Login → upload template → detector review → sidebar edit → save → use template → independent edit → download/reopen | `frontend/e2e/mvp-acceptance.spec.ts`, through actual controls and the real API/worker/storage stack |
| Source restoration preserves the derived document's saved bytes, review and history | The same journey checks source history 3/2/1, copy history 2/1, exact downloads and unchanged copy current revision |
| Four pages in Ukrainian/English with one correct source badge each | The same journey walks login/library/profile/workspace in both languages on desktop/mobile; `version-badge.spec.ts` independently covers exact CSS, themes, safe areas and click-through |
| Readable remaining allowance | Profile allowance renders localized GB values; `app.test.tsx` covers decimal B/kB/MB/GB/TB/PB formatting without changing exact API counters |
| Direct editing, linked fields, selection, undo/redo, Unicode and native composition | `e2e-dev/editor.spec.ts`, `review.spec.ts`, `manual-save.spec.ts`, `autosave.spec.ts`, `editing-lease.spec.ts` |
| Localized profile persistence/failure and draft preservation | `profile.spec.ts`, `library.spec.ts`, profile/unit tests, plus the complete acceptance journey |
| Expired/revoked sessions, same-owner draft/undo recovery and explicit account isolation | `session-recovery.spec.ts`, merged E07.1a PR62; request-body/response-body cancellation and exact retry unit tests |
| History read-only previews, selected downloads, restore/quota/conflict/uncertain retry | `history.spec.ts`, `saves-api.spec.ts`, and real PostgreSQL save/restore/retention tests |
| Operator accounts/quotas and displayed enforcement | `scripts/verify-development.sh` provisions synthetic accounts, changes default/override/inherit through Docker commands, verifies zero-quota allocation rejection and persisted accounting; account/quota backend tests and library/profile browser flows |
| Required source-inclusive line and branch coverage | `.github/workflows/ci.yml`, raw report validation, real unimported-source negative probes and required `ci-required`; final repository-wide audit is E07.6 |

The browser suite is serial because its fixture accounts intentionally persist
language preferences and quota state. Each full verification uses an isolated
synthetic Docker project and retains its volumes. Tests do not use private user
files or a deployed server.

Compatibility remains the scope documented in [Editor feasibility](EDITOR_FEASIBILITY.md)
and [Test corpus](TEST_CORPUS.md): structural XML checks, embedded editor reopening,
and independent LibreOffice/PDF rendering are distinct evidence. The editor canvas
is structural, not Word pagination. These checks do not claim execution in Microsoft
Word or universal DOCX fidelity. Originals remain immutable, unsupported features
are surfaced, and UI language never translates document data. No AI, paid component,
backup system, administrator page or extra persistent environment is introduced.
