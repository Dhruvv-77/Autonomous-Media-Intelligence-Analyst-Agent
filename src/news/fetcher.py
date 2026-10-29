"""Safe article fetching, SSRF protection, body extraction, and exact body preservation."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
import trafilatura
from src.models import Article, BodyStatus


class SafeFetcher:
    def __init__(
        self,
        timeout_seconds: int = 20,
        max_retries: int = 3,
        blocked_hosts: list[str] | None = None
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.blocked_hosts = set(blocked_hosts or [
            "localhost",
            "127.0.0.1",
            "::1",
            "169.254.169.254",
            "metadata.google.internal",
        ])

    def is_safe_url(self, url: str) -> bool:
        """Validates that a URL does not resolve to private, loopback, or cloud-metadata IPs."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            hostname = parsed.hostname
            if not hostname:
                return False
            if hostname.lower() in self.blocked_hosts:
                return False

            # Check resolved IP address
            try:
                ip_info = socket.getaddrinfo(hostname, None)
                for addr in ip_info:
                    ip_str = addr[4][0]
                    ip = ipaddress.ip_address(ip_str)
                    if (
                        ip.is_private
                        or ip.is_loopback
                        or ip.is_link_local
                        or ip.is_reserved
                        or ip.is_multicast
                    ):
                        return False
            except socket.gaierror:
                return False

            return True
        except Exception:
            return False

    def fetch_article_body(self, article: Article) -> Article:
        """Fetches full article text if URL is safe, preserving body text unmodified."""
        if article.body and len(article.body.strip()) > 50:
            article.body_status = BodyStatus.FULL
            return article

        if not self.is_safe_url(article.url):
            article.body_status = BodyStatus.BLOCKED
            article.retrieval_error = "URL blocked by SSRF safety policy"
            return article

        headers = {
            "User-Agent": "AutonomousMediaIntelligenceBot/1.0 (+https://example.com/bot; compliance-contact@example.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        transport = httpx.HTTPTransport(retries=self.max_retries)
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=transport, follow_redirects=True) as client:
                resp = client.get(article.url, headers=headers)
                if resp.status_code == 200:
                    html_content = resp.text
                    extracted_text = trafilatura.extract(
                        html_content,
                        include_comments=False,
                        include_tables=False,
                        no_fallback=False
                    )
                    
                    if not extracted_text:
                        # Fallback to BeautifulSoup clean text extraction
                        soup = BeautifulSoup(html_content, "html.parser")
                        for tag in soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()
                        paragraphs = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 20]
                        extracted_text = "\n\n".join(paragraphs)

                    if extracted_text and len(extracted_text.strip()) > 50:
                        # Store exact un-normalized extracted body to enable exact slice indexing
                        article.body = extracted_text.strip()
                        article.body_status = BodyStatus.FULL
                    else:
                        article.body_status = BodyStatus.METADATA_ONLY
                elif resp.status_code in (401, 403):
                    article.body_status = BodyStatus.BLOCKED
                    article.retrieval_error = f"HTTP {resp.status_code} Access Denied / Paywall"
                else:
                    article.body_status = BodyStatus.FAILED
                    article.retrieval_error = f"HTTP {resp.status_code}"
        except Exception as e:
            article.body_status = BodyStatus.FAILED
            article.retrieval_error = str(e)

        return article
