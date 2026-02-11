import { describe, it, expect, beforeEach } from "vitest";
import { loadConfig, config } from "../src/config.js";

beforeEach(() => {
  delete process.env.USE_IPAAS;
  delete process.env.JIRA_API_BASE_URL;
  delete process.env.JIRA_API_KEY;
  delete process.env.JIRA_IMS_TOKEN;
  delete process.env.JIRA_PAT;
  delete process.env.PORT;
});

describe("loadConfig", () => {
  it("sets iPaaS mode when USE_IPAAS is true", () => {
    process.env.USE_IPAAS = "true";
    loadConfig();
    expect(config.mode).toBe("ipaas");
  });

  it("sets direct mode when USE_IPAAS is not set", () => {
    loadConfig();
    expect(config.mode).toBe("direct");
  });

  it("sets direct mode when USE_IPAAS is false", () => {
    process.env.USE_IPAAS = "false";
    loadConfig();
    expect(config.mode).toBe("direct");
  });

  it("defaults to iPaaS base URL in iPaaS mode", () => {
    process.env.USE_IPAAS = "true";
    loadConfig();
    expect(config.baseUrl).toBe(
      "https://ipaasapi.adobe-services.com/jira/rest/api/2"
    );
  });

  it("defaults to corp base URL in direct mode", () => {
    loadConfig();
    expect(config.baseUrl).toBe(
      "https://jira.corp.adobe.com/rest/api/2"
    );
  });

  it("uses custom base URL when provided", () => {
    process.env.JIRA_API_BASE_URL = "https://custom.example.com/api";
    loadConfig();
    expect(config.baseUrl).toBe("https://custom.example.com/api");
  });

  it("reads port from PORT env var", () => {
    process.env.PORT = "9090";
    loadConfig();
    expect(config.port).toBe(9090);
  });

  it("defaults port to 8081", () => {
    loadConfig();
    expect(config.port).toBe(8081);
  });
});
