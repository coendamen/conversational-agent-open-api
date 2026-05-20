import json
import logging

import requests
import duckduckgoscraper

logging.basicConfig(level=logging.INFO)


class QwenClient:
    def __init__(self):
        self.base_url = "http://host.docker.internal:8000/v1/chat/completions"
        self.model = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"
        self.openserp_url = "http://host.docker.internal:7000/bing/search"

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
                        "description": "Search the web using OpenSERP for current information. Always include the current date context in temporal queries (e.g., 'today news', 'recent events') to ensure accurate, up-to-date results.",
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

        logging.debug("[DEBUG] Sending payload:")
        logging.debug(json.dumps(payload, indent=2))

        response = requests.post(self.base_url, json=payload)
        response.raise_for_status()
        data = response.json()

        logging.debug("[DEBUG] Response:")
        logging.debug(json.dumps(data, indent=2))

        msg = data["choices"][0]["message"]

        # ---------------------------------------------------------
        # Tool call handling
        # ---------------------------------------------------------
        if "tool_calls" in msg and msg["tool_calls"]:
            tool = msg["tool_calls"][0]
            args = json.loads(tool["function"]["arguments"])
            query = args.get("query", "")

            logging.info(f"[DEBUG] Tool call: web_search('{query}')")

            search_results = duckduckgoscraper.ResilientDuckDuckGoScraper().search_and_scrape(query)

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
