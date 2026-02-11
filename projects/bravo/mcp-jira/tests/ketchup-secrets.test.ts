import { describe, it, expect, vi, beforeEach } from "vitest";

const mockSend = vi.fn();

vi.mock("@aws-sdk/client-secrets-manager", () => ({
  SecretsManagerClient: vi.fn(() => ({ send: mockSend })),
  GetSecretValueCommand: vi.fn((input: unknown) => input),
}));

import { getIpaasAuth, _resetForTesting } from "../src/ketchup-secrets.js";

beforeEach(() => {
  _resetForTesting();
  delete process.env.JIRA_IMS_TOKEN;
  delete process.env.JIRA_API_KEY;
  process.env.USE_AWS_SECRETS = "true";
  vi.restoreAllMocks();
});

describe("getIpaasAuth", () => {
  it("returns env var override when both set", async () => {
    process.env.JIRA_IMS_TOKEN = "env-ims";
    process.env.JIRA_API_KEY = "env-key";

    const result = await getIpaasAuth();

    expect(result).toEqual({ imsToken: "env-ims", apiKey: "env-key" });
    expect(mockSend).not.toHaveBeenCalled();
  });

  it("fetches from AWS on first call", async () => {
    mockSend.mockResolvedValue({
      SecretString: JSON.stringify({
        ims_access_token: "aws-ims",
        ipaas_api_key: "aws-key",
      }),
    });

    const result = await getIpaasAuth();

    expect(result).toEqual({ imsToken: "aws-ims", apiKey: "aws-key" });
    expect(mockSend).toHaveBeenCalledOnce();
  });

  it("returns cached on second call within TTL", async () => {
    mockSend.mockResolvedValue({
      SecretString: JSON.stringify({
        ims_access_token: "aws-ims",
        ipaas_api_key: "aws-key",
      }),
    });

    await getIpaasAuth();
    await getIpaasAuth();

    expect(mockSend).toHaveBeenCalledOnce();
  });

  it("re-fetches after TTL expires", async () => {
    vi.useFakeTimers();
    mockSend.mockResolvedValue({
      SecretString: JSON.stringify({
        ims_access_token: "aws-ims",
        ipaas_api_key: "aws-key",
      }),
    });

    await getIpaasAuth();
    vi.advanceTimersByTime(5 * 60 * 1000 + 1);
    await getIpaasAuth();

    expect(mockSend).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("throws on empty SecretString", async () => {
    mockSend.mockResolvedValue({ SecretString: "" });

    await expect(getIpaasAuth()).rejects.toThrow("empty SecretString");
  });

  it("throws when required keys missing", async () => {
    mockSend.mockResolvedValue({
      SecretString: JSON.stringify({ some_other_key: "value" }),
    });

    await expect(getIpaasAuth()).rejects.toThrow(
      "missing ims_access_token or ipaas_api_key"
    );
  });
});
