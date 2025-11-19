/**
 * Test 6: Update AWS Secrets with New PAT Token
 * Updates the ketchup_jira_pat in AWS Secrets Manager with a new token value
 */

import { SecretsManagerClient, GetSecretValueCommand, UpdateSecretCommand } from '@aws-sdk/client-secrets-manager';

const AWS_REGION = 'eu-west-1';
const SECRET_NAME = 'Ketchup_Token_Secrets';

async function updatePATInSecrets(newPatToken, newPatExpiryDate) {
  console.log('\n========================================');
  console.log('TEST 6: Update AWS Secrets with New PAT');
  console.log('========================================');
  console.log(`Secret: ${SECRET_NAME}`);
  console.log(`Region: ${AWS_REGION}`);
  console.log(`Timestamp: ${new Date().toISOString()}`);

  try {
    const client = new SecretsManagerClient({
      region: AWS_REGION,
    });

    // Step 1: Fetch current secrets
    console.log('\n[STEP 1] Fetching current secrets...');
    const getCommand = new GetSecretValueCommand({
      SecretId: SECRET_NAME,
    });
    const getResponse = await client.send(getCommand);

    if (!getResponse.SecretString) {
      throw new Error('Could not retrieve current secrets');
    }

    const currentSecrets = JSON.parse(getResponse.SecretString);
    console.log('✓ Current secrets retrieved');

    // Step 2: Update the PAT token
    console.log('\n[STEP 2] Updating PAT token in secrets...');
    console.log(`  Old PAT: ${currentSecrets.ketchup_jira_pat?.substring(0, 20)}...`);
    console.log(`  New PAT: ${newPatToken.substring(0, 20)}...`);

    const updatedSecrets = {
      ...currentSecrets,
      ketchup_jira_pat: newPatToken,
      ketchup_jira_pat_expiry: newPatExpiryDate || new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString(),
      ketchup_jira_pat_updated_at: new Date().toISOString(),
    };

    // Step 3: Update AWS Secrets
    console.log('\n[STEP 3] Pushing update to AWS Secrets Manager...');
    const updateCommand = new UpdateSecretCommand({
      SecretId: SECRET_NAME,
      SecretString: JSON.stringify(updatedSecrets),
    });

    const updateResponse = await client.send(updateCommand);
    console.log('✓ Secrets updated successfully');
    console.log(`  Version ID: ${updateResponse.VersionId}`);
    console.log(`  ARN: ${updateResponse.ARN}`);

    // Step 4: Verify update
    console.log('\n[STEP 4] Verifying update...');
    const verifyCommand = new GetSecretValueCommand({
      SecretId: SECRET_NAME,
    });
    const verifyResponse = await client.send(verifyCommand);
    const verifiedSecrets = JSON.parse(verifyResponse.SecretString);

    const patMatches = verifiedSecrets.ketchup_jira_pat === newPatToken;
    const expirySet = verifiedSecrets.ketchup_jira_pat_expiry !== undefined;
    const timestampSet = verifiedSecrets.ketchup_jira_pat_updated_at !== undefined;

    if (patMatches && expirySet && timestampSet) {
      console.log('✓ PAT token updated and verified');
      console.log(`✓ Expiry date set: ${verifiedSecrets.ketchup_jira_pat_expiry}`);
      console.log(`✓ Last updated: ${verifiedSecrets.ketchup_jira_pat_updated_at}`);
    }

    // Report results
    const isSuccess = patMatches && expirySet && timestampSet;

    console.log('\n========================================');
    console.log('TEST 6: Update AWS Secrets with New PAT');
    console.log('========================================');
    console.log(`Status: ${isSuccess ? 'PASS ✅' : 'FAIL ❌'}`);
    console.log(`Token Updated: ${patMatches}`);
    console.log(`Expiry Set: ${expirySet}`);
    console.log(`Timestamp Set: ${timestampSet}`);
    console.log(`Version ID: ${updateResponse.VersionId}`);
    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_update_pat_in_secrets',
      result: isSuccess ? 'PASS' : 'FAIL',
      versionId: updateResponse.VersionId,
      arn: updateResponse.ARN,
      tokenUpdated: patMatches,
      expiryDate: verifiedSecrets.ketchup_jira_pat_expiry,
      lastUpdated: verifiedSecrets.ketchup_jira_pat_updated_at,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.log('\n========================================');
    console.log('TEST 6: Update AWS Secrets with New PAT');
    console.log('========================================');
    console.log(`Status: FAIL ❌`);
    console.log(`Error: ${error.message}`);
    console.log(`Timestamp: ${new Date().toISOString()}`);

    return {
      testName: 'test_update_pat_in_secrets',
      result: 'FAIL',
      error: error.message,
      timestamp: new Date().toISOString(),
    };
  }
}

// Usage: provide new PAT token and optional expiry date
const newPatToken = process.argv[2];
const newPatExpiry = process.argv[3];

if (!newPatToken) {
  console.log('\n⚠️  Usage: node test-pat-update-secrets.js <newPatToken> [expiryDate]');
  console.log('   Example: node test-pat-update-secrets.js "abc123def456" "2026-02-19T00:00:00Z"');
  process.exit(1);
}

// Run the test
const result = await updatePATInSecrets(newPatToken, newPatExpiry);

export { result };

process.exit(result.result === 'PASS' ? 0 : 1);
