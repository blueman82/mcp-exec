import { z } from "zod";
import { jiraRequest } from "../common/utils.js";

export const ValidatePATSchema = z.object({
  token: z.string().describe("PAT token to validate"),
});

export type ValidatePATRequest = z.infer<typeof ValidatePATSchema>;

interface ValidatePATResponse {
  success: boolean;
  message: string;
  valid?: boolean;
  error?: string;
}

/**
 * Validates a PAT token by attempting authentication
 * Used by rotation service to verify new token works before committing to secrets
 * @param token The PAT token to validate
 * @returns Object indicating if token is valid
 */
export async function validatePAT(request: ValidatePATRequest): Promise<ValidatePATResponse> {
  try {
    const { token } = request;

    if (!token || token.trim().length === 0) {
      return {
        success: false,
        valid: false,
        message: "Token validation failed",
        error: "Token cannot be empty"
      };
    }

    console.log("Validating PAT token by attempting authentication");

    // Attempt to use the token for authentication
    // We'll make a request to the API using the token to see if it's valid
    const result = await jiraRequest("myself", {
      method: "GET",
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });

    // If we get here without an exception, the token is valid
    console.log("PAT token validation successful");

    return {
      success: true,
      valid: true,
      message: "Token is valid and can authenticate with Jira API"
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";

    // Determine if it's an authentication error without exposing sensitive details
    const isAuthError = errorMessage.includes("401") ||
                        errorMessage.includes("Unauthorized") ||
                        errorMessage.includes("Invalid") ||
                        errorMessage.includes("authentication");

    console.error("PAT validation error:", errorMessage);

    // Return generic error message without exposing sensitive details
    const message = isAuthError
      ? "Token validation failed"
      : "Error during token validation";

    return {
      success: false,
      valid: false,
      message: message
    };
  }
}
