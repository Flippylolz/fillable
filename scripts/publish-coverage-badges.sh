#!/bin/sh
# Publish generated files only; never change the application branch.
set -eu
badges=$(cd "$1" && pwd)
revision=$2
current=$(git ls-remote origin refs/heads/main | cut -f1)
if [ "$current" != "$revision" ]; then
  echo "Skip badges: this run is no longer the main revision."
  exit 0
fi
work=$(mktemp -d)
trap 'git worktree remove --force "$work" >/dev/null 2>&1 || true; rmdir "$work" 2>/dev/null || true' EXIT
remote=$(git ls-remote origin refs/heads/coverage-badges)
if [ -n "$remote" ]; then
  git fetch origin refs/heads/coverage-badges
  git worktree add --detach "$work" FETCH_HEAD
else
  git worktree add --detach --no-checkout "$work" HEAD
  git -C "$work" switch --orphan coverage-badges
fi
cp "$badges/backend.svg" "$badges/frontend.svg" "$badges/coverage.json" "$work/"
git -C "$work" add backend.svg frontend.svg coverage.json
if git -C "$work" diff --cached --quiet; then
  echo "Coverage badges already current."
  exit 0
fi
git -C "$work" -c user.name='github-actions[bot]' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' commit -m "Update coverage badges for $revision"
# Recheck after preparation; never force-push over another publisher.
current=$(git ls-remote origin refs/heads/main | cut -f1)
if [ "$current" != "$revision" ]; then
  echo "Skip badges: main advanced during badge preparation."
  exit 0
fi
git -C "$work" push origin HEAD:refs/heads/coverage-badges
