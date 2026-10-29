import { describe, expect, it } from "vitest";
import { CONTRACT_VERSION, parseHealthResponse } from "./contract";

describe("API contract stub", () => {
  it("pins the contract version shared with the backend", () => {
    expect(CONTRACT_VERSION).toBe("0.7.0");
  });

  it("accepts a recorded /health payload", () => {
    const payload = {
      status: "ok",
      service: "strompilot-api",
      contract_version: "0.7.0",
    };
    expect(parseHealthResponse(payload)).toEqual(payload);
  });

  it("rejects malformed payloads", () => {
    expect(() => parseHealthResponse(null)).toThrow();
    expect(() => parseHealthResponse({ status: "ok" })).toThrow();
  });
});
