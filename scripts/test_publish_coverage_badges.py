"""Check publishing against a disposable local remote, without credentials."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("publish-coverage-badges.sh").resolve()


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], stderr=subprocess.STDOUT, text=True
    ).strip()


class BadgePublicationTests(unittest.TestCase):
    def test_create_update_idempotence_and_stale_main(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, repo, badges = (root / name for name in ("remote", "repo", "badges"))
            for path in (remote, repo, badges):
                path.mkdir()
            git(remote, "init", "--bare")
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.name", "Test")
            git(repo, "config", "user.email", "test@example.test")
            git(repo, "remote", "add", "origin", str(remote))
            (repo / "application.txt").write_text("preserve me")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "Initial main")
            git(repo, "push", "origin", "main")
            revision = git(repo, "rev-parse", "HEAD")
            for name in ("backend.svg", "frontend.svg"):
                (badges / name).write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            (badges / "coverage.json").write_text(json.dumps({"revision": revision}))

            def publish(sha):
                subprocess.run([str(SCRIPT), str(badges), sha], cwd=repo, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            publish(revision)
            first = git(remote, "rev-parse", "coverage-badges")
            self.assertEqual(git(remote, "ls-tree", "--name-only", "coverage-badges").splitlines(),
                             ["backend.svg", "coverage.json", "frontend.svg"])
            publish(revision)
            self.assertEqual(git(remote, "rev-parse", "coverage-badges"), first)
            git(repo, "commit", "--allow-empty", "-m", "Next main")
            git(repo, "push", "origin", "main")
            next_revision = git(repo, "rev-parse", "HEAD")
            publish(revision)
            self.assertEqual(git(remote, "rev-parse", "coverage-badges"), first)
            (badges / "coverage.json").write_text(json.dumps({"revision": next_revision}))
            publish(next_revision)
            self.assertNotEqual(git(remote, "rev-parse", "coverage-badges"), first)
            self.assertEqual(git(remote, "rev-parse", "main"), next_revision)
            self.assertEqual((repo / "application.txt").read_text(), "preserve me")
            self.assertEqual(git(repo, "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
