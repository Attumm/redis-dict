"""Dynamic version resolution and isolated virtual environment provisioning for cross-version tests."""
from __future__ import annotations

from dataclasses import dataclass
import io
import os
from pathlib import Path
import re
import shutil
import subprocess  # nosec B404
import sys
import tarfile
from typing import Dict, List, Optional, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
PRERELEASE_BRANCH_RE = re.compile(r"^(?:refs/(?:heads|remotes/origin)/)?(v(\d+)\.(\d+)\.(\d+)-pre-release)$")
PYPROJECT_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


@dataclass(frozen=True)
class ResolvedVersion:
    """Canonical representation of a resolved target or baseline version."""

    spec: str
    kind: str
    label: str
    ref_or_ver: str
    cache_key: str


def _git_executable() -> str:
    git_bin = shutil.which("git")
    if git_bin is None:
        raise RuntimeError("git executable not found on PATH")
    return git_bin


def _run_git(args: List[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603
        [_git_executable(), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def git_rev_parse(ref: str) -> Optional[str]:
    """Resolve a git ref to its full commit SHA if present locally.

    Args:
        ref (str): Git tag, branch, or commit identifier.

    Returns:
        Optional[str]: Full 40-char commit SHA, or ``None`` if ``ref`` does not exist.
    """
    proc = _run_git(["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def parse_semver(raw: str) -> Optional[Tuple[int, int, int]]:
    """Parse a ``MAJOR.MINOR.PATCH`` or ``vMAJOR.MINOR.PATCH`` string into an integer tuple.

    Args:
        raw (str): Version string to parse.

    Returns:
        Optional[Tuple[int, int, int]]: Parsed ``(major, minor, patch)`` tuple, or ``None``.
    """
    match = SEMVER_RE.match(raw.strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def read_worktree_semver() -> Optional[Tuple[int, int, int]]:
    """Read the current working tree's ``(major, minor, patch)`` from ``pyproject.toml``.

    Returns:
        Optional[Tuple[int, int, int]]: Parsed version tuple from ``pyproject.toml``, if present.
    """
    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.is_file():
        return None
    match = PYPROJECT_VERSION_RE.search(pyproject.read_text(encoding="utf-8"))
    if not match:
        return None
    return parse_semver(match.group(1))


def list_released_tags() -> List[Tuple[Tuple[int, int, int], str]]:
    """List all local released SemVer tags ``vMAJOR.MINOR.PATCH`` sorted ascending.

    Returns:
        List[Tuple[Tuple[int, int, int], str]]: Sorted ``((major, minor, patch), tag_name)`` pairs.
    """
    proc = _run_git(["tag", "--list", "v*"])
    tags: List[Tuple[Tuple[int, int, int], str]] = []
    for line in proc.stdout.splitlines():
        tag = line.strip()
        if not tag.startswith("v"):
            continue
        ver = parse_semver(tag)
        if ver is not None:
            tags.append((ver, tag))
    tags.sort()
    return tags


def list_unreleased_prerelease_refs() -> List[Tuple[Tuple[int, int, int], str]]:
    """Discover active upcoming ``vX.Y.Z-pre-release`` branches newer than the latest release tag.

    Returns:
        List[Tuple[Tuple[int, int, int], str]]: Sorted ``((major, minor, patch), git_ref)`` pairs.
    """
    released = list_released_tags()
    released_versions = {ver for ver, _ in released}
    latest_released = released[-1][0] if released else (0, 0, 0)
    proc = _run_git(
        [
            "for-each-ref",
            "--format=%(refname)",
            "refs/heads/v*-pre-release",
            "refs/remotes/origin/v*-pre-release",
        ]
    )
    by_ver: Dict[Tuple[int, int, int], str] = {}
    for line in proc.stdout.splitlines():
        raw_ref = line.strip()
        match = PRERELEASE_BRANCH_RE.match(raw_ref)
        if not match:
            continue
        ver = (int(match.group(2)), int(match.group(3)), int(match.group(4)))
        if ver in released_versions or ver <= latest_released:
            continue
        short_ref = raw_ref[len("refs/remotes/"):] if raw_ref.startswith("refs/remotes/") else match.group(1)
        if ver not in by_ver or short_ref.startswith("origin/"):
            by_ver[ver] = short_ref
    return sorted(by_ver.items())


def resolve_version_spec(spec: str) -> ResolvedVersion:
    """Resolve a user or CI version specifier into a concrete ``ResolvedVersion``.

    Supports ``WORKTREE``, ``pypi:<version>``, exact git refs, or SemVer shorthands
    (e.g. ``X.Y.Z`` resolving to ``vX.Y.Z`` if tagged or ``origin/vX.Y.Z-pre-release``).

    Args:
        spec (str): Version specifier string.

    Raises:
        ValueError: If ``spec`` cannot be resolved to any git ref, worktree, or PyPI version.

    Returns:
        ResolvedVersion: Canonical resolved version metadata.
    """
    cleaned = spec.strip()
    if cleaned.upper() == "WORKTREE":
        head_sha = git_rev_parse("HEAD") or "worktree"
        return ResolvedVersion(
            spec=cleaned,
            kind="worktree",
            label="WORKTREE",
            ref_or_ver="WORKTREE",
            cache_key=f"worktree-{head_sha[:12]}",
        )
    if cleaned.startswith("pypi:"):
        ver_str = cleaned[len("pypi:"):].strip()
        if not ver_str:
            raise ValueError("Empty version in 'pypi:<version>' specifier")
        return ResolvedVersion(
            spec=cleaned,
            kind="pypi",
            label=f"pypi:{ver_str}",
            ref_or_ver=ver_str,
            cache_key=f"pypi-{ver_str}",
        )

    candidates = [
        cleaned,
        f"v{cleaned}",
        f"origin/{cleaned}",
        f"origin/v{cleaned}-pre-release",
        f"v{cleaned}-pre-release",
    ]
    for candidate in candidates:
        sha = git_rev_parse(candidate)
        if sha is not None:
            return ResolvedVersion(
                spec=cleaned,
                kind="git",
                label=candidate,
                ref_or_ver=candidate,
                cache_key=f"git-{sha[:12]}",
            )
    raise ValueError(
        f"Cannot resolve version specifier {spec!r} locally. "
        f"Pass a valid git tag/branch/SHA, 'WORKTREE', 'pypi:<version>', or run with --fetch-refs."
    )


def _select_baseline_tags(
    released: List[Tuple[Tuple[int, int, int], str]],
    target_ver: Optional[Tuple[int, int, int]],
) -> List[str]:
    if not released:
        return []
    prior = [item for item in released if target_ver is None or item[0] < target_ver]
    if not prior:
        return [released[-1][1]]
    return [prior[-1][1]]


def _resolve_sha_or_key(resolved: ResolvedVersion) -> str:
    if resolved.kind == "worktree":
        return f"WORKTREE:{git_rev_parse('HEAD') or 'dirty'}"
    if resolved.kind == "git":
        return git_rev_parse(resolved.ref_or_ver) or resolved.cache_key
    return resolved.cache_key


def _append_unique_pair(
    pairs: List[Tuple[ResolvedVersion, ResolvedVersion]],
    seen_pairs: Set[Tuple[str, str]],
    prev_ver: ResolvedVersion,
    next_ver: ResolvedVersion,
) -> None:
    prev_id = _resolve_sha_or_key(prev_ver)
    next_id = _resolve_sha_or_key(next_ver)
    raw_prev_sha = git_rev_parse(prev_ver.ref_or_ver) if prev_ver.kind == "git" else prev_id
    raw_next_sha = git_rev_parse("HEAD") if next_ver.kind == "worktree" else (
        git_rev_parse(next_ver.ref_or_ver) if next_ver.kind == "git" else next_id
    )
    if raw_prev_sha and raw_next_sha and raw_prev_sha == raw_next_sha and next_ver.kind != "worktree":
        return
    pair_key = (prev_id, next_id)
    if pair_key not in seen_pairs:
        seen_pairs.add(pair_key)
        pairs.append((prev_ver, next_ver))


def _add_branch_worktree_pair(
    pairs: List[Tuple[ResolvedVersion, ResolvedVersion]],
    seen_pairs: Set[Tuple[str, str]],
    candidates: Tuple[str, ...],
    worktree: ResolvedVersion,
) -> None:
    worktree_sha = git_rev_parse("HEAD")
    for candidate in candidates:
        sha = git_rev_parse(candidate)
        if sha is not None:
            if sha != worktree_sha:
                _append_unique_pair(pairs, seen_pairs, resolve_version_spec(candidate), worktree)
            return


def discover_default_pairs() -> List[Tuple[ResolvedVersion, ResolvedVersion]]:
    """Dynamically discover baseline -> target pairs without any hardcoded version strings.

    Includes:
    1. Latest prior released SemVer tag (and latest tag of prior major on major bumps) -> ``WORKTREE``
    2. ``origin/main`` (or ``main``) -> ``WORKTREE`` when distinct from ``HEAD``
    3. ``origin/$GITHUB_BASE_REF`` -> ``WORKTREE`` on pull requests when distinct
    4. Latest released SemVer tag -> each active unreleased ``v*-pre-release`` branch unless
       ``CROSS_VERSION_INCLUDE_PRERELEASES=0`` is set.

    Raises:
        RuntimeError: When running in CI and no baseline git tags or ``main`` ref are present.

    Returns:
        List[Tuple[ResolvedVersion, ResolvedVersion]]: Ordered list of ``(prev, next)`` pairs.
    """
    worktree = resolve_version_spec("WORKTREE")
    released = list_released_tags()
    target_ver = read_worktree_semver()

    pairs: List[Tuple[ResolvedVersion, ResolvedVersion]] = []
    seen_pairs: Set[Tuple[str, str]] = set()

    for tag in _select_baseline_tags(released, target_ver):
        _append_unique_pair(pairs, seen_pairs, resolve_version_spec(tag), worktree)

    _add_branch_worktree_pair(pairs, seen_pairs, ("origin/main", "main"), worktree)

    pr_base = os.environ.get("GITHUB_BASE_REF", "").strip()
    if pr_base:
        _add_branch_worktree_pair(pairs, seen_pairs, (f"origin/{pr_base}", pr_base), worktree)

    if os.environ.get("CROSS_VERSION_INCLUDE_PRERELEASES", "1") != "0" and released:
        latest_release = resolve_version_spec(released[-1][1])
        worktree_sha = git_rev_parse("HEAD")
        for _, prerelease_ref in list_unreleased_prerelease_refs():
            if git_rev_parse(prerelease_ref) != worktree_sha:
                _append_unique_pair(pairs, seen_pairs, latest_release, resolve_version_spec(prerelease_ref))

    if not pairs and (os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"):
        raise RuntimeError(
            "No baseline git tags or 'origin/main' found in CI checkout. "
            "Ensure checkout uses fetch-depth: 0 or run scripts/test_cross_version.sh --fetch-refs."
        )
    return pairs


def _safe_extract_tar_bytes(raw_tar: bytes, dest_dir: Path) -> None:
    resolved_dest = dest_dir.resolve()
    with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:") as archive_tar:
        for member in archive_tar.getmembers():
            member_target = (resolved_dest / member.name).resolve()
            if resolved_dest not in (member_target, *member_target.parents):
                raise RuntimeError(f"Unsafe tar member path {member.name!r}")
        if hasattr(tarfile, "data_filter"):
            archive_tar.extractall(path=str(resolved_dest), filter="data")
        else:
            for member in archive_tar.getmembers():
                if member.isdir():
                    (resolved_dest / member.name).mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    src_fh = archive_tar.extractfile(member)
                    if src_fh is not None:
                        target_file = resolved_dest / member.name
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        target_file.write_bytes(src_fh.read())


def _extract_git_tree(ref: str, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(  # nosec B603
        [_git_executable(), "archive", ref],
        cwd=str(REPO_ROOT),
        capture_output=True,
        timeout=20,
        check=False,
    )
    if archive.returncode != 0:
        raise RuntimeError(f"git archive failed for {ref!r}: {archive.stderr.decode('utf-8', 'replace')}")
    _safe_extract_tar_bytes(archive.stdout, dest_dir)


def _uv_install(uv_bin: str, venv_python: Path, packages: List[str]) -> subprocess.CompletedProcess[str]:
    cmd = [uv_bin, "pip", "install", "--quiet", "--python", str(venv_python), *packages]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)  # nosec B603
    if res.returncode != 0:
        res = subprocess.run(  # nosec B603
            [*cmd, "--offline"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    return res


def _install_target_into_venv(venv_dir: Path, install_target: str, use_uv: bool) -> Path:
    uv_bin = shutil.which("uv")
    if use_uv and uv_bin is not None:
        subprocess.run(  # nosec B603
            [uv_bin, "venv", "--quiet", "--python", sys.executable, str(venv_dir)],
            check=True,
            timeout=30,
        )
        venv_python = venv_dir / "bin" / "python"
        res = _uv_install(uv_bin, venv_python, [install_target])
        if res.returncode != 0:
            raise RuntimeError(f"uv pip install failed for {install_target!r}:\n{res.stderr}")
        # Best-effort install of optional cryptography extra so EncryptedRedisDict works in isolated venvs
        _uv_install(uv_bin, venv_python, ["cryptography"])
        return venv_python

    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, timeout=30)  # nosec B603
    venv_python = venv_dir / "bin" / "python"
    pip_cmd = [str(venv_python), "-m", "pip", "install", "--quiet"]
    subprocess.run([*pip_cmd, "--no-build-isolation", install_target], check=True, timeout=90)  # nosec B603
    subprocess.run([*pip_cmd, "cryptography"], capture_output=True, timeout=90, check=False)  # nosec B603
    return venv_python


class IsolatedEnvPool:  # pylint: disable=too-few-public-methods
    """Session cache provisioning one genuine virtual environment per resolved version."""

    def __init__(self, root_dir: Path, use_uv: bool = True) -> None:
        """Initialize an IsolatedEnvPool rooted at ``root_dir``.

        Args:
            root_dir (Path): Temporary directory holding extracted trees and venvs.
            use_uv (bool): Whether to prefer ``uv venv`` / ``uv pip install`` when available.
        """
        self.root_dir = root_dir
        self.use_uv = use_uv
        self._python_by_key: Dict[str, Path] = {}

    def get_python(self, resolved: ResolvedVersion) -> Path:
        """Provision (or reuse) an isolated virtual environment for ``resolved``.

        Args:
            resolved (ResolvedVersion): Version specification to install.

        Returns:
            Path: Path to the isolated virtual environment's ``python`` executable.
        """
        cached = self._python_by_key.get(resolved.cache_key)
        if cached is not None:
            return cached

        slot_dir = self.root_dir / resolved.cache_key
        venv_dir = slot_dir / "venv"
        if resolved.kind == "worktree":
            install_target = str(REPO_ROOT)
        elif resolved.kind == "pypi":
            install_target = f"redis-dict=={resolved.ref_or_ver}"
        else:
            src_checkout = slot_dir / "checkout"
            _extract_git_tree(resolved.ref_or_ver, src_checkout)
            install_target = str(src_checkout)

        venv_python = _install_target_into_venv(venv_dir, install_target, self.use_uv)
        self._python_by_key[resolved.cache_key] = venv_python
        return venv_python
