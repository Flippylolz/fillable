# Local authentication

E02.1 uses PostgreSQL users, opaque server sessions and login-attempt windows.
Accounts have UUIDs, normalized email, display name, role (`user`/`admin`), active
status and constrained `ui_language` (`uk`/`en`, default `uk`). Public responses
whitelist account fields; password hashes and session hashes are never returned.
Provisioning/reset require operator access to container commands; no public signup.

Passwords use pinned argon2-cffi 25.1.0's Argon2id defaults, random salts and
rehashing after successful authentication when parameters change. Passwords contain
12–1024 Unicode characters and are not trimmed or normalized. Hashing/verification
is bounded to two simultaneous operations per process. Unknown accounts undergo a
dummy verification and receive the same credential error. PostgreSQL attempt rows,
keyed by a hash of normalized email, serialize concurrent attempts and limit five
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

The distinct host-only HttpOnly SameSite=Strict cookie has Secure=false for the
explicitly accepted HTTP origin; HTTPS configuration enables Secure. Exact-origin
checks include the port. Cookies themselves are not port-isolated. This preserves
D019, rather than silently changing the requested public origin. The four-page UI
restores the saved account language on session load/login; successful logout clears
the password field. Failed requests retain inputs/authenticated state as appropriate.
Profile editing and language preference updates remain E02.6/E02.7.

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
