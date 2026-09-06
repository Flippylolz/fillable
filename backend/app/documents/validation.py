"""Production DOCX admission rules; validation never writes or fetches resources."""

import posixpath
from urllib.parse import unquote, urlsplit

from app.documents.package import DocxPackage, InvalidDocument, W, safe_part_name

CONTENT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
MAIN_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)


def content_types(package):
    root = package.roots.get("[Content_Types].xml")
    if root is None or root.tag != CONTENT + "Types":
        raise InvalidDocument("invalid_package")
    defaults: dict[str, str] = {}
    overrides: dict[str, str] = {}
    for entry in root:
        content = entry.get("ContentType", "")
        if not content:
            raise InvalidDocument("invalid_package")
        if any(
            marker in content.lower()
            for marker in ("macroenabled", "vba", "oleobject", "activex")
        ):
            raise InvalidDocument("unsupported_document")
        if entry.tag == CONTENT + "Default":
            key = entry.get("Extension", "").lower()
            target = defaults
        elif entry.tag == CONTENT + "Override":
            name = entry.get("PartName", "")
            if not name.startswith("/") or name[1:] not in package.parts:
                raise InvalidDocument("invalid_package")
            key = name[1:]
            target = overrides
        else:
            raise InvalidDocument("invalid_package")
        if not key or key in target:
            raise InvalidDocument("invalid_package")
        target[key] = content
    for name in package.parts:
        if name == "[Content_Types].xml" or name.endswith("/"):
            continue
        if name not in overrides and name.rsplit(".", 1)[-1].lower() not in defaults:
            raise InvalidDocument("invalid_package")
    if overrides.get("word/document.xml") != MAIN_TYPE:
        raise InvalidDocument("unsupported_document")


def relationships(package):
    main = []
    by_source: dict[str, set[str]] = {}
    for name, root in package.roots.items():
        if not name.endswith(".rels"):
            continue
        if root.tag != REL + "Relationships":
            raise InvalidDocument("invalid_package")
        if name == "_rels/.rels":
            base = ""
            source_part = ""
        else:
            directory, filename = posixpath.split(name)
            if posixpath.basename(directory) != "_rels":
                raise InvalidDocument("invalid_package")
            base = posixpath.dirname(directory)
            source_part = posixpath.join(base, filename[:-5])
            if source_part not in package.parts:
                raise InvalidDocument("invalid_package")
        ids: set[str] = set()
        by_source[source_part] = ids
        for entry in root:
            identity, kind = entry.get("Id", ""), entry.get("Type", "")
            target, mode = entry.get("Target", ""), entry.get("TargetMode", "Internal")
            if (
                entry.tag != REL + "Relationship"
                or not identity
                or identity in ids
                or not kind
                or not target
            ):
                raise InvalidDocument("invalid_package")
            ids.add(identity)
            if kind.rsplit("/", 1)[-1] in {
                "vbaProject",
                "oleObject",
                "control",
                "aFChunk",
                "attachedTemplate",
                "package",
            }:
                raise InvalidDocument("unsupported_document")
            if mode == "External":
                # Inert hyperlinks remain source data; nothing follows their URL.
                if kind != OFFICE + "hyperlink":
                    raise InvalidDocument("unsupported_document")
                continue
            if mode != "Internal":
                raise InvalidDocument("invalid_package")
            try:
                parsed = urlsplit(target)
            except ValueError as error:
                raise InvalidDocument("invalid_package") from error
            decoded = unquote(parsed.path)
            if parsed.scheme or parsed.netloc or parsed.query or "\\" in decoded:
                raise InvalidDocument("invalid_package")
            resolved = posixpath.normpath(posixpath.join(base, decoded))
            if decoded.startswith("/"):
                resolved = decoded[1:]
            if not safe_part_name(resolved) or resolved not in package.parts:
                raise InvalidDocument("invalid_package")
            if name == "_rels/.rels" and kind == OFFICE + "officeDocument":
                main.append(resolved)
    if main != ["word/document.xml"]:
        raise InvalidDocument("invalid_package")
    namespace = "{" + OFFICE.rstrip("/") + "}"
    for name, root in package.roots.items():
        for element in root.iter():
            for attribute, value in element.attrib.items():
                if attribute.startswith(namespace) and value not in by_source.get(
                    name, set()
                ):
                    raise InvalidDocument("invalid_package")


def validate_upload(data: bytes, filename: str) -> DocxPackage:
    """Return the source-preserving package only after the upload contract passes."""
    if (
        not filename
        or len(filename) > 255
        or any(ord(char) < 32 for char in filename)
        or any(char in filename for char in "/\\")
        or not filename.lower().endswith(".docx")
    ):
        raise InvalidDocument("unsupported_document")
    package = DocxPackage(data)
    content_types(package)
    relationships(package)
    root = package.roots["word/document.xml"]
    if root.tag != W + "document" or len(root.findall(W + "body")) != 1:
        raise InvalidDocument("invalid_package")
    for root in package.roots.values():
        for element in root.iter():
            if element.tag in {W + "documentProtection", W + "altChunk", W + "object"}:
                raise InvalidDocument("unsupported_document")
        package.check_deadline()
    # Binary active parts may have no XML root or content-type declaration.
    if any(
        any(
            marker in name.lower()
            for marker in ("vbaproject", "activex/", "embeddings/")
        )
        for name in package.parts
    ):
        raise InvalidDocument("unsupported_document")
    return package
