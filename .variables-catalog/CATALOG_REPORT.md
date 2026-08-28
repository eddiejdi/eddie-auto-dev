# Homelab Variables Catalog Report
**Generated:** 2026-06-21T02:00:44.207745
**Total Variables:** 1838
**Source Files:** 140
---
## 📊 Summary by Category
### Authentication (111 variables)
- `ADMIN_TOKEN` (string) ✓
- `ALL_CHILDREN_HOMELAB_HOSTS_HOMELAB_ANSIBLE_SSH_PRIVATE_KEY_FILE` (string) ✓
- `AUTHENTIK_NEXTCLOUD_CLIENT_ID` (string) ✓
- `AUTHENTIK_NEXTCLOUD_CLIENT_SECRET` (string) ✓
- `AUTHENTIK_SUBDOMAIN` (string) ✓
- `AUTHENTIK_TOKEN` (string) ✓
- `AUTHENTIK_VERIFY_TLS` (boolean) ✓
- `AUTH_RATELIMIT` (string) ✓
- `COMPONENTS_SCHEMAS_USERRESPONSE_PROPERTIES_TOKEN_TYPE` (string) ✓
- `CONTACTPOINTS_0_RECEIVERS_0_SETTINGS_BOTTOKEN` (string) ✓
  ... and 101 more

### Database (51 variables)
- `CMDB_PROXY_BIND` (string) ✓
- `CMDB_PROXY_HTTP_PORT` (integer) ✓
- `CMDB_TIMEZONE` (string) ✓
- `DATABASE_URL` (string) ✓
- `DATASOURCES_1_DATABASE` (string) ✓
- `DATASOURCES_1_JSONDATA_POSTGRESVERSION` (integer) ✓
- `DATASOURCES_2_DATABASE` (string) ✓
- `DATASOURCES_2_JSONDATA_POSTGRESVERSION` (integer) ✓
- `DB_HOST` (string) ✓
- `DB_NAME` (string) ✓
  ... and 41 more

### Infrastructure (5 variables)
- `AGENT_NETWORK_EXPORTER_PORT` (integer) ✓
- `DOCKER_HOST` (string) ✓
- `LTFS_ALLOW_UNMOUNTED_OUTSIDE_WINDOW` (boolean) ✓
- `LTFS_MOUNT_POINT` (path) ✓
- `REQUIRE_MOUNTPOINT` (path) ✓

### Integrations (13 variables)
- `GITHUB_AGENT_URL` (string) ✓
- `GLOBAL_TELEGRAM_API_URL` (url) ✓
- `GOOGLE_SDM_PROJECT` (string) ✓
- `GOOGLE_SDM_PROJECT_ID` (string) ✓
- `GOOGLE_SDM_PROJECT_NUMBER` (string) ✓
- `RECEIVERS_1_WEBHOOK_CONFIGS_0_HEADERS_X-ALERT-TYPE` (string) ✓
- `RECEIVERS_1_WEBHOOK_CONFIGS_0_SEND_RESOLVED` (boolean) ✓
- `RECEIVERS_1_WEBHOOK_CONFIGS_0_URL` (url) ✓
- `RECEIVERS_2_WEBHOOK_CONFIGS_0_HEADERS_X-ALERT-TYPE` (string) ✓
- `RECEIVERS_2_WEBHOOK_CONFIGS_0_SEND_RESOLVED` (boolean) ✓
  ... and 3 more

### Monitoring (17 variables)
- `CONTACTPOINTS_1_RECEIVERS_0_SETTINGS_MAXALERTS` (boolean) ✓
- `GRAFANA_CONTAINER` (string) ✓
- `GRAFANA_URL` (url) ✓
- `GROUPS_0_RULES_0_ALERT` (string) ✓
- `GROUPS_0_RULES_1_ALERT` (string) ✓
- `GROUPS_0_RULES_2_ALERT` (string) ✓
- `GROUPS_0_RULES_3_ALERT` (string) ✓
- `GROUPS_0_RULES_4_ALERT` (string) ✓
- `GROUPS_0_RULES_5_ALERT` (string) ✓
- `GROUPS_0_RULES_6_ALERT` (string) ✓
  ... and 7 more

### Services (1609 variables)
- `ADMIN` (string) ✓
- `ADMIN_CHAT_ID` (integer) ✓
- `ADMIN_EMAIL` (string) ✓
- `ADMIN_NUMBERS` (string) ✓
- `ADMIN_PHONE` (integer) ✓
- `ALLOWED_HOSTS` (string) ✓
- `ALL_CHILDREN_HOMELAB_HOSTS_HOMELAB_ANSIBLE_HOST` (string) ✓
- `ALL_CHILDREN_HOMELAB_HOSTS_HOMELAB_ANSIBLE_SSH_COMMON_ARGS` (string) ✓
- `ALL_CHILDREN_HOMELAB_HOSTS_HOMELAB_ANSIBLE_USER` (string) ✓
- `ALL_CHILDREN_HOMELAB_HOSTS_HOMELAB_OLLAMA_CHECK_INTERVAL` (integer) ✓
  ... and 1599 more

### Trading (32 variables)
- `ALL_CHILDREN_HOMELAB_VARS_ANSIBLE_BECOME_METHOD` (string) ✓
- `ALL_CHILDREN_HOMELAB_VARS_PROMETHEUS_METRICS_DIR` (path) ✓
- `ALL_CHILDREN_HOMELAB_VARS_PROMETHEUS_TEXTFILE_COLLECTOR` (path) ✓
- `BTC_ENGINE_API_PORT` (integer) ✓
- `COIN_CONFIG_FILE` (string) ✓
- `COMPATIBILITY_METHOD` (string) ✓
- `CONTACTPOINTS_1_RECEIVERS_0_SETTINGS_HTTPMETHOD` (string) ✓
- `DATASOURCES_0_JSONDATA_HTTPMETHOD` (string) ✓
- `GROUPS_2_RULES_0_LABELS_COIN` (string) ✓
- `GROUPS_2_RULES_1_LABELS_COIN` (string) ✓
  ... and 22 more

## 🔐 Sensitive Variables Summary
Total sensitive variables: **0**


---
## 📚 Full Variable Count

| Authentication | 111 |
| Database | 51 |
| Infrastructure | 5 |
| Integrations | 13 |
| Monitoring | 17 |
| Services | 1609 |
| Trading | 32 |
