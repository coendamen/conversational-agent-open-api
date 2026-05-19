import json

import requests
from bs4 import BeautifulSoup


class QwenClient:
    def __init__(self, debug=False):
        self.base_url = "http://host.docker.internal:8000/v1/chat/completions"
        self.model = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"
        self.debug = debug
        self.openserp_url = "http://host.docker.internal:7000/duck/search"

    # ---------------------------------------------------------
    # Fetch readable text from a webpage
    # ---------------------------------------------------------
    def fetch_page_text(self, url):
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

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())

        return cleaned[:5000]

    # ---------------------------------------------------------
    # OpenSERP API search
    # ---------------------------------------------------------
    def web_search(self, query: str, max_results=None):
        """Search using OpenSERP API. Use snippets, no page fetching."""
        params = {"text": query, "limit": 50, "lang": "EN"}

        try:
            r = requests.get(self.openserp_url, params=params, timeout=10)
            r.raise_for_status()
        except Exception as e:
            return f"[Web search failed: {e}]"

        try:
            data = r.json()
        except Exception as e:
            return f"[Failed to parse OpenSERP response: {e}]"

        if self.debug:
            print(f"\n[DEBUG] OpenSERP raw response keys: {data.keys()}")

        # Use snippets from SERP results
        results = []
        search_results = data.get("results", [])

        if self.debug:
            print(f"[DEBUG] OpenSERP returned {search_results} total results")

        for idx, result in enumerate(search_results):
            title = result.get("title", "")
            url = result.get("url", "")
            snippet = result.get("snippet", "")

            if not url or not snippet:
                if self.debug:
                    print(f"[DEBUG] Skipping result {idx}: title='{title[:50]}', has_url={bool(url)}, has_snippet={bool(snippet)}")
                continue

            results.append(
                f"• **{title}**\n  URL: {url[:50]}\n  {snippet}"
            )

        if self.debug:
            print(f"[DEBUG] Processed {len(results)} valid results\n")

        return "\n\n".join(results) if results else "[No search results found]"

    # ---------------------------------------------------------
    # Chat with Qwen (tool-calling enabled)
    # ---------------------------------------------------------
    def chat(self, messages, max_tokens=1024):
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
                        "description": "Search the web using OpenSERP and fetch page content for current information.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"}
                            },
                            "required": ["query"]
                        }
                    }
                }
            ]
        }

        if self.debug:
            print("[DEBUG] Sending payload:")
            print(json.dumps(payload, indent=2))

        response = requests.post(self.base_url, json=payload)
        response.raise_for_status()
        data = response.json()

        if self.debug:
            print("[DEBUG] Response:")
            print(json.dumps(data, indent=2))

        msg = data["choices"][0]["message"]

        # ---------------------------------------------------------
        # Tool call handling
        # ---------------------------------------------------------
        if "tool_calls" in msg and msg["tool_calls"]:
            tool = msg["tool_calls"][0]
            args = json.loads(tool["function"]["arguments"])
            query = args.get("query", "")

            if self.debug:
                print(f"[DEBUG] Tool call: web_search('{query}')")

            search_results = self.web_search(query)

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

        return msg["content"]
