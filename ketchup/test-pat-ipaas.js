/**
 * Test 2: iPaaS Proxy with JIRA Credentials
 * Tests if JIRA credentials work through the iPaaS proxy with proper headers
 */

import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';
import { request } from 'undici';

const IPAAS_PROXY_ENDPOINT = 'https://ipaasapi.adobe-services.com/jira/rest/api/2/myself';
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

async function testIpaasProxyWithPAT() {
  console.log('\n========================================');
  console.log('TEST 2: iPaaS Proxy with PAT (x-authorization)');
  console.log('========================================');
  console.log(`Endpoint: ${IPAAS_PROXY_ENDPOINT}`);
  console.log(`Timestamp: ${new Date().toISOString()}`);

  try {
    // Fetch all required credentials from AWS Secrets
    console.log('\n[STEP 1] Fetching credentials from AWS Secrets Manager...');
    const secrets = await fetchSecretFromAWS();
    const imsAccessToken = secrets.ims_access_token;
    const ipaasApiKey = secrets.ipaas_api_key;
    const ipaasUsername = secrets.ipaas_username;
    const ipaasPassword = secrets.ipaas_password;

    if (!imsAccessToken || !ipaasApiKey || !ipaasUsername || !ipaasPassword) {
      throw new Error(
        `Missing required secrets: ims=${!!imsAccessToken}, api_key=${!!ipaasApiKey}, username=${!!ipaasUsername}, password=${!!ipaasPassword}`
      );
    }
    console.log('✓ All credentials fetched successfully');

    // Make HTTP request to iPaaS proxy
    console.log('\n[STEP 2] Making HTTP GET request to iPaaS proxy...');
    const response = await request(IPAAS_PROXY_ENDPOINT, {
      method: 'GET',
      headers: {
        'Authorization': imsAccessToken,
        'Username': ipaasUsername,
        'Password': ipaasPassword,
        'Api_key': ipaasApiKey,
        'Content-Type': 'application/json',
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
    const hasUserInfo = bodyObj.self && bodyObj.key && (bodyObj.name || bodyObj.displayName);

    if (isSuccess && hasUserInfo) {
      console.log('✓ Response status is 200 OK');
      console.log(`✓ User info found: username="${bodyObj.name || bodyObj.displayName}"`);
    }

    // Report results
    console.log('\n========================================');
    console.log('TEST 2: iPaaS Proxy with JIRA Credentials');
    console.log('========================================');
    console.log(`Status: ${isSuccess && hasUserInfo ? 'PASS ✅' : 'FAIL ❌'}`);
    console.log(`HTTP Code: ${statusCode}`);
    console.log(`Response: ${JSON.stringify(bodyObj).substring(0, 200)}...`);
    if (!isSuccess || !hasUserInfo) {
      console.log(`Error: ${isSuccess ? 'Invalid response structure' : body}`);
    }
    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_ipaas_proxy_with_jira_credentials',
      result: isSuccess && hasUserInfo ? 'PASS' : 'FAIL',
      statusCode,
      responsePreview: JSON.stringify(bodyObj).substring(0, 200),
      error: !isSuccess || !hasUserInfo ? body : null,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.log('\n========================================');
    console.log('TEST 2: iPaaS Proxy with JIRA Credentials');
    console.log('========================================');
    console.log(`Status: FAIL ❌`);
    console.log(`Error: ${error.message}`);
    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_ipaas_proxy_with_jira_credentials',
      result: 'FAIL',
      statusCode: null,
      responsePreview: null,
      error: error.message,
      timestamp: new Date().toISOString(),
    };
  }
}

// Run the test
const result = await testIpaasProxyWithPAT();
process.exit(result.result === 'PASS' ? 0 : 1);
