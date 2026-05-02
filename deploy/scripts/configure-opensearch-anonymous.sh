#!/usr/bin/env bash
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/opspilot/opspilot-enterprise/deploy/docker}"
OPENSEARCH_CONTAINER="${OPENSEARCH_CONTAINER:-docker-opensearch-1}"
OPENSEARCH_URL="${OPENSEARCH_URL:-https://127.0.0.1:9200}"
OPENSEARCH_USERNAME="${OPENSEARCH_USERNAME:-admin}"
OPENSEARCH_PASSWORD="${OPENSEARCH_PASSWORD:-OpsPilot-OpenSearch-2026!}"
ANON_USER="${OPENSEARCH_ANON_USER:-opendistro_security_anonymous}"
ANON_BACKEND_ROLE="${OPENSEARCH_ANON_BACKEND_ROLE:-opendistro_security_anonymous_backendrole}"
READONLY_ROLE="${OPENSEARCH_ANON_ROLE:-opspilot_logs_readonly}"
INDEX_PATTERN="${OPENSEARCH_INDEX_PATTERN:-opspilot-vmware-*}"

cd "$COMPOSE_DIR"

for _ in $(seq 1 60); do
  if curl -sk -u "${OPENSEARCH_USERNAME}:${OPENSEARCH_PASSWORD}" "${OPENSEARCH_URL}/_cluster/health" >/dev/null; then
    break
  fi
  sleep 2
done

docker exec "$OPENSEARCH_CONTAINER" bash -lc "
  set -euo pipefail
  cp config/opensearch-security/config.yml /tmp/opspilot-security-config.yml
  sed -i 's/anonymous_auth_enabled: false/anonymous_auth_enabled: true/' /tmp/opspilot-security-config.yml
  plugins/opensearch-security/tools/securityadmin.sh \
    -f /tmp/opspilot-security-config.yml \
    -t config \
    -icl \
    -nhnv \
    -cacert config/root-ca.pem \
    -cert config/kirk.pem \
    -key config/kirk-key.pem
"

curl -sk -u "${OPENSEARCH_USERNAME}:${OPENSEARCH_PASSWORD}" \
  -X PUT "${OPENSEARCH_URL}/_plugins/_security/api/roles/${READONLY_ROLE}" \
  -H "Content-Type: application/json" \
  -d "{
    \"cluster_permissions\": [
      \"cluster_composite_ops_ro\",
      \"cluster:admin/opensearch/security/tenantinfo\",
      \"cluster:admin/opendistro/security/tenantinfo\"
    ],
    \"index_permissions\": [
      {
        \"index_patterns\": [\"${INDEX_PATTERN}\"],
        \"allowed_actions\": [\"read\"]
      },
      {
        \"index_patterns\": [\".kibana*\", \".opensearch_dashboards*\"],
        \"allowed_actions\": [\"read\", \"crud\"]
      }
    ]
  }" >/dev/null

curl -sk -u "${OPENSEARCH_USERNAME}:${OPENSEARCH_PASSWORD}" \
  -X PUT "${OPENSEARCH_URL}/_plugins/_security/api/rolesmapping/${READONLY_ROLE}" \
  -H "Content-Type: application/json" \
  -d "{
    \"backend_roles\": [\"${ANON_BACKEND_ROLE}\"],
    \"users\": [\"${ANON_USER}\"],
    \"hosts\": []
  }" >/dev/null

curl -sk -u "${OPENSEARCH_USERNAME}:${OPENSEARCH_PASSWORD}" \
  -X PUT "${OPENSEARCH_URL}/_plugins/_security/api/rolesmapping/kibana_user" \
  -H "Content-Type: application/json" \
  -d "{
    \"backend_roles\": [\"kibanauser\", \"${ANON_BACKEND_ROLE}\"],
    \"users\": [\"${ANON_USER}\"],
    \"hosts\": []
  }" >/dev/null

echo "OpenSearch anonymous read-only access is enabled for ${INDEX_PATTERN}."
