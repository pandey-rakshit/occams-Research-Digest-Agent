import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ingestion.fetcher import URLFetcher, LocalFileFetcher
from src.ingestion.cleaner import TextCleaner


class TestURLFetcher:

    def test_unreachable_url_returns_failed_status(self):
        fetcher = URLFetcher()
        result = fetcher.fetch("https://thisdomaindoesnotexist12345.com/page")
        assert result.metadata.status == "failed"
        assert result.metadata.error_message is not None
        assert result.raw_text == ""

    def test_invalid_url_returns_failed_status(self):
        fetcher = URLFetcher()
        result = fetcher.fetch("not-a-valid-url")
        assert result.metadata.status == "failed"

    def test_each_url_gets_unique_source_id(self):
        fetcher = URLFetcher()
        r1 = fetcher.fetch("https://example.com/page1")
        r2 = fetcher.fetch("https://example.com/page2")
        assert r1.metadata.source_id != r2.metadata.source_id


class TestLocalFileFetcher:

    def test_nonexistent_file_returns_failed(self):
        fetcher = LocalFileFetcher()
        result = fetcher.fetch("/nonexistent/path/to/file.txt")
        assert result.metadata.status == "failed"
        assert "not found" in result.metadata.error_message.lower()

    def test_empty_file_returns_empty_status(self):
        fetcher = LocalFileFetcher()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            path = f.name
        try:
            result = fetcher.fetch(path)
            assert result.metadata.status == "empty"
        finally:
            os.unlink(path)

    def test_reads_txt_file_with_real_article_content(self):
        fetcher = LocalFileFetcher()
        content = (
            "The European Union has enacted the world's first comprehensive AI regulation. "
            "Known as the AI Act, this landmark legislation categorizes AI systems by risk levels. "
            "High-risk systems face strict requirements including conformity assessments and human oversight. "
            "The Act bans certain practices like social scoring and real-time biometric identification. "
            "Implementation will be phased, with full enforcement expected by 2026. "
            "Critics worry about stifling innovation, while supporters say clear rules build trust."
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            result = fetcher.fetch(path)
            assert result.metadata.status == "success"
            assert result.metadata.char_length > 300
            assert "AI regulation" in result.raw_text or "AI Act" in result.raw_text
        finally:
            os.unlink(path)

    def test_parses_html_with_nested_structure(self):
        fetcher = LocalFileFetcher()
        html = """<!DOCTYPE html>
        <html>
        <head><title>AI Regulation Report</title></head>
        <body>
            <nav><a href="/">Home</a><a href="/about">About</a></nav>
            <main>
                <h1>Global AI Regulation Landscape</h1>
                <p>The European Union has taken the lead with its comprehensive AI Act,
                which categorizes AI systems into risk tiers and imposes corresponding
                requirements on developers and deployers.</p>
                <p>Meanwhile, the United States relies more heavily on voluntary frameworks
                and sector-specific regulation, though state-level legislation is increasing.</p>
            </main>
            <footer>Copyright 2025</footer>
            <script>console.log("tracking");</script>
        </body>
        </html>"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(html)
            path = f.name
        try:
            result = fetcher.fetch(path)
            assert result.metadata.status == "success"
            assert result.metadata.title == "AI Regulation Report"
            assert "European Union" in result.raw_text
            assert "tracking" not in result.raw_text
            assert "Home" not in result.raw_text
        finally:
            os.unlink(path)

    def test_rejects_unsupported_file_type(self):
        fetcher = LocalFileFetcher()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as f:
            f.write("fake pdf")
            path = f.name
        try:
            result = fetcher.fetch(path)
            assert result.metadata.status == "failed"
        finally:
            os.unlink(path)

    def test_handles_file_with_encoding_issues(self):
        fetcher = LocalFileFetcher()
        content = "Caf\u00e9 culture and na\u00efve approaches to AI regulation in Montr\u00e9al."
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            result = fetcher.fetch(path)
            assert result.metadata.status == "success"
            assert "Montr" in result.raw_text
        finally:
            os.unlink(path)


class TestTextCleaner:

    def test_handles_none_and_empty(self):
        cleaner = TextCleaner()
        assert cleaner.clean("") == ""
        assert cleaner.clean(None) == ""

    def test_collapses_excessive_whitespace(self):
        cleaner = TextCleaner()
        text = "This is the first paragraph.\n\n\n\n\nThis is the second paragraph.\n\n\n\nThis is the third paragraph."
        result = cleaner.clean(text)
        assert "\n\n\n" not in result
        assert "first paragraph" in result
        assert "third paragraph" in result

    def test_removes_noise_lines_but_keeps_sentences(self):
        cleaner = TextCleaner()
        text = (
            "Home\n"
            "Menu\n"
            "The AI Act establishes a comprehensive framework for regulating artificial intelligence.\n"
            "OK\n"
            "This regulation applies to all AI systems deployed within the European Union."
        )
        result = cleaner.clean(text)
        assert "comprehensive framework" in result
        assert "European Union" in result

    def test_normalizes_smart_quotes(self):
        cleaner = TextCleaner()
        text = "\u201cAI regulation\u201d is \u2018essential\u2019 for public safety\u2014experts say."
        result = cleaner.clean(text)
        assert '"AI regulation"' in result
        assert "'essential'" in result

    def test_handles_real_webpage_noise(self):
        cleaner = TextCleaner()
        text = (
            "Skip to content\n"
            "Search\n"
            "EN\n"
            "\n"
            "The rapid advancement of artificial intelligence has prompted governments worldwide "
            "to develop regulatory frameworks. The European Union leads with its AI Act, while "
            "the United States takes a more sector-specific approach. China has implemented "
            "targeted regulations for specific AI applications including generative AI and "
            "algorithmic recommendation systems.\n"
            "\n"
            "Share\n"
            "Tweet\n"
            "© 2025 All rights reserved."
        )
        result = cleaner.clean(text)
        assert "artificial intelligence" in result
        assert "Share" not in result
        assert "Tweet" not in result
