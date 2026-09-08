"""Release evidence must fail closed before a receiver can be invoked."""

import copy
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import release_gate as gate
from release_artifact import file_info, pack, unpack, validate_image_archive

SOURCE = "a" * 40


def evidence():
    workflow = {"id": gate.WORKFLOW_ID, "path": gate.WORKFLOW_PATH, "state": "active"}
    run = {
        "id": 123,
        "workflow_id": gate.WORKFLOW_ID,
        "path": gate.WORKFLOW_PATH,
        "event": "push",
        "head_branch": "main",
        "head_sha": SOURCE,
        "repository": {"full_name": gate.REPOSITORY},
        "head_repository": {"full_name": gate.REPOSITORY},
        "status": "completed",
        "conclusion": "success",
        "run_attempt": 1,
    }
    jobs = {
        "total_count": 3,
        "jobs": [
            {
                "name": name,
                "status": "completed",
                "conclusion": "success",
                "head_sha": SOURCE,
                "run_attempt": 1,
            }
            for name in sorted(gate.REQUIRED_JOBS)
        ],
    }
    return workflow, run, jobs


class ReleaseGateTests(unittest.TestCase):
    def test_only_current_dispatched_main_source_is_eligible(self):
        context = {
            "repository": gate.REPOSITORY,
            "ref": "refs/heads/main",
            "event": "workflow_dispatch",
            "sha": SOURCE,
        }
        branch = {"object": {"sha": SOURCE}}
        gate.validate_source(SOURCE, context, branch)
        for value in ("", "a" * 7, "A" * 40, "b" * 40, "$(command)"):
            with self.assertRaises(ValueError):
                gate.validate_source(value, context, branch)
        for key, value in (
            ("repository", "other/repo"),
            ("ref", "refs/tags/main"),
            ("ref", "refs/heads/task"),
            ("event", "pull_request"),
        ):
            with self.assertRaises(ValueError):
                gate.validate_source(SOURCE, {**context, key: value}, branch)
        with self.assertRaises(ValueError):
            gate.validate_source(SOURCE, context, {"object": {"sha": "b" * 40}})

    def test_all_jobs_and_exact_workflow_attempt_are_required(self):
        workflow, run, jobs = evidence()
        gate.validate_ci(SOURCE, workflow, run, jobs)
        for state in (None, "failure", "cancelled", "skipped", "neutral", "timed_out"):
            with self.assertRaises(ValueError):
                gate.validate_ci(SOURCE, workflow, {**run, "conclusion": state}, jobs)
            for index in range(3):
                changed = copy.deepcopy(jobs)
                changed["jobs"][index]["conclusion"] = state
                with self.assertRaises(ValueError):
                    gate.validate_ci(SOURCE, workflow, run, changed)
        for key, value in (
            ("workflow_id", 1),
            ("path", ".github/workflows/other.yml"),
            ("head_sha", "b" * 40),
            ("event", "pull_request"),
            ("head_branch", "task"),
            ("status", "in_progress"),
            ("run_attempt", 2),
            ("head_repository", {"full_name": "fork/repo"}),
        ):
            with self.assertRaises(ValueError):
                gate.validate_ci(SOURCE, workflow, {**run, key: value}, jobs)
        for changed in (
            {},
            {"total_count": 3, "jobs": jobs["jobs"][:2]},
            {"total_count": 3, "jobs": [jobs["jobs"][0]] * 3},
        ):
            with self.assertRaises(ValueError):
                gate.validate_ci(SOURCE, workflow, run, changed)
        with self.assertRaises(ValueError):
            gate.validate_ci(
                SOURCE, {**workflow, "state": "disabled_manually"}, run, jobs
            )

    def test_latest_run_and_main_are_rechecked_after_job_lookup(self):
        workflow, run, jobs = evidence()
        branch = {"object": {"sha": SOURCE}}
        environment = {
            "GITHUB_REPOSITORY": gate.REPOSITORY,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_SHA": SOURCE,
        }
        responses = [
            branch,
            workflow,
            {"workflow_runs": [run]},
            jobs,
            run,
            {"workflow_runs": [run]},
            branch,
        ]
        with (
            patch.dict("os.environ", environment),
            patch.object(gate, "request", side_effect=responses),
        ):
            self.assertEqual(
                gate.verify(SOURCE), {"source_sha": SOURCE, "ci_run_id": 123}
            )
        for index, replacement in (
            (2, {"workflow_runs": []}),
            (2, {"workflow_runs": [{**run, "conclusion": "failure"}]}),
            (4, {**run, "run_attempt": 2}),
            (5, {"workflow_runs": [{**run, "id": 124}]}),
            (6, {"object": {"sha": "b" * 40}}),
        ):
            changed = copy.deepcopy(responses)
            changed[index] = replacement
            with (
                patch.dict("os.environ", environment),
                patch.object(gate, "request", side_effect=changed),
            ):
                with self.assertRaises(ValueError):
                    gate.verify(SOURCE)


def add(archive, name, content):
    member = tarfile.TarInfo(name)
    member.size = len(content)
    archive.addfile(member, io.BytesIO(content))


def fixture(root, *, oci=False):
    with tarfile.open(
        root / "source.tar.gz", "w:gz", pax_headers={"comment": SOURCE}
    ) as archive:
        add(archive, "app/source.py", b"value = 1\n")
    rows = []
    descriptors = []
    with tarfile.open(root / "images.tar.gz", "w:gz") as archive:
        for role in ("backend", "gateway"):
            config = {
                "architecture": "amd64",
                "os": "linux",
                "config": {
                    "Labels": {"org.opencontainers.image.revision": SOURCE},
                    "role": role,
                },
            }
            data = json.dumps(config).encode()
            digest = hashlib.sha256(data).hexdigest()
            filename = f"blobs/sha256/{digest}"
            add(archive, filename, data)
            rows.append({"Config": filename, "RepoTags": [f"fillable-{role}:{SOURCE}"]})
            if oci:
                media_type = "application/vnd.oci.image.manifest.v1+json"
                image = json.dumps(
                    {
                        "schemaVersion": 2,
                        "mediaType": media_type,
                        "config": {"digest": "sha256:" + digest},
                        "layers": [],
                    }
                ).encode()
                image_digest = hashlib.sha256(image).hexdigest()
                add(archive, "blobs/sha256/" + image_digest, image)
                descriptors.append(
                    {
                        "mediaType": media_type,
                        "digest": "sha256:" + image_digest,
                        "size": len(image),
                        "annotations": {
                            "io.containerd.image.name": (
                                f"docker.io/library/fillable-{role}:{SOURCE}"
                            ),
                            "org.opencontainers.image.ref.name": SOURCE,
                        },
                    }
                )
            (root / f"{role}.json").write_text(
                json.dumps(
                    {
                        "id": "sha256:" + digest,
                        "os": "linux",
                        "architecture": "amd64",
                        "revision": SOURCE,
                    }
                )
            )
        add(archive, "manifest.json", json.dumps(rows).encode())
        if oci:
            add(archive, "oci-layout", b'{"imageLayoutVersion":"1.0.0"}')
            add(
                archive,
                "index.json",
                json.dumps({"schemaVersion": 2, "manifests": descriptors}).encode(),
            )


class ReleaseArtifactTests(unittest.TestCase):
    def test_only_archive_bound_config_and_oci_identities_are_returned(self):
        for oci in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture(root, oci=oci)
                pack(root, SOURCE, 123)
                manifest = json.loads((root / "manifest.json").read_text())
                identities = validate_image_archive(root / "images.tar.gz", manifest)
                self.assertEqual(set(identities), {"backend", "gateway"})
                for role, candidates in identities.items():
                    self.assertEqual(candidates[0], manifest["images"][role]["id"])
                    self.assertEqual(len(candidates), 2 if oci else 1)
                    if oci:
                        with tarfile.open(root / "images.tar.gz") as archive:
                            data = archive.extractfile(
                                "blobs/sha256/" + candidates[1][7:]
                            ).read()
                        self.assertEqual(
                            candidates[1], "sha256:" + hashlib.sha256(data).hexdigest()
                        )
                        self.assertEqual(
                            json.loads(data)["config"]["digest"], candidates[0]
                        )

    def test_oci_index_cannot_load_other_tags_or_nested_images(self):
        for corruption in (None, "tag", "nested", "extra", "config"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture(root, oci=True)
                with tarfile.open(root / "images.tar.gz", "r:gz") as archive:
                    members = {
                        member.name: archive.extractfile(member).read()
                        for member in archive
                    }
                index = json.loads(members["index.json"])
                if corruption == "tag":
                    index["manifests"][0]["annotations"]["io.containerd.image.name"] = (
                        "other-service:latest"
                    )
                elif corruption == "nested":
                    index["manifests"][0]["mediaType"] = (
                        "application/vnd.oci.image.index.v1+json"
                    )
                elif corruption == "extra":
                    index["manifests"].append(index["manifests"][0])
                elif corruption == "config":
                    descriptor = index["manifests"][0]
                    old = "blobs/sha256/" + descriptor["digest"].split(":")[1]
                    image = json.loads(members[old])
                    image["config"]["digest"] = "sha256:" + "0" * 64
                    data = json.dumps(image).encode()
                    digest = hashlib.sha256(data).hexdigest()
                    members["blobs/sha256/" + digest] = data
                    descriptor.update(digest="sha256:" + digest, size=len(data))
                members["index.json"] = json.dumps(index).encode()
                with tarfile.open(root / "images.tar.gz", "w:gz") as archive:
                    for name, data in members.items():
                        add(archive, name, data)
                if corruption is None:
                    pack(root, SOURCE, 123)
                else:
                    with self.assertRaises(ValueError):
                        pack(root, SOURCE, 123)

    def test_round_trip_and_outer_tampering_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            result = pack(root, SOURCE, 123)
            manifest = unpack(
                root / "release.tar", SOURCE, result["sha256"], root / "verified"
            )
            self.assertEqual(manifest["source_sha"], SOURCE)
            self.assertEqual(manifest["ci_run_id"], 123)
            with (root / "release.tar").open("ab") as stream:
                stream.write(b"changed")
            with self.assertRaisesRegex(ValueError, "digest"):
                unpack(root / "release.tar", SOURCE, result["sha256"], root / "bad")
            self.assertFalse((root / "bad").exists())

    def test_source_identity_symlinks_and_image_revision_fail(self):
        for corruption in ("commit", "symlink", "duplicate", "image"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture(root)
                if corruption in ("commit", "symlink", "duplicate"):
                    with tarfile.open(
                        root / "source.tar.gz",
                        "w:gz",
                        pax_headers={
                            "comment": SOURCE if corruption != "commit" else "b" * 40
                        },
                    ) as archive:
                        if corruption == "symlink":
                            member = tarfile.TarInfo("escape")
                            member.type = tarfile.SYMTYPE
                            member.linkname = "/outside"
                            archive.addfile(member)
                        else:
                            add(archive, "source.py", b"x = 1")
                            if corruption == "duplicate":
                                add(archive, "source.py", b"x = 2")
                else:
                    data = json.loads((root / "backend.json").read_text())
                    data["revision"] = "b" * 40
                    (root / "backend.json").write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    pack(root, SOURCE, 123)
                self.assertFalse((root / "release.tar").exists())

    def test_duplicate_member_and_inner_digest_change_fail(self):
        for corruption in ("duplicate", "digest", "path"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture(root)
                pack(root, SOURCE, 123)
                artifact = root / "altered.tar"
                with tarfile.open(artifact, "w") as archive:
                    for name in ("manifest.json", "images.tar.gz", "source.tar.gz"):
                        data = (root / name).read_bytes()
                        if corruption == "digest" and name == "images.tar.gz":
                            data += b"tamper"
                        add(archive, name, data)
                    if corruption == "duplicate":
                        add(archive, "manifest.json", b"{}")
                    if corruption == "path":
                        add(archive, "../escape", b"bad")
                with self.assertRaises(ValueError):
                    unpack(
                        artifact, SOURCE, file_info(artifact)["sha256"], root / "bad"
                    )
                self.assertFalse((root.parent / "escape").exists())

    def test_image_config_bytes_must_match_declared_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            pack(root, SOURCE, 123)
            manifest = json.loads((root / "manifest.json").read_text())
            manifest["images"]["backend"]["id"] = "sha256:" + "0" * 64
            with self.assertRaisesRegex(ValueError, "config digest"):
                validate_image_archive(root / "images.tar.gz", manifest)


if __name__ == "__main__":
    unittest.main()
