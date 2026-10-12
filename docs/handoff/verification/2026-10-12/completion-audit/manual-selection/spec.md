# Named manual revision selection

Observed production index.html:218 exposes an opaque document ID input. Existing test_portal_display_metadata_ui.py:230 requires the exact backend ID value after source reopening; a select retains that contract.

Replace input with named new-document / revision selection. Preserve raw filenames and exact option values. History refresh must preserve selected document and draft; missing/foreign IDs remain an explicit unresolved selection, never silently become new. Saved-source previews may supply a same-source filename before history arrives. History failure retains last known options and selection. No backend writes or ID translations.

Reference evidence: final-delegated/README.md:11 documents ProcessGPT monorepo6084127 and ontology-studio20afcde; use named business entities and retained technical provenance rather than opaque IDs as primary choices. This is scoped authoring correction, not a redesign or reference app runtime claim.

Verification: isolated Chromium production HTML/script with captured-style history and source envelopes; negative history failure, missing/foreign IDs, duplicate revisions, source before history; closest existing display metadata file. No live HTTP/model/process writes.

Follow-up transaction invariant: lock the selector while a preview exists; changing the next file clears preview and unlocks. Preview response selects exact generated identity before rendering. Source-only labels mean review in progress, not ingested revision. Duplicate filenames remain separate exact identities and use actual timestamp metadata for distinction.

Primary choices include current registered documents only. Full history remains an internal name lookup for explicit historical revision/source intent; a selected historical document remains named and exact through refresh, while unknown IDs remain unresolved.
