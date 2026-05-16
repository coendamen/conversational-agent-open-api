import requests


class QwenClient:
    def __init__(self, base_url="http://host.docker.internal:8000/v1/chat/completions"):
        self.base_url = base_url
        self.model = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"

    def chat(self, messages, max_tokens=512):
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        response = requests.post(self.base_url, json=payload)
        response.raise_for_status()
        data = response.json()

        return data["choices"][0]["message"]["content"]