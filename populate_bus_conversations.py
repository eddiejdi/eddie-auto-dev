#!/usr/bin/env python3
"""
Populate bus_conversations table with sample data for Grafana dashboards
"""
import subprocess
import json
from datetime import datetime, timedelta
import random

def ssh_exec(cmd):
    """Execute command via SSH to homelab"""
    ssh_cmd = [
        'ssh', '-o', 'StrictHostKeyChecking=no',
        'homelab@192.168.15.2',
        cmd
    ]
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1

def populate_conversations():
    """Insert sample conversation data"""
    
    # Sample data: 8 conversations with various types and timestamps
    base_time = datetime.now()
    conversations = []
    
    for i in range(8):
        timestamp = (base_time - timedelta(hours=i)).isoformat()
        conv_id = f"conv_{i+1:03d}"
        
        conv_data = {
            'id': conv_id,
            'timestamp': timestamp,
            'message_type': random.choice(['request', 'response', 'error', 'info']),
            'source': random.choice(['telegram', 'whatsapp', 'api', 'webhook']),
            'target': random.choice(['assistant', 'director', 'coder', 'reviewer']),
            'content': f'Sample conversation {i+1} content',
        }
        conversations.append(conv_data)
    
    # Build INSERT statement with actual columns from table
    insert_sql = "INSERT INTO bus_conversations (id, timestamp, message_type, source, target, content) VALUES "
    values = []
    
    for conv in conversations:
        # Escape single quotes in content
        content = conv['content'].replace("'", "''")
        val = f"('{conv['id']}', '{conv['timestamp']}', '{conv['message_type']}', '{conv['source']}', '{conv['target']}', '{content}')"
        values.append(val)
    
    insert_sql += ",".join(values) + ";"
    
    # Execute via SSH
    psql_cmd = f"""docker exec eddie-postgres psql -U eddie -d eddie_bus -c "{insert_sql}" """
    stdout, stderr, code = ssh_exec(psql_cmd)
    
    if code == 0:
        print(f"✅ Inserted {len(conversations)} conversations successfully")
        print(f"Output: {stdout}")
        return True
    else:
        print(f"❌ Failed to insert conversations")
        print(f"Error: {stderr}")
        return False

def verify_data():
    """Verify data was inserted"""
    cmd = """docker exec eddie-postgres psql -U eddie -d eddie_bus -c 'SELECT COUNT(*) as total_conversations FROM bus_conversations;' """
    stdout, stderr, code = ssh_exec(cmd)
    
    if code == 0:
        print(f"✅ Data verification:")
        print(stdout)
    else:
        print(f"❌ Verification failed: {stderr}")

if __name__ == "__main__":
    print("Populating bus_conversations table...")
    if populate_conversations():
        print("\nVerifying data...")
        verify_data()
    else:
        print("Failed to populate table")
