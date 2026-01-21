import { z } from 'zod';
import { jiraRequest, buildUrl } from '../common/utils.js';

interface JiraFieldMetadata {
  required?: boolean;
  name?: string;
  fieldId?: string;
  allowedValues?: unknown[];
  [key: string]: unknown;
}

// Response format for the path-based createmeta endpoint (v3 style)
// GET /issue/createmeta/{projectIdOrKey}/issuetypes/{issueTypeId}
interface JiraCreateMetaV3Response {
  maxResults?: number;
  startAt?: number;
  total?: number;
  isLast?: boolean;
  values?: Array<{
    fieldId: string;
    name: string;
    required: boolean;
    hasDefaultValue?: boolean;
    operations?: string[];
    allowedValues?: unknown[];
    schema?: {
      type: string;
      system?: string;
    };
    [key: string]: unknown;
  }>;
  [key: string]: unknown;
}

// Schema for getting issue types
export const GetIssueTypesSchema = z.object({
  projectKey: z.string().describe('The project key (e.g., CPGNREQ)')
});

// Schema for getting field metadata
export const GetFieldMetadataSchema = z.object({
  projectKey: z.string().describe('The project key (e.g., CPGNREQ)'),
  issueTypeId: z.string().describe('The issue type ID (e.g., 10200)'),
  userPat: z.string().optional().describe('Optional user-provided PAT for authentication')
});

// Interface for the project statuses response
interface ProjectStatusesResponse extends Array<{
  id: string;
  name: string;
  subtask: boolean;
  statuses: Array<{ id: string; name: string }>;
}> {}

/**
 * Get all issue types available for a project
 * Uses the project/statuses endpoint which returns issue types with their statuses
 * This endpoint works reliably through iPaaS unlike createmeta
 */
export async function getProjectIssueTypes(params: z.infer<typeof GetIssueTypesSchema>) {
  try {
    const { projectKey } = params;

    // Use the project statuses endpoint - returns issue types with their statuses
    // This works through iPaaS while createmeta doesn't
    const result = await jiraRequest(`project/${projectKey}/statuses`, {
      method: 'GET'
    }) as ProjectStatusesResponse;

    // Extract issue types from the response (array of issue types with statuses)
    const issueTypes = result.map(issueType => ({
      id: issueType.id,
      name: issueType.name,
      subtask: issueType.subtask
    }));

    return {
      success: true,
      message: `Retrieved ${issueTypes.length} issue types for project ${projectKey}`,
      data: { issueTypes }
    };
  } catch (error) {
    console.error('Get Issue Types Error:', error);

    const errorDetails = error instanceof Error
      ? error.message
      : 'Unknown error occurred';

    return {
      success: false,
      message: `Error getting issue types: ${errorDetails}`
    };
  }
}

/**
 * Get field metadata including allowedValues for a specific issue type
 * Uses the path-based createmeta endpoint which works through iPaaS:
 * GET /issue/createmeta/{projectIdOrKey}/issuetypes/{issueTypeId}
 *
 * NOTE: The query-string format (/issue/createmeta?projectKeys=X) DOES NOT work
 * through iPaaS because the Layer7 gateway treats "createmeta" as an issue key.
 */
export async function getIssueTypeFieldMetadata(params: z.infer<typeof GetFieldMetadataSchema>) {
  try {
    const { projectKey, issueTypeId, userPat } = params;

    // Use path-based endpoint format - this works through iPaaS!
    // The query-string format (/issue/createmeta?projectKeys=X) fails because
    // iPaaS gateway interprets "createmeta" as an issue key
    const endpoint = `issue/createmeta/${projectKey}/issuetypes/${issueTypeId}`;

    const result = await jiraRequest(endpoint, {
      method: 'GET',
      userPat  // Pass user PAT for authentication if provided
    }) as JiraCreateMetaV3Response;

    // The v3-style endpoint returns values directly in { values: [...] } format
    const values = result.values || [];

    const fieldsWithValues = values.filter((field) => field.allowedValues)?.length || 0;
    const requiredFields = values.filter((field) => field.required)?.length || 0;
    console.log(`Retrieved ${values.length} fields for ${projectKey}/${issueTypeId}, ${requiredFields} required, ${fieldsWithValues} with allowedValues`);

    return {
      success: true,
      message: `Successfully retrieved field metadata for ${projectKey} issue type ${issueTypeId}`,
      data: {
        values,
        pagination: {
          maxResults: result.maxResults,
          startAt: result.startAt,
          total: result.total,
          isLast: result.isLast
        }
      }
    };
  } catch (error) {
    console.error('Get Field Metadata Error:', error);

    const errorDetails = error instanceof Error
      ? error.message
      : 'Unknown error occurred';

    return {
      success: false,
      message: `Error getting field metadata: ${errorDetails}`
    };
  }
}

export type GetIssueTypesInput = z.infer<typeof GetIssueTypesSchema>;
export type GetFieldMetadataInput = z.infer<typeof GetFieldMetadataSchema>;