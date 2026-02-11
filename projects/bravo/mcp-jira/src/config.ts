export interface JiraConfig {
  mode: "ipaas" | "direct";
  baseUrl: string;
  port: number;
  auth: {
    pat: string;
  };
}

const IPAAS_DEFAULT_URL = "https://ipaasapi.adobe-services.com/jira/rest/api/2";
const DIRECT_DEFAULT_URL = "https://jira.corp.adobe.com/rest/api/2";

export let config: JiraConfig;

export function loadConfig(): JiraConfig {
  const mode = process.env.USE_IPAAS === "true" ? "ipaas" : "direct";
  const defaultUrl = mode === "ipaas" ? IPAAS_DEFAULT_URL : DIRECT_DEFAULT_URL;

  config = {
    mode,
    baseUrl: process.env.JIRA_API_BASE_URL ?? defaultUrl,
    port: parseInt(process.env.PORT ?? "8081", 10),
    auth: {
      pat: process.env.JIRA_PAT ?? "",
    },
  };

  return config;
}

export function getConfig(): JiraConfig {
  if (!config) {
    throw new Error("Config not loaded. Call loadConfig() first.");
  }
  return config;
}
