export class JiraError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly jiraErrors?: string[]
  ) {
    super(message);
    this.name = "JiraError";
  }
}
