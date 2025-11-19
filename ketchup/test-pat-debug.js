import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';

const AWS_REGION = 'eu-west-1';
const SECRET_NAME = 'Ketchup_Token_Secrets';

async function checkToken() {
  const client = new SecretsManagerClient({
    region: AWS_REGION,
  });

  try {
    const command = new GetSecretValueCommand({
      SecretId: SECRET_NAME,
    });
    const response = await client.send(command);

    if (response.SecretString) {
      const secrets = JSON.parse(response.SecretString);
      console.log('\n📋 Secrets retrieved:');
      console.log('Keys available:', Object.keys(secrets));
      console.log('\nPAT Token:');
      console.log('  - Exists:', !!secrets.ketchup_jira_pat);
      console.log('  - Length:', secrets.ketchup_jira_pat?.length || 0);
      console.log('  - Prefix:', secrets.ketchup_jira_pat?.substring(0, 20) + '...');
      console.log('  - Full token:', secrets.ketchup_jira_pat);
    }
  } catch (error) {
    console.error('Error:', error.message);
  }
}

await checkToken();
