import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';

const AWS_REGION = process.env.AWS_REGION || 'eu-west-1';
const SECRET_NAME = process.env.AWS_SECRET_NAME || 'Ketchup_Token_Secrets';

// Initialize Secrets Manager client
const client = new SecretsManagerClient({ region: AWS_REGION });

/**
 * Fetches secrets from AWS Secrets Manager and sets them as environment variables
 */
async function loadSecretsFromAWS(): Promise<void> {
  console.error(`Loading secrets from AWS Secrets Manager (${SECRET_NAME})...`);
  
  try {
    const command = new GetSecretValueCommand({
      SecretId: SECRET_NAME,
    });
    
    const response = await client.send(command);
    
    if (!response.SecretString) {
      throw new Error('No secret string found in response');
    }
    
    const secrets = JSON.parse(response.SecretString);
    
    // Map AWS secrets to environment variables expected by MCP server
    const mappings = {
      'ipaas_username': 'JIRA_USERNAME',
      'ipaas_password': 'JIRA_PASSWORD',
      'ipaas_api_key': 'JIRA_API_KEY',
      'ims_access_token': 'JIRA_IMS_TOKEN',
      'ketchup_jira_pat': 'JIRA_PAT',
      'ketchup_jira_pat_expiry': 'JIRA_PAT_EXPIRY'
    };
    
    // Also set backward compatibility variables
    if (secrets.ipaas_username) {
      process.env.JIRA_EMAIL = secrets.ipaas_username;
    }
    if (secrets.ipaas_api_key) {
      process.env.JIRA_PERSONAL_ACCESS_TOKEN = secrets.ipaas_api_key;
    }
    
    for (const [awsKey, envKey] of Object.entries(mappings)) {
      if (secrets[awsKey]) {
        process.env[envKey] = secrets[awsKey];
      }
    }
    
    console.error('Environment variables loaded successfully from AWS Secrets Manager');
    console.error('JIRA_USERNAME:', process.env.JIRA_USERNAME || 'not set');
    console.error('JIRA_API_KEY:', process.env.JIRA_API_KEY ? '[REDACTED]' : 'not set');
    console.error('JIRA_IMS_TOKEN:', process.env.JIRA_IMS_TOKEN ? '[REDACTED]' : 'not set');
    console.error('JIRA_PAT:', process.env.JIRA_PAT ? '[REDACTED]' : 'not set');
    console.error('JIRA_PAT_EXPIRY:', process.env.JIRA_PAT_EXPIRY || 'not set');
    
  } catch (error) {
    console.error('Failed to load secrets from AWS:', error);
    
    // Fall back to checking if environment variables are already set
    if (process.env.JIRA_USERNAME && process.env.JIRA_API_KEY) {
      console.error('Using existing environment variables');
    } else {
      throw new Error('No JIRA credentials available from AWS or environment');
    }
  }
}

// Export the initialization function
export { loadSecretsFromAWS };

// Auto-initialize if this module is imported
if (process.env.USE_AWS_SECRETS !== 'false') {
  await loadSecretsFromAWS();
}