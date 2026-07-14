"""Real-adapter test lane (#458, T11-F4-8).

Every module here exercises a real production adapter against its REAL substrate — not a fake — so a
fake that has silently drifted from reality (the ``{#fake-adapter-hides-real-path-mismatch}`` class
of bug) cannot pass. The first migrated seam is the U7 worktree-liveness oracle
(``plugins/saga/scripts/outcome_worktrees.git_worktree_ops``), driven against the real ``git
worktree`` CLI under a non-canonical (symlinked / relative) repo root.
"""
