import { describe, it, expect, vi, beforeEach } from "vitest";
import { loadConfig, config } from "../src/config.js";
import { jiraRequest } from "../src/utils.js";
import { JiraError } from "../src/errors.js";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

vi.mock("../src/ketchup-secrets.js", () => ({
  getIpaasAuth: vi.fn().mockResolvedValue({ imsToken: "test-ims", apiKey: "test-key" }),
}));

import { getIpaasAuth } from "../src/ketchup-secrets.js";
const mockGetIpaasAuth = vi.mocked(getIpaasAuth);

beforeEach(() => {
  process.env.USE_IPAAS = "true";
  process.env.JIRA_PAT = "test-pat";
  process.env.JIRA_API_BASE_URL = "https://test.example.com/api";
  loadConfig();
  vi.restoreAllMocks();
  vi.stubGlobal("fetch", mockFetch);
  mockGetIpaasAuth.mockResolvedValue({ imsToken: "test-ims", apiKey: "test-key" });
});

describe("jiraRequest", () => {
  it("sends iPaaS mode headers", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: "1" }),
    });

    await jiraRequest("/myself");

    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe("https://test.example.com/api/myself");
    expect(options.headers["Authorization"]).toBe("test-ims");
    expect(options.headers["Api_key"]).toBe("test-key");
    expect(options.headers["x-authorization"]).toBe("Bearer test-pat");
  });

  it("sends direct mode headers", async () => {
    config.mode = "direct";
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: "1" }),
    });

    await jiraRequest("/myself");

    const [, options] = mockFetch.mock.calls[0];
    expect(options.headers["Authorization"]).toBe("Bearer test-pat");
    expect(options.headers["Api_key"]).toBeUndefined();
    expect(options.headers["x-authorization"]).toBeUndefined();
  });

  it("uses userPat over config PAT", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    });

    await jiraRequest("/myself", { userPat: "user-specific-pat" });

    const [, options] = mockFetch.mock.calls[0];
    expect(options.headers["x-authorization"]).toBe(
      "Bearer user-specific-pat"
    );
  });

  it("throws JiraError when PAT is missing", async () => {
    config.auth.pat = "";

    await expect(jiraRequest("/myself")).rejects.toThrow(JiraError);
    await expect(jiraRequest("/myself")).rejects.toMatchObject({
      statusCode: 401,
    });
  });

  it("throws JiraError on HTTP error", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      json: () => Promise.resolve({}),
    });

    await expect(jiraRequest("/myself")).rejects.toThrow(JiraError);
    await expect(jiraRequest("/myself")).rejects.toMatchObject({
      statusCode: 403,
    });
  });

  it("returns empty object for 204 response", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 204,
    });

    const result = await jiraRequest("/issue/TEST-1/comment/123");
    expect(result).toEqual({});
  });

  it("parses JSON response", async () => {
    const payload = { key: "TEST-1", fields: { summary: "Hello" } };
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(payload),
    });

    const result = await jiraRequest("/issue/TEST-1");
    expect(result).toEqual(payload);
  });

  it("throws JiraError when getIpaasAuth returns undefined in iPaaS mode", async () => {
    mockGetIpaasAuth.mockResolvedValue(undefined);

    await expect(jiraRequest("/myself")).rejects.toThrow(JiraError);
    await expect(jiraRequest("/myself")).rejects.toMatchObject({
      statusCode: 401,
    });
  });
});
