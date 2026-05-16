from pathlib import Path

from qwen_client import QwenClient


class Memory:
    def __init__(self, max_turns=20):
        self.max_turns = max_turns
        self.messages = []

    def add(self, role, content):
        self.messages.append({"role": role, "content": content})
        self.messages = self.messages[-self.max_turns:]

    def get(self):
        return self.messages


class Agent:
    def __init__(self, name):
        self.name = name
        self.client = QwenClient()
        self.memory = Memory()

        # Load and inject SOUL.md framework
        soul_content = self._load_soul_framework()

        self.memory.add("system", soul_content)

    def _load_soul_framework(self):
        """Load SOUL.md and inject agent name."""
        soul_path = Path(__file__).parent / "SOUL.md"

        if soul_path.exists():
            with open(soul_path, 'r', encoding='utf-8') as f:
                soul_content = f.read()

        # Replace agent name placeholder
        soul_content = soul_content.replace("{{AGENT_NAME}}", self.name)
        return soul_content

    def send(self, message):
        self.memory.add("user", message)
        reply = self.client.chat(self.memory.get())
        self.memory.add("assistant", reply)
        return reply
