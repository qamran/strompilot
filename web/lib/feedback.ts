/** Feedback types mirroring the /feedback endpoints in main.py. */

export interface FeedbackEpisode {
  id: number;
  household_id: string;
  kind: string;
  text: string;
  created_at: string;
}

export interface WindowShift {
  earliest_shift_h: number;
  latest_shift_h: number;
}

export interface FeedbackResponse {
  household_id: string;
  episode: FeedbackEpisode;
  learned_windows: Record<string, WindowShift>;
}

export interface FeedbackListResponse {
  household_id: string;
  feedback: FeedbackEpisode[];
}

function parseEpisode(value: unknown): FeedbackEpisode {
  if (typeof value !== "object" || value === null) {
    throw new Error("FeedbackEpisode must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.id !== "number" ||
    typeof record.household_id !== "string" ||
    typeof record.kind !== "string" ||
    typeof record.text !== "string" ||
    typeof record.created_at !== "string"
  ) {
    throw new Error("FeedbackEpisode has invalid fields");
  }
  return {
    id: record.id,
    household_id: record.household_id,
    kind: record.kind,
    text: record.text,
    created_at: record.created_at,
  };
}

function parseShift(value: unknown): WindowShift {
  if (typeof value !== "object" || value === null) {
    throw new Error("WindowShift must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.earliest_shift_h !== "number" ||
    typeof record.latest_shift_h !== "number"
  ) {
    throw new Error("WindowShift has invalid fields");
  }
  return {
    earliest_shift_h: record.earliest_shift_h,
    latest_shift_h: record.latest_shift_h,
  };
}

function parseLearned(value: unknown): Record<string, WindowShift> {
  if (typeof value !== "object" || value === null) {
    throw new Error("learned_windows must be an object");
  }
  const record = value as Record<string, unknown>;
  const parsed: Record<string, WindowShift> = {};
  for (const [name, shift] of Object.entries(record)) {
    parsed[name] = parseShift(shift);
  }
  return parsed;
}

export function parseFeedbackResponse(value: unknown): FeedbackResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("FeedbackResponse must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.household_id !== "string" ||
    typeof record.episode !== "object" ||
    typeof record.learned_windows !== "object"
  ) {
    throw new Error("FeedbackResponse has invalid fields");
  }
  return {
    household_id: record.household_id,
    episode: parseEpisode(record.episode),
    learned_windows: parseLearned(record.learned_windows),
  };
}

export function parseFeedbackListResponse(value: unknown): FeedbackListResponse {
  if (typeof value !== "object" || value === null) {
    throw new Error("FeedbackListResponse must be an object");
  }
  const record = value as Record<string, unknown>;
  if (
    typeof record.household_id !== "string" ||
    !Array.isArray(record.feedback)
  ) {
    throw new Error("FeedbackListResponse has invalid fields");
  }
  return {
    household_id: record.household_id,
    feedback: record.feedback.map(parseEpisode),
  };
}
