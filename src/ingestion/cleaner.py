import logging

logger = logging.getLogger(__name__)


class TextCleaner:

    UNICODE_REPLACEMENTS = {
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2014": "—",
        "\u2013": "–",
        "\u2026": "...",
    }

    ZERO_WIDTH_CHARS = {"\u200b", "\u200c", "\u200d", "\ufeff"}

    def clean(self, text: str) -> str:
        if not text:
            return ""

        text = self._remove_zero_width_chars(text)
        text = self._normalize_unicode(text)
        text = self._collapse_blank_lines(text)
        text = self._collapse_spaces(text)
        text = self._remove_noise_lines(text)

        return text.strip()

    def _remove_zero_width_chars(self, text: str) -> str:
        return "".join(ch for ch in text if ch not in self.ZERO_WIDTH_CHARS)

    def _normalize_unicode(self, text: str) -> str:
        for old, new in self.UNICODE_REPLACEMENTS.items():
            text = text.replace(old, new)
        return text

    def _collapse_blank_lines(self, text: str) -> str:
        lines = text.split("\n")
        result = []
        blank_count = 0

        for line in lines:
            if not line.strip():
                blank_count += 1
                if blank_count <= 1:
                    result.append("")
            else:
                blank_count = 0
                result.append(line)

        return "\n".join(result)

    def _collapse_spaces(self, text: str) -> str:
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            words = line.split()
            cleaned.append(" ".join(words))
        return "\n".join(cleaned)

    def _remove_noise_lines(self, text: str, min_words: int = 3) -> str:
        lines = text.split("\n")
        filtered = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                filtered.append(line)
                continue

            word_count = len(stripped.split())
            if word_count >= min_words:
                filtered.append(line)

        return "\n".join(filtered)
