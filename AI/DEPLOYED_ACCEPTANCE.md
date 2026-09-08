# Verified deployed MVP acceptance — E08.5

The application was deployed through [Actions run 34215081786](https://github.com/Flippylolz/fillable/actions/runs/34215081786)
from protected-main source `141288bcb12215fb34aede79ac2d7b7e799654d3`. Exact-main
[CI 34211072187](https://github.com/Flippylolz/fillable/actions/runs/34211072187)
passed `checks`, `upgrade-checks` and `ci-required` before dispatch. The served badge
is `141288b`, matching the immutable artifact rather than a later acceptance-doc commit.
Final acceptance delivery is tracked by [PR #75](https://github.com/Flippylolz/fillable/pull/75);
its own final merge evidence belongs in that PR body.

The delivered archive contains 130,181,120 bytes and has SHA-256
`c325afd2ad9984427fa543a2a729db712ef1bff0076f5cd6a4037869fdad0aab`.
Its source, image config bytes, OCI descriptors, platform and full revision labels
were verified. The receiver used the archive-bound immutable identities appropriate
to the target's containerd image store. See [Release artifacts](RELEASE_ARTIFACTS.md).

## Routing and preservation

D024's public origin is `https://<DEPLOY_HOST>:3200`. Only Fillable's TCP relay owns
host port 3200; shared nginx terminates TLS on its existing internal listener and
forwards HTTP to `fillable-gateway:8080` over `wef-edge`. Normal certificate/hostname
verification and Secure/HttpOnly/SameSite cookies passed. No certificate policy,
HSTS, shared nginx template/configuration/state, port mapping or reload was changed.

An active WEF rollout was allowed to finish before the final baseline was captured.
All 15 unrelated containers and six existing route/HSTS observations matched after
Fillable deployment and again after its scoped restart. Forecast HTTP 3000 and WEF
HTTP 3100/HTTPS 443 were preserved. The historical candidate edge's already-unhealthy
healthcheck remained its recorded baseline; it was not repaired or replaced.

## Private account and public flows

The requested account was created privately with `admin`, the highest supported role.
Its supplied password was preserved. Stored role and authenticated public HTTPS
session role were verified, including after restart. Credentials never entered
GitHub secrets, repository files or workflow logs; Actions uses only transport secrets.
Account identity, credentials, browser reports and detailed receipts remain private.

Credential-free Actions readiness passed. Private authenticated smoke then verified
login, cookie/origin/CSRF policy, upload, asynchronous processing, save, and exact
original/current/history downloads. Desktop and mobile browser journeys passed both
Ukrainian and English: reviewed template fields, independent filled copies, reload,
historical previews, restore-as-new-revision, downloads and persisted language changes.
The account language was returned to Ukrainian. Actual deployment screenshots were
visually inspected; the Docs-like workspace, long labels and mobile history remained
usable. No universal Microsoft Word layout compatibility is claimed.

A full Fillable-only restart preserved all 12 retained files, byte digests and quota
counters. Public post-restart checks compared the recorded current revision IDs,
canonical document models, complete history lists, and every retained revision's
DOCX digest for both desktop/mobile journeys. All matched. Synthetic acceptance
resources remain retained and quota-charged under the keep-all policy.

Four controlled desktop/mobile browser checks first required the real source badge,
then changed only the disposable browser's displayed value to `development` or a
wrong hash and verified rejection. No production asset or alternate image was served
for that negative check. The real application badge remains `141288b`.

## CI and recovery

Measured raw coverage for the deployed source is backend 3970/3999 lines (99.27%)
and 1174/1206 branches (97.35%); frontend 1292/1303 lines (99.16%) and 1500/1569
branches (95.60%). Real unimported-source probes were rejected by the independent
90% gates. Strict required `ci-required` protection includes administrator enforcement;
no administrator merge bypass or lowered threshold was used.

Runtime recovery remains schema-aware under [Server runtime](SERVER_RUNTIME.md).
Keep schema `0013_maintenance_state`, local documents and namespaced database/Redis
volumes. Prefer reviewed forward repair; older images need explicit schema and stored-
document compatibility review. An ingress verification failure stops only Fillable's
relay and preserves the owner's TLS route and private data. No shared-service rollback,
Docker restart/prune, volume deletion, backup or staging environment is part of recovery.
