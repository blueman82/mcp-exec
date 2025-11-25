import { z } from "zod";
import { jiraRequest } from "../common/utils.js";

export const ListPATsSchema = z.object({});

export type ListPATsRequest = z.infer<typeof ListPATsSchema>;

interface PAT {
  id: string;
  name: string;
  expiresAt: string;
  lastUsed?: string;
  createdAt?: string;
}

interface ListPATsResponse {
  success: boolean;
  message: string;
  data?: {
    tokens: PAT[];
    count: number;
  };
}

export async function listPATs(): Promise<ListPATsResponse> {
  try {
    console.log("Fetching list of all active JIRA PAT tokens");

    const result = await jiraRequest("rest/api/3/tokens/tokens", {
      method: "GET",
      headers: {
        "Accept": "application/json"
      }
    });

    // Handle response - JIRA API returns array of tokens directly or wrapped in an object
    let tokens: PAT[] = [];

    if (Array.isArray(result)) {
      tokens = result;
    } else if (result && typeof result === 'object' && 'tokens' in result) {
      tokens = (result as any).tokens;
    } else if (result && typeof result === 'object' && 'values' in result) {
      tokens = (result as any).values;
    }

    const count = tokens.length;

    console.log(`Successfully fetched ${count} PAT tokens`);

    return {
      success: true,
      message: `Retrieved ${count} active PAT tokens`,
      data: {
        tokens,
        count
      }
    };
  } catch (error) {
    const errorDetails = error instanceof Error ? error.message : 'Unknown error';
    console.error('List PATs Error:', error);
    return {
      success: false,
      message: `Error: ${errorDetails}`
    };
  }
}
