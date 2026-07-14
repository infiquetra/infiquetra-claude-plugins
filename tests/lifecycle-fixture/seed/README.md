# lifecycle-fixture seed repo

This directory is the seed content of the lifecycle-regression fixture repository (#428).
Every scenario run copies these files into a throwaway temporary directory, runs `git init`
there, commits them, and drives the saga lifecycle CLIs against that clone — never against
the `infiquetra-claude-plugins` working tree.

Files here are deliberately tiny: just enough for a scenario to author a plan, seed a diff,
and record lifecycle state against a real (if toy) repository.
