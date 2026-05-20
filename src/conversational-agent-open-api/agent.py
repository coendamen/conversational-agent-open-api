from pathlib import Path
from datetime import datetime

from qwen_client import QwenClient


class Memory:
    def __init__(self, max_turns=100):
        self.max_turns = max_turns
        self.messages = []

    def add(self, role, content):
        self.messages.append({"role": role, "content": content})
        # Keep system message + last max_turns user/assistant exchanges
        if len(self.messages) > self.max_turns + 1:
            self.messages = [self.messages[0]] + self.messages[-(self.max_turns):]

    def get(self):
        return self.messages

    def get_safe_subset(self, max_chars=None):
        """Return all messages - no trimming."""
        return self.messages


class Agent:
    def __init__(self, name, debug=False):
        self.name = name
        self.client = QwenClient()
        self.memory = Memory()

        # Load and inject SOUL.md framework
        soul_content = self._load_soul_framework()

        self.memory.add("system", soul_content)

    def _load_soul_framework(self):
        """Load SOUL.md and inject agent name and current date."""
        soul_path = Path(__file__).parent / "SOUL.md"

        if soul_path.exists():
            with open(soul_path, 'r', encoding='utf-8') as f:
                soul_content = f.read()
        else:
            soul_content = ""

        # Replace agent name and current date
        soul_content = soul_content.replace("{{AGENT_NAME}}", self.name)
        current_date = datetime.now().strftime("%B %d, %Y")
        soul_content = soul_content.replace("{{CURRENT_DATE}}", current_date)
        return soul_content

    def send(self, message):
        self.memory.add("user", message)

        # Send all messages - no trimming
        reply = self.client.chat(self.memory.get(), max_tokens=1024)
        self.memory.add("assistant", reply)
        return reply
