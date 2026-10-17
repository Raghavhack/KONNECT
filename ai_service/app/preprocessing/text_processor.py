"""
Production spaCy-based Text Preprocessor.
Performs tokenization, sentence segmentation, entity spotting, and text normalization.
Critically sits on the fast path of the edit -> updated answer latency pipeline.
"""

import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try importing spacy
try:
    import spacy
    from spacy.language import Language
    SPACY_AVAILABLE = True
except ImportError:
    spacy = None
    Language = None
    SPACY_AVAILABLE = False


class TextProcessor:
    """
    High-performance text preprocessing pipeline powered by spaCy.
    Falls back gracefully to rule-based segmentation if spaCy or model weights are missing.
    """

    def __init__(self, model_name: str = "en_core_web_sm"):
        self.model_name = model_name
        self.nlp = None
        self._initialize_spacy()

    def _initialize_spacy(self) -> None:
        """Loads spaCy model with optimized disabled pipes for speed."""
        if not SPACY_AVAILABLE:
            logger.warning("spaCy is not installed. Falling back to rule-based text processing.")
            return

        try:
            # We enable tagger, parser (or senter), and ner for high-throughput pipeline
            self.nlp = spacy.load(self.model_name)
            logger.info(f"Loaded spaCy model '{self.model_name}' successfully.")
        except Exception as e:
            logger.warning(
                f"Could not load spaCy model '{self.model_name}' ({e}). "
                "Attempting blank 'en' model or fallback."
            )
            try:
                self.nlp = spacy.blank("en")
                self.nlp.add_pipe("sentencizer")
                logger.info("Initialized fallback blank spaCy pipeline with sentencizer.")
            except Exception as e2:
                logger.warning(f"Could not initialize blank spaCy pipeline: {e2}. Using regex fallback.")
                self.nlp = None

    def clean_text(self, text: str) -> str:
        """Cleans input text by normalizing whitespace, unicode, and carriage returns."""
        if not text:
            return ""
        # Normalize carriage returns and non-breaking spaces
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
        # Collapse multiple spaces while preserving paragraph breaks
        text = re.sub(r"[ \t]+", " ", text)
        # Collapse excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def split_sentences(self, text: str) -> List[str]:
        """Splits text into sentences using spaCy parser/sentencizer or regex."""
        cleaned = self.clean_text(text)
        if not cleaned:
            return []

        if self.nlp is not None:
            doc = self.nlp(cleaned)
            return [sent.text.strip() for sent in doc.sents if sent.text.strip()]

        # Fallback regex sentence splitter
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", cleaned)
        return [s.strip() for s in sentences if s.strip()]

    def extract_spotted_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Fast candidate Named Entity Recognition using spaCy.
        Returns list of dicts with text, label, start_char, end_char.
        """
        cleaned = self.clean_text(text)
        if not cleaned:
            return []

        if self.nlp is not None and self.nlp.has_pipe("ner"):
            doc = self.nlp(cleaned)
            return [
                {
                    "text": ent.text,
                    "label": ent.label_,
                    "start_char": ent.start_char,
                    "end_char": ent.end_char,
                }
                for ent in doc.ents
            ]

        # Fast heuristic/regex entity detector (capitalized sequences)
        pattern = r"\b[A-Z][a-zA-Z0-9_]+(?:\s+[A-Z][a-zA-Z0-9_]+)*\b"
        matches = []
        for match in re.finditer(pattern, cleaned):
            text_match = match.group(0)
            if len(text_match) > 1:
                matches.append({
                    "text": text_match,
                    "label": "CANDIDATE",
                    "start_char": match.start(),
                    "end_char": match.end(),
                })
        return matches

    def tokenize_words(self, text: str) -> List[str]:
        """Fast tokenization returning clean tokens without punctuation/stopwords."""
        cleaned = self.clean_text(text)
        if not cleaned:
            return []

        if self.nlp is not None:
            doc = self.nlp(cleaned)
            return [token.text for token in doc if not token.is_space]

        return re.findall(r"\b\w+\b", cleaned)
