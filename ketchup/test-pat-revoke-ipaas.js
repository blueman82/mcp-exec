/**
 * Test 5: Revoke PAT via iPaaS Proxy
 * Revokes a personal access token via iPaaS proxy
 *
 * This test uses a known test token ID that can be revoked
 */

import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';
import { request } from 'undici';

const IPAAS_PROXY_BASE = 'https://ipaasapi.adobe-services.com/jira';
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

async function revokePATViaiPaaS(tokenIdToRevoke) {
  const PAT_REVOKE_ENDPOINT = `${IPAAS_PROXY_BASE}/rest/pat/latest/tokens/${tokenIdToRevoke}`;

  console.log('\n========================================');
  console.log('TEST 5: Revoke PAT via iPaaS Proxy');
  console.log('========================================');
  console.log(`Endpoint: DELETE ${PAT_REVOKE_ENDPOINT}`);
  console.log(`Token ID to revoke: ${tokenIdToRevoke}`);
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

    // Revoke PAT
    console.log('\n[STEP 2] Revoking PAT via iPaaS proxy...');

    const response = await request(PAT_REVOKE_ENDPOINT, {
      method: 'DELETE',
      headers: {
        'Authorization': imsAccessToken,
        'Username': ipaasUsername,
        'Password': ipaasPassword,
        'Api_key': ipaasApiKey,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      signal: AbortSignal.timeout(10000),
    });

    const statusCode = response.statusCode;
    const body = await response.body.text();

    console.log(`✓ Received HTTP ${statusCode}`);

    // Check success criteria
    console.log('\n[STEP 3] Validating response...');
    // Successful revocation typically returns 204 No Content or 200 OK
    const isSuccess = statusCode === 204 || statusCode === 200;

    if (isSuccess) {
      console.log('✓ Response status indicates successful revocation');
      console.log(`✓ Token revoked: ${tokenIdToRevoke}`);
    }

    // Report results
    console.log('\n========================================');
    console.log('TEST 5: Revoke PAT via iPaaS Proxy');
    console.log('========================================');
    console.log(`Status: ${isSuccess ? 'PASS ✅' : 'FAIL ❌'}`);
    console.log(`HTTP Code: ${statusCode}`);
    console.log(`Token Revoked: ${tokenIdToRevoke}`);
    console.log(`Response: ${body.substring(0, 200) || '(empty body)'}`);

    if (!isSuccess) {
      console.log(`Error: HTTP ${statusCode} - ${body}`);
    }

    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_revoke_pat_via_ipaas',
      result: isSuccess ? 'PASS' : 'FAIL',
      statusCode,
      revokedTokenId: tokenIdToRevoke,
      error: !isSuccess ? body : null,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.log('\n========================================');
    console.log('TEST 5: Revoke PAT via iPaaS Proxy');
    console.log('========================================');
    console.log(`Status: FAIL ❌`);
    console.log(`Error: ${error.message}`);
    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_revoke_pat_via_ipaas',
      result: 'FAIL',
      statusCode: null,
      revokedTokenId: tokenIdToRevoke,
      error: error.message,
      timestamp: new Date().toISOString(),
    };
  }
}

// For testing, we need a token ID to revoke
// In a real scenario, this would be passed from the creation test
// For now, we'll require it as an argument or show usage

const tokenIdToRevoke = process.argv[2];

if (!tokenIdToRevoke) {
  console.log('\n⚠️  Usage: node test-pat-revoke-ipaas.js <tokenId>');
  console.log('   Example: node test-pat-revoke-ipaas.js 12345');
  console.log('\nNote: Get token IDs from test-pat-list-ipaas.js output');
  process.exit(1);
}

// Run the test
const result = await revokePATViaiPaaS(tokenIdToRevoke);

export { result };

process.exit(result.result === 'PASS' ? 0 : 1);
