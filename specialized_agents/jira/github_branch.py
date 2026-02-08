#!/usr/bin/env python3
"""GitHub branch-per-task management for Jira-distributed work.

Creates feature branches in the target GitHub repo for each Jira ticket
assigned to an agent, ensuring isolated development per task.

Usage (standalone):
    python -m specialized_agents.jira.github_branch EA-19

Usage (from distribute_and_sync):
    branches = await create_branches_for_tickets(
        repo="eddiejdi/estou-aqui",
        tickets={"python_agent": ["EA-19", "EA-20"]},
        project_key="EA",
    )
"""
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

# Map Jira project keys to GitHub repos
PROJECT_REPOS: Dict[str, str] = {
    "EA": "eddiejdi/estou-aqui",
    "SCRUM": "eddiejdi/eddie-auto-dev",
}

DEFAULT_BASE_BRANCH = "main"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(text: str, max_len: int = 50) -> str:
    """Convert text to a safe branch-name slug."""
    slug = text.lower()
    for old, new in [
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("ã", "a"), ("õ", "o"), ("ç", "c"), ("ê", "e"), ("â", "a"),
        ("ô", "o"), ("à", "a"), (" ", "-"),
    ]:
        slug = slug.replace(old, new)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_len].rstrip("-")


def branch_name_for_ticket(key: str, summary: str) -> str:
    """Generate branch name: feat/<key>-<summary-slug>"""
    slug = _slugify(summary)
    return f"feat/{key.lower()}-{slug}"


def _run_gh(args: List[str], cwd: str = None) -> subprocess.CompletedProcess:
    """Run a `gh` CLI command."""
    cmd = ["gh"] + args
    logger.debug("Running: %s", " ".join(cmd))
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, cwd=cwd,
    )


# ─── Core functions ──────────────────────────────────────────────────────────

def create_branch(
    repo: str,
    branch: str,
    base: str = DEFAULT_BASE_BRANCH,
) -> Dict:
    """Create a branch in a GitHub repo using the gh CLI.
    
    Returns dict with status info.
    """
    # Check if branch already exists
    check = _run_gh(["api", f"repos/{repo}/branches/{branch}"])
    if check.returncode == 0:
        logger.info("Branch %s already exists in %s", branch, repo)
        return {"branch": branch, "repo": repo, "status": "exists"}

    # Get base branch SHA
    sha_result = _run_gh([
        "api", f"repos/{repo}/git/ref/heads/{base}",
        "--jq", ".object.sha",
    ])
    if sha_result.returncode != 0:
        logger.error("Failed to get SHA for %s/%s: %s", repo, base, sha_result.stderr)
        return {"branch": branch, "repo": repo, "status": "error",
                "error": f"Cannot get base SHA: {sha_result.stderr.strip()}"}

    base_sha = sha_result.stdout.strip()
    if not base_sha:
        return {"branch": branch, "repo": repo, "status": "error",
                "error": "Empty SHA returned"}

    # Create the ref
    import json
    create_result = _run_gh([
        "api", f"repos/{repo}/git/refs",
        "-f", f"ref=refs/heads/{branch}",
        "-f", f"sha={base_sha}",
    ])

    if create_result.returncode == 0:
        logger.info("✅ Created branch %s in %s", branch, repo)
        return {"branch": branch, "repo": repo, "status": "created", "sha": base_sha}
    elif "Reference already exists" in create_result.stderr:
        logger.info("Branch %s already exists in %s (race)", branch, repo)
        return {"branch": branch, "repo": repo, "status": "exists"}
    else:
        logger.error("Failed to create branch %s: %s", branch, create_result.stderr)
        return {"branch": branch, "repo": repo, "status": "error",
                "error": create_result.stderr.strip()}


async def create_branches_for_tickets(
    tickets_by_agent: Dict[str, List[str]],
    project_key: str = "EA",
    ticket_summaries: Dict[str, str] = None,
) -> Dict:
    """Create feature branches for all distributed tickets.
    
    Args:
        tickets_by_agent: {agent_name: [ticket_keys]}
        project_key: Jira project key (to resolve repo)
        ticket_summaries: {ticket_key: summary} for branch naming
        
    Returns:
        Dict with results per ticket
    """
    repo = PROJECT_REPOS.get(project_key)
    if not repo:
        return {"error": f"No GitHub repo mapped for project {project_key}"}

    results = {"repo": repo, "branches": {}, "created": 0, "existed": 0, "errors": 0}
    summaries = ticket_summaries or {}

    for agent_name, keys in tickets_by_agent.items():
        for key in keys:
            summary = summaries.get(key, key)
            branch = branch_name_for_ticket(key, summary)

            res = create_branch(repo, branch)
            results["branches"][key] = {
                "branch": branch,
                "agent": agent_name,
                **res,
            }

            if res["status"] == "created":
                results["created"] += 1
            elif res["status"] == "exists":
                results["existed"] += 1
            else:
                results["errors"] += 1

    logger.info(
        "Branch creation: %d created, %d existed, %d errors",
        results["created"], results["existed"], results["errors"],
    )
    return results


def get_ticket_branch(key: str, summary: str = "") -> str:
    """Get the expected branch name for a Jira ticket key."""
    return branch_name_for_ticket(key, summary or key)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _cli():
    import sys
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python -m specialized_agents.jira.github_branch <ticket-key> [summary]")
        print("       python -m specialized_agents.jira.github_branch EA-19 'Login social'")
        sys.exit(1)

    key = sys.argv[1]
    summary = sys.argv[2] if len(sys.argv) > 2 else key
    project = key.split("-")[0]

    repo = PROJECT_REPOS.get(project)
    if not repo:
        print(f"No repo mapped for project {project}. Known: {list(PROJECT_REPOS.keys())}")
        sys.exit(1)

    branch = branch_name_for_ticket(key, summary)
    print(f"Creating branch '{branch}' in {repo}...")
    result = create_branch(repo, branch)
    print(f"Result: {result}")


if __name__ == "__main__":
    _cli()
