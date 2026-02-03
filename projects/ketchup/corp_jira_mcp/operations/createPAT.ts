import { z } from "zod";
import { apiClient } from "../common/api-client.js";
import { config } from "../common/config.js";

// Schema for PAT creation request
export const CreatePATSchema = z.object({
  tokenName: z.string().min(1, "Token name is required"),
  expiryDays: z.number().int().min(1, "Expiry days must be at least 1")
});

export type CreatePATRequest = z.infer<typeof CreatePATSchema>;

// Response type from JIRA PAT creation endpoint
// API returns rawToken (token value), id (token ID), and expiringAt (ISO date)
interface JiraPATResponse {
  rawToken: string;
  id: string;
  expiringAt: string;
}

/**
 * Creates a new JIRA Personal Access Token (PAT)
 * Used by the rotation service to generate replacement tokens
 *
 * @param params The PAT creation parameters (tokenName, expiryDays)
 * @returns Object with token and expiry date if successful, error message if failed
 *
 * Key behaviors:
 * - Calls JIRA API endpoint via iPaaS proxy
 * - Sets 90-day expiry on generated PAT (matches rotation schedule)
 * - Logs token creation without exposing the token value
 * - Returns token and ISO 8601 formatted expiry date
 */
export async function createPAT(params: CreatePATRequest): Promise<{
  success: boolean;
  message: string;
  data?: { pat: string; id: string; expiryDate: string };
}> {
  try {
    // Log token creation request (without exposing parameters)
    console.log(`Creating PAT token: ${params.tokenName} with ${params.expiryDays}-day expiry`);

    // Call JIRA PAT API endpoint via iPaaS proxy
    // PAT API is at /rest/pat/latest/tokens, NOT under /rest/api/2/
    // Construct full URL to bypass buildUrl which appends to apiBaseUrl
    const patApiUrl = config.apiBaseUrl.replace('/rest/api/2', '/rest/pat/latest/tokens');
    const result = await apiClient.jiraRequest(patApiUrl, {
      method: "POST",
      body: {
        name: params.tokenName,
        expirationDuration: params.expiryDays
      }
    });

    const patResponse = result as JiraPATResponse;

    // Log successful creation without exposing the token value
    console.log(`Created PAT token: ${params.tokenName} (ID: ${patResponse.id}) - expires at ${patResponse.expiringAt}`);

    return {
      success: true,
      message: `Successfully created PAT token: ${params.tokenName}`,
      data: {
        pat: patResponse.rawToken,
        id: String(patResponse.id),  // Convert to string for revokePAT schema
        expiryDate: patResponse.expiringAt
      }
    };
  } catch (error) {
    const errorDetails = error instanceof Error ? error.message : 'Unknown error occurred';
    console.error('Create PAT Error:', error);

    return {
      success: false,
      message: `Error creating PAT: ${errorDetails}`
    };
  }
}
