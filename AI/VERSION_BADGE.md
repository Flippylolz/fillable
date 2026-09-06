# Git version badge

Status: E01.8 implements the shared shell badge and Docker build metadata. Live release wiring and verification remain E08; later page tasks preserve the shared mount.

## Display and behavior

Render one small badge in the shared application shell on all four pages, including login. Show `version: abc1234`, where the value is the first seven characters of the deployed source commit, or exactly `version: development` when commit metadata is unavailable. `abc1234` is an example, never a hardcoded release value.

Keep it fixed near the bottom-right corner on desktop and mobile using the safe-area-aware positions below. Preserve the deliberate `2.75rem` bottom offset for other bottom-edge controls; this does not add a map or attribution feature to Fillable. Mount outside transformed or clipped page/editor containers so positioning remains relative to the viewport.

The badge is subtle and translucent, with explicit colors independent of light/dark theme. It has no icon, link, tooltip, hover action, event handler, or focus/tab stop. Pointer/touch clicks pass through to underlying controls; descendants must not override `pointer-events: none`. Keep the value in a monospace `code` element and expose the version through an accessible label without a live announcement.

User-supplied English markup reference:

```html
<div class="version-badge" aria-label="Application version abc1234">
  version: <code>abc1234</code>
</div>
```

## Required styling

Preserve these supplied declarations and literal colors; do not substitute theme tokens or responsive offsets:

```css
.version-badge {
  position: fixed;
  z-index: 20;
  right: max(0.5rem, env(safe-area-inset-right));
  bottom: calc(2.75rem + max(env(safe-area-inset-bottom), 0rem));

  padding: 0.2rem 0.4rem;
  border: 1px solid #30363d;
  border-radius: 0.35rem;
  background: rgb(22 27 34 / 85%);
  color: #8b949e;
  box-shadow: 0 0.2rem 0.8rem rgb(0 0 0 / 40%);

  font-family: Inter, ui-sans-serif, system-ui, -apple-system,
    BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 0.65rem;
  line-height: 1.2;

  opacity: 0.78;
  pointer-events: none;
  backdrop-filter: blur(4px);
}

.version-badge code {
  font-size: inherit;
  font-variant-numeric: tabular-nums;
}
```

Also give `.version-badge code` an explicit system monospace stack (for example `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace`). Inherit the badge's text color and neutralize any theme's inline-code background, border, or padding. Do not download a font just for the badge. Preserve the badge's dimensions and supplied outer styling.

## Version source

- Inject the full source commit into the frontend at build time. Proposed configuration: a `VITE_APP_COMMIT_SHA` build argument/environment value available to the frontend build, carried through Docker and consumed in the compilation stage. This value is public metadata, never a credential. See [Vite environment handling](https://vite.dev/guide/env-and-mode) and [Docker build variables and scope](https://docs.docker.com/build/building/variables/).
- Derive it from the exact checked-out revision whose tested artifacts are being deployed. A manually selected older release must show that release's hash, not the workflow trigger's revision, current default-branch tip, or the deployment server's checkout.
- Trim the supplied value, accept a hexadecimal commit value of at least seven characters, and display its first seven characters. Missing, blank, malformed, or too-short metadata yields `development`; do not render `undefined`, an empty badge, or a guessed hash.
- Local Docker builds may receive the current commit explicitly and must work without it using the same fallback. No browser request to GitHub, backend version endpoint, runtime `.git` directory, or Node backend service is needed.
- Ensure a changed commit value reaches the frontend compilation and invalidates its relevant Docker build cache. A runtime environment variable on a container serving already-built static assets is insufficient.
- The E08 workflow supplies the verified full source commit and checks the served badge against the released artifact. The fallback keeps unconfigured local/manual builds usable; a controlled production release showing `development` or the wrong commit fails its release smoke check. Build and deploy immutable artifacts under the existing [CI and deployment](CI_CD.md) contract.

## i18n

Store badge messages in both catalogs under D021. Preserve the user's exact visible `version:` label and `development` token in both languages as a narrow design requirement; other UI text continues to use Ukrainian/English translations. Localize the accessible label. Proposed logical keys:

| Key | Ukrainian catalog | English catalog |
| --- | --- | --- |
| `versionBadge.text` | `version: {version}` | `version: {version}` |
| `versionBadge.development` | `development` | `development` |
| `versionBadge.ariaLabel` | `Версія застосунку {version}` | `Application version {version}` |

Render the message's version interpolation through a safe component slot so only its value is inside `code`; do not inject HTML or build translation keys from the hash. The commit value itself is build data, not translated text. Exact key syntax follows the free i18n library selected in E01.

## Acceptance for implementation

- A known full commit shows its first seven characters; absent/invalid metadata shows the exact fallback. The accessible label follows the displayed value and selected UI language.
- The badge appears once across all four pages, stays fixed during scrolling, and retains the specified offset, colors, opacity, and monospace value at desktop/mobile viewport sizes and with safe-area insets.
- Check light/dark theme styling and any global inline-code styles. Verify clicks/taps reach a real control beneath the badge and keyboard focus skips it; there is no tooltip, link, icon, or interaction.
- Verify the built static frontend with supplied and missing metadata through Docker. For a controlled release, confirm the badge matches that artifact's source commit, including when deploying a selected older revision.
- Use focused version-resolution/build checks and browser verification within the existing 90% coverage/CI contract. Do not add exhaustive tests mirroring every CSS declaration for this small presentation feature.

Implementation is in `frontend/src/VersionBadge.tsx`, mounted beside the application
outside page containers in `main.tsx`. Catalog component slots safely place only
the resolved value in `code`. The exact `version:` and `development` strings remain
in both catalogs; accessible labels follow the selected locale. The Docker build
stage consumes `VITE_APP_COMMIT_SHA`, forwarded by Compose, before Vite compiles.

Focused unit tests cover valid/invalid/missing metadata and locale updates without
remounting. Browser checks cover desktop/mobile fixed placement, keyboard skipping,
mouse/touch click-through to the real retry button, theme inline-code overrides and
simulated safe-area insets through Chromium's
[Emulation API](https://chromedevtools.github.io/devtools-protocol/tot/Emulation/#method-setSafeAreaInsetsOverride).
CI checks a supplied checked-out commit in the first production build and the
fallback in the fresh-development build. Four-page integration awaits those pages
and E07; live immutable-release verification remains final epic E08.
