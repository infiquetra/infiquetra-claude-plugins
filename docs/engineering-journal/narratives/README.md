# Narratives

Self-contained, longer-form companion docs for the engineering journal. Each narrative is standalone-readable cold by an outside reader (a future maintainer, a plugin consumer, you-six-months-out). Linked from the relevant entry in `LEARNINGS.md` or `DECISIONS.md`.

## When to write a narrative

The four core files (`LEARNINGS.md`, `DECISIONS.md`, `QUEUED.md`, `ARCHIVE.md`) are designed to be **scannable**. An entry that runs more than ~30 lines of body text or needs diagrams, multi-section context, or a full reproduction recipe is a signal that the content belongs in a narrative.

Concrete triggers:

- **Plugin design walkthrough.** A new plugin's architecture spans multiple skills, commands, scripts, and external integrations — and you need to explain why the pieces are arranged the way they are. Don't bury this in the plugin's `README.md` (which is a *user* doc); narrative is a *contributor* doc.
- **Multi-PR post-mortem.** A bug or feature played out across 3+ PRs over time. The story is the value; the LEARNING entry just points at the narrative.
- **Migration write-up.** A repo-wide rename, layout reshuffle, or version bump that touched many files. Capture the before/after and why.
- **Rejected-design memo.** When a design was carefully considered and rejected, the *consideration* is worth preserving even though the design isn't shipped. Pair with a DECISIONS entry whose "Rejected alternatives" line points here.
- **Inventory snapshot.** Forensics-grade record of "what existed at this date" — useful when later debugging asks "did this plugin even exist when X happened?"

## Format

- **Filename**: `YYYY-MM-DD-short-slug.md` (date-prefixed kebab-case).
- **Title** (H1): a descriptive sentence — narratives are linked-to, not browsed by filename.
- **Header metadata block** at the top: a few lines of `**Date**:`, `**Type**:` (design / post-mortem / migration / rejected-memo / inventory), `**Status**:` (current / superseded), `**Refs**:` (back-links to entries that cite this).
- **Body**: prose-first. Sections as needed. Diagrams as ASCII or linked PNGs.
- **Last updated** line at the bottom if the document evolves; bump the date when content changes substantively.

Unlike the four core files (append-only at the top), narratives **can be edited inline** when new information arrives — but always preserve the "Last updated YYYY-MM-DD" trail so a reader knows the document evolved.

## Cross-references

Every narrative should be cited from at least one entry in the four core files. If a narrative doesn't have a back-link, either it should (add the back-link) or the narrative belongs in a different location (a plugin's own `README.md`, a top-level doc, etc.).

When a narrative is *superseded* by a later one, mark the old one's status as `superseded by [link]` at the top — never delete.
