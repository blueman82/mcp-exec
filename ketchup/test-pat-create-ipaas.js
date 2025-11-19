/**
 * Test 3: Create PAT via iPaaS Proxy
 * Creates a new personal access token via iPaaS proxy
 */

import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';
import { request } from 'undici';

const IPAAS_PROXY_BASE = 'https://ipaasapi.adobe-services.com/jira';
const PAT_CREATE_ENDPOINT = `${IPAAS_PROXY_BASE}/rest/pat/latest/tokens`;
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

async function createPATViaiPaaS() {
  console.log('\n========================================');
  console.log('TEST 3: Create PAT via iPaaS Proxy');
  console.log('========================================');
  console.log(`Endpoint: POST ${PAT_CREATE_ENDPOINT}`);
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

    // Prepare PAT creation payload
    const tokenName = `ketchup-pat-${Date.now()}`;
    const expirationDuration = 90; // 90 days as per Adobe standards

    const payload = {
      name: tokenName,
      expirationDuration,
    };

    console.log('\n[STEP 2] Creating PAT via iPaaS proxy...');
    console.log(`  Token name: ${tokenName}`);
    console.log(`  Expiration: ${expirationDuration} days`);

    const response = await request(PAT_CREATE_ENDPOINT, {
      method: 'POST',
      headers: {
        'Authorization': imsAccessToken,
        'Username': ipaasUsername,
        'Password': ipaasPassword,
        'Api_key': ipaasApiKey,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(10000),
    });

    const statusCode = response.statusCode;
    const body = await response.body.text();
    const bodyObj = JSON.parse(body);

    console.log(`✓ Received HTTP ${statusCode}`);

    // Check success criteria
    console.log('\n[STEP 3] Validating response...');
    const isSuccess = statusCode === 201 || statusCode === 200;
    const hasTokenData = bodyObj.id && (bodyObj.name || bodyObj.token);

    if (isSuccess && hasTokenData) {
      console.log('✓ Response status is 200/201 Created');
      console.log(`✓ Token created successfully`);
      console.log(`  Token ID: ${bodyObj.id}`);
      console.log(`  Token name: ${bodyObj.name}`);
      if (bodyObj.token) {
        console.log(`  Token value: ${bodyObj.token.substring(0, 20)}...`);
      }
    }

    // Report results
    console.log('\n========================================');
    console.log('TEST 3: Create PAT via iPaaS Proxy');
    console.log('========================================');
    console.log(`Status: ${isSuccess && hasTokenData ? 'PASS ✅' : 'FAIL ❌'}`);
    console.log(`HTTP Code: ${statusCode}`);
    console.log(`Response: ${JSON.stringify({
      id: bodyObj.id,
      name: bodyObj.name,
      expiresAt: bodyObj.expiresAt,
    }).substring(0, 200)}...`);

    if (isSuccess && hasTokenData) {
      console.log(`\n⚠️  NEW TOKEN CREATED:`);
      if (bodyObj.token) {
        console.log(`  Token Value: ${bodyObj.token.substring(0, 20)}...`);
        console.log(`  Store this safely! It won't be shown again.`);
      } else {
        console.log(`  Note: Use the token ID ${bodyObj.id} for token management`);
      }
    } else if (!isSuccess) {
      console.log(`Error: HTTP ${statusCode}`);
    } else {
      console.log(`Error: Invalid response structure`);
    }

    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_create_pat_via_ipaas',
      result: isSuccess && hasTokenData ? 'PASS' : 'FAIL',
      statusCode,
      tokenId: bodyObj.id || null,
      tokenValue: bodyObj.token || null,
      tokenName: bodyObj.name || null,
      expiresAt: bodyObj.expiresAt || null,
      error: !isSuccess || !hasTokenData ? body : null,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.log('\n========================================');
    console.log('TEST 3: Create PAT via iPaaS Proxy');
    console.log('========================================');
    console.log(`Status: FAIL ❌`);
    console.log(`Error: ${error.message}`);
    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_create_pat_via_ipaas',
      result: 'FAIL',
      statusCode: null,
      error: error.message,
      timestamp: new Date().toISOString(),
    };
  }
}

// Run the test
const result = await createPATViaiPaaS();

// Export result for use by other tests
export { result };

process.exit(result.result === 'PASS' ? 0 : 1);
