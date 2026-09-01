#!/bin/bash
SSHPASS='Rpa_four_all!' sshpass -e ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@192.168.15.4 /usr/local/bin/tape-monitor.sh 2>/dev/null || echo "SSH-FAIL"
