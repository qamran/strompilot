/** API client aborts slow fetches with a friendly retry hint. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchMe } from "./api";

describe("api timeout", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("fails slow calls after 15 seconds with a retry hint", async () => {
    vi.stubGlobal(
      "fetch",
      (_url: string, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
        }),
    );
    const pending = fetchMe();
    const assertion = expect(pending).rejects.toThrow(/retry/i);
    await vi.advanceTimersByTimeAsync(15_000);
    await assertion;
  });
});
