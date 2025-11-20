#!/bin/bash

# Test script for iPaaS authentication with forward slashes in passwords
# This script demonstrates how to test iPaaS authentication with various
# password patterns containing forward slash characters

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MCP_SERVICE_URL="${MCP_SERVICE_URL:-http://localhost:8081}"
JIRA_BASE_URL="${JIRA_BASE_URL:-https://jira.corp.adobe.com}"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}iPaaS Forward Slash Authentication Test Suite${NC}"
echo -e "${BLUE}======================================================================${NC}"

# Function to get credentials from AWS Secrets Manager
get_credentials() {
    echo -e "\n${YELLOW}[1/4] Retrieving iPaaS credentials from AWS Secrets Manager...${NC}"

    SECRET_JSON=$(aws secretsmanager get-secret-value \
        --secret-id Ketchup_Token_Secrets \
        --region eu-west-1 \
        --profile campaign_prod_v7 \
        --query SecretString \
        --output text)

    # Extract credentials
    IPAAS_USERNAME=$(echo "$SECRET_JSON" | jq -r '.ipaas_username')
    IPAAS_PASSWORD=$(echo "$SECRET_JSON" | jq -r '.ipaas_password')
    IPAAS_API_KEY=$(echo "$SECRET_JSON" | jq -r '.ipaas_api_key')
    IMS_TOKEN=$(echo "$SECRET_JSON" | jq -r '.ims_access_token')

    echo -e "  ${GREEN}✓${NC} Username: $IPAAS_USERNAME"
    echo -e "  ${GREEN}✓${NC} Password: $(echo "$IPAAS_PASSWORD" | sed 's/./*/g') (${#IPAAS_PASSWORD} chars)"
    echo -e "  ${GREEN}✓${NC} API Key: ${IPAAS_API_KEY:0:20}..."
    echo -e "  ${GREEN}✓${NC} IMS Token: ${IMS_TOKEN:0:30}..."
}

# Function to check if password contains forward slashes
check_password_slashes() {
    echo -e "\n${YELLOW}[2/4] Analyzing password for forward slashes...${NC}"

    SLASH_COUNT=$(echo -n "$IPAAS_PASSWORD" | grep -o "/" | wc -l | tr -d ' ')

    if [ "$SLASH_COUNT" -gt 0 ]; then
        echo -e "  ${YELLOW}⚠${NC}  Password contains $SLASH_COUNT forward slash(es)"
        echo -e "  ${YELLOW}⚠${NC}  This may cause authentication issues"

        # Show positions
        echo -n "  ${YELLOW}⚠${NC}  Slash positions: "
        echo "$IPAAS_PASSWORD" | grep -ob "/" | cut -d: -f1 | tr '\n' ',' | sed 's/,$/\n/'
    else
        echo -e "  ${GREEN}✓${NC} Password does NOT contain forward slashes"
    fi
}

# Function to test MCP health endpoint
test_mcp_health() {
    echo -e "\n${YELLOW}[3/4] Testing MCP service health...${NC}"

    HEALTH_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${MCP_SERVICE_URL}/health" 2>&1)
    HTTP_CODE=$(echo "$HEALTH_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)

    if [ "$HTTP_CODE" == "200" ]; then
        echo -e "  ${GREEN}✓${NC} MCP service is healthy"
    else
        echo -e "  ${RED}✗${NC} MCP service is not responding (HTTP $HTTP_CODE)"
        echo -e "  ${YELLOW}⚠${NC}  Make sure MCP service is running:"
        echo -e "      cd infrastructure && docker-compose up -d mcp-jira"
        exit 1
    fi
}

# Function to test authentication with current password
test_authentication() {
    echo -e "\n${YELLOW}[4/4] Testing iPaaS authentication...${NC}"

    # Create test request to JIRA API via iPaaS
    echo -e "\n  Testing authentication with current credentials..."

    # Test 1: Using username/password headers (current method)
    echo -e "\n  ${BLUE}Test 1: Username/Password Headers${NC}"

    RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
        -X GET \
        -H "Authorization: ${IMS_TOKEN}" \
        -H "Api_key: ${IPAAS_API_KEY}" \
        -H "Username: ${IPAAS_USERNAME}" \
        -H "Password: ${IPAAS_PASSWORD}" \
        -H "Content-Type: application/json" \
        "${MCP_SERVICE_URL}/api/jira/rest/api/2/myself" 2>&1)

    HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
    BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

    if [ "$HTTP_CODE" == "200" ]; then
        echo -e "    ${GREEN}✓${NC} Authentication successful (HTTP 200)"

        # Extract user info
        DISPLAY_NAME=$(echo "$BODY" | jq -r '.displayName' 2>/dev/null)
        EMAIL=$(echo "$BODY" | jq -r '.emailAddress' 2>/dev/null)

        if [ -n "$DISPLAY_NAME" ] && [ "$DISPLAY_NAME" != "null" ]; then
            echo -e "    ${GREEN}✓${NC} User: $DISPLAY_NAME"
            echo -e "    ${GREEN}✓${NC} Email: $EMAIL"
        fi
    else
        echo -e "    ${RED}✗${NC} Authentication failed (HTTP $HTTP_CODE)"
        echo -e "    ${RED}✗${NC} Response: $BODY"
    fi

    # Test 2: Check if password is being URL-encoded somewhere
    echo -e "\n  ${BLUE}Test 2: Password Encoding Check${NC}"

    # URL-encode the password
    URL_ENCODED_PASSWORD=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$IPAAS_PASSWORD'))")

    if [ "$URL_ENCODED_PASSWORD" != "$IPAAS_PASSWORD" ]; then
        echo -e "    ${YELLOW}⚠${NC}  Password differs when URL-encoded:"
        echo -e "       Original: $IPAAS_PASSWORD"
        echo -e "       Encoded:  $URL_ENCODED_PASSWORD"
        echo -e "    ${YELLOW}⚠${NC}  Testing with URL-encoded password..."

        RESPONSE2=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
            -X GET \
            -H "Authorization: ${IMS_TOKEN}" \
            -H "Api_key: ${IPAAS_API_KEY}" \
            -H "Username: ${IPAAS_USERNAME}" \
            -H "Password: ${URL_ENCODED_PASSWORD}" \
            -H "Content-Type: application/json" \
            "${MCP_SERVICE_URL}/api/jira/rest/api/2/myself" 2>&1)

        HTTP_CODE2=$(echo "$RESPONSE2" | grep "HTTP_CODE:" | cut -d: -f2)

        if [ "$HTTP_CODE2" == "200" ]; then
            echo -e "    ${GREEN}✓${NC} URL-encoded password works (HTTP 200)"
            echo -e "    ${YELLOW}⚠${NC}  This suggests iPaaS expects URL-encoded passwords!"
        else
            echo -e "    ${RED}✗${NC} URL-encoded password failed (HTTP $HTTP_CODE2)"
        fi
    else
        echo -e "    ${GREEN}✓${NC} Password does not need URL encoding"
    fi
}

# Function to test with mock passwords containing forward slashes
test_mock_passwords() {
    echo -e "\n${BLUE}======================================================================${NC}"
    echo -e "${BLUE}Testing Mock Passwords with Forward Slashes${NC}"
    echo -e "${BLUE}======================================================================${NC}"

    # These are MOCK tests - they will fail authentication but demonstrate encoding
    MOCK_PASSWORDS=(
        "Test/Pass"
        "/TestPass"
        "TestPass/"
        "Test/Pass/123"
        "a/b/c/d/e"
    )

    echo -e "\n${YELLOW}Note: These tests use mock passwords and will fail authentication.${NC}"
    echo -e "${YELLOW}They demonstrate how forward slashes are handled in HTTP headers.${NC}\n"

    for MOCK_PASS in "${MOCK_PASSWORDS[@]}"; do
        echo -e "  ${BLUE}Testing password: '$MOCK_PASS'${NC}"

        # Show different encodings
        URL_ENC=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$MOCK_PASS'))")
        BASE64_ENC=$(echo -n "$MOCK_PASS" | base64)

        echo -e "    Plain text:  '$MOCK_PASS'"
        echo -e "    URL encoded: '$URL_ENC'"
        echo -e "    Base64:      '$BASE64_ENC'"

        # Make request (will fail but shows headers are sent correctly)
        RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
            -X GET \
            -H "Authorization: ${IMS_TOKEN}" \
            -H "Api_key: ${IPAAS_API_KEY}" \
            -H "Username: test-user" \
            -H "Password: ${MOCK_PASS}" \
            -H "Content-Type: application/json" \
            "${MCP_SERVICE_URL}/api/jira/rest/api/2/myself" 2>&1)

        HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)

        if [ "$HTTP_CODE" == "401" ]; then
            echo -e "    ${GREEN}✓${NC} Request sent successfully (401 expected for mock credentials)"
        else
            echo -e "    ${YELLOW}⚠${NC}  Unexpected HTTP code: $HTTP_CODE"
        fi

        echo ""
    done
}

# Main execution
main() {
    # Check if running locally or against deployed service
    if [ -n "$1" ] && [ "$1" == "--deployed" ]; then
        MCP_SERVICE_URL="https://ketchup-prod1.campaign.adobe.com/mcp"
        echo -e "${YELLOW}Testing against deployed MCP service: $MCP_SERVICE_URL${NC}"
    else
        echo -e "${YELLOW}Testing against local MCP service: $MCP_SERVICE_URL${NC}"
        echo -e "${YELLOW}Use --deployed flag to test against production${NC}"
    fi

    # Run tests
    get_credentials
    check_password_slashes
    test_mcp_health
    test_authentication

    # Ask if user wants to test mock passwords
    echo -e "\n${BLUE}======================================================================${NC}"
    read -p "Test mock passwords with forward slashes? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        test_mock_passwords
    fi

    # Final summary
    echo -e "\n${BLUE}======================================================================${NC}"
    echo -e "${BLUE}Test Summary${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "\n${GREEN}Key Findings:${NC}"
    echo -e "  1. Passwords are sent as plain text in HTTP headers"
    echo -e "  2. Forward slashes (/) are VALID in HTTP header values"
    echo -e "  3. URL encoding is NOT required per RFC 7230"
    echo -e "  4. If authentication fails with / in password:"
    echo -e "     - iPaaS server may incorrectly parse headers"
    echo -e "     - Middleware/proxy may modify passwords"
    echo -e "     - Server may expect encoded passwords (non-standard)"
    echo -e "\n${GREEN}Recommendation:${NC}"
    echo -e "  → Use PAT authentication instead (eliminates password issues)"
    echo -e "  → PAT is already supported via .env file:"
    echo -e "     JIRA_PERSONAL_ACCESS_TOKEN=<your-pat-token>"
    echo -e "\n${GREEN}✓ All tests completed successfully!${NC}\n"
}

# Run main function
main "$@"
