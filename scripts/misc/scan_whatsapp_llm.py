#!/usr/bin/env python3
"""
Scan WhatsApp groups for job postings and analyze compatibility using LLM skill extraction.
Fetches from job-specific groups, extracts skills via Ollama, scores compatibility.
"""
import os
import sys
import json
import time
import subprocess
import logging
import re

# Config
os.environ.setdefault("SEND_TO_CONTACT", "0")
os.environ.setdefault("AUTO_SEND_TO_SELF", "0")
os.environ.setdefault("COMPATIBILITY_THRESHOLD", "20.0")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apply_real_job import (
    extract_contact_email, extract_skills_llm, compute_compatibility,
    load_curriculum_text
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WAHA_API = os.getenv("WAHA_API", "http://localhost:3001")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "")
MSG_LIMIT = int(os.getenv("MSG_LIMIT", "50"))


def waha_get(endpoint: str, timeout: int = 10):
    """GET request to WAHA API."""
    url = f"{WAHA_API}{endpoint}"
    cmd = ["curl", "-s", "-m", str(timeout),
           "-H", f"X-Api-Key: {WAHA_API_KEY}",
           "-H", "Accept: application/json", url]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def find_job_groups() -> list:
    """Find WhatsApp groups that are likely job posting groups."""
    chats = waha_get("/api/default/chats")
    if not chats:
        return []
    groups = [c for c in chats if "@g.us" in c.get("id", "")]
    job_groups = []
    job_keywords = ["vaga", "emprego", "oportunidade", "trabalho", "job", "career",
                    "contrat", "dev", "tech", "ti ", "python", "java", "devops"]
    for g in groups:
        gid = g.get("id", "")
        info = waha_get(f"/api/default/groups/{gid}", timeout=5)
        subject = (info.get("subject", "") if info else "").lower()
        if any(kw in subject for kw in job_keywords):
            job_groups.append({"id": gid, "name": info.get("subject", gid)})
            logger.info(f"  Grupo de vagas: {info.get('subject', gid)}")
    return job_groups


def is_job_posting(text: str) -> bool:
    """Quick keyword check if text looks like a job posting."""
    if not text or len(text) < 80:
        return False
    lower = text.lower()
    job_terms = ["vaga", "oportunidade", "contrat", "selecion", "processo seletivo",
                 "clt", "pj", "remoto", "híbrido", "presencial", "requisitos",
                 "devops", "sre", "engenheiro", "cloud", "kubernetes", "aws",
                 "desenvolvedor", "analista", "senior", "pleno", "tech lead",
                 "experiência", "habilidades", "skills", "stack", "salário",
                 "benefícios", "enviar cv", "enviar currículo", "candidatura"]
    return sum(1 for t in job_terms if t in lower) >= 2


def main():
    print("=" * 70)
    print("SCAN WHATSAPP - LLM Skills Extraction")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    if not WAHA_API_KEY:
        print("ERROR: WAHA_API_KEY nao definida")
        sys.exit(1)

    # Step 1: Load curriculum
    print("\n[1/5] Carregando curriculo...")
    cv = load_curriculum_text()
    if not cv or len(cv) < 50:
        print("ERROR: Curriculo nao carregado corretamente")
        sys.exit(1)
    print(f"  CV carregado: {len(cv)} chars")

    # Step 2: Extract CV skills via LLM
    print("\n[2/5] Extraindo skills do curriculo via LLM...")
    cv_skills = extract_skills_llm(cv, text_type="resume")
    print(f"  Technical Skills ({len(cv_skills.get('technical_skills', []))}): "
          f"{', '.join(cv_skills.get('technical_skills', []))}")
    print(f"  Domains: {', '.join(cv_skills.get('domains', []))}")
    print(f"  Seniority: {cv_skills.get('seniority', 'unknown')}")

    # Step 3: Find job groups
    print("\n[3/5] Buscando grupos de vagas no WhatsApp...")
    job_groups = find_job_groups()
    if not job_groups:
        print("  Nenhum grupo de vagas encontrado. Buscando no primeiro grupo...")
        chats = waha_get("/api/default/chats")
        groups = [c for c in (chats or []) if "@g.us" in c.get("id", "")]
        if groups:
            job_groups = [{"id": groups[0]["id"], "name": "primeiro grupo"}]
    print(f"  Grupos de vagas: {len(job_groups)}")
    for g in job_groups:
        print(f"    - {g['name']} ({g['id']})")

    # Step 4: Fetch & classify messages from job groups
    print(f"\n[4/5] Buscando mensagens (limit={MSG_LIMIT} por grupo)...")
    all_job_msgs = []
    for group in job_groups:
        msgs = waha_get(f"/api/default/chats/{group['id']}/messages?limit={MSG_LIMIT}")
        if not msgs:
            print(f"  {group['name']}: sem mensagens")
            continue
        jobs_in_group = 0
        for m in msgs:
            body = m.get("body", "") or ""
            if is_job_posting(body):
                all_job_msgs.append({"text": body, "group": group["name"], "group_id": group["id"]})
                jobs_in_group += 1
        print(f"  {group['name']}: {len(msgs)} mensagens, {jobs_in_group} vagas detectadas")

    if not all_job_msgs:
        print("  Nenhuma vaga encontrada nas mensagens")
        sys.exit(0)
    print(f"\n  Total vagas para analise: {len(all_job_msgs)}")

    # Step 5: LLM analysis of each job posting
    print(f"\n[5/5] Analisando vagas com LLM (pode demorar ~60s por vaga)...")
    vagas = []
    for i, job_msg in enumerate(all_job_msgs):
        text = job_msg["text"]
        print(f"\n{'='*70}")
        print(f"VAGA #{i+1}/{len(all_job_msgs)} (grupo: {job_msg['group']})")
        print(f"  Texto: {text[:150]}...")

        vaga = {
            "index": i + 1,
            "group": job_msg["group"],
            "text_preview": text[:300],
            "full_text": text,
            "email": extract_contact_email(text),
        }

        # Compute compatibility (internally uses LLM skills)
        try:
            score, explanation, details = compute_compatibility(cv, text)
            vaga["score"] = score
            vaga["method"] = details.get("method", "unknown")
            vaga["explanation"] = explanation[:300]
            vaga["common_skills"] = details.get("common_technical_skills", [])
            vaga["job_skills"] = details.get("job_technical_skills", [])
            vaga["resume_skills"] = details.get("resume_technical_skills", [])
            vaga["component_scores"] = details.get("component_scores", {})
        except Exception as e:
            logger.error(f"  Erro na compatibilidade: {e}")
            vaga["score"] = 0
            vaga["method"] = "error"
            vaga["explanation"] = str(e)

        vagas.append(vaga)

        # Print result
        print(f"  Score: {vaga.get('score', 0):.1f}% ({vaga.get('method', '?')})")
        if vaga.get("email"):
            print(f"  Email: {vaga['email']}")
        if vaga.get("common_skills"):
            print(f"  Skills em comum: {', '.join(vaga['common_skills'][:8])}")
        if vaga.get("job_skills"):
            print(f"  Job requer: {', '.join(vaga['job_skills'][:8])}")
        cs = vaga.get("component_scores", {})
        if cs:
            print(f"  Componentes: tech={cs.get('technical',0):.0f}% "
                  f"domain={cs.get('domain',0):.0f}% soft={cs.get('soft_skills',0):.0f}%")

    # Summary
    print(f"\n{'='*70}")
    print("RESUMO FINAL")
    print(f"{'='*70}")
    print(f"Grupos analisados: {len(job_groups)}")
    print(f"Vagas analisadas: {len(vagas)}")

    if vagas:
        vagas_sorted = sorted(vagas, key=lambda v: v.get("score", 0), reverse=True)
        threshold = float(os.environ.get("COMPATIBILITY_THRESHOLD", "20.0"))

        print(f"\nRanking de compatibilidade (threshold: {threshold}%):")
        for v in vagas_sorted:
            icon = "+" if v.get("score", 0) >= threshold else "-"
            print(f"  [{icon}] {v.get('score',0):5.1f}% | {v['text_preview'][:80]}...")
            if v.get("common_skills"):
                print(f"           Skills: {', '.join(v['common_skills'][:6])}")

        compativeis = [v for v in vagas if v.get("score", 0) >= threshold]
        print(f"\nVagas compativeis (>={threshold}%): {len(compativeis)}/{len(vagas)}")

        if compativeis:
            print("\nDETALHES DAS VAGAS COMPATIVEIS:")
            for v in sorted(compativeis, key=lambda x: x.get("score", 0), reverse=True):
                print(f"\n  Score: {v.get('score',0):.1f}% | {v.get('method','?')}")
                print(f"  Grupo: {v.get('group','?')}")
                print(f"  Texto: {v['text_preview'][:200]}")
                if v.get("email"):
                    print(f"  Email: {v['email']}")
                if v.get("job_skills"):
                    print(f"  Skills requeridos: {', '.join(v['job_skills'])}")
                if v.get("common_skills"):
                    print(f"  Em comum: {', '.join(v['common_skills'])}")

    # Save results
    output_file = "/tmp/whatsapp_llm_skills_scan.json"
    save_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cv_skills": cv_skills,
        "groups_scanned": [g["name"] for g in job_groups],
        "total_vagas": len(vagas),
        "vagas": [{k: v for k, v in vaga.items() if k != "full_text"} for vaga in vagas],
    }
    with open(output_file, "w") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    print(f"\nResultados salvos em: {output_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
