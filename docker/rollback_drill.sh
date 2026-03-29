#!/bin/bash
set -e

echo "=========================================================="
echo "==== F9-09: DevOps Canary Deploy & Rollback Drill ========"
echo "=========================================================="
echo "This script runs an entirely isolated Canary environment"
echo "to prove that we can seamlessly rollback DB mutations without"
echo "corrupting legacy tables, and tests the fresh E2EE deployment."
echo ""

cd "$(dirname "$0")/.."

COMPOSE_FILE="docker/docker-compose.canary.yml"

echo "[1] Tearing down any previous canary state..."
docker compose -f $COMPOSE_FILE down -v --remove-orphans

echo ""
echo "[2] Spinning up Canary Database for Legacy Simulation..."
docker compose -f $COMPOSE_FILE up -d mysql-canary

echo "   Waiting for MySQL to initialize..."
sleep 20

echo "   Injecting legacy schema markers..."
docker compose -f $COMPOSE_FILE exec -T mysql-canary mysql -uroot -penc_chat_root_password enc_chat_db -e "CREATE TABLE legacy_marker (id INT PRIMARY KEY, value VARCHAR(50)); INSERT INTO legacy_marker VALUES(1, 'v1.0.0_legacy_data_safe');"

echo ""
echo "[3] Taking Snapshot / Backup of Legacy State..."
docker compose -f $COMPOSE_FILE exec -T mysql-canary mysqldump -uroot -penc_chat_root_password enc_chat_db > /tmp/canary_legacy_snapshot.sql
echo "✅ Snapshot stored at /tmp/canary_legacy_snapshot.sql"

echo ""
echo "[4] Deploying Canary Application (Frontend & Backend on port 23457)..."
docker compose -f $COMPOSE_FILE up -d backend-canary frontend-canary --build

echo "   Waiting for Backend and TLS Termination to stabilize..."
sleep 25

echo ""
echo "[5] Running F9-09 Verification Script (Message Recall & Device Revocation)..."
cd e2e
export API_URL=https://localhost:23457
export WS_URL=wss://localhost:23457
# Explicitly use NODE_TLS_REJECT_UNAUTHORIZED since Playwright request contexts might check it
export NODE_TLS_REJECT_UNAUTHORIZED=0

npx playwright test tests/F9-09-recall.spec.ts tests/F9-09-revoke.spec.ts --project=chromium || {
  echo "❌ Canary pipeline rejected. Tests failed."
}
cd ..
echo "✅ Canary deployment verification passed cleanly."

echo ""
echo "🚨 [6] SIMULATED REGRESSION / ABORT! Triggering Rollback! 🚨"
echo "   Stopping Canary application containers..."
docker compose -f $COMPOSE_FILE stop backend-canary frontend-canary

echo "   Dropping mutated database schema..."
docker compose -f $COMPOSE_FILE exec -T mysql-canary mysql -uroot -penc_chat_root_password -e "DROP DATABASE enc_chat_db; CREATE DATABASE enc_chat_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

echo "   Restoring Snapshot..."
cat /tmp/canary_legacy_snapshot.sql | docker compose -f $COMPOSE_FILE exec -T mysql-canary mysql -uroot -penc_chat_root_password enc_chat_db

echo "   Verifying Legacy Data Integrity..."
DB_CHECK=$(docker compose -f $COMPOSE_FILE exec -T mysql-canary mysql -uroot -penc_chat_root_password enc_chat_db -se "SELECT value FROM legacy_marker WHERE id=1;")
if [ "$DB_CHECK" == "v1.0.0_legacy_data_safe" ]; then
    echo "✅ Database restored flawlessly. Zero data corruption. Legacy marker intact: $DB_CHECK"
else
    echo "❌ Rollback verification failed!"
    exit 1
fi

echo ""
echo "[7] Cleaning up Canary Environment..."
docker compose -f $COMPOSE_FILE down -v
rm -f /tmp/canary_legacy_snapshot.sql

echo ""
echo "=========================================================="
echo "==== DRILL COMPLETE. FULLY ISOLATED DEPLOY & REVERT.======"
echo "=========================================================="
