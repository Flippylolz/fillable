"""Package and verify a bounded, content-addressed Fillable release."""

import gzip
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path, PurePosixPath

MAX_IMAGE_BYTES = 2 * 1024**3
MAX_SOURCE_BYTES = 128 * 1024**2
MAX_ARCHIVE_BYTES = MAX_IMAGE_BYTES + MAX_SOURCE_BYTES + 1024**2
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
FILES = {"images.tar.gz", "source.tar.gz"}


def hash_stream(stream, limit):
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024**2):
        size += len(chunk)
        if size > limit:
            raise ValueError("Artifact exceeds size bound")
        digest.update(chunk)
    return {"bytes": size, "sha256": digest.hexdigest()}


def file_info(path):
    with path.open("rb") as stream:
        return hash_stream(stream, MAX_ARCHIVE_BYTES)


def validate_manifest(manifest, source):
    if (
        not SHA.fullmatch(source)
        or set(manifest) != {"version", "source_sha", "ci_run_id", "images", "files"}
        or type(manifest["version"]) is not int
        or manifest["version"] != 1
        or manifest["source_sha"] != source
        or type(manifest["ci_run_id"]) is not int
        or manifest["ci_run_id"] <= 0
        or set(manifest["images"]) != {"backend", "gateway"}
        or set(manifest["files"]) != FILES
    ):
        raise ValueError("Invalid release manifest")
    for row in manifest["images"].values():
        if (
            set(row) != {"id", "os", "architecture", "revision"}
            or not DIGEST.fullmatch(row["id"])
            or row["os"] != "linux"
            or row["architecture"] != "amd64"
            or row["revision"] != source
        ):
            raise ValueError("Image must match the release revision and platform")
    for row in manifest["files"].values():
        if (
            set(row) != {"bytes", "sha256"}
            or type(row["bytes"]) is not int
            or not 0 < row["bytes"] <= MAX_ARCHIVE_BYTES
            or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
        ):
            raise ValueError("Invalid artifact file digest")


def validate_source_archive(path, source):
    total = count = 0
    names = set()
    with gzip.open(path, "rb") as stream:
        hash_stream(stream, MAX_SOURCE_BYTES)
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            count += 1
            total += member.size
            name = PurePosixPath(member.name)
            if (
                count > 10000
                or str(name) in names
                or member.size < 0
                or total > MAX_SOURCE_BYTES
                or name.is_absolute()
                or ".." in name.parts
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("Unsafe source archive")
            names.add(str(name))
        if archive.pax_headers.get("comment") != source or not count:
            raise ValueError("Source archive must identify the exact Git commit")


def validate_image_archive(path, manifest):
    # Bound decompression before tarfile's seek-based metadata reads.
    with gzip.open(path, "rb") as stream:
        hash_stream(stream, MAX_IMAGE_BYTES)
    with tarfile.open(path, "r:gz") as archive:
        names = set()
        for item in archive:
            path = PurePosixPath(item.name)
            if (
                str(path) in names
                or len(names) >= 10000
                or path.is_absolute()
                or ".." in path.parts
                or not (item.isfile() or item.isdir())
            ):
                raise ValueError("Duplicate or excessive Docker archive members")
            names.add(str(path))
        member = archive.getmember("manifest.json")
        if not member.isfile() or member.size > 65536:
            raise ValueError("Invalid Docker archive manifest")
        rows = json.load(archive.extractfile(member))
        if len(rows) != 2:
            raise ValueError("Docker archive must contain exactly two images")
        found = set()
        for row in rows:
            config_member = archive.getmember(row["Config"])
            if not config_member.isfile() or config_member.size > 1024**2:
                raise ValueError("Invalid image config")
            config_bytes = archive.extractfile(config_member).read()
            config = json.loads(config_bytes)
            image_id = "sha256:" + hashlib.sha256(config_bytes).hexdigest()
            matches = [
                role
                for role, expected in manifest["images"].items()
                if expected["id"] == image_id
            ]
            if len(matches) != 1:
                raise ValueError("Unexpected image config digest")
            role = matches[0]
            if (
                role in found
                or row["RepoTags"] != [f"fillable-{role}:{manifest['source_sha']}"]
                or config.get("architecture") != "amd64"
                or config.get("os") != "linux"
                or config.get("config", {})
                .get("Labels", {})
                .get("org.opencontainers.image.revision")
                != manifest["source_sha"]
            ):
                raise ValueError("Docker archive image identity mismatch")
            found.add(role)
        validate_oci_index(archive, names, manifest)


def validate_oci_index(archive, names, manifest):
    """Docker may load OCI metadata instead of the legacy manifest."""

    def read_json(name, limit=1024**2):
        member = archive.getmember(name)
        if not member.isfile() or not 0 < member.size <= limit:
            raise ValueError("Invalid OCI metadata member")
        data = archive.extractfile(member).read()
        return data, json.loads(data)

    if "repositories" in names:
        _, repositories = read_json("repositories")
        if set(repositories) != {"fillable-backend", "fillable-gateway"} or any(
            set(tags) != {manifest["source_sha"]} for tags in repositories.values()
        ):
            raise ValueError("Unexpected Docker repository alias")
    if "index.json" not in names and "oci-layout" not in names:
        return  # Older Docker archives use only the checked legacy manifest.
    _, layout = read_json("oci-layout")
    _, index = read_json("index.json")
    if layout != {"imageLayoutVersion": "1.0.0"} or index.get("schemaVersion") != 2:
        raise ValueError("Unexpected OCI layout")
    descriptors = index.get("manifests", [])
    if len(descriptors) != 2:
        raise ValueError("Unexpected OCI image count")
    found = set()
    for descriptor in descriptors:
        if descriptor.get("mediaType") not in {
            "application/vnd.oci.image.manifest.v1+json",
            "application/vnd.docker.distribution.manifest.v2+json",
        }:
            raise ValueError("Unexpected nested OCI index")
        digest = descriptor.get("digest", "")
        if not DIGEST.fullmatch(digest):
            raise ValueError("Invalid OCI manifest digest")
        data, image = read_json("blobs/sha256/" + digest.removeprefix("sha256:"))
        if (
            "sha256:" + hashlib.sha256(data).hexdigest() != digest
            or len(data) != descriptor.get("size")
            or image.get("schemaVersion") != 2
            or image.get("mediaType") != descriptor["mediaType"]
        ):
            raise ValueError("OCI manifest bytes mismatch")
        matches = [
            role
            for role, expected in manifest["images"].items()
            if image.get("config", {}).get("digest") == expected["id"]
        ]
        if len(matches) != 1 or matches[0] in found:
            raise ValueError("Unexpected OCI image config")
        role = matches[0]
        tag = f"docker.io/library/fillable-{role}:{manifest['source_sha']}"
        if descriptor.get("annotations") != {
            "io.containerd.image.name": tag,
            "org.opencontainers.image.ref.name": manifest["source_sha"],
        }:
            raise ValueError("Unexpected OCI repository alias")
        found.add(role)


def pack(root, source, ci_run_id):
    root = Path(root)
    manifest = {
        "version": 1,
        "source_sha": source,
        "ci_run_id": ci_run_id,
        "images": {
            role: json.loads((root / f"{role}.json").read_text())
            for role in ("backend", "gateway")
        },
        "files": {name: file_info(root / name) for name in sorted(FILES)},
    }
    validate_manifest(manifest, source)
    validate_source_archive(root / "source.tar.gz", source)
    validate_image_archive(root / "images.tar.gz", manifest)
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    artifact = root / "release.tar"
    with (
        artifact.open("xb") as target,
        tarfile.open(fileobj=target, mode="w") as archive,
    ):
        for name in sorted(FILES | {"manifest.json"}):
            path = root / name
            member = tarfile.TarInfo(name)
            member.size = path.stat().st_size
            member.mode = 0o400
            with path.open("rb") as stream:
                archive.addfile(member, stream)
    result = {"source_sha": source, "ci_run_id": ci_run_id, **file_info(artifact)}
    (root / "artifact.json").write_text(json.dumps(result, sort_keys=True) + "\n")
    return result


def unpack(artifact, source, expected_digest, destination):
    artifact, destination = Path(artifact), Path(destination)
    if file_info(artifact)["sha256"] != expected_digest:
        raise ValueError("Release archive digest mismatch")
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    found = set()
    with tarfile.open(artifact, "r:") as archive:
        for member in archive:
            if (
                member.name not in FILES | {"manifest.json"}
                or member.name in found
                or not member.isfile()
                or member.size <= 0
                or member.size > MAX_ARCHIVE_BYTES
                or (member.name == "manifest.json" and member.size > 65536)
            ):
                raise ValueError("Unsafe release archive member")
            found.add(member.name)
            with archive.extractfile(member) as stream:
                with (destination / member.name).open("xb") as target:
                    while chunk := stream.read(1024**2):
                        target.write(chunk)
    if found != FILES | {"manifest.json"}:
        raise ValueError("Incomplete release archive")
    manifest = json.loads((destination / "manifest.json").read_text())
    validate_manifest(manifest, source)
    for name in FILES:
        if file_info(destination / name) != manifest["files"][name]:
            raise ValueError("Release member digest mismatch")
    validate_source_archive(destination / "source.tar.gz", source)
    validate_image_archive(destination / "images.tar.gz", manifest)
    return manifest


if __name__ == "__main__":
    try:
        if sys.argv[1] == "pack":
            result = pack(sys.argv[2], sys.argv[3], int(sys.argv[4]))
        elif sys.argv[1] == "unpack":
            result = unpack(*sys.argv[2:])
        else:
            raise ValueError("Unknown release artifact command")
        print(json.dumps(result, sort_keys=True))
    except Exception:
        print("release_artifact_failed", file=sys.stderr)
        raise SystemExit(1) from None
