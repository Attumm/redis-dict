## What this changes
<!-- A short description of the change and why it's needed. -->

Fixes #<!-- issue number, if there is one -->

## How changes get into a release
Every version is collected on its own branch, `vX.Y.Z-pre-release`, before it goes to `main`:

1. **Branch:** start from the latest open pre-release branch on GitHub. Without write access, fork the repository first and use `upstream` instead of `origin`.
   ```sh
   git fetch origin
   git checkout -b my-change origin/vX.Y.Z-pre-release
   ```
2. **Pull request:** open this PR with **base `vX.Y.Z-pre-release`, not `main`**. Keep it to one change. If there is no open pre-release branch, target `main`, and a maintainer will retarget it.
3. **Checks:** CI (Python 3.8 to 3.12 against Redis), Supports Valkey, Build and Upload to PyPI (build only, nothing is published) and the docs build run on this PR. All of them must be green.
4. **Merge:** a maintainer squash merges this PR into the pre-release branch, together with the other changes for that version.
5. **Release:** when the version is ready, one PR goes from `vX.Y.Z-pre-release` into `main`. A maintainer then creates the GitHub Release, which publishes the version to PyPI.

The full process is in [CONTRIBUTING.md](https://github.com/Attumm/redis-dict/blob/main/CONTRIBUTING.md#branches-and-pull-requests) and [RELEASING.md](https://github.com/Attumm/redis-dict/blob/main/RELEASING.md).

## Checklist
- [ ] This branch was created from the latest `origin/vX.Y.Z-pre-release` (fetched first), and the base of this PR is that branch, not `main`.
- [ ] `./scripts/verify.sh` passes locally: mypy, darglint, pylama, the unit tests, bandit and pydocstyle. The tests need Redis 6.2 or newer on `localhost:6379`: `./scripts/start_redis_docker.sh`.
- [ ] Tests are added or updated for the change.
- [ ] If `pyproject.toml` changed: `uv lock` was run and `uv.lock` is committed in this PR.
- [ ] Docs are updated if the behaviour changed (README, docstrings).
- [ ] The version number is not changed. Maintainers bump it at the start of each version.
