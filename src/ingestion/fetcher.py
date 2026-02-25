import hashlib
import logging
import os
from abc import ABC, abstractmethod

import requests
from bs4 import BeautifulSoup

from config.settings import settings
from src.models import ProcessedSource, SourceMetadata

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):

    @abstractmethod
    def fetch(self, source: str) -> ProcessedSource:
        pass

    def _generate_id(self, source: str) -> str:
        return hashlib.md5(source.encode()).hexdigest()[:10]

    def _extract_text_from_html(self, html_content: str) -> tuple[str, str]:
        soup = BeautifulSoup(html_content, "lxml")

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        for unwanted in soup(
            [
                "script",
                "style",
                "noscript",
                "head",
                "meta",
                "link",
                "nav",
                "footer",
                "form",
            ]
        ):
            unwanted.decompose()

        text = soup.get_text(separator="\n", strip=True)
        return title, text


class URLFetcher(BaseFetcher):

    def fetch(self, url: str) -> ProcessedSource:
        source_id = self._generate_id(url)
        metadata = SourceMetadata(
            source_id=source_id, source_type="url", source_path=url
        )

        try:
            response = requests.get(
                url,
                timeout=settings.REQUEST_TIMEOUT,
                headers={"User-Agent": "ResearchDigestAgent/1.0"},
            )
            print(f"Fetching URL: {url} - Status Code: {response.status_code}")
            logger.info(f"Fetching URL: {url} - Status Code: {response.status_code}")

            response.raise_for_status()

            title, raw_text = self._extract_text_from_html(response.text)
            metadata.title = title
            metadata.char_length = len(raw_text)

            print(title)
            print(f"Character length: {metadata.char_length}")
            if not raw_text.strip():
                metadata.status = "empty"

            logger.info(f"Fetched URL: {url} ({metadata.char_length} chars)")
            return ProcessedSource(metadata=metadata, raw_text=raw_text)

        except requests.RequestException as e:
            metadata.status = "failed"
            metadata.error_message = str(e)
            logger.error(f"Failed to fetch {url}: {e}")
            return ProcessedSource(metadata=metadata)


class LocalFileFetcher(BaseFetcher):

    SUPPORTED = {".txt", ".html", ".htm"}

    def fetch(self, file_path: str) -> ProcessedSource:
        source_id = self._generate_id(file_path)
        metadata = SourceMetadata(
            source_id=source_id, source_type="local", source_path=file_path
        )

        try:
            self._validate_file(file_path)
            content = self._read_file(file_path)
            ext = os.path.splitext(file_path)[1].lower()

            if ext in {".html", ".htm"}:
                title, raw_text = self._extract_text_from_html(content)
                metadata.title = title
            else:
                raw_text = content
                metadata.title = os.path.basename(file_path)

            metadata.char_length = len(raw_text)

            if not raw_text.strip():
                metadata.status = "empty"

            logger.info(f"Read file: {file_path} ({metadata.char_length} chars)")
            return ProcessedSource(metadata=metadata, raw_text=raw_text)

        except (FileNotFoundError, ValueError, IOError) as e:
            metadata.status = "failed"
            metadata.error_message = str(e)
            logger.error(f"Failed to read {file_path}: {e}")
            return ProcessedSource(metadata=metadata)

    def _validate_file(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.SUPPORTED:
            raise ValueError(f"Unsupported file type: {ext}")

    def _read_file(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
