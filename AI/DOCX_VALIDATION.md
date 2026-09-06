# DOCX upload admission

E03.2 provides `app.documents.validation.validate_upload(data, filename)` for the
production upload service. It returns the same source-preserving `DocxPackage`
used by the editor adapter. This task exposes no upload HTTP endpoint and writes no
files; E03.3 supplies persistence and E03.1 supplies the upload UI.

The boundary accepts a case-insensitive `.docx` filename of at most 255 characters,
with no path separators or control characters. It requires the transitional
WordprocessingML document namespace, the DOCX main-part content type, one package
main-document relationship to `word/document.xml`, and exactly one main body.
Strict OOXML, legacy `.doc`, `.docm`, `.dotx`, encrypted OLE containers and other
formats are rejected rather than silently converted. This is a tested support
contract, not full ISO schema validation or a claim of universal Word compatibility.

Content types must cover all retained parts and use unique declarations. Relationship
parts must have valid roots, unique nonempty IDs, existing source parts and existing
normalized internal targets. Relative parent references within the package and
package-absolute targets work; traversal outside it, URL-like internal targets,
queries and malformed targets fail. External hyperlinks are retained as inert source
data, never fetched or rendered as executable links by this validator. Other external
relationships, attached templates, macros, ActiveX, embedded objects/packages,
`altChunk` and document protection are unsupported. The existing E00 support matrix
continues to govern locked complex content such as page fields; validation does not
remove it or reconstruct the file from text.

The shared package reader enforces these limits for uploads and the editor proof:

| Bound | Limit |
| --- | --- |
| Compressed input | 10 MiB |
| Archive entries | 256 |
| Total expanded bytes | 50 MiB, checked in metadata and actual reads |
| Read chunk | At most 64 KiB, reduced at the remaining-byte boundary |
| Part name | 512 characters, safe canonical segments |
| XML elements across parsed parts | 100,000 |
| XML parser | lxml safe depth defaults; no recovery, DTD, entities or network |
| Processing deadline | 5 seconds, checked between bounded reads, parses and model operations |

ZIP members must use stored/deflate compression, unique safe names and regular-file
or directory modes. Symlinks, encrypted flags, malformed ZIP/CRC, unsafe names,
unsupported compression and truncated input fail closed. Both XML and relationship
parts use the hardened XML parser. The time budget is cooperative: it rejects an
over-budget operation after control returns; it is not preemptive process isolation.
Worker runtime supervision remains part of job/operational integration in E03.5/E07.
The production upload handler must also bound request concurrency and body size;
this function does not itself allocate request capacity.

Errors are stable `InvalidDocument` codes (`unsupported_document`,
`invalid_package`, package/parser limit codes and existing adapter validation codes).
Callers translate them through the machine-readable API error contract without
exposing exception text, XML, filenames or physical paths. A rejected validation
must not become a committed resource or consume retained quota. E03.3 verifies that
integration; no file/accounting cleanup is claimed from these in-memory tests.

Validation includes the immutable Ukrainian corpus, byte/part preservation, minimal
valid packages, ordinary external hyperlinks, malformed manifests/relationships,
active content, unsafe paths, encryption flags, corruption/truncation, real expanded
ZIP and XML depth/element limits, and the cooperative deadline. Editor round-trip,
structural exports and independent renderer checks remain separate fidelity evidence.
No Microsoft Word execution or private user document is part of this validation.

Primary format/security references inspected on 2026-09-06:
[Microsoft WordprocessingML structure](https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document),
[Microsoft package construction](https://learn.microsoft.com/en-us/office/open-xml/general/how-to-create-a-package),
and [Python ZIP resource limits](https://docs.python.org/3.13/library/zipfile.html#decompression-pitfalls).
