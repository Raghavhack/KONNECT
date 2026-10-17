"""
Semantic Document Chunker.
Splits documents into overlapping chunks respecting sentence boundaries and token budgets.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import hashlib

from .text_processor import TextProcessor


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    start_char: int
    end_char: int
    token_count: int
    detected_entities: List[str] = field(default_factory=list)


class SemanticChunker:
    """
    Chunks document content into semantic segments respecting sentence boundaries
    and token overlaps.
    """

    def __init__(
        self,
        processor: Optional[TextProcessor] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.processor = processor or TextProcessor()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, document_id: str, text: str) -> List[Chunk]:
        """
        Splits document text into a list of Chunk objects.
        Ensures chunks do not break in the middle of sentences where possible.
        """
        cleaned = self.processor.clean_text(text)
        if not cleaned:
            return []

        sentences = self.processor.split_sentences(cleaned)
        if not sentences:
            sentences = [cleaned]

        chunks: List[Chunk] = []
        current_sentences: List[str] = []
        current_tokens = 0
        current_start_char = 0
        chunk_idx = 0

        # Estimate tokens roughly as len(words)
        for sentence in sentences:
            sent_tokens = len(self.processor.tokenize_words(sentence))
            if sent_tokens == 0:
                sent_tokens = 1

            if current_tokens + sent_tokens > self.chunk_size and current_sentences:
                chunk_text = " ".join(current_sentences)
                chunk_end_char = current_start_char + len(chunk_text)
                chunk_id = hashlib.sha256(
                    f"{document_id}:{chunk_idx}:{chunk_text[:30]}".encode()
                ).hexdigest()[:16]

                spotted = [
                    e["text"]
                    for e in self.processor.extract_spotted_entities(chunk_text)
                ]

                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        chunk_index=chunk_idx,
                        text=chunk_text,
                        start_char=current_start_char,
                        end_char=chunk_end_char,
                        token_count=current_tokens,
                        detected_entities=list(set(spotted)),
                    )
                )
                chunk_idx += 1

                # Calculate overlap sentences
                overlap_sentences: List[str] = []
                overlap_tokens = 0
                for s in reversed(current_sentences):
                    s_tok = len(self.processor.tokenize_words(s))
                    if overlap_tokens + s_tok <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_tokens += s_tok
                    else:
                        break

                current_sentences = overlap_sentences + [sentence]
                current_tokens = overlap_tokens + sent_tokens
                # Update start char approximately
                current_start_char = max(0, chunk_end_char - sum(len(s) + 1 for s in overlap_sentences))
            else:
                current_sentences.append(sentence)
                current_tokens += sent_tokens

        # Tail chunk
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            chunk_end_char = current_start_char + len(chunk_text)
            chunk_id = hashlib.sha256(
                f"{document_id}:{chunk_idx}:{chunk_text[:30]}".encode()
            ).hexdigest()[:16]

            spotted = [
                e["text"]
                for e in self.processor.extract_spotted_entities(chunk_text)
            ]

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    chunk_index=chunk_idx,
                    text=chunk_text,
                    start_char=current_start_char,
                    end_char=chunk_end_char,
                    token_count=current_tokens,
                    detected_entities=list(set(spotted)),
                )
            )

        return chunks
