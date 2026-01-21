#!/usr/bin/env python3
"""Publish a uniquely identifiable TestAgent message via the communication bus."""
import time
import os
import sys
from specialized_agents.agent_communication_bus import get_communication_bus, MessageType

def publish_unique():
    bus = get_communication_bus()
    ts = time.strftime('%Y%m%d%H%M%S')
    conv_id = f"tester_ui_check_{ts}"
    content = f"TEST_BOX_RENDER_{ts}"
    # publish initial message with metadata
    bus.publish(
        message_type=MessageType.REQUEST,
        source="TestAgent",
        target="Dashboard",
        content=content,
        metadata={"conversation_id": conv_id}
    )
    # add a follow-up message
    bus.publish(
        message_type=MessageType.LLM_CALL,
        source="TestAgent",
        target="Dashboard",
        content=f"Follow-up {content}",
        metadata={"conversation_id": conv_id}
    )
    print('Published test conversation:', conv_id, content)
    return conv_id, content

if __name__ == '__main__':
    conv_id, content = publish_unique()
    # optional: print DB path for debugging
    db_path = os.environ.get('INTERCEPTOR_DB', 'agent_data/interceptor_data/conversations.db')
    print('DB (expected):', db_path)
    sys.exit(0)
