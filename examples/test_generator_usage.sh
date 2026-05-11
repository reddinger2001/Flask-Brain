#!/bin/bash
# Example: Using the Flask Brain test generator endpoint

# This script demonstrates how to use the POST /api/generate/tests endpoint
# to generate pytest test scaffolding for a Flask application.

# Prerequisites:
# 1. Flask Brain server must be running: flask-brain serve --port 7891
# 2. Project must be scanned: flask-brain scan

BASE_URL="http://localhost:7891"

echo "=== Flask Brain Test Generator Examples ==="
echo ""

# Example 1: Generate tests for a blueprint
echo "1. Generate tests for a blueprint:"
echo "   curl -X POST $BASE_URL/api/generate/tests \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"target\": \"blueprint::auth\"}' | jq ."
echo ""

# Example 2: Generate tests for a specific route
echo "2. Generate tests for a specific route:"
echo "   curl -X POST $BASE_URL/api/generate/tests \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"target\": \"route::POST /auth/login\"}' | jq ."
echo ""

# Example 3: Generate tests for a service
echo "3. Generate tests for a service:"
echo "   curl -X POST $BASE_URL/api/generate/tests \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"target\": \"service::AuthService.authenticate\"}' | jq ."
echo ""

# Example 4: Write generated tests directly to a file
echo "4. Write generated tests to a file:"
echo "   curl -X POST $BASE_URL/api/generate/tests \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"target\": \"blueprint::auth\", \"output_path\": \"tests/test_auth.py\"}' \\"
echo "     | jq -r '.combined' > tests/test_auth.py"
echo ""

# Example 5: Get only the routes tier
echo "5. Get only the routes tier:"
echo "   curl -X POST $BASE_URL/api/generate/tests \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"target\": \"blueprint::auth\"}' | jq -r '.tiers.routes'"
echo ""

# Example 6: Get only the services tier
echo "6. Get only the services tier:"
echo "   curl -X POST $BASE_URL/api/generate/tests \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"target\": \"blueprint::auth\"}' | jq -r '.tiers.services'"
echo ""

# Example 7: Get stats and warnings
echo "7. Get stats and warnings:"
echo "   curl -X POST $BASE_URL/api/generate/tests \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"target\": \"blueprint::auth\"}' | jq '{stats, warnings}'"
echo ""

# Example 8: Error handling - missing target
echo "8. Error handling - missing target:"
echo "   curl -X POST $BASE_URL/api/generate/tests \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{}' | jq ."
echo "   # Expected: {\"error\": \"Missing 'target' parameter\"}"
echo ""

# Example 9: Error handling - unknown node
echo "9. Error handling - unknown node:"
echo "   curl -X POST $BASE_URL/api/generate/tests \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"target\": \"route::nonexistent\"}' | jq ."
echo "   # Expected: {\"error\": \"Node 'route::nonexistent' not found\"}"
echo ""

echo "=== Response Structure ==="
echo ""
echo "{"
echo "  \"target_id\": \"blueprint::auth\","
echo "  \"target_label\": \"auth\","
echo "  \"target_type\": \"blueprint\","
echo "  \"output_path\": \"tests/test_auth.py\","
echo "  \"tiers\": {"
echo "    \"routes\": \"...generated pytest code...\","
echo "    \"services\": \"...generated pytest code...\""
echo "  },"
echo "  \"combined\": \"...full combined test file...\","
echo "  \"stats\": {"
echo "    \"route_count\": 5,"
echo "    \"service_count\": 2,"
echo "    \"model_count\": 3,"
echo "    \"test_count\": 14"
echo "  },"
echo "  \"warnings\": ["
echo "    \"Service UserService has no callers (dead-weight) — pragma: no cover candidate\""
echo "  ]"
echo "}"
echo ""

echo "=== Tips ==="
echo ""
echo "- Use 'jq -r .combined' to extract just the test code"
echo "- Use 'jq .stats' to see test counts"
echo "- Use 'jq .warnings' to see actionable insights"
echo "- The 'combined' field is ready to write to disk"
echo "- Route tests are fully functional"
echo "- Service tests are scaffolded with TODOs"
echo ""
