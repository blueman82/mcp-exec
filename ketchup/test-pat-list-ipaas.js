/**
 * Test 4: List PATs via iPaaS Proxy
 * Lists all personal access tokens for the authenticated user
 */

import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';
import { request } from 'undici';

const IPAAS_PROXY_BASE = 'https://ipaasapi.adobe-services.com/jira';
const PAT_LIST_ENDPOINT = `${IPAAS_PROXY_BASE}/rest/pat/latest/tokens`;
const AWS_REGION = 'eu-west-1';
const SECRET_NAME = 'Ketchup_Token_Secrets';

async function fetchSecretsFromAWS() {
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
    throw new Error(`Failed to fetch secrets: ${error.message}`);
  }
}

async function listPATsViaIPaaS() {
  console.log('\n========================================');
  console.log('TEST 4: List PATs via iPaaS Proxy');
  console.log('========================================');
  console.log(`Endpoint: GET ${PAT_LIST_ENDPOINT}`);
  console.log(`Timestamp: ${new Date().toISOString()}`);

  try {
    // Fetch credentials from AWS Secrets
    console.log('\n[STEP 1] Fetching credentials from AWS Secrets Manager...');
    const secrets = await fetchSecretsFromAWS();
    const imsAccessToken = secrets.ims_access_token;
    const ipaasApiKey = secrets.ipaas_api_key;
    const ipaasUsername = secrets.ipaas_username;
    const ipaasPassword = secrets.ipaas_password;

    if (!imsAccessToken || !ipaasApiKey || !ipaasUsername || !ipaasPassword) {
      throw new Error('Missing required secrets for authentication');
    }
    console.log('✓ All credentials fetched successfully');

    // List PATs
    console.log('\n[STEP 2] Listing PATs via iPaaS proxy...');

    const response = await request(PAT_LIST_ENDPOINT, {
      method: 'GET',
      headers: {
        'Authorization': imsAccessToken,
        'Username': ipaasUsername,
        'Password': ipaasPassword,
        'Api_key': ipaasApiKey,
        'Accept': 'application/json',
      },
      signal: AbortSignal.timeout(10000),
    });

    const statusCode = response.statusCode;
    const body = await response.body.text();
    let bodyObj;

    try {
      bodyObj = JSON.parse(body);
    } catch (e) {
      bodyObj = { error: 'Could not parse response' };
    }

    console.log(`✓ Received HTTP ${statusCode}`);

    // Check success criteria
    console.log('\n[STEP 3] Validating response...');
    const isSuccess = statusCode === 200;
    const hasTokenList = Array.isArray(bodyObj) || (bodyObj.tokens && Array.isArray(bodyObj.tokens));
    const tokens = Array.isArray(bodyObj) ? bodyObj : (bodyObj.tokens || []);

    if (isSuccess && hasTokenList) {
      console.log('✓ Response status is 200 OK');
      console.log(`✓ Found ${tokens.length} PAT(s)`);
      tokens.forEach((token, idx) => {
        console.log(`  [${idx + 1}] ${token.name || token.id}`);
      });
    }

    // Report results
    console.log('\n========================================');
    console.log('TEST 4: List PATs via iPaaS Proxy');
    console.log('========================================');
    console.log(`Status: ${isSuccess && hasTokenList ? 'PASS ✅' : 'FAIL ❌'}`);
    console.log(`HTTP Code: ${statusCode}`);
    console.log(`Token Count: ${tokens.length}`);
    console.log(`Response: ${JSON.stringify(tokens.slice(0, 2)).substring(0, 200)}...`);

    if (!isSuccess || !hasTokenList) {
      console.log(`Error: ${isSuccess ? 'Invalid response structure' : body}`);
    }

    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_list_pats_via_ipaas',
      result: isSuccess && hasTokenList ? 'PASS' : 'FAIL',
      statusCode,
      tokenCount: tokens.length,
      tokens,
      error: !isSuccess || !hasTokenList ? body : null,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.log('\n========================================');
    console.log('TEST 4: List PATs via iPaaS Proxy');
    console.log('========================================');
    console.log(`Status: FAIL ❌`);
    console.log(`Error: ${error.message}`);
    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_list_pats_via_ipaas',
      result: 'FAIL',
      statusCode: null,
      tokenCount: 0,
      tokens: [],
      error: error.message,
      timestamp: new Date().toISOString(),
    };
  }
}

// Run the test
const result = await listPATsViaIPaaS();

export { result };

process.exit(result.result === 'PASS' ? 0 : 1);
