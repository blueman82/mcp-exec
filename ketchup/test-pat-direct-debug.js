import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';
import { request } from 'undici';

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
  console.log('TEST 1: Direct JIRA API with PAT (DEBUG)');
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
    console.log(`  Token length: ${pat.length}`);
    console.log(`  Token prefix: ${pat.substring(0, 20)}...`);

    // Prepare headers
    const headers = {
      'Authorization': `Bearer ${pat}`,
      'Accept': 'application/json',
    };

    console.log('\n[DEBUG] Headers being sent:');
    console.log(`  Authorization: Bearer ${pat.substring(0, 20)}...`);
    console.log(`  Accept: application/json`);

    // Make HTTP request to JIRA
    console.log('\n[STEP 2] Making HTTP GET request to JIRA...');
    console.log(`  Endpoint: ${JIRA_DIRECT_ENDPOINT}`);

    const response = await request(JIRA_DIRECT_ENDPOINT, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(10000),
    });

    const statusCode = response.statusCode;
    const body = await response.body.text();

    console.log(`✓ Received HTTP ${statusCode}`);
    console.log(`  Response: ${body.substring(0, 100)}`);

    // Try to parse response
    try {
      const bodyObj = JSON.parse(body);
      console.log(`  Parsed: ${JSON.stringify(bodyObj).substring(0, 100)}`);
    } catch (e) {
      console.log(`  Could not parse as JSON`);
    }

    return statusCode === 200;
  } catch (error) {
    console.error(`\n❌ Error: ${error.message}`);
    console.error(error);
    return false;
  }
}

const success = await testDirectJiraAPI();
process.exit(success ? 0 : 1);
