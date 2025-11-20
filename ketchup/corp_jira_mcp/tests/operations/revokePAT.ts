import { z } from "zod";
import { jiraRequest } from "../common/utils.js";

// Schema for PAT revocation request
export const RevokePATSchema = z.object({
  tokenId: z.string().min(1, "Token ID is required")
});

export type RevokePATRequest = z.infer<typeof RevokePATSchema>;

/**
 * Revokes (deletes) a JIRA Personal Access Token (PAT)
 * Used by the rotation service to clean up old tokens after new one is validated
 *
 * @param params The PAT revocation parameters (tokenId)
 * @returns Object with success status
 *
 * Key behaviors:
 * - Calls JIRA API endpoint to revoke PAT by token ID
 * - Returns success/failure status
 * - Logs revocation without exposing token details
 * - Handles errors gracefully
 */
export async function revokePAT(params: RevokePATRequest): Promise<{
  success: boolean;
  message: string;
}> {
  try {
    // Log token revocation request
    console.log(`Revoking PAT token with ID: ${params.tokenId}`);

    // Call JIRA API endpoint via iPaaS proxy
    // Endpoint: DELETE /rest/api/3/tokens/tokens/{tokenId}
    await jiraRequest(`tokens/tokens/${params.tokenId}`, {
      method: "DELETE"
    });

    // Log successful revocation
    console.log(`Successfully revoked PAT token: ${params.tokenId}`);

    return {
      success: true,
      message: `Successfully revoked PAT token: ${params.tokenId}`
    };
  } catch (error) {
    const errorDetails = error instanceof Error ? error.message : 'Unknown error occurred';
    console.error('Revoke PAT Error:', error);

    return {
      success: false,
      message: `Error revoking PAT: ${errorDetails}`
    };
  }
}
