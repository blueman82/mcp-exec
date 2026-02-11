import {
  SecretsManagerClient,
  GetSecretValueCommand,
} from "@aws-sdk/client-secrets-manager";

export interface IpaasAuth {
  imsToken: string;
  apiKey: string;
}

const TTL_MS = 5 * 60 * 1000;

let cached: IpaasAuth | undefined;
let cachedAt = 0;
let client: SecretsManagerClient | undefined;

export async function getIpaasAuth(): Promise<IpaasAuth | undefined> {
  const envToken = process.env.JIRA_IMS_TOKEN;
  const envKey = process.env.JIRA_API_KEY;
  if (envToken && envKey) {
    return { imsToken: envToken, apiKey: envKey };
  }

  if (process.env.USE_AWS_SECRETS !== "true") {
    return undefined;
  }

  if (cached && Date.now() - cachedAt < TTL_MS) {
    return cached;
  }

  try {
    client ??= new SecretsManagerClient({
      region: process.env.AWS_REGION ?? "eu-west-1",
    });

    const response = await client.send(
      new GetSecretValueCommand({ SecretId: "Ketchup_Token_Secrets" })
    );

    if (!response.SecretString) {
      throw new Error("Ketchup_Token_Secrets returned empty SecretString");
    }

    const secrets = JSON.parse(response.SecretString) as Record<string, string>;
    const imsToken = secrets.ims_access_token;
    const apiKey = secrets.ipaas_api_key;

    if (!imsToken || !apiKey) {
      throw new Error(
        "Ketchup_Token_Secrets missing ims_access_token or ipaas_api_key"
      );
    }

    cached = { imsToken, apiKey };
    cachedAt = Date.now();
    return cached;
  } catch (err) {
    if (cached) {
      return cached;
    }
    throw err;
  }
}

export function _resetForTesting(): void {
  cached = undefined;
  cachedAt = 0;
  client = undefined;
}
