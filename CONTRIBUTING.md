# Contributing to redis-dict

Thank you for helping out. This guide explains how to set up the project, run the tests and checks, and get a change into a release.

## Prerequisites
* [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.7 or newer (CI uses 0.13.0)
* Python 3.8 to 3.15, the versions CI tests
* Docker (for the Redis and Valkey scripts) and `make` (for the docs)
* A Redis server on `localhost:6379` for the tests, version 6.2 or newer (redis-dict uses `GETDEL` and `SET ... KEEPTTL`). **The tests flush databases 0 and 11**, so use a throwaway Redis, such as the Docker container below, and not one that holds data you care about.

Start Redis or Valkey in Docker. Both use port 6379, so run one at a time.
```sh
bash scripts/start_redis_docker.sh   # container "my-redis"
bash scripts/start_valkey_docker.sh  # container "my-valkey"
```
The scripts fail when the container already exists. After the first time, use `docker start my-redis` or `docker start my-valkey`.

## Setup
The project uses [uv](https://docs.astral.sh/uv/). The exact versions of all dependencies are pinned in `uv.lock`, which is committed to the repository.
```sh
uv sync --locked --extra dev
```
This creates `.venv` with the exact versions from `uv.lock`, just like CI. `--locked` stops with an error instead of changing `uv.lock`.

The scripts use their own environment, `.venv_dev`. Create it with:
```sh
bash scripts/build_dev.sh
```
The scripts can be run from any directory, as `./scripts/<name>.sh` or `bash scripts/<name>.sh`. `tests.sh`, `verify.sh`, `lint.sh` and `formatter.sh` set up `.venv_dev` themselves: with uv they run `uv sync --locked` first on every run, so the tools always match `uv.lock`.

Without uv, the scripts fall back to pip and venv. This happens automatically when uv isn't installed, or on request:
```sh
USE_UV=false bash scripts/build_dev.sh
bash scripts/build_dev.sh false
```
The pip fallback recreates `.venv_dev` with `python3 -m venv` and installs the project with `pip install -e ".[dev]"`. It doesn't use `uv.lock`, so the versions can differ from CI.

## Tests
The test suite covers the data types, edge cases and error handling.
```sh
bash scripts/tests.sh                                             # in .venv_dev, verbose, stops at the first failure
uv run --locked --extra dev python -m unittest discover -s tests  # in .venv
```
The property-based tests with Hypothesis are in `tests/fuzzing`. The commands above and CI don't run them; run them separately:
```sh
uv run --locked --extra dev python -m unittest discover -s tests/fuzzing
```

## Quality checks
```sh
bash scripts/verify.sh            # mypy, darglint, pylama, unit tests, bandit, pydocstyle
bash scripts/build_dev_checks.sh  # sets up .venv_dev, then mypy, darglint, bandit, pylama, unit tests, pydocstyle
bash scripts/lint.sh              # mypy, darglint, pylama, bandit, pydocstyle, pylint
```
`ci.yml` runs the same checks as `verify.sh`, on Python 3.8 to 3.15. Run `verify.sh` before opening a PR.

## Documentation
```sh
bash scripts/build_docs.sh  # docs env in .venv_docs, builds docs/build/html
bash scripts/view_docs.sh   # opens docs/build/html/index.html (macOS)
```
`build_docs.sh` first removes the generated `docs/Makefile`, `docs/build` and `docs/source`, then generates them again.

All scripts that set up or use an environment accept `false` or `USE_UV=false` for pip, like `build_dev.sh`.

## Dependencies and uv.lock
CI installs with `uv sync --locked`, which fails when `pyproject.toml` and `uv.lock` don't match. Commit `uv.lock` together with every `pyproject.toml` change.
```sh
uv lock                                 # after changing dependencies in pyproject.toml
uv lock --check                         # check that uv.lock matches pyproject.toml
uv lock --upgrade                       # update all packages to the latest allowed versions
uv lock --upgrade-package cryptography  # update a single package
```
Contributors don't bump the version; see [RELEASING.md](RELEASING.md).

## Branches and pull requests
Every version is collected on its own branch, `vX.Y.Z-pre-release`, before it goes to `main`.

1. A new version gets one branch, `vX.Y.Z-pre-release`, created from `main`. Its first commit is `bumped version vX.Y.Z`.
2. Each change is its own branch made from the latest `vX.Y.Z-pre-release` on GitHub, with a squash PR back into it.
   Find the open pre-release branch in the branch list on GitHub, or with
   `git ls-remote --heads https://github.com/Attumm/redis-dict.git 'v*-pre-release'`.
   Without write access, fork the repository first:
   ```sh
   git remote add upstream https://github.com/Attumm/redis-dict.git
   git fetch upstream
   git checkout -b my-change upstream/vX.Y.Z-pre-release
   # work, commit
   git push -u origin my-change   # origin is your fork
   ```
   With write access, use `origin` instead of `upstream`.
   Open the PR with base `vX.Y.Z-pre-release`, **not `main`**. It's merged with *Squash and merge*.
   If there is no open pre-release branch, open the PR against `main`, and a maintainer will retarget it.
3. When the version is ready, one squash PR goes from `vX.Y.Z-pre-release` into `main`.
4. A maintainer creates the GitHub Release, which publishes the version to PyPI. See [RELEASING.md](RELEASING.md).

### Checks on pull requests
* **CI** (`ci.yml`): Python 3.8 to 3.15 against Redis, with the quality checks and unit tests. Also runs on every push.
* **Supports Valkey** (`valkey_support.yml`): the unit tests on Python 3.8 to 3.15 against Valkey.
* **Build and Upload to PyPI** (`build_package_pypi.yml`): the quality checks, unit tests and package build, on PRs into `main` and into `vX.Y.Z-pre-release`. It only publishes on a release tag.
* **Build and Deploy Documentation** (`deploy_docs.yml`): builds the docs on PRs into `main` and into `vX.Y.Z-pre-release`. It only deploys to GitHub Pages on a push to `main`.

### Why this flow
* **Each change works with the work of others.** Every change starts from the pre-release branch, which already contains everything merged for that version. Changes are built and tested together, one PR at a time, instead of meeting for the first time at release.
* **`main` always matches a release.** Only one tested squash PR per version reaches `main`, and the release tags that exact commit.
* **Work in progress has its own place.** Several people can work on the same version without each of them having to keep `main` releasable.
* **Small, focused PRs.** One squash commit per change makes reviews easy, keeps conflicts small, and a change is easy to revert.
* **Checks run twice.** On every PR into the pre-release branch, and again on the complete version in the PR into `main`, before anything reaches PyPI.
* **Releasing is a deliberate step.** Merging into `main` publishes nothing to PyPI (only the docs are deployed). A person creates the GitHub Release, which matters because PyPI never accepts the same version twice.

Trade-off: if something else lands on `main` while a version is open (a hotfix, or another version), merge `main` into the open pre-release branch.
