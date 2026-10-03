# Repository history

On 2026-10-03 the history of this repository was rewritten to replace the author and
committer email on every commit. Nothing else changed: file contents, commit messages and the
author and commit dates of every commit are identical to the original history.

Because a commit hash depends on the commit's author, **every commit hash changed**. The
repository moved to a new GitHub repository at the same time, so the GitHub Actions runs linked
from older release records belong to the original repository and are cited there as plain text.

## What this means when reading the release records

- The release records on each tag (`docs/releases/vX.Y.Z.md`, the verification runbooks) are
  **unchanged at their tags** and cite the *old* hashes. On `main` they cite the *new* hashes.
- The verification results themselves were observed on the original commits, before the rewrite.
  The rewritten commits have identical content, so the same trees were verified.
- Every old hash maps to its new hash in [`commit-map.txt`](commit-map.txt).

## Tags

| Tag | Original commit | Current commit |
| --- | --- | --- |
| `v0.1.0` | `78e3622` | `662a83b` |
| `v0.2.0` | `477e0bd` | `63ae5a5` |
| `v0.3.0` | `2831c65` | `ad51dbd` |
| `v0.4.0` | `65c96ba` | `51e93c0` |
| `v0.5.0` | `49e806b` | `22d1bf4` |
| `v0.6.0` | `21892f5` | `a59589d` |
| `v0.7.0` | `98e27f5` | `5842371` |
| `v0.8.0` | `d339667` | `2f9a808` |
| `v0.9.0` | `cc332c1` | `13943e0` |
| `v1.0.0` | `8b2e055` | `b281577` |

## How the mapping was produced

`git filter-repo --mailmap` rewrote author and committer. The tool wrote the old-to-new commit
map that is published as `commit-map.txt`.
