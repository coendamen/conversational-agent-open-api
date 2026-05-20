import logging
import random
import time
from urllib.parse import urlparse, quote_plus

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

        url = f"https://duckduckgo.com/html/?q={encoded}&kl=us-en&df=d"

        headers = {"User-Agent": random.choice(self.DEFAULT_UAS)}

        logging.info(f"[DDG] Searching DuckDuckGo for: {url}")

        self.session = requests.Session()

        r = self.session.get(url, headers=self.BROWSER_HEADERS, timeout=self.timeout)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        logging.info(f"[DDG] Parsing search results for query: {soup}")

        links = []
        for a in soup.select(".result__a"):
            href = a.get("href")
            if href and href.startswith("http"):
                links.append(href)
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

                headers = {"User-Agent": random.choice(self.DEFAULT_UAS)}
                proxy = self._pick_proxy()

                logging.debug(f"[Scraper] Attempt {attempt} → {url}")

                r = requests.get(
                    url,
                    headers=headers,
                    proxies=proxy,
                    timeout=self.timeout,
                )
                r.raise_for_status()

                if len(r.text) < 50 and self.enable_js_fallback:
                    logging.info("[Scraper] HTML too small, using JS fallback")
                    return self._js_fallback(url)

                return r.text

            except Exception as e:
                logging.warning(f"[Scraper] Attempt {attempt} failed: {e}")

                if attempt == self.max_retries:
                    raise

                time.sleep(1.5 * attempt + random.random())

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

    def _extract_snippet(self, html, max_chars=350):
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
