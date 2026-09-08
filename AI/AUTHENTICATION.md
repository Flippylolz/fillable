# Local authentication

E02.1 uses PostgreSQL users, opaque server sessions and login-attempt windows.
Accounts have UUIDs, normalized login, display name, role (`user`/`admin`), active
status and constrained `ui_language` (`uk`/`en`, default `uk`). Public responses
whitelist account fields; password hashes and session hashes are never returned.
Login names contain 3–254 Unicode letters, numbers, underscores or `. @ + -`,
with surrounding whitespace removed and case folded. The API exposes `login`;
legacy `email` request input and CLI `--email` remain aliases. Existing email-shaped
identifiers, UUIDs, password hashes, sessions and document ownership are preserved.
The historical database column remains `users.email`; no data migration is needed.
Provisioning/reset require operator access to container commands; no public signup.

Passwords use pinned argon2-cffi 25.1.0's Argon2id defaults, random salts and
rehashing after successful authentication when parameters change. Passwords contain
10–1024 Unicode characters and are not trimmed or normalized. Hashing/verification
is bounded to two simultaneous operations per process. Unknown accounts undergo a
dummy verification and receive the same credential error. PostgreSQL attempt rows,
keyed by a hash of normalized login, serialize concurrent attempts and limit five
failures per 15-minute window, including unknown accounts. Failure increments
commit before the response; successful login/reset clears the window.

Cookies carry a fresh random 256-bit token; only its domain-separated SHA-256 hash
is stored. CSRF tokens use a separate hash domain over the unpredictable raw token,
and are returned only through same-origin session responses. They cannot recover
the cookie token. Browser mutations require this token and the explicitly configured
exact origin; request Host/forwarded headers do not establish trust. Cookie values
with duplicate names are not accepted as sessions. No tokens use localStorage/JWT.

Anonymous login sessions expire after 15 minutes. Authenticated sessions expire
absolutely after 12 hours and after 30 minutes idle; requests never extend the
absolute deadline. Login rotates token/CSRF; logout revokes and creates an anonymous
session. Credential reset revokes all user sessions. Disabled users lose session
access. Absolute-expired session rows are cleaned during bootstrap; idle/disabled sessions are rejected and removed when read. Expired attempt windows are cleaned during authentication.
All auth/error responses are `no-store`. Role guards query current account state;
future protected APIs must use these guards and their own ownership checks.

The distinct host-only HttpOnly SameSite=Strict cookie requires Secure for the
D024 production HTTPS origin. Local HTTP development retains its scheme-specific configuration. Exact-origin
checks include the port. Cookies themselves are not port-isolated. This preserves
D019, rather than silently changing the requested public origin. The four-page UI
restores the saved account language on session load/login; successful logout clears
the password field. Failed requests retain inputs/authenticated state as appropriate.
E02.6 adds profile editing; E02.7 adds persisted language preferences.

The profile shows read-only login and authenticated storage usage, and permits a
trimmed nonblank display name up to 120 characters. `PATCH /api/profile` accepts
only `display_name`. `POST /api/profile/password` requires the current password and
a new 10–1024-character password; five failed verifications per 15-minute window
are allowed per account. Successful changes revoke every existing session and issue
a fresh current cookie/CSRF pair. Invalid current credentials preserve sessions.
Both mutations recheck active account/session state under transaction locks and
reject extra fields, including role, quota and language. Credential operations
acquire attempt buckets before user rows to avoid reset/login lock inversion.

Profile and logout requests are serialized in the UI. Failed saves preserve drafts;
successful password changes clear credential inputs. Usage failures have an explicit
retry and never display fabricated zero counters. The responsive profile is currently
the signed-in content of the foundation shell; E03 supplies library navigation.

`PATCH /api/profile/language` accepts only `ui_language: "uk" | "en"`, using the
same exact-origin, CSRF and active-session transaction checks. Its only database
write is the authenticated user's preference; it does not write files, reserve
storage, or create document work. The returned account preference applies immediately
without remounting profile/editor state. Failed saves restore the saved selector
value and keep the applied language and other drafts. Every authenticated bootstrap
and login restores the database value, overriding stale browser UI state. A fresh
anonymous page defaults to Ukrainian regardless of browser locale; no browser-local
language preference is persisted.

Validation must include real PostgreSQL migrations/constraints, concurrent attempt
accounting, session rotation/expiry/revocation, inactive users, role separation,
CSRF/origin failures, private operator commands and browser login/logout on both
viewports. The test harness explicitly provisions a synthetic fixture only in its
isolated databases. No application startup creates credentials.

Primary references inspected on 2026-09-06: [argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html),
[package metadata](https://pypi.org/project/argon2-cffi/),
[OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html),
and [password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

## Expired-session recovery

A protected API 401 opens an inline recovery form. The authenticated workspace
stays mounted, hidden and inert; editing, autosave and new protected requests pause.
Recovery fetches a fresh session/CSRF token. The same account UUID resumes its draft
and undo history; otherwise the form fixes the original account login and requests
its password. Failed login retains the form. Bootstrap and login requests abort on
unmount and time out after ten seconds. The account strip also offers sign-in again
for stale-CSRF errors or session changes in another tab.

Switching to a different account or leaving for the login page requires the existing
unsaved-work discard guard. A different account UUID remounts the page tree so it
cannot inherit the prior account's workspace. A locale/name update alone does not
replace the request generation. Recovery and CSRF/identity changes fence old protected
responses: they cannot apply old data, and discarded write responses remain uncertain
so the original idempotency key and snapshot can be retried explicitly. Fresh-session
editing still obeys server lease expiry and ownership; recovery does not steal a live
lease or silently reload a newer saved revision.
