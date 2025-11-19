import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';

const JIRA_DIRECT_ENDPOINT = 'https://jira.corp.adobe.com/rest/api/2/myself';
const AWS_REGION = 'eu-west-1';
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
  console.log('TEST 1: Direct JIRA API with PAT (FETCH)');
  console.log('========================================');

  try {
    // Fetch PAT from AWS Secrets
    console.log('\n[STEP 1] Fetching PAT from AWS Secrets Manager...');
    const secrets = await fetchSecretFromAWS();
    const pat = secrets.ketchup_jira_pat;

    if (!pat) {
      throw new Error('PAT token not found in secrets');
    }
    console.log('✓ PAT fetched successfully');

    // Make HTTP request to JIRA using native fetch
    console.log('\n[STEP 2] Making HTTP GET request to JIRA (using fetch)...');
    const response = await fetch(JIRA_DIRECT_ENDPOINT, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${pat}`,
        'Accept': 'application/json',
      },
    });

    const statusCode = response.status;
    const body = await response.text();
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
    console.log('TEST 1: Direct JIRA with PAT');
    console.log('========================================');
    console.log(`Status: ${isSuccess && hasUserInfo ? 'PASS ✅' : 'FAIL ❌'}`);
    console.log(`HTTP Code: ${statusCode}`);
    console.log(`Response: ${JSON.stringify(bodyObj).substring(0, 200)}...`);
    if (!isSuccess || !hasUserInfo) {
      console.log(`Error: ${isSuccess ? 'Invalid response structure' : body}`);
    }
    console.log(`Timestamp: ${new Date().toISOString()}`);

    return isSuccess && hasUserInfo;
  } catch (error) {
    console.log('\n========================================');
    console.log('TEST 1: Direct JIRA with PAT');
    console.log('========================================');
    console.log(`Status: FAIL ❌`);
    console.log(`Error: ${error.message}`);
    console.log(`Timestamp: ${new Date().toISOString()}`);
    return false;
  }
}

const success = await testDirectJiraAPI();
process.exit(success ? 0 : 1);
