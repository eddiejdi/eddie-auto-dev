#!/usr/bin/env python3
"""
Training data collector for eddie-whatsapp model fine-tuning.
Collects feedback on compatibility predictions to improve future predictions.
"""
import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Optional


TRAINING_DB = os.getenv("TRAINING_DB", "/tmp/whatsapp_training.db")


def init_training_db():
    """Initialize SQLite database for training data collection."""
    conn = sqlite3.connect(TRAINING_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            resume_text TEXT NOT NULL,
            job_text TEXT NOT NULL,
            predicted_score REAL,
            actual_score REAL,
            user_feedback TEXT,
            was_sent INTEGER DEFAULT 0,
            email_status TEXT,
            notes TEXT,
            llm_explanation TEXT,
            jaccard_score REAL,
            method TEXT DEFAULT 'llm'
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp ON training_samples(timestamp)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_was_sent ON training_samples(was_sent)
    """)
    
    conn.commit()
    conn.close()
    print(f"✅ Training database initialized at {TRAINING_DB}")


def collect_training_sample(
    resume_text: str,
    job_text: str,
    predicted_score: float,
    actual_score: Optional[float] = None,
    user_feedback: Optional[str] = None,
    was_sent: bool = False,
    email_status: Optional[str] = None,
    llm_explanation: Optional[str] = None,
    jaccard_score: Optional[float] = None,
    method: str = "llm"
) -> int:
    """
    Collect a training sample.
    
    Args:
        resume_text: Candidate resume
        job_text: Job posting
        predicted_score: Score predicted by model (0-100)
        actual_score: Actual/corrected score (if available)
        user_feedback: User feedback (accepted/rejected/spam/good_match/etc)
        was_sent: Whether email was sent for this match
        email_status: Status of email (SENT/FAILED/DRAFT_SAVED)
        llm_explanation: Model's explanation
        jaccard_score: Baseline Jaccard score
        method: Method used (llm/jaccard/hybrid)
    
    Returns:
        Sample ID
    """
    conn = sqlite3.connect(TRAINING_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO training_samples (
            timestamp, resume_text, job_text, predicted_score, actual_score,
            user_feedback, was_sent, email_status, notes, llm_explanation,
            jaccard_score, method
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        resume_text[:5000],  # Truncate very long texts
        job_text[:5000],
        predicted_score,
        actual_score,
        user_feedback,
        1 if was_sent else 0,
        email_status,
        None,
        llm_explanation[:500] if llm_explanation else None,
        jaccard_score,
        method
    ))
    
    sample_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return sample_id


def update_training_feedback(sample_id: int, user_feedback: str, actual_score: Optional[float] = None):
    """Update training sample with user feedback after review."""
    conn = sqlite3.connect(TRAINING_DB)
    cursor = conn.cursor()
    
    if actual_score is not None:
        cursor.execute("""
            UPDATE training_samples 
            SET user_feedback = ?, actual_score = ?, notes = ?
            WHERE id = ?
        """, (user_feedback, actual_score, f"Updated on {datetime.now().isoformat()}", sample_id))
    else:
        cursor.execute("""
            UPDATE training_samples 
            SET user_feedback = ?, notes = ?
            WHERE id = ?
        """, (user_feedback, f"Updated on {datetime.now().isoformat()}", sample_id))
    
    conn.commit()
    conn.close()
    print(f"✅ Feedback updated for sample {sample_id}")


def get_training_stats() -> Dict:
    """Get statistics on collected training data."""
    conn = sqlite3.connect(TRAINING_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM training_samples")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM training_samples WHERE was_sent = 1")
    sent = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM training_samples WHERE user_feedback IS NOT NULL")
    with_feedback = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM training_samples WHERE actual_score IS NOT NULL")
    with_correction = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT AVG(predicted_score), AVG(actual_score), AVG(jaccard_score)
        FROM training_samples
        WHERE actual_score IS NOT NULL
    """)
    avg_row = cursor.fetchone()
    avg_predicted = avg_row[0] if avg_row[0] else 0
    avg_actual = avg_row[1] if avg_row[1] else 0
    avg_jaccard = avg_row[2] if avg_row[2] else 0
    
    # Calculate error
    cursor.execute("""
        SELECT AVG(ABS(predicted_score - actual_score))
        FROM training_samples
        WHERE actual_score IS NOT NULL
    """)
    mae = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        "total_samples": total,
        "sent_emails": sent,
        "with_feedback": with_feedback,
        "with_correction": with_correction,
        "avg_predicted_score": round(avg_predicted, 2),
        "avg_actual_score": round(avg_actual, 2),
        "avg_jaccard_score": round(avg_jaccard, 2),
        "mean_absolute_error": round(mae, 2)
    }


def export_training_dataset(output_file: str = "/tmp/whatsapp_training_dataset.jsonl"):
    """
    Export training data in JSONL format for model fine-tuning.
    
    Format for Ollama fine-tuning:
    {"prompt": "...", "completion": "..."}
    """
    conn = sqlite3.connect(TRAINING_DB)
    cursor = conn.cursor()
    
    # Export samples with corrections or feedback
    cursor.execute("""
        SELECT resume_text, job_text, predicted_score, actual_score, 
               user_feedback, llm_explanation
        FROM training_samples
        WHERE actual_score IS NOT NULL OR user_feedback IS NOT NULL
        ORDER BY timestamp DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("⚠️  No training data available for export")
        return 0
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for row in rows:
            resume, job, predicted, actual, feedback, explanation = row
            
            # Use actual score if available, otherwise infer from feedback
            target_score = actual if actual is not None else predicted
            
            # Adjust score based on feedback
            if actual is None and feedback:
                if feedback in ['good_match', 'accepted', 'relevant']:
                    target_score = max(predicted, 70)  # Boost if good
                elif feedback in ['bad_match', 'rejected', 'spam', 'irrelevant']:
                    target_score = min(predicted, 20)  # Lower if bad
            
            prompt = f"""Você é um especialista em recrutamento técnico. Analise a compatibilidade entre o currículo e a vaga abaixo.

**CURRÍCULO:**
{resume[:2000]}

**VAGA:**
{job[:2000]}

**TAREFA:**
1. Avalie a compatibilidade técnica (tecnologias, ferramentas, experiência)
2. Considere sinônimos e termos equivalentes (ex: Kubernetes = K8s, DevOps = SRE)
3. Avalie a senioridade esperada vs experiência do candidato
4. Ignore diferenças irrelevantes (formato, língua, estilo de escrita)

**RESPONDA NO SEGUINTE FORMATO:**
Score: [número de 0 a 100]%
Justificativa: [explicação breve de 1-2 linhas]"""

            completion = f"Score: {target_score}%\nJustificativa: {explanation or 'Match baseado em análise técnica e experiência.'}"
            
            training_item = {
                "prompt": prompt,
                "completion": completion
            }
            
            f.write(json.dumps(training_item, ensure_ascii=False) + '\n')
    
    print(f"✅ Exported {len(rows)} training samples to {output_file}")
    return len(rows)


def show_training_dashboard():
    """Display training data dashboard."""
    stats = get_training_stats()
    
    print("\n" + "=" * 80)
    print("📊 DASHBOARD DE TREINAMENTO - eddie-whatsapp")
    print("=" * 80)
    
    print(f"\n📈 Estatísticas Gerais:")
    print(f"   Total de amostras coletadas: {stats['total_samples']}")
    print(f"   Emails enviados: {stats['sent_emails']}")
    print(f"   Amostras com feedback: {stats['with_feedback']}")
    print(f"   Amostras com correção: {stats['with_correction']}")
    
    if stats['with_correction'] > 0:
        print(f"\n🎯 Métricas de Acurácia:")
        print(f"   Score médio predito: {stats['avg_predicted_score']}%")
        print(f"   Score médio real: {stats['avg_actual_score']}%")
        print(f"   Score Jaccard médio: {stats['avg_jaccard_score']}%")
        print(f"   Erro absoluto médio: {stats['mean_absolute_error']}%")
        
        improvement = stats['avg_predicted_score'] - stats['avg_jaccard_score']
        print(f"\n💡 Melhoria do LLM sobre Jaccard: {improvement:+.2f}%")
    
    print("\n" + "=" * 80)
    
    # Check if ready for fine-tuning
    if stats['with_correction'] >= 10:
        print("✅ Dados suficientes para fine-tuning (≥10 amostras corrigidas)")
        print("   Execute: python3 finetune_whatsapp_model.py")
    else:
        needed = 10 - stats['with_correction']
        print(f"⚠️  Colete mais {needed} amostras com correção para fine-tuning")
    
    print("=" * 80 + "\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init_training_db()
    elif len(sys.argv) > 1 and sys.argv[1] == "export":
        init_training_db()
        count = export_training_dataset()
        if count > 0:
            print(f"✅ Dataset exportado com {count} amostras")
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        init_training_db()
        show_training_dashboard()
    else:
        # Default: show dashboard
        init_training_db()
        show_training_dashboard()
