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
    def __init__(self, name, system_prompt=None):
        self.name = name
        self.client = QwenClient()
        self.memory = Memory()


        if system_prompt:
            self.memory.add("system", system_prompt)

    def send(self, message):
        self.memory.add("user", message)
        reply = self.client.chat(self.memory.get())
        self.memory.add("assistant", reply)
        return reply
