import { describe, expect, it } from "vitest";

import { parseApprovalStatus } from "./approvals";

const REVIEW = {
  type: "plan_approval",
  schedule: [
    {
      device: "Waschmaschine",
      start: "02:00",
      end: "04:00",
      reason: "billig",
      energy_kwh: 4.0,
      price_ct_kwh: 15.0,
      cost_eur: 0.6,
    },
  ],
  total_cost_eur: 0.6,
  narration: "Wasche nachts.",
};

describe("parseApprovalStatus", () => {
  it("parses a paused thread with its review", () => {
    expect(
      parseApprovalStatus({
        thread_id: "t1",
        status: "paused",
        published: false,
        review: REVIEW,
        error: null,
      }),
    ).toEqual({
      thread_id: "t1",
      status: "paused",
      published: false,
      review: REVIEW,
      error: null,
    });
  });

  it("parses a published thread", () => {
    expect(
      parseApprovalStatus({
        thread_id: "t1",
        status: "published",
        published: true,
        review: null,
        error: null,
      }),
    ).toEqual({
      thread_id: "t1",
      status: "published",
      published: true,
      review: null,
      error: null,
    });
  });

  it("rejects invalid payloads", () => {
    expect(() => parseApprovalStatus(null)).toThrow();
    expect(() =>
      parseApprovalStatus({ thread_id: "t1", status: "paused" }),
    ).toThrow();
    expect(() =>
      parseApprovalStatus({
        thread_id: "t1",
        status: "paused",
        published: false,
        review: { type: "plan_approval" },
        error: null,
      }),
    ).toThrow();
  });
});
