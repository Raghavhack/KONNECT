"""
Tests for spaCy Text Preprocessor and Semantic Chunker.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.preprocessing.text_processor import TextProcessor
from app.preprocessing.chunker import SemanticChunker


def test_text_cleaning():
    processor = TextProcessor()
    raw = "Hello   world!\r\n\r\nThis is a   test\xa0string.\n\n\n\nNext line."
    cleaned = processor.clean_text(raw)
    assert "Hello world!" in cleaned
    assert "\r" not in cleaned
    assert "\xa0" not in cleaned


def test_sentence_splitting():
    processor = TextProcessor()
    text = "KONNECT is an intelligence platform. It processes dynamic documents. Does it support incremental updates? Yes it does!"
    sentences = processor.split_sentences(text)
    assert len(sentences) >= 3
    assert any("KONNECT" in s for s in sentences)


def test_entity_spotting():
    processor = TextProcessor()
    text = "Google Drive and Microsoft OneDrive provide cloud file storage for Apple Inc."
    entities = processor.extract_spotted_entities(text)
    assert len(entities) > 0
    names = [e["text"] for e in entities]
    assert any("Google" in n or "OneDrive" in n or "Apple" in n for n in names)


def test_semantic_chunker():
    processor = TextProcessor()
    chunker = SemanticChunker(processor=processor, chunk_size=30, chunk_overlap=10)
    text = (
        "Document ingestion begins here. Each document is parsed and cleaned. "
        "Sentences are grouped into semantic segments. Chunks maintain overlap for contextual continuity. "
        "Finally entities are spotted and indexed."
    )
    chunks = chunker.chunk_document(document_id="doc_test_1", text=text)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.document_id == "doc_test_1"
        assert len(c.text) > 0
        assert c.chunk_id is not None
