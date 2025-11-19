/**
 * Test 1: Direct JIRA API with PAT (Bearer Token)
 * Tests if PAT works when calling JIRA directly (no proxy)
 */

import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';
import { request } from 'undici';

const JIRA_DIRECT_ENDPOINT = 'https://jira.corp.adobe.com/rest/api/2/myself';
const AWS_REGION = 'eu-west-1';
const AWS_PROFILE = 'campaign_prod_v7';
const SECRET_NAME = 'Ketchup_Token_Secrets';

async function fetchSecretFromAWS() {
  const client = new SecretsManagerClient({
    region: AWS_REGION,
  });

  try {
    const command = new GetSecretValueCommand({
      SecretId: SECRET_NAME,
    });
    const response = await client.send(command);

    if (response.SecretString) {
      return JSON.parse(response.SecretString);
    }
    throw new Error('Secret string not found');
  } catch (error) {
    throw new Error(`Failed to fetch secret: ${error.message}`);
  }
}

async function testDirectJiraAPI() {
  console.log('\n========================================');
  console.log('TEST 1: Direct JIRA API with PAT');
  console.log('========================================');
  console.log(`Endpoint: ${JIRA_DIRECT_ENDPOINT}`);
  console.log(`Timestamp: ${new Date().toISOString()}`);

  try {
    // Fetch PAT from AWS Secrets
    console.log('\n[STEP 1] Fetching PAT from AWS Secrets Manager...');
    const secrets = await fetchSecretFromAWS();
    const pat = secrets.ketchup_jira_pat;

    if (!pat) {
      throw new Error('PAT token not found in secrets');
    }
    console.log('✓ PAT fetched successfully');

    // Make HTTP request to JIRA
    console.log('\n[STEP 2] Making HTTP GET request to JIRA...');
    const response = await request(JIRA_DIRECT_ENDPOINT, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${pat}`,
        'Accept': 'application/json',
      },
      signal: AbortSignal.timeout(10000), // 10 second timeout
    });

    const statusCode = response.statusCode;
    const body = await response.body.text();
    const bodyObj = JSON.parse(body);

    console.log(`✓ Received HTTP ${statusCode}`);

    // Check success criteria
    console.log('\n[STEP 3] Validating response...');
    const isSuccess = statusCode === 200;
    const hasUserInfo = bodyObj.displayName && bodyObj.emailAddress;

    if (isSuccess && hasUserInfo) {
      console.log('✓ Response status is 200 OK');
      console.log(`✓ User info found: displayName="${bodyObj.displayName}"`);
    }

    // Report results
    console.log('\n========================================');
    console.log('TEST 1: Direct JIRA with PAT');
    console.log('========================================');
    console.log(`Status: ${isSuccess && hasUserInfo ? 'PASS ✅' : 'FAIL ❌'}`);
    console.log(`HTTP Code: ${statusCode}`);
    console.log(`Response: ${JSON.stringify(bodyObj).substring(0, 200)}...`);
    if (!isSuccess || !hasUserInfo) {
      console.log(`Error: ${isSuccess ? 'Invalid response structure' : body}`);
    }
    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_pat_direct_jira_api',
      result: isSuccess && hasUserInfo ? 'PASS' : 'FAIL',
      statusCode,
      responsePreview: JSON.stringify(bodyObj).substring(0, 200),
      error: !isSuccess || !hasUserInfo ? body : null,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.log('\n========================================');
    console.log('TEST 1: Direct JIRA with PAT');
    console.log('========================================');
    console.log(`Status: FAIL ❌`);
    console.log(`Error: ${error.message}`);
    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_pat_direct_jira_api',
      result: 'FAIL',
      statusCode: null,
      responsePreview: null,
      error: error.message,
      timestamp: new Date().toISOString(),
    };
  }
}

// Run the test
const result = await testDirectJiraAPI();
process.exit(result.result === 'PASS' ? 0 : 1);
