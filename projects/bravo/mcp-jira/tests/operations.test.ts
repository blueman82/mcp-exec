import { vi, describe, it, expect, beforeEach } from "vitest";

const mockWriteFile = vi.fn();

vi.mock("../src/utils.js", () => ({
  jiraRequest: vi.fn(),
}));

vi.mock("../src/ketchup-secrets.js", () => ({
  getIpaasAuth: vi.fn().mockResolvedValue({ imsToken: "test-ims", apiKey: "test-key" }),
}));

vi.mock("../src/config.js", () => ({
  config: {
    mode: "ipaas",
    baseUrl: "https://test.example.com/api",
    port: 8081,
    auth: { pat: "test-pat" },
  },
  getConfig: () => ({
    mode: "ipaas",
    baseUrl: "https://test.example.com/api",
    port: 8081,
    auth: { pat: "test-pat" },
  }),
  loadConfig: vi.fn(),
}));

vi.mock("node:fs/promises", () => ({
  writeFile: (...args: unknown[]) => mockWriteFile(...args),
}));

import { jiraRequest } from "../src/utils.js";
import { testAuthHandler } from "../src/operations/auth.js";
import { searchHandler } from "../src/operations/search.js";
import { addCommentHandler } from "../src/operations/addComment.js";
import { deleteCommentHandler } from "../src/operations/deleteComment.js";
import {
  getTransitionsHandler,
  transitionHandler,
} from "../src/operations/status.js";
import { createIssueHandler } from "../src/operations/create.js";
import { updateIssueHandler } from "../src/operations/update.js";
import { getProjectIssueTypesHandler } from "../src/operations/createmeta.js";
import { downloadAttachmentHandler } from "../src/operations/attachment.js";
import { getIpaasAuth } from "../src/ketchup-secrets.js";

const mockJiraRequest = vi.mocked(jiraRequest);
const mockGetIpaasAuth = vi.mocked(getIpaasAuth);

beforeEach(() => {
  vi.restoreAllMocks();
  mockGetIpaasAuth.mockResolvedValue({ imsToken: "test-ims", apiKey: "test-key" });
});

describe("testAuthHandler", () => {
  it("calls GET /myself without userPat", async () => {
    const user = { name: "testuser", displayName: "Test User" };
    mockJiraRequest.mockResolvedValue(user);

    const result = await testAuthHandler({});

    expect(mockJiraRequest).toHaveBeenCalledWith("/myself", {
      userPat: undefined,
    });
    expect(result).toEqual(user);
  });

  it("passes userPat through to jiraRequest", async () => {
    const user = { name: "patuser", displayName: "PAT User" };
    mockJiraRequest.mockResolvedValue(user);

    const result = await testAuthHandler({ userPat: "user-pat-abc" });

    expect(mockJiraRequest).toHaveBeenCalledWith("/myself", {
      userPat: "user-pat-abc",
    });
    expect(result).toEqual(user);
  });

});

describe("searchHandler", () => {
  it("calls POST /search with correct body", async () => {
    const searchResult = {
      issues: [{ key: "TEST-1", fields: { summary: "Test" } }],
      total: 1,
    };
    mockJiraRequest.mockResolvedValue(searchResult);

    const result = await searchHandler({
      jql: "project = TEST",
      startAt: 0,
      maxResults: 50,
      minimizeOutput: false,
    });

    expect(mockJiraRequest).toHaveBeenCalledWith("/search", {
      method: "POST",
      body: {
        jql: "project = TEST",
        startAt: 0,
        maxResults: 50,
        fields: undefined,
      },
    });
    expect(result).toEqual({ data: searchResult });
  });

  it("strips verbose fields when minimizeOutput is true", async () => {
    const searchResult = {
      issues: [
        {
          key: "TEST-1",
          fields: {
            summary: "Test",
            status: { name: "Open" },
            assignee: { displayName: "User" },
            updated: "2024-01-01",
            comment: { comments: [] },
            description: "verbose field to strip",
            customfield_12345: "another verbose field",
            environment: "production",
          },
        },
      ],
      total: 1,
    };
    mockJiraRequest.mockResolvedValue(searchResult);

    const result = (await searchHandler({
      jql: "project = TEST",
      startAt: 0,
      maxResults: 50,
      minimizeOutput: true,
    })) as { data: { issues: Array<{ fields: Record<string, unknown> }> } };

    const fields = result.data.issues[0].fields;
    expect(fields["summary"]).toBe("Test");
    expect(fields["status"]).toEqual({ name: "Open" });
    expect(fields["description"]).toBeUndefined();
    expect(fields["customfield_12345"]).toBeUndefined();
    expect(fields["environment"]).toBeUndefined();
  });
});

describe("addCommentHandler", () => {
  it("calls POST /issue/{key}/comment with body and userPat", async () => {
    const commentResult = { id: "10001", body: "Hello" };
    mockJiraRequest.mockResolvedValue(commentResult);

    const result = await addCommentHandler({
      issueIdOrKey: "TEST-1",
      comment: { body: "Hello" },
      userPat: "user-pat-123",
    });

    expect(mockJiraRequest).toHaveBeenCalledWith("/issue/TEST-1/comment", {
      method: "POST",
      body: { body: "Hello" },
      userPat: "user-pat-123",
    });
    expect(result).toEqual(commentResult);
  });
});

describe("deleteCommentHandler", () => {
  it("calls DELETE /issue/{key}/comment/{id}", async () => {
    mockJiraRequest.mockResolvedValue({});

    await deleteCommentHandler({
      issueIdOrKey: "TEST-1",
      commentId: "10001",
    });

    expect(mockJiraRequest).toHaveBeenCalledWith(
      "/issue/TEST-1/comment/10001",
      {
        method: "DELETE",
        userPat: undefined,
      }
    );
  });
});

describe("getTransitionsHandler", () => {
  it("calls GET /issue/{key}/transitions and wraps in data", async () => {
    const transitions = {
      transitions: [{ id: "1", name: "In Progress" }],
    };
    mockJiraRequest.mockResolvedValue(transitions);

    const result = await getTransitionsHandler({ issueIdOrKey: "TEST-1" });

    expect(mockJiraRequest).toHaveBeenCalledWith(
      "/issue/TEST-1/transitions"
    );
    expect(result).toEqual({ data: transitions });
  });
});

describe("transitionHandler", () => {
  it("calls POST /issue/{key}/transitions with transition body", async () => {
    mockJiraRequest.mockResolvedValue({});

    await transitionHandler({
      issueIdOrKey: "TEST-1",
      transitionId: "21",
    });

    expect(mockJiraRequest).toHaveBeenCalledWith(
      "/issue/TEST-1/transitions",
      {
        method: "POST",
        body: { transition: { id: "21" } },
        userPat: undefined,
      }
    );
  });

  it("includes resolution in fields when provided", async () => {
    mockJiraRequest.mockResolvedValue({});

    await transitionHandler({
      issueIdOrKey: "TEST-1",
      transitionId: "31",
      resolution: { name: "Done" },
      userPat: "pat-456",
    });

    expect(mockJiraRequest).toHaveBeenCalledWith(
      "/issue/TEST-1/transitions",
      {
        method: "POST",
        body: {
          transition: { id: "31" },
          fields: { resolution: { name: "Done" } },
        },
        userPat: "pat-456",
      }
    );
  });
});

describe("createIssueHandler", () => {
  it("calls POST /issue with fields", async () => {
    const created = { id: "10000", key: "TEST-2" };
    mockJiraRequest.mockResolvedValue(created);

    const result = await createIssueHandler({
      fields: { project: { key: "TEST" }, summary: "New issue" },
    });

    expect(mockJiraRequest).toHaveBeenCalledWith("/issue", {
      method: "POST",
      body: {
        fields: { project: { key: "TEST" }, summary: "New issue" },
      },
      userPat: undefined,
    });
    expect(result).toEqual(created);
  });
});

describe("updateIssueHandler", () => {
  it("calls PUT /issue/{key} with fields", async () => {
    mockJiraRequest.mockResolvedValue({});

    await updateIssueHandler({
      issueIdOrKey: "TEST-1",
      fields: { summary: "Updated summary" },
    });

    expect(mockJiraRequest).toHaveBeenCalledWith("/issue/TEST-1", {
      method: "PUT",
      body: { fields: { summary: "Updated summary" } },
      userPat: undefined,
    });
  });
});

describe("getProjectIssueTypesHandler", () => {
  it("calls GET /project/{key}/statuses", async () => {
    const statuses = [{ name: "Bug", statuses: [] }];
    mockJiraRequest.mockResolvedValue(statuses);

    const result = await getProjectIssueTypesHandler({
      projectKey: "TEST",
    });

    expect(mockJiraRequest).toHaveBeenCalledWith("/project/TEST/statuses");
    expect(result).toEqual(statuses);
  });
});

describe("downloadAttachmentHandler", () => {
  it("downloads attachment and writes to file", async () => {
    mockWriteFile.mockResolvedValue(undefined);

    const fileContent = new Uint8Array([72, 101, 108, 108, 111]);
    const mockAttachmentFetch = vi.fn().mockResolvedValue({
      ok: true,
      arrayBuffer: () => Promise.resolve(fileContent.buffer),
    });
    vi.stubGlobal("fetch", mockAttachmentFetch);

    const result = (await downloadAttachmentHandler({
      issueIdOrKey: "TEST-1",
      attachmentId: "att-123",
      destinationPath: "/tmp/test-file.pdf",
    })) as { success: boolean; path: string; size: number };

    expect(result.success).toBe(true);
    expect(result.path).toBe("/tmp/test-file.pdf");
    expect(result.size).toBe(5);
    expect(mockAttachmentFetch).toHaveBeenCalledWith(
      "https://test.example.com/api/attachment/content/att-123",
      expect.objectContaining({
        headers: expect.objectContaining({
          Accept: "application/octet-stream",
        }),
      })
    );
  });
});
