#!/bin/bash
# Ensure Grafana is connected to homelab_monitoring network
# Required for PostgreSQL datasource (eddie-postgres hostname resolution)
docker network connect homelab_monitoring grafana 2>/dev/null
echo "$(date): Grafana connected to homelab_monitoring network"
