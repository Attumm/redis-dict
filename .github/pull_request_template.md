## What this changes
<!-- A short description of the change, and the issue it fixes (for example "Fixes #123"). -->

## Checklist
- [ ] The base branch is the open `vX.Y.Z-pre-release` branch, not `main` (see [CONTRIBUTING.md](https://github.com/Attumm/redis-dict/blob/main/CONTRIBUTING.md#branches-and-pull-requests)).
- [ ] `bash scripts/verify.sh` passes locally.
- [ ] Tests are added or updated for the change.
- [ ] If `pyproject.toml` changed, `uv.lock` is updated (`uv lock`) and committed.
