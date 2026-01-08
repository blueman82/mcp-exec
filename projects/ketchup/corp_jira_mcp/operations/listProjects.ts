import { z } from "zod";
import { jiraRequest, buildUrl } from "../common/utils.js";

/**
 * Schema for listing JIRA projects accessible to the authenticated user.
 *
 * @property {string} [expand] - Comma-separated list of fields to expand in the response.
 *   Available options:
 *   - `description`: Include project description
 *   - `lead`: Include project lead user details
 *   - `url`: Include project URL
 *   - `projectKeys`: Include all project keys (for renamed projects)
 *   - `issueTypes`: Include issue types available in the project
 *   Example: "description,lead,issueTypes"
 *
 * @property {number} [recent] - Return only the N most recently accessed projects.
 *   Useful for building "recent projects" dropdowns.
 *   Example: 10 returns the 10 most recently accessed projects.
 *
 * @property {string[]} [properties] - List of project property keys to include.
 *   Project properties are custom key-value pairs stored on projects.
 *   Example: ["customProperty1", "customProperty2"]
 *
 * @see https://docs.atlassian.com/software/jira/docs/api/REST/8.22.0/#api/2/project-getAllProjects
 */
export const ListProjectsSchema = z.object({
  expand: z.string().optional().describe("Comma-separated fields to expand: description, lead, url, projectKeys, issueTypes"),
  recent: z.number().optional().describe("Return only the N most recently accessed projects"),
  properties: z.array(z.string()).optional().describe("Project property keys to include in the response")
});

export type ListProjectsRequest = z.infer<typeof ListProjectsSchema>;

/**
 * Lists all JIRA projects visible to the authenticated user
 * @param params Optional parameters for filtering and expanding project data
 * @returns List of projects with success wrapper
 */
export async function listJiraProjects(params: ListProjectsRequest = {}) {
  try {
    // Build query parameters
    const queryParams: Record<string, string | undefined> = {};

    if (params.expand) {
      queryParams.expand = params.expand;
    }

    if (params.recent !== undefined) {
      queryParams.recent = params.recent.toString();
    }

    if (params.properties && params.properties.length > 0) {
      queryParams.properties = params.properties.join(',');
    }

    // Build URL with query parameters
    const url = buildUrl("project", queryParams);

    const response = await jiraRequest(url, {
      method: "GET"
    });

    // Response is an array of projects
    const projects = Array.isArray(response) ? response : [];

    return {
      success: true,
      message: `Found ${projects.length} projects`,
      data: projects
    };
  } catch (error) {
    return {
      success: false,
      message: error instanceof Error ? error.message : 'Unknown error occurred',
      error
    };
  }
}
