import { JiraError } from "./errors.js";
import { config } from "./config.js";
import { getIpaasAuth } from "./ketchup-secrets.js";

interface JiraRequestOptions {
  method?: string;
  body?: unknown;
  userPat?: string;
  headers?: Record<string, string>;
}

export async function jiraRequest<T = unknown>(
  path: string,
  options: JiraRequestOptions = {}
): Promise<T> {
  const { method = "GET", body, userPat } = options;
  const effectivePat = userPat ?? config.auth.pat;

  if (!effectivePat) {
    throw new JiraError(
      "Jira PAT not configured. Set JIRA_PAT environment variable or configure via AWS Secrets Manager.",
      401
    );
  }

  const url = `${config.baseUrl}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  if (config.mode === "ipaas") {
    const ipaasAuth = await getIpaasAuth();
    if (!ipaasAuth) {
      throw new JiraError(
        "iPaaS auth not available. Set JIRA_IMS_TOKEN + JIRA_API_KEY env vars or enable USE_AWS_SECRETS.",
        401
      );
    }
    headers["Authorization"] = ipaasAuth.imsToken;
    headers["Api_key"] = ipaasAuth.apiKey;
    headers["x-authorization"] = `Bearer ${effectivePat}`;
  } else {
    headers["Authorization"] = `Bearer ${effectivePat}`;
  }

  const fetchOptions: RequestInit = { method, headers };
  if (body) {
    fetchOptions.body = JSON.stringify(body);
  }

  const response = await fetch(url, fetchOptions);

  if (!response.ok) {
    let errorMessage = `Jira API error: ${response.status} ${response.statusText}`;
    let jiraErrors: string[] | undefined;
    try {
      const errorBody = (await response.json()) as Record<string, unknown>;
      if (Array.isArray(errorBody.errorMessages)) {
        jiraErrors = errorBody.errorMessages as string[];
        errorMessage = jiraErrors.join("; ") || errorMessage;
      }
    } catch {
      // ignore parse errors
    }
    throw new JiraError(errorMessage, response.status, jiraErrors);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}
