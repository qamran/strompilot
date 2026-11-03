/** Ask-why types mirroring the /ask endpoint in main.py. */

export interface AskCitation {
  title: string;
  source_name: string;
  source_url: string;
}

export interface AskAnswer {
  question: string;
  answer: string;
  citations: AskCitation[];
  model: string;
}

function asRecord(value: unknown, name: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null) {
    throw new Error(`${name} must be an object`);
  }
  return value as Record<string, unknown>;
}

function parseCitation(value: unknown): AskCitation {
  const record = asRecord(value, "AskCitation");
  if (
    typeof record.title !== "string" ||
    typeof record.source_name !== "string" ||
    typeof record.source_url !== "string"
  ) {
    throw new Error("AskCitation needs title, source_name, source_url");
  }
  return {
    title: record.title,
    source_name: record.source_name,
    source_url: record.source_url,
  };
}

export function parseAskAnswer(value: unknown): AskAnswer {
  const record = asRecord(value, "AskAnswer");
  if (
    typeof record.question !== "string" ||
    typeof record.answer !== "string" ||
    !Array.isArray(record.citations) ||
    typeof record.model !== "string"
  ) {
    throw new Error("AskAnswer needs question, answer, citations, model");
  }
  return {
    question: record.question,
    answer: record.answer,
    citations: record.citations.map(parseCitation),
    model: record.model,
  };
}
