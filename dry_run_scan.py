#!/usr/bin/env python3
"""
Dry-run: processa TODAS as mensagens do WhatsApp, calcula compatibilidade
e imprime o email gerado para cada match (sem enviar).
"""
import sys
import os
import json
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Force threshold from env or default
os.environ.setdefault("COMPATIBILITY_THRESHOLD", "20.0")
os.environ.setdefault("COMPATIBILITY_METHOD", "semantic")

from apply_real_job import (
    load_curriculum_text,
    extract_skills_summary,
    classify_message_strict,
    classify_message_llm,
    compute_compatibility,
    generate_application_email_llm,
    extract_contact_email,
    get_waha_api_key,
    review_compatibility_with_llm,
    WAHA_API,
    CURRICULUM_TEXT,
    CURRICULUM_SKILLS,
    COMPATIBILITY_THRESHOLD,
    MESSAGE_MIN_LENGTH,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    global CURRICULUM_TEXT, CURRICULUM_SKILLS

    print("\n" + "=" * 70)
    print("🔍 DRY-RUN: Scan completo WhatsApp (sem envio de email)")
    print("=" * 70)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Threshold: {COMPATIBILITY_THRESHOLD}%")
    print(f"📏 Min length: {MESSAGE_MIN_LENGTH} chars\n")

    # 1. Load curriculum
    print("📄 Carregando currículo com Docling...")
    CURRICULUM_TEXT = load_curriculum_text()
    if not CURRICULUM_TEXT or len(CURRICULUM_TEXT) < 50:
        print("❌ Currículo não carregado. Abortando.")
        return
    print(f"  ✅ Currículo: {len(CURRICULUM_TEXT)} caracteres")

    # Extract skills summary for better semantic matching
    import apply_real_job
    CURRICULUM_SKILLS = extract_skills_summary(CURRICULUM_TEXT)
    apply_real_job.CURRICULUM_SKILLS = CURRICULUM_SKILLS
    print(f"  🎯 Skills summary: {len(CURRICULUM_SKILLS)} caracteres\n")

    # 2. Get WAHA key and session
    try:
        api_key = get_waha_api_key()
    except Exception as e:
        print(f"❌ WAHA key error: {e}")
        return

    def curl_json(url, timeout=15):
        cmd = ["curl", "-s", "-m", str(timeout),
               "-H", f"X-Api-Key: {api_key}",
               "-H", "Accept: application/json", url]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 3)
        return res.stdout

    # Get session
    try:
        sessions = json.loads(curl_json(f"{WAHA_API}/api/sessions"))
        if isinstance(sessions, list) and sessions:
            session_name = sessions[0].get('name', 'default')
        else:
            session_name = 'default'
    except Exception:
        session_name = 'default'

    # 3. List all chats
    try:
        chats_raw = json.loads(curl_json(f"{WAHA_API}/api/{session_name}/chats"))
        if isinstance(chats_raw, dict):
            if 'error' in chats_raw:
                print(f"❌ Erro WAHA: {chats_raw.get('error')}")
                print(f"   Status da sessão: {chats_raw.get('status', 'unknown')}")
                return
            chats = chats_raw.get('data', [])
        else:
            chats = chats_raw
    except Exception as e:
        print(f"❌ Erro ao listar chats: {e}")
        return

    group_chats = [c for c in chats if isinstance(c, dict) and ('@g.us' in (c.get('id') or '') or c.get('isGroup') or c.get('type') == 'group')]
    print(f"📱 Total de grupos encontrados: {len(group_chats)}\n")

    # 4. Scan ALL messages
    cutoff = datetime.now() - timedelta(days=60)
    cutoff_ts = int(cutoff.timestamp())

    total_messages = 0
    jobs_found = 0
    matches = []
    filtered_strict = 0
    filtered_llm = 0
    below_threshold = 0

    for idx, chat in enumerate(group_chats, 1):
        cid = chat.get('id') or chat.get('chatId')
        if not cid:
            continue
        chat_name = chat.get('name') or cid
        is_archived = chat.get('isArchived') or chat.get('archived')
        arch_tag = " [ARCHIVED]" if is_archived else ""

        print(f"  [{idx}/{len(group_chats)}] 📂 {chat_name}{arch_tag}")

        try:
            msgs = json.loads(curl_json(f"{WAHA_API}/api/{session_name}/chats/{cid}/messages?limit=200"))
        except Exception as ex:
            print(f"    ⚠️  Erro: {ex}")
            continue

        chat_msg_count = 0
        for m in msgs:
            ts = m.get('timestamp') or m.get('t')
            if ts:
                try:
                    ts_int = int(ts) if isinstance(ts, (int, float)) else int(datetime.fromisoformat(str(ts).replace('Z', '+00:00')).timestamp())
                    if ts_int < cutoff_ts:
                        continue
                except Exception:
                    pass

            text = m.get('body') or ''
            if not text or len(text) < MESSAGE_MIN_LENGTH:
                continue

            total_messages += 1
            chat_msg_count += 1

            # Classify strict
            label, reason = classify_message_strict(text)
            if label != "job":
                filtered_strict += 1
                continue

            # Classify LLM
            llm_label, llm_reason = classify_message_llm(text)
            if llm_label != "job":
                filtered_llm += 1
                continue

            jobs_found += 1

            # Compute compatibility
            compat, explanation, details = compute_compatibility(CURRICULUM_TEXT, text)

            contact_email = extract_contact_email(text)
            job_title = text.split('\n', 1)[0][:120]

            if compat >= COMPATIBILITY_THRESHOLD:
                match_data = {
                    'title': job_title,
                    'company': chat_name,
                    'description': text,
                    'excerpt': text[:300],
                    'compatibility': compat,
                    'explanation': explanation,
                    'details': details,
                    'contact_email': contact_email,
                    'chat_id': cid,
                }
                matches.append(match_data)
                print(f"    ✅ MATCH: {compat:.1f}% | {job_title[:60]}...")
            else:
                below_threshold += 1
                print(f"    ❌ Abaixo: {compat:.1f}% | {job_title[:60]}...")

        if chat_msg_count > 0:
            print(f"    📊 {chat_msg_count} mensagens processadas")

    # 5. Summary
    print("\n" + "=" * 70)
    print("📊 RESULTADO DO SCAN")
    print("=" * 70)
    print(f"  📱 Grupos escaneados: {len(group_chats)}")
    print(f"  💬 Mensagens processadas: {total_messages}")
    print(f"  🚫 Filtradas (strict): {filtered_strict}")
    print(f"  🚫 Filtradas (LLM): {filtered_llm}")
    print(f"  🏷️  Vagas detectadas: {jobs_found}")
    print(f"  ❌ Abaixo do threshold: {below_threshold}")
    print(f"  ✅ Matches (>= {COMPATIBILITY_THRESHOLD}%): {len(matches)}")

    # 6. Print emails for each match
    if matches:
        print("\n" + "=" * 70)
        print("📧 EMAILS QUE SERIAM ENVIADOS (DRY-RUN)")
        print("=" * 70)

        for i, job in enumerate(matches, 1):
            compat = float(job.get('compatibility', 0))
            contact = job.get('contact_email') or '(não encontrado)'

            print(f"\n{'─' * 70}")
            print(f"📧 EMAIL #{i}")
            print(f"{'─' * 70}")
            print(f"  Vaga: {job['title']}")
            print(f"  Grupo: {job['company']}")
            print(f"  Compatibilidade: {compat:.1f}%")
            print(f"  Contato: {contact}")
            print(f"  Explicação: {job.get('explanation', 'N/A')}")

            # Generate email
            try:
                subject, body = generate_application_email_llm(job, compat)
                print(f"\n  📬 PARA: {contact}")
                print(f"  📌 ASSUNTO: {subject}")
                print(f"  📎 ANEXO: Curriculo_Edenilson.docx")
                print(f"\n  {'─' * 50}")
                print(f"  CORPO DO EMAIL:")
                print(f"  {'─' * 50}")
                for line in body.split('\n'):
                    print(f"  {line}")
                print(f"  {'─' * 50}")
            except Exception as e:
                print(f"  ⚠️  Erro ao gerar email: {e}")

            # LLM review
            try:
                review = review_compatibility_with_llm(CURRICULUM_TEXT, job['description'], compat, job.get('details', {}))
                if review:
                    print(f"\n  🔍 REVISÃO LLM:")
                    for line in review.split('\n')[:15]:
                        print(f"    {line}")
            except Exception as e:
                print(f"  ⚠️  Revisão LLM falhou: {e}")

    else:
        print("\n  ℹ️  Nenhum match encontrado. Nenhum email seria gerado.")

    print(f"\n{'=' * 70}")
    print(f"✅ DRY-RUN FINALIZADO - {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
