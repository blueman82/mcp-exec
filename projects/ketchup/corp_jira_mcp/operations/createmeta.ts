import { z } from 'zod';
import { jiraRequest } from '../common/utils.js';

// Type definitions for JIRA API responses
interface JiraFieldMetadata {
  allowedValues?: unknown[];
  [key: string]: unknown;
}

interface JiraCreateMetaResponse {
  values?: JiraFieldMetadata[];
  [key: string]: unknown;
}

// Schema for getting issue types
export const GetIssueTypesSchema = z.object({
  projectKey: z.string().describe('The project key (e.g., CPGNREQ)')
});

// Schema for getting field metadata
export const GetFieldMetadataSchema = z.object({
  projectKey: z.string().describe('The project key (e.g., CPGNREQ)'),
  issueTypeId: z.string().describe('The issue type ID (e.g., 10200)')
});

/**
 * Get all issue types available for a project
 * Uses the new createmeta API endpoint
 */
export async function getProjectIssueTypes(params: z.infer<typeof GetIssueTypesSchema>) {
  try {
    const { projectKey } = params;
    
    // Use API v3 endpoint
    const result = await jiraRequest(`issue/createmeta/${projectKey}/issuetypes`, {
      method: 'GET',
      apiVersion: '3'
    });
    
    return {
      success: true,
      message: `Successfully retrieved issue types for project ${projectKey}`,
      data: result
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
 * This is where the "data goldmine" lives!
 */
export async function getIssueTypeFieldMetadata(params: z.infer<typeof GetFieldMetadataSchema>) {
  try {
    const { projectKey, issueTypeId } = params;

    // Use API v3 endpoint
    const result = await jiraRequest(`issue/createmeta/${projectKey}/issuetypes/${issueTypeId}`, {
      method: 'GET',
      apiVersion: '3'
    }) as JiraCreateMetaResponse;

    // Count fields with allowedValues for logging
    const fieldsWithValues = result.values?.filter((field) => field.allowedValues)?.length || 0;

    console.log(`Retrieved ${result.values?.length || 0} fields for ${projectKey}/${issueTypeId}, ${fieldsWithValues} with allowedValues`);

    return {
      success: true,
      message: `Successfully retrieved field metadata for ${projectKey} issue type ${issueTypeId}`,
      data: result
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