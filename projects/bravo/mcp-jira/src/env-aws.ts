import {
  SecretsManagerClient,
  GetSecretValueCommand,
} from "@aws-sdk/client-secrets-manager";

const SECRET_KEY_MAP: Record<string, string> = {
  jira_pat: "JIRA_PAT",
  jira_pat_expiry: "JIRA_PAT_EXPIRY",
};

export async function loadAwsSecrets(): Promise<void> {
  const region = process.env.AWS_REGION || "eu-west-1";
  const client = new SecretsManagerClient({ region });

  const command = new GetSecretValueCommand({ SecretId: "bravo/jira" });
  const response = await client.send(command);

  if (!response.SecretString) {
    console.warn("AWS secret bravo/jira returned no SecretString");
    return;
  }

  const secrets = JSON.parse(response.SecretString) as Record<string, string>;

  for (const [secretKey, envVar] of Object.entries(SECRET_KEY_MAP)) {
    const value = secrets[secretKey];
    if (value && !process.env[envVar]) {
      process.env[envVar] = value;
    }
  }
}
