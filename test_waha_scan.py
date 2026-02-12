#!/usr/bin/env python3
"""
Test script to verify WAHA scanning capabilities
Shows statistics of groups (including archived) and messages from last 30 days
"""
import sys
import os
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from apply_real_job import get_waha_api_key, WAHA_API, logger

def main():
    print("🔍 Testing WAHA scan capabilities\n")
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
        print(f"✅ Total chats retrieved: {len(chats)}")
    except Exception as e:
        print(f"❌ Failed to get chats: {e}")
        return
    
    # Filter groups
    group_chats = [c for c in chats if ('@g.us' in (c.get('id') or '') or c.get('isGroup') == True or c.get('type') == 'group')]
    archived_groups = [g for g in group_chats if g.get('isArchived') or g.get('archived')]
    active_groups = [g for g in group_chats if not (g.get('isArchived') or g.get('archived'))]
    
    print("=" * 70)
    print(f"\n📊 GROUP STATISTICS:")
    print(f"   Total groups: {len(group_chats)}")
    print(f"   Active groups: {len(active_groups)}")
    print(f"   Archived groups: {len(archived_groups)}")
    
    # Sample groups
    print(f"\n📋 SAMPLE GROUPS (first 10):")
    for i, chat in enumerate(group_chats[:10], 1):
        name = chat.get('name') or chat.get('id', 'Unknown')[:20]
        archived = '🗄️' if (chat.get('isArchived') or chat.get('archived')) else '✅'
        print(f"   {i}. {archived} {name}")
    
    # Test message retrieval from first 3 groups
    print(f"\n📨 MESSAGE SAMPLE (first 3 groups, last 30 days):")
    cutoff_date = datetime.now() - timedelta(days=30)
    cutoff_timestamp = int(cutoff_date.timestamp())
    
    total_messages = 0
    messages_last_30_days = 0
    
    for i, chat in enumerate(group_chats[:3], 1):
        cid = chat.get('id') or chat.get('chatId')
        name = chat.get('name') or 'Unknown'
        archived = '🗄️' if (chat.get('isArchived') or chat.get('archived')) else '✅'
        
        try:
            msgs_out = curl_json(f"{WAHA_API}/api/{session_name}/chats/{cid}/messages?limit=100")
            msgs = json.loads(msgs_out)
            total_messages += len(msgs)
            
            # Count messages in last 30 days
            recent_msgs = 0
            for m in msgs:
                msg_timestamp = m.get('timestamp') or m.get('t')
                if msg_timestamp:
                    try:
                        if isinstance(msg_timestamp, (int, float)):
                            ts = int(msg_timestamp)
                        else:
                            ts = int(datetime.fromisoformat(str(msg_timestamp).replace('Z', '+00:00')).timestamp())
                        
                        if ts >= cutoff_timestamp:
                            recent_msgs += 1
                    except:
                        pass
            
            messages_last_30_days += recent_msgs
            print(f"   {i}. {archived} {name[:40]}")
            print(f"      Total msgs: {len(msgs)} | Last 30 days: {recent_msgs}")
        except Exception as e:
            print(f"   {i}. {archived} {name[:40]} - Failed to retrieve: {e}")
    
    print(f"\n📊 MESSAGE STATISTICS (from {len(group_chats[:3])} sample groups):")
    print(f"   Total messages retrieved: {total_messages}")
    print(f"   Messages from last 30 days: {messages_last_30_days}")
    
    print("\n" + "=" * 70)
    print(f"\n✅ Test complete! System will scan:")
    print(f"   • Up to 1000 groups (including {len(archived_groups)} archived)")
    print(f"   • Up to 100 messages per group")
    print(f"   • Only messages from last 30 days")
    print(f"   • Estimated total: ~{len(group_chats) * 50} messages to check")


if __name__ == '__main__':
    main()
