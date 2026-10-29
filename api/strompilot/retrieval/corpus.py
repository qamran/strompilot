"""Rule corpus loader."""

import json
from pathlib import Path

from pydantic import BaseModel

DATA_PATH = Path(__file__).parent / "data" / "corpus.json"


class Document(BaseModel):
    """One sourced rule document in German."""

    id: str
    title: str
    body: str
    source_name: str
    source_url: str


def load_corpus() -> list[Document]:
    """Load all corpus documents from the packaged JSON file."""
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return [Document.model_validate(item) for item in payload["documents"]]
