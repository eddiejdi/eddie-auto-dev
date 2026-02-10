#!/usr/bin/env python3
"""
Script para corrigir/normalizar o campo de repositório em issues do Jira Cloud.
Uso:
  JIRA_REPOSITORY_FIELD=customfield_12345 python3 tools/fix_jira_repo_field.py --dry-run

O script mapeia o `project_key` para repositório via `PROJECT_REPOS` em
`specialized_agents/jira/github_branch.py` e aplica comentário + atualiza o
custom field se `JIRA_REPOSITORY_FIELD` estiver definido.
"""
import asyncio
import os
import argparse
from typing import Dict
import importlib.util


def _load_module_from_path(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Carregar módulos diretamente pelos paths para evitar importar o pacote
_HERE = os.path.dirname(__file__)
_PKG = os.path.normpath(os.path.join(_HERE, '..', 'specialized_agents', 'jira'))
atlassian_client_mod = _load_module_from_path(os.path.join(_PKG, 'atlassian_client.py'), 'atlassian_client')
github_branch_mod = _load_module_from_path(os.path.join(_PKG, 'github_branch.py'), 'github_branch')

get_jira_cloud_client = atlassian_client_mod.get_jira_cloud_client
PROJECT_REPOS = github_branch_mod.PROJECT_REPOS


def _args():
    p = argparse.ArgumentParser()
    p.add_argument("--project", help="Somente processar este project key (ex: SCRUM)", default=None)
    p.add_argument("--dry-run", help="Não faz alterações, só mostra o que faria", action="store_true")
    p.add_argument("--max", help="Max results por query (default:200)", type=int, default=200)
    return p.parse_args()


async def _process_project(client, project: str, dry_run: bool, max_results: int):
    repo = PROJECT_REPOS.get(project)
    if not repo:
        print(f"[skip] Sem repo mapeado para {project}")
        return 0

    jql = f"project = {project} ORDER BY key ASC"
    print(f"Processing project={project} -> repo={repo} (jql={jql})")
    res = await client.search_issues(jql, max_results=max_results)
    issues = res.get("issues", [])
    print(f"  Found {len(issues)} issues")

    field_name = os.environ.get("JIRA_REPOSITORY_FIELD", "")
    changed = 0
    for iss in issues:
        key = iss.get("key")
        fields = iss.get("fields", {})
        # Heurística: avoid touching if field already set to same value
        current = None
        if field_name:
            current = fields.get(field_name)
            if current == repo:
                continue

        print(f"  -> {key}")
        if dry_run:
            print(f"     would add comment and set {field_name}={repo}")
            changed += 1
            continue

        # Add comment
        try:
            await client.add_comment(key, f"[Auto-fix] Repositório associado: {repo}")
        except Exception as e:
            print(f"     comment failed for {key}: {e}")
        # Update custom field if configured
        if field_name:
            try:
                await client.update_issue(key, {field_name: repo})
                changed += 1
            except Exception as e:
                print(f"     update failed for {key}: {e}")
    return changed


async def main():
    args = _args()
    client = get_jira_cloud_client()
    if not client.is_configured:
        print("JIRA_API_TOKEN não configurado — abortando.")
        return

    projects = [args.project] if args.project else list(PROJECT_REPOS.keys())
    total = 0
    for p in projects:
        changed = await _process_project(client, p, args.dry_run, args.max)
        total += changed

    print(f"Done. Total modified: {total}")


if __name__ == '__main__':
    asyncio.run(main())
