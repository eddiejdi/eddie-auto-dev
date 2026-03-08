#!/usr/bin/env python3
"""
Analyze compatibility scores of WhatsApp messages to help determine optimal threshold
"""
import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from apply_real_job import (
    get_waha_api_key, 
    WAHA_API, 
    compute_compatibility, 
    CURRICULUM_TEXT,
    logger
)

def main():
    print("📊 Analyzing compatibility scores of WhatsApp messages\n")
    print("=" * 70)
    
    try:
        api_key = get_waha_api_key()
        print("✅ WAHA API key obtained")
    except Exception as e:
        print(f"❌ Failed to get WAHA API key: {e}")
        return
    
    def curl_json(url: str, timeout: int = 12):
        cmd = [
            "curl", "-s", "-m", str(timeout),
            "-H", f"X-Api-Key: {api_key}",
            "-H", "Accept: application/json",
            url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 3)
        if res.returncode != 0:
            raise RuntimeError(f"curl failed: {res.stderr}")
        return res.stdout
    
    # Get session
    try:
        sessions_out = curl_json(f"{WAHA_API}/api/sessions")
        sessions = json.loads(sessions_out)
        
        session_name = 'default'
        if isinstance(sessions, list) and sessions:
            session_name = sessions[0].get('name', session_name)
        elif isinstance(sessions, dict):
            data = sessions.get('data') or sessions
            if isinstance(data, list) and data:
                session_name = data[0].get('name', session_name)
        
        print(f"✅ Session: {session_name}")
    except Exception as e:
        print(f"❌ Failed to get sessions: {e}")
        return
    
    # Get all chats
    try:
        chats_out = curl_json(f"{WAHA_API}/api/{session_name}/chats")
        chats = json.loads(chats_out)
    except Exception as e:
        print(f"❌ Failed to get chats: {e}")
        return
    
    # Filter groups
    group_chats = [c for c in chats if ('@g.us' in (c.get('id') or '') or c.get('isGroup') == True or c.get('type') == 'group')]
    
    print(f"✅ Found {len(group_chats)} groups")
    print("=" * 70)
    
    # Analyze messages
    cutoff_date = datetime.now() - timedelta(days=30)
    cutoff_timestamp = int(cutoff_date.timestamp())
    
    product_indicators = ['r$', 'reais', 'desconto', 'compre', 'oferta', 'promoção', 'mercado', '🔥', '💰', '🛒', 'link:', 'comprar', 'frete', 'parcelado', 'à vista', 'http']
    
    scores = []
    
    print("\n🔍 Scanning messages and computing compatibility...\n")
    
    for chat in group_chats:
        cid = chat.get('id') or chat.get('chatId')
        if not cid:
            continue
        
        chat_name = chat.get('name') or cid[:20]
        
        try:
            msgs_out = curl_json(f"{WAHA_API}/api/{session_name}/chats/{cid}/messages?limit=100")
            msgs = json.loads(msgs_out)
        except Exception:
            continue
        
        for m in msgs:
            # Filter by timestamp
            msg_timestamp = m.get('timestamp') or m.get('t')
            if msg_timestamp:
                try:
                    if isinstance(msg_timestamp, (int, float)):
                        ts = int(msg_timestamp)
                    else:
                        ts = int(datetime.fromisoformat(str(msg_timestamp).replace('Z', '+00:00')).timestamp())
                    
                    if ts < cutoff_timestamp:
                        continue
                except:
                    pass
            
            text = (m.get('body') or '')
            if not text or len(text) < 30:
                continue
            
            lower = text.lower()
            
            # Exclude product ads
            if any(ind in lower for ind in product_indicators):
                continue
            
            # Compute compatibility
            compat = compute_compatibility(CURRICULUM_TEXT, text)
            
            scores.append({
                'score': compat,
                'group': chat_name,
                'preview': text[:100].replace('\n', ' ')
            })
    
    if not scores:
        print("❌ No messages found (after filtering)")
        return
    
    # Sort by score
    scores.sort(key=lambda x: x['score'], reverse=True)
    
    print("=" * 70)
    print(f"\n📈 COMPATIBILITY ANALYSIS ({len(scores)} messages)")
    print("=" * 70)
    
    # Statistics
    all_scores = [s['score'] for s in scores]
    avg_score = sum(all_scores) / len(all_scores)
    max_score = max(all_scores)
    min_score = min(all_scores)
    
    # Percentiles
    sorted_scores = sorted(all_scores, reverse=True)
    p90 = sorted_scores[int(len(sorted_scores) * 0.1)] if len(sorted_scores) > 10 else max_score
    p75 = sorted_scores[int(len(sorted_scores) * 0.25)] if len(sorted_scores) > 4 else max_score
    p50 = sorted_scores[int(len(sorted_scores) * 0.5)] if len(sorted_scores) > 2 else max_score
    
    print(f"\n📊 Statistics:")
    print(f"   Maximum: {max_score:.1f}%")
    print(f"   Top 10% (P90): {p90:.1f}%")
    print(f"   Top 25% (P75): {p75:.1f}%")
    print(f"   Median (P50): {p50:.1f}%")
    print(f"   Average: {avg_score:.1f}%")
    print(f"   Minimum: {min_score:.1f}%")
    
    print(f"\n🏆 TOP 10 MATCHES:\n")
    for i, score in enumerate(scores[:10], 1):
        print(f"{i}. {score['score']:5.1f}% | {score['group'][:30]}")
        print(f"   {score['preview']}")
        print()
    
    print("=" * 70)
    print("\n💡 RECOMMENDED THRESHOLDS:")
    print(f"   • Conservative (top 10%): {p90:.1f}%")
    print(f"   • Balanced (top 25%): {p75:.1f}%")
    print(f"   • Liberal (top 50%): {p50:.1f}%")
    print(f"   • Very liberal (average): {avg_score:.1f}%")
    
    # Count by thresholds
    count_75 = len([s for s in all_scores if s >= 75])
    count_50 = len([s for s in all_scores if s >= 50])
    count_25 = len([s for s in all_scores if s >= 25])
    count_10 = len([s for s in all_scores if s >= 10])
    count_5 = len([s for s in all_scores if s >= 5])
    
    print(f"\n📈 MATCH COUNTS BY THRESHOLD:")
    print(f"   ≥ 75%: {count_75} messages")
    print(f"   ≥ 50%: {count_50} messages")
    print(f"   ≥ 25%: {count_25} messages")
    print(f"   ≥ 10%: {count_10} messages")
    print(f"   ≥  5%: {count_5} messages")
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    main()
