from agent import Agent


def run_agent(debug=False):
    print("Qwen 2.5 Conversational Agent")
    print("Type 'exit' to quit.\n")

    agent_smith = Agent("Smith", debug=debug)

    while True:
        user_input = input("You> ").strip()
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break

        try:
            reply = agent_smith.send(user_input)
        except Exception as e:
            reply = f"Error communicating with Qwen: {e}"

        print(f"Qwen> {reply}\n")

        agent_smith.memory.print_size()


def run_duo_chat(debug=False):
    alice = Agent("Alice", debug=debug)
    bob = Agent("Bob", debug=debug)

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
    # run_duo_chat(debug=True)
    run_agent(debug=True)
