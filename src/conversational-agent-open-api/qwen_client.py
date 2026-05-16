import json

import requests
from bs4 import BeautifulSoup


class QwenClient:
    def __init__(self, base_url="http://host.docker.internal:8000/v1/chat/completions", debug=False):
        self.base_url = base_url
        self.model = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"
        self.debug = debug

    # --- Fetch readable text from a webpage ---
    def fetch_page_text(self, url):
        """Extract clean, readable text from a webpage via web crawl."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }

        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
        except Exception as e:
            return f"[Failed to fetch {url}: {e}]"

        soup = BeautifulSoup(r.text, "html.parser")

        # Remove scripts, styles, nav, footer, etc.
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())

        return cleaned[:5000]  # limit to avoid overloading Qwen

    # --- Web crawler: Google search + page fetching ---
    def web_search(self, query: str):
        """
        Search Google via web crawling (no API) and fetch page content.
        Returns top 3 pages with title, URL, and content.
        """
        url = "https://www.google.com/search"
        params = {"q": query}

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }

        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
        except Exception as e:
            return f"[Web search failed: {e}]"

        soup = BeautifulSoup(r.text, "html.parser")
        results = []

        # Parse Google search results
        for g in soup.select("div.g"):
            title_elem = g.select_one("h3")
            link_elem = g.select_one("a")

            if not title_elem or not link_elem:
                continue

            title = title_elem.get_text()
            page_url = link_elem.get("href", "")

            if not page_url or page_url.startswith("/"):
                continue

            # Fetch actual page content
            page_text = self.fetch_page_text(page_url)

            results.append(
                f"### {title}\nURL: {page_url}\n\nContent:\n{page_text}\n\n---\n"
            )

            if len(results) >= 3:  # limit to top 3 pages
                break

        return "\n".join(results) if results else "[No search results found]"

    def chat(self, messages, max_tokens=512):
        """Chat with Qwen, supporting tool calling for web search."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search Google web pages and fetch their content to answer questions about current information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "The search query to look up on Google"}
                            },
                            "required": ["query"]
                        }
                    }
                }
            ]
        }

        if self.debug:
            print("[DEBUG] Sending payload to vLLM API:")
            print(json.dumps(payload, indent=2))

        try:
            response = requests.post(self.base_url, json=payload)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] HTTP {e.response.status_code}")
            print(f"[ERROR] Response body: {e.response.text}")
            raise

        data = response.json()

        if self.debug:
            print("[DEBUG] Response from vLLM:")
            print(json.dumps(data, indent=2))

        try:
            msg = data["choices"][0]["message"]
        except (KeyError, IndexError) as e:
            print(f"[ERROR] Failed to parse response: {e}")
            print(f"[ERROR] Full response: {json.dumps(data, indent=2)}")
            raise

        # Handle tool calls if Qwen decides to use web search
        if "tool_calls" in msg and msg["tool_calls"]:
            try:
                tool = msg["tool_calls"][0]
                args = json.loads(tool["function"]["arguments"])
                query = args.get("query", "")

                if self.debug:
                    print(f"[DEBUG] Tool call detected: web_search('{query}')")

                # Execute web search
                search_results = self.web_search(query)

                if self.debug:
                    print(f"[DEBUG] Search results fetched, sending follow-up request...")

                # Send follow-up with search results
                followup_payload = {
                    "model": self.model,
                    "messages": [
                        *messages,
                        msg,
                        {
                            "role": "tool",
                            "tool_call_id": tool["id"],
                            "content": search_results
                        }
                    ],
                    "max_tokens": max_tokens
                }

                followup = requests.post(self.base_url, json=followup_payload)
                followup.raise_for_status()
                final = followup.json()

                return final["choices"][0]["message"]["content"]
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                print(f"[ERROR] Failed to parse tool call: {e}")
                print(f"[ERROR] tool_calls structure: {msg.get('tool_calls', 'N/A')}")
                raise

        return msg["content"]
