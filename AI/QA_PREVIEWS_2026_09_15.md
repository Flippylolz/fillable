# Preview and control acceptance — 2026-09-15

Status: manual verification in progress for E09.25–E09.28. The local Docker app and
an isolated `fillable-gallery-qa` stack use the committed synthetic Ukrainian corpus
and dedicated synthetic accounts. No private user documents were used. Browser
control used Chrome; this is not a Microsoft Word compatibility test.

## Completed manual checks

| Area | Action and observed result |
| --- | --- |
| Login/recovery | Ukrainian sign-in opened the English account; account-load and connection retry controls recovered after the isolated API/gateway rebuild. |
| Library | Upload toggle opened the form; refresh reloaded cards; search produced the empty state and recovered; title sort changed selection. |
| Placeholder | The unopened saved template showed a plain document placeholder. |
| Gallery preview | Opening the workspace and returning populated the source title, tables and typography; a full browser refresh retained the preview. |
| Template copy | Cancel closed the prompt; Create and open document produced an independent document with its requested title. |
| Fill view | Switching from document mode showed the form and a source-layout preview. The preview was inert and contenteditable=false. |
| Linked edits | Editing the client-name field updated both occurrences and the live preview; Undo and Redo restored the values. |
| Responsive preview | Desktop and 390×844 mobile screenshots inspected. At mobile width the page body stayed 390px wide and the preview fitted inside its viewport. |
| Settings | Rename changed the workspace heading; autosave toggled off; 150% editor zoom did not enlarge the fill preview; highlighting toggled off. |
| Field controls | Go to field selected the requested entry; Remove reduced the form from five entries to four; Undo restored five. |
| Save/history | Manual save completed; history listed the new revision; selecting the original displayed its original field text; restore returned to editing with the old contents. Mode buttons were disabled while history was open. |

Additional completed checks:

- Profile display-name save, storage refresh and Ukrainian language save succeeded;
  returning to the workspace preserved fill mode and its five fields.
- Selected ordinary text became a named field; Undo removed it. Previous/Next field
  controls selected entries and disabled correctly at the boundary.
- An ordinary selected glyph toggled from ☐ to ☒. Native date-field keyboard entry
  selected 2026-01-01; filling eight selected boxes produced `0|1|0|1|2|0|2|6`, and
  Undo restored `0|0|0|0|0|0|0|0`.
- Review focus, name configuration, Apply settings, Accept, Dismiss, accepted-from-
  dismissed, Undo and Save were exercised. The accepted named entry appeared in the
  field sidebar and the review changes used the same save/undo path.

## Finding and separate fix

Restoring a revision duplicated the settings panel. The settings and editor siblings
shared an epoch key. E09.28 gives each a distinct component prefix and adds a restore
regression asserting one settings panel and one editor. PR #144 carries the fix and
coverage. A temporary local integration with E09.26 was manually restored again:
DOM inspection confirmed exactly one settings panel and one editor afterward.

## Verification limits

- The browser extension rejected file-chooser upload because file-URL access was not
  enabled. The local API seeded the synthetic DOCX for manual tests. Automated browser
  upload coverage is separate evidence, not a claimed manual upload pass.
- The historical-download action reported no application error, but the browser tool
  did not deliver a download event or a verifiable local file. Transfer completion
  remains unverified manually.
- Final irreversible deletion, password-change submission and the native print dialog
  have not been manually verified in this pass. Existing automated coverage does not
  turn these into manual passes. Further control checks are recorded below as completed.
- Gallery thumbnails and fill previews use the supported browser source presentation;
  exact Word pagination remains unclaimed.

## Automated evidence

E09.25 PR #142 merged as `882de80337353c0ae4c0b980f0b5580bf36831d5` with all required
CI checks successful. Its local frontend suite passed 323 tests at 96.71% lines /
92.72% branches. E09.26 and E09.28 test/coverage and final PR evidence are recorded
in [Epics](EPICS.md) and their PRs. These measurements belong to those code changes,
not to this documentation-only task.
