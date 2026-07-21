"""Git-first patch handling. Sentinel never writes a fix to the default branch."""
from __future__ import annotations

import subprocess
import uuid
import os
import re
from difflib import unified_diff
from pathlib import Path

from git import Repo

from sentinel.schemas import GitPatchResult, PatchPlan
from sentinel.swarm_agents import decode_code


def _github_slug(remote_url: str) -> str | None:
    match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", remote_url)
    return f"{match.group(1)}/{match.group(2)}" if match else None


def _open_github_pr(repo: Repo, branch: str, base: str) -> str | None:
    """Push the Sentinel branch and create a real GitHub pull request when configured."""
    token = os.getenv("GITHUB_TOKEN")
    if not token or "origin" not in [remote.name for remote in repo.remotes]:
        return None
    remote = repo.remotes.origin
    slug = _github_slug(next(remote.urls))
    if not slug:
        return None
    remote.push(refspec=f"{branch}:{branch}")
    from github import Auth, Github

    client = Github(auth=Auth.Token(token), timeout=30)
    pull = client.get_repo(slug).create_pull(
        title="Sentinel: serialize ticket inventory mutation",
        body="Automated Sentinel remediation. Review the Docker telemetry and invariant failure before merging.",
        head=branch,
        base=base,
    )
    return pull.html_url


def _is_dirty(repository_root: Path) -> bool:
    """Check worktree state without GitPython's diff-based implementation.

    Some Windows environments set Git's ``diff.noIndex`` globally, which makes
    ``git diff --cached`` invalid.  ``git status --porcelain`` is unaffected.
    """
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"Unable to inspect Git worktree: {completed.stderr.strip()}")
    return bool(completed.stdout.strip())


def apply_patch_on_branch(repository_root: Path, target: Path, patch: PatchPlan) -> GitPatchResult:
    repo = Repo(repository_root)
    if _is_dirty(repository_root):
        raise RuntimeError("Refusing to patch a dirty repository; commit or stash changes first.")
    main_branch = repo.heads.main
    main_branch.checkout()
    # Repeated runs never reset, delete, or overwrite user history. Each run
    # gets a reviewable branch rooted at main, including if a previous Sentinel
    # branch already exists.
    branch_name = f"{patch.branch_name}-{uuid.uuid4().hex[:8]}"
    repo.create_head(branch_name, main_branch.commit).checkout()
    destination = (target / patch.file_path).resolve()
    if target.resolve() not in destination.parents:
        raise RuntimeError("Patch path escaped the approved target directory")
    original_source = destination.read_text(encoding="utf-8")
    patched_source = decode_code(patch.patched_source_b64)
    destination.write_text(patched_source, encoding="utf-8")
    repo.index.add([str(destination.relative_to(repository_root))])
    commit = repo.index.commit("Auto-patch: serialize ticket inventory mutation")
    # Render the reviewed diff directly. This avoids a Windows/GitPython display
    # incompatibility while keeping Git responsible for the actual commit.
    relative = destination.relative_to(repository_root).as_posix()
    diff = "".join(unified_diff(
        original_source.splitlines(keepends=True),
        patched_source.splitlines(keepends=True),
        fromfile=f"a/{relative}",
        tofile=f"b/{relative}",
    ))
    pr_url = _open_github_pr(repo, branch_name, main_branch.name)
    return GitPatchResult(branch=branch_name, commit=commit.hexsha, diff=diff, github_pr_url=pr_url)


def ensure_initial_repository(root: Path) -> None:
    if (root / ".git").exists():
        return
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=Sentinel.dev", "-c", "user.email=sentinel@example.invalid", "commit", "-m", "Initial Sentinel.dev prototype"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
