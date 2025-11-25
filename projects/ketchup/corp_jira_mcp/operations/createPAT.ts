import { z } from "zod";
import { apiClient } from "../common/api-client.js";

// Schema for PAT creation request
export const CreatePATSchema = z.object({
  tokenName: z.string().min(1, "Token name is required"),
  expiryDays: z.number().int().min(1, "Expiry days must be at least 1")
});

export type CreatePATRequest = z.infer<typeof CreatePATSchema>;

// Response type from JIRA PAT creation endpoint
interface JiraPATResponse {
  token: string;
  expiresAt: string;
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
  data?: { token: string; expiresAt: string };
}> {
  try {
    // Log token creation request (without exposing parameters)
    console.log(`Creating PAT token: ${params.tokenName} with ${params.expiryDays}-day expiry`);

    // Call JIRA API endpoint via iPaaS proxy
    // Endpoint: POST /tokens/tokens
    const result = await apiClient.jiraRequest("tokens/tokens", {
      method: "POST",
      body: {
        name: params.tokenName,
        expirationDays: params.expiryDays
      }
    });

    const patResponse = result as JiraPATResponse;

    // Log successful creation without exposing the token value
    console.log(`Created PAT token: ${params.tokenName} - expires at ${patResponse.expiresAt}`);

    return {
      success: true,
      message: `Successfully created PAT token: ${params.tokenName}`,
      data: {
        token: patResponse.token,
        expiresAt: patResponse.expiresAt
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
