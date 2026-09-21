"""Content-based document identity generation (Issue #13 V2.5).

Document identity is a pure function of the file's content bytes rather than
its on-disk path, so the same document uploaded from different filenames or
directories resolves to a single ``document_id``.  This stops duplicate
processed-/hierarchy-/provenance-/vector artifacts from being created on
every re-upload.

The bundled canonical Acts (Indian Contract Act 1872 / Indian Penal Code)
ship under established document ids that the retrieval layer
(``src/retrieval/query.py::_ACT_NAME_TO_DOC_ID``), canonical selection
(``src/knowledge_graph/canonical.py::_STABLE_CANONICAL_IDS``), evaluation
golds and docs all reference.  :data:`CANONICAL_CONTENT_IDS` preserves those
ids: when an uploaded file's full SHA-256 exactly matches a bundled source
document, the registered id is returned; every other file is strictly
content-addressed.
"""

from __future__ import annotations

import hashlib

# Length of the public document_id (matches the project's existing 16-hex ids).
DOCUMENT_ID_LENGTH = 16

# Full SHA-256 hexdigest of the bundled source documents -> the established
# document_id that must be retained.  Values are derived from the tracked
# sources in ``data/uploads/``:
#   - 6f1e824b..._the-indian-contract-act-1872.pdf   (ICA 1872)
#   - 8d5f3557..._ipc.pdf                             (IPC)
# A re-upload of a bundled Act therefore resolves to the same identity
# instead of creating a duplicate document.
CANONICAL_CONTENT_IDS: dict[str, str] = {
    "6ecc0edf1d1e1c861a57038e68da2e6fd1c8d623f3ace7e7c997914f1bfb645a": "0d1934142f67c5f5",
    "ae8920ad726fbb6dfdec8d327c4bdda580ca175bcad1ef4212ca868fe4d1ea3a": "cf20a14c52127fd5",
}


def content_document_id(file_bytes: bytes) -> str:
    """Path-independent document id: SHA-256 of the file bytes, truncated.

    Changing only the filename or the upload directory never changes the id;
    changing any content byte always does.
    """
    return hashlib.sha256(file_bytes).hexdigest()[:DOCUMENT_ID_LENGTH]


def resolve_document_id(file_bytes: bytes) -> str:
    """Return the content-derived id, honouring bundled canonical overrides.

    The override applies only when the full content hash exactly matches a
    bundled document, so the canonical ids stay stable while arbitrary
    uploads remain strictly content-addressed.
    """
    digest = hashlib.sha256(file_bytes).hexdigest()
    registered = CANONICAL_CONTENT_IDS.get(digest)
    if registered is not None:
        return registered
    return digest[:DOCUMENT_ID_LENGTH]
