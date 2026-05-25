import logging
import random
import time
from urllib.parse import urlparse, parse_qs, unquote, quote_plus

import requests
from bs4 import BeautifulSoup


class ResilientGoogleScraper:
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

    def __init__(self, max_retries=4, timeout=12, proxies=None, throttle=True):
        self.max_retries = max_retries
        self.timeout = timeout
        self.proxies = proxies or []
        self.throttle = throttle
        self.last_domain_access = {}


    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    def search_and_scrape(self, query: str, max_results=5):
        urls = self._google_search(query, max_results=max_results)

        results = []
        for url in urls:
            scraped = self.fetch(url)
            results.append(scraped)

        formatted = "\n\n".join(
            f"URL: {r['url']}\nSTATUS: {r['status']}\nCONTENT:\n{r.get('content') or r.get('error')}"
            for r in results
        )
        return formatted


    def _google_search(self, query, max_results=5):
        cleaned = " ".join(query.replace(",", " ").split())
        encoded = quote_plus(cleaned)

        url = f"https://www.google.com/search?q={encoded}&hl=en&num={max_results}"

        logging.info(f"[Google] Searching: {url}")
        logging.info(f"[Google] Using UA: {self.BROWSER_HEADERS['User-Agent']}")

        r = requests.get(url, headers=self.BROWSER_HEADERS, timeout=self.timeout)
        logging.info(f"[Google] HTTP {r.status_code}, final URL: {r.url}")
        logging.info(f"[Google] Content: {r.text}")

        r.raise_for_status()

        html = r.text
        soup = BeautifulSoup(html, "html.parser")

        # ---------------------------------------------------------
        # DEEP DIAGNOSTICS
        # ---------------------------------------------------------
        logging.debug("========== GOOGLE HTML (FIRST 2000 CHARS) ==========")
        logging.debug(html[:2000])

        logging.debug("========== GOOGLE HTML (LAST 2000 CHARS) ==========")
        logging.debug(html[-2000:])

        logging.debug(f"[Google] Tag counts: "
                      f"a={len(soup.find_all('a'))}, "
                      f"div={len(soup.find_all('div'))}, "
                      f"script={len(soup.find_all('script'))}, "
                      f"form={len(soup.find_all('form'))}, "
                      f"noscript={len(soup.find_all('noscript'))}")

        # ---------------------------------------------------------
        # BOT DETECTION MARKERS
        # ---------------------------------------------------------
        markers = {
            "unusual traffic": "Google thinks you're a bot",
            "/sorry/": "Google 'Sorry' page",
            "detected unusual": "Bot detection",
            "validate your request": "CAPTCHA page",
            "id=\"captcha\"": "CAPTCHA element",
            "please show you're not a robot": "Robot check",
            "before you continue": "Consent page",
            "consent.google.com": "Consent redirect",
            "g-recaptcha": "Invisible CAPTCHA",
            "window._cf_chl_opt": "Cloudflare challenge",
            "js-required": "JS-only SERP",
        }

        for key, meaning in markers.items():
            if key.lower() in html.lower():
                logging.error(f"[Google] BOT DETECTION MARKER FOUND: {meaning} ({key})")
                return []

        # ---------------------------------------------------------
        # NORMAL EXTRACTION
        # ---------------------------------------------------------
        links = []

        # 1. Standard
        std_links = soup.select("a[href^='/url?q=']")
        logging.debug(f"[Google] Standard selector matches: {len(std_links)}")

        for a in std_links:
            href = a.get("href")
            real = self._decode_google_link(href)
            if real:
                links.append(real)
            if len(links) >= max_results:
                logging.info(f"[Google] Extracted URLs: {links}")
                return links

        # 2. Mobile
        mobile_links = soup.select("a[jsname='UWckNb']")
        logging.debug(f"[Google] Mobile selector matches: {len(mobile_links)}")

        for a in mobile_links:
            href = a.get("href", "")
            if href.startswith("/url?q="):
                real = self._decode_google_link(href)
                if real:
                    links.append(real)
            if len(links) >= max_results:
                logging.info(f"[Google] Extracted URLs: {links}")
                return links

        # 3. data-hveid
        hveid_links = soup.select("div[data-hveid] a")
        logging.debug(f"[Google] data-hveid selector matches: {len(hveid_links)}")

        for div in hveid_links:
            href = div.get("href", "")
            if href.startswith("/url?q="):
                real = self._decode_google_link(href)
                if real:
                    links.append(real)
            if len(links) >= max_results:
                logging.info(f"[Google] Extracted URLs: {links}")
                return links

        logging.warning("[Google] No results found — Google likely returned a bot-detection page")
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

                r = requests.get(
                    url,
                    headers=self.BROWSER_HEADERS,
                    proxies=proxy,
                    timeout=self.timeout,
                )
                r.raise_for_status()
                return r.text

            except Exception as e:
                logging.warning(f"[Scraper] Attempt {attempt} failed: {e}")
                if attempt == self.max_retries:
                    raise
                time.sleep(1.5 * attempt + random.random())


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
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return ""
        snippet = " ".join(lines)[:max_chars].rstrip()
        return snippet + "..."


    # ---------------------------------------------------------
    # Google link decoding
    # ---------------------------------------------------------
    def _decode_google_link(self, href):
        # href looks like: /url?q=https://example.com&sa=U&ved=...
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        if "q" in qs:
            return unquote(qs["q"][0])
        return None
