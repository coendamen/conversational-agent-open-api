import logging
import random
import re
import time
from urllib.parse import quote_plus
from urllib.parse import urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup


class ResilientDuckDuckGoScraper:
    """
    A resilient scraper that:
    - Performs DuckDuckGo search
    - Extracts top result URLs
    - Scrapes each URL with retries, UA rotation, throttling
    - Cleans and returns readable text
    - Returns tool-compatible schema
    """

    DEFAULT_UAS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/125.0",
    ]

    BROWSER_HEADERS = {
        "User-Agent": random.choice(DEFAULT_UAS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    def __init__(
            self,
            max_retries=4,
            timeout=12,
            proxies=None,
            enable_js_fallback=False,
            throttle=True,
    ):
        self.max_retries = max_retries
        self.timeout = timeout
        self.proxies = proxies or []
        self.enable_js_fallback = enable_js_fallback
        self.throttle = throttle
        self.last_domain_access = {}

    # ---------------------------------------------------------
    # Public API (tool-compatible)
    # ---------------------------------------------------------
    def search_and_scrape(self, query: str, max_results=5):
        """
        Returns a plain string because Qwen tool calls expect string output.
        """

        urls = self._duckduckgo_search(query, max_results=max_results)

        results = []
        for url in urls:
            logging.info(f"[Scraper] Fetching URL: {url}")
            scraped = self.fetch(url)
            results.append(scraped)

        # Convert results to a single string
        formatted = "\n\n".join(
            f"URL: {r['url']}\nSTATUS: {r['status']}\nCONTENT:\n{r.get('content') or r.get('error')}"
            for r in results
        )

        return formatted

    # ---------------------------------------------------------
    # DuckDuckGo Search
    # ---------------------------------------------------------
    def _duckduckgo_search(self, query, max_results=5):
        """
        DuckDuckGo HTML search that supports:
        - multi-word queries
        - dates
        - commas
        - natural language
        """

        # Normalize query
        cleaned = query.replace(",", " ").strip()
        cleaned = " ".join(cleaned.split())  # collapse multiple spaces

        encoded = quote_plus(cleaned)

        links = []

        for page in range(3):  # 0, 1, 2
            offset = page * 5  # real DDG pagination: 0, 5, 10

            paged_url = (
                f"https://duckduckgo.com/html/?q={encoded}"
                f"&kl=us-en&df=d&s={offset}"
            )

            logging.info(f"[DDG] Searching DuckDuckGo page {page}: {paged_url}")

            self.session = requests.Session()

            r = self.session.get(paged_url, headers=self.BROWSER_HEADERS, timeout=self.timeout)
            r.raise_for_status()

            soup = BeautifulSoup(r.text, "html.parser")

            for a in soup.select("a.result__a"):
                href = a.get("href")
                real_url = self._decode_ddg_link(href)
                links.append(real_url)

                if len(links) >= max_results:
                    break

            if len(links) >= max_results:
                break

        logging.info(f"[DDG] Found {len(links)} results for query: {cleaned}")
        return links

    # ---------------------------------------------------------
    # Resilient fetch
    # ---------------------------------------------------------
    def fetch(self, url: str) -> dict:
        try:
            html = self._fetch_resilient(url)
            text = self._extract_snippet(html)
            return {"url": url, "status": "ok", "content": text}

        except Exception as e:
            return {"url": url, "status": "error", "content": None, "error": str(e)}

    def _fetch_resilient(self, url):
        domain = urlparse(url).netloc

        for attempt in range(1, self.max_retries + 1):
            try:
                self._throttle_domain(domain)

                proxy = self._pick_proxy()

                logging.debug(f"[Scraper] Attempt {attempt} → {url}")

                r = requests.get(
                    url,
                    headers=self.BROWSER_HEADERS,
                    proxies=proxy,
                    timeout=self.timeout,
                )
                r.raise_for_status()

                if len(r.text) < 50 and self.enable_js_fallback:
                    logging.info("[Scraper] HTML too small, using JS fallback")
                    return self._js_fallback(url)

                return r.text

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code
                logging.warning(f"[Scraper] HTTP error {status} on attempt {attempt}")

                if status in (400, 401, 403):
                    raise

                if attempt == self.max_retries:
                    raise

                time.sleep(1.5 * attempt + random.random())

            except Exception as e:
                logging.warning(f"[Scraper] Attempt {attempt} failed: {e}")

                if attempt == self.max_retries:
                    raise

                time.sleep(1.5 * attempt + random.random())
        return None

    # ---------------------------------------------------------
    # JS fallback hook
    # ---------------------------------------------------------
    def _js_fallback(self, url):
        raise RuntimeError("JS fallback not implemented")

    # ---------------------------------------------------------
    # Throttling
    # ---------------------------------------------------------
    def _throttle_domain(self, domain):
        if not self.throttle:
            return

        now = time.time()
        last = self.last_domain_access.get(domain, 0)

        if now - last < 1.2:
            time.sleep(1.2 - (now - last))

        self.last_domain_access[domain] = time.time()

    # ---------------------------------------------------------
    # Proxy rotation
    # ---------------------------------------------------------
    def _pick_proxy(self):
        if not self.proxies:
            return None
        p = random.choice(self.proxies)
        return {"http": p, "https": p}

    # ---------------------------------------------------------
    # Clean text extraction
    # ---------------------------------------------------------

    def _extract_snippet(self, html, max_chars=200):
        """
        Extracts a short snippet from the page.
        - Removes scripts, nav, ads, etc.
        - Returns the first meaningful text block.
        - max_chars controls snippet length.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        if not lines:
            return ""

        snippet = " ".join(lines)[:max_chars].rstrip()

        return snippet + "..."

    def _decode_ddg_link(self, href):
        if href.startswith("//duckduckgo.com/l/?"):
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
        return href

    def scrape_direct(self, url):
        try:
            html = requests.get(url, headers=self.BROWSER_HEADERS, timeout=10).text
            logging.info(f"Successfully scraped {url} (length: {html})")
            return html
        except Exception as e:
            return f"Error scraping {url}: {e}"

    def is_url(text):
        return re.match(r'https?://|^[\w\-]+\.\w{2,}', text) is not None
