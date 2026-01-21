import { z } from "zod";
import { jiraRequest } from "../common/utils.js";

// Schema for issue fields
const IssueFieldsSchema = z.object({
  project: z.object({
    key: z.string()
  }),
  summary: z.string(),
  description: z.string().optional(),
  issuetype: z.object({
    name: z.string()
  }),
  assignee: z.object({
    name: z.string()
  }).optional(),
  priority: z.object({
    name: z.string()
  }).optional(),
  labels: z.array(z.string()).optional(),
  components: z.array(z.object({
    name: z.string()
  })).optional(),
  // Custom fields with proper value typing
  customfield_18203: z.object({
    value: z.string()
  }).optional(),
  customfield_24800: z.object({
    value: z.string()
  }).optional(),
  customfield_11801: z.string().optional(), // Epic Name field - direct string
  customfield_18507: z.object({
    value: z.string()
  }).optional(),
  customfield_27200: z.object({
    value: z.string()
  }).optional(),
  customfield_21400: z.string().optional(), // Team field - direct string
  customfield_11700: z.object({
    value: z.string()
  }).optional(),
  customfield_13400: z.string().optional(), // Acceptance Criteria - direct string
  // For any other custom fields
  customfield_10000: z.record(z.string(), z.any()).optional(),
  customfield_21401: z.string().optional(), // Parent Link field - direct string
  customfield_11800: z.string().optional(), // Epic Link field - direct string
  customfield_12900: z.object({
    value: z.string().optional()  // Team name - direct string
  }).optional(),
  customfield_29601: z.object({
    value: z.string().optional() // Type of Request - direct string
  }).optional(),
  customfield_23300: z.object({
    value: z.string().optional() // Domain name
  }).optional(),
});

// Schema for create issue request
export const CreateJiraIssueSchema = z.object({
  fields: IssueFieldsSchema,
  update: z.record(z.string(), z.any()).optional(),
  userPat: z.string().optional(),  // Optional user-provided PAT for authentication
});

export type CreateJiraIssueRequest = z.infer<typeof CreateJiraIssueSchema>;

/**
 * Creates a new Jira issue
 * @param params The issue creation parameters
 * @returns The created issue
 */
export async function createJiraIssue(params: CreateJiraIssueRequest) {
  try {
    // Check if we need to add a warning about QE Lead field
    const projectKey = params.fields.project.key;
    const hasQELead = params.fields.customfield_18203 !== undefined;

    // Projects known to require QE Lead field
    const projectsRequiringQELead = ['LM'];

    if (projectsRequiringQELead.includes(projectKey) && !hasQELead) {
      console.warn(`Warning: Project ${projectKey} typically requires QE Lead field (customfield_18203)`);
    }

    // Extract userPat from params (don't send it to JIRA API)
    const { userPat, ...jiraParams } = params;

    const result = await jiraRequest("issue", {
      method: "POST",
      body: jiraParams,
      userPat  // Pass user PAT for authentication
    });

    return {
      success: true,
      message: `Successfully created issue ${(result as { key: string }).key}`,
      data: result
    };
  } catch (error) {
    console.error('Create Jira Issue Error:', error);

    const errorDetails = error instanceof Error
      ? error.message
      : 'Unknown error occurred';
    
    return {
      success: false,
      message: `Error creating issue: ${errorDetails}`
    };
  }
}
