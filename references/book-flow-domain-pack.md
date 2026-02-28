# Book Flow Domain Pack

## Invariants

- TOC ordering authority is Admin Topic Manager detail view:
  - `/admin/topic-manager/<topic-slug>/detail`
- Reader is mature open-source baseline; prefer minimal invasive changes.
- Slug and URL migration must preserve sacred-texts legacy URL behavior and 301 flow.
- RBAC is mandatory for admin and management paths.

## TOC and Type-Template Direction

- A book may have pages before first chapter (title pages, notes, transcription notices).
- TOC entries are not equivalent to chapter-only content.
- Type templates should support categories beyond TOC:
  - footnotes
  - book pages
  - topic pages
  - reader pages
  - audiobook metadata/segments

## Planning Guardrails

- Avoid single-schema assumptions across millions of books.
- Support flexible type/category taxonomy while keeping deterministic ordering in Topic Manager.
- Preserve backward URL compatibility in every routing plan.
- Include RBAC checks in every admin flow proposal.
