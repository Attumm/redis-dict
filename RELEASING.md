# Releasing redis-dict

How a new version goes from a pre-release branch to PyPI. This is for maintainers; for development setup and pull requests, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Overview
```text
main ─▶ vX.Y.Z-pre-release (bump commit) ◀─ squash PRs ─ work branches
vX.Y.Z-pre-release ─ squash version PR ─▶ main ─ push ─▶ deploy_docs.yml (docs)
GitHub Release (by hand) ─ creates tag vX.Y.Z ─▶ build_package_pypi.yml ─▶ PyPI
```

## 1. Start the version
1. Every version gets exactly **one** new branch, created from an up-to-date `main`, named **`vX.Y.Z-pre-release`** (with the `v`).
2. The first commit, pushed directly to the branch, only bumps the version, in `pyproject.toml` and `uv.lock`. `uv.lock` records the project version, and `uv sync --locked` fails in CI if it doesn't match.
   ```sh
   git checkout main && git pull
   git checkout -b vX.Y.Z-pre-release
   uv version X.Y.Z --no-sync  # updates pyproject.toml and uv.lock (needs uv 0.7 or newer)
   git commit -am "bumped version vX.Y.Z"
   git push -u origin vX.Y.Z-pre-release
   ```

## 2. Collect changes
3. Each change is its own branch made from `origin/vX.Y.Z-pre-release`, with a PR back into it, merged with **Squash and merge** (see [CONTRIBUTING.md](CONTRIBUTING.md#branches-and-pull-requests)).
4. Dependabot and contributor PRs that target `main` are retargeted to the pre-release branch. First-time contributors from a fork need their workflow runs approved.
5. If `main` moves ahead in the meantime, merge `main` into the pre-release branch.

## 3. Version PR into main
6. Open a PR from `vX.Y.Z-pre-release` → `main`. The description is the release notes.
7. Wait until all checks are green: CI, Supports Valkey, Build and Upload to PyPI (build only, no publish) and the docs build.
8. **Squash and merge**. The squash commit on `main` becomes `<PR title> (#NN)`.
9. The push to `main` starts `deploy_docs.yml`, which deploys the docs to GitHub Pages: https://attumm.github.io/redis-dict/. Any push to `main` deploys the docs, even without a release.

## 4. Release and publish to PyPI
10. Before the first release in a while, check on pypi.org that the API token behind `PYPI_API_TOKEN` still exists and isn't revoked.
11. Check that `pyproject.toml` on `main` says `version = "X.Y.Z"`, the same as the tag you're about to create.
    Then on GitHub: **Releases → Draft a new release**.
    - **Tag:** type `vX.Y.Z` and choose *create new tag on publish*. Target: **`main`**. The tag is created by the release; it's never pushed from the command line.
    - **Title:** a short description, not just the version. Examples: *Valkey Compatibility Check*, *v3.2.1 Maintenance*, *v3.0.0 Modernization of Package*.
    - **Notes:** the version PR description, expanded where useful. Credit outside reporters and contributors by `@handle`.
    - Not marked as pre-release. Publish.
12. The new tag starts `build_package_pypi.yml`:
    - `build-and-test`: Python 3.11 with a Redis service. Runs the quality checks and the unit tests, then `uv build` (see the workflow for the exact steps).
    - `publish-to-pypi`: runs only for `refs/tags/v*`. Uploads `dist/` with `pypa/gh-action-pypi-publish`, using the `PYPI_API_TOKEN` secret.
13. Check https://pypi.org/project/redis-dict/. The wheel and sdist appear a few minutes after the release is published. Then install it in a clean environment:
    ```sh
    uv run --no-project --with redis-dict==X.Y.Z python -c "import redis_dict"
    ```

## 5. After the release
14. The pre-release branch stays on GitHub.
15. The next version starts again at step 1, from the new `main`.

## Secrets and settings
| Name | Used by | Note |
|---|---|---|
| `PYPI_API_TOKEN` | `build_package_pypi.yml`, publish job | Check it's still valid before releasing. |
| `CODECOV_TOKEN` | `ci.yml`, coverage upload (Python 3.12 only) | |
| Environment `github-pages` | `deploy_docs.yml`, deploy job | Pages are deployed from GitHub Actions. |

## If something goes wrong
- **The publish job fails:** if nothing reached PyPI (for example an expired `PYPI_API_TOKEN`), fix the cause and use *Re-run failed jobs* on the tag's workflow run. If the code needs a change, or the upload partly succeeded, release a new version: PyPI never accepts the same file name twice, even after deleting it.
- **`uv sync --locked` fails in CI:** `pyproject.toml` changed without `uv lock`. Run `uv lock` and commit `uv.lock`.
- **The docs didn't update:** `deploy_docs.yml` can be started by hand from the Actions tab (`workflow_dispatch`).
