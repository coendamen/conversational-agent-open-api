from agent import Agent
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


def run_agent():
    print("Qwen 2.5 Conversational Agent")
    print("Type 'exit' to quit.\n")

    memory = Memory()

    agent_smith = Agent("Smith")

    while True:
        user_input = input("You> ").strip()
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break

        memory.add("user", user_input)

        try:
            reply = agent_smith.send(user_input)
        except Exception as e:
            reply = f"Error communicating with Qwen: {e}"

        memory.add("assistant", reply)

        print(f"Qwen> {reply}\n")


def run_duo_chat():
    alice = Agent("Alice",
                  system_prompt="You are Alice, a nazi, who keeps firm in her viewpoints. Keep the responses short, limited to about 200 characters in Dutch")
    bob = Agent("Bob",
                system_prompt="You are Bob, a communist, who keeps firm in his viewpoints. Keep the responses short, limited to about 200 characters in Dutch")

    message = "Hello Bob, what shall we do with the human race?"

    print(f"Alice> {message}")
    for turn in range(10):

        reply = bob.send(message)

        print(f"Bob> {reply}")
        message = reply  # Bob's reply becomes Alice's next input

        reply = alice.send(message)
        print(f"Alice> {reply}")
        message = reply  # Alice's reply becomes Bob's next input


if __name__ == "__main__":
    # run_duo_chat()
    run_agent()
