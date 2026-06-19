#!/bin/bash
# Quick test script for MAX API connectivity
# Usage: bash scripts/test_max_api.sh <token>

set -euo pipefail

TOKEN="${1:?Usage: $0 <max-bot-token>}"
BASE_URL="https://platform-api.max.ru"

echo "Testing MAX API connectivity..."
echo "  URL: $BASE_URL"
echo ""

# Test 1: Get bot info
echo "[1] GET /me — Bot info:"
curl -s "$BASE_URL/me" \
  -H "Authorization: $TOKEN" | python3 -m json.tool 2>/dev/null || echo "  ❌ Failed"
echo ""

# Test 2: Get subscriptions
echo "[2] GET /subscriptions — Webhook subscriptions:"
curl -s "$BASE_URL/subscriptions" \
  -H "Authorization: $TOKEN" | python3 -m json.tool 2>/dev/null || echo "  ❌ Failed"
echo ""

# Test 3: Get updates (long polling, 5s timeout)
echo "[3] GET /updates — Long Polling (5s timeout):"
curl -s "$BASE_URL/updates?limit=10&timeout=5" \
  -H "Authorization: $TOKEN" | python3 -m json.tool 2>/dev/null || echo "  ❌ Failed"
echo ""

echo "Done."
