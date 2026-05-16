# Conversational Agent with Qwen 2.5

A Python-based conversational agent powered by **Qwen/Qwen2.5-7B-Instruct** that can have meaningful dialogues, search the web for information, and maintain conversation context across multiple turns.

## Features

- **Conversational AI**: Interactive chat powered by Qwen 2.5 LLM
- **Web Search Integration**: Real-time Google search with page content fetching
- **Memory Management**: Maintains conversation history with configurable memory buffer
- **Multi-Agent Support**: Run multiple agents with different system prompts for agent-to-agent conversations
- **Tool Calling**: LLM can invoke web search tools when needed
- **Docker Ready**: Includes Dockerfile for containerized deployment
- **SOUL Framework**: Agent behavior guided by self, observations, understanding, and long-term tendencies (see [SOUL.md](./src/conversational-agent-open-api/SOUL.md))

## Architecture

```
conversational-agent-open-api/
├── src/conversational-agent-open-api/
│   ├── main.py           # Entry point & interactive CLI
│   ├── agent.py          # Agent class with conversation memory
│   ├── qwen_client.py    # Qwen API client with web search capabilities
│   ├── requirements.txt   # Python dependencies
│   └── SOUL.md           # Agent design philosophy
├── docker/
│   └── Dockerfile        # Container configuration
└── README.md             # This file
```

### Core Components

**`QwenClient`** (`qwen_client.py`)
- Handles communication with the Qwen API endpoint
- Manages tool calling for web searches
- Fetches and processes webpage content
- Converts message formats to API-compatible structures

**`Agent`** (`agent.py`)
- Wraps the QwenClient with memory management
- Maintains conversation history (last N turns)
- Adds user/assistant/system messages to memory
- Provides a simple `.send(message)` interface

**`Memory`** (`agent.py`)
- FIFO queue with configurable size (default: 20 turns)
- Stores role-based messages (system, user, assistant, tool)
- Automatically prunes old messages to stay within limits

## Prerequisites

- **Python** 3.10 or higher
- **Qwen API Server** running at `http://host.docker.internal:8000/v1/chat/completions` (or configure a custom URL)
- Internet access (for web search functionality)

## Installation

### Option 1: Local Development

1. Clone or navigate to the workspace:
   ```powershell
   cd D:\Dev\Workspaces\conversational-agent-open-api
   ```

2. Install dependencies:
   ```powershell
   pip install -r src/conversational-agent-open-api/requirements.txt
   ```

3. Ensure your Qwen API server is running and accessible

### Option 2: Docker Deployment

1. Build the image:
   ```bash
   docker build -t conversational-agent -f docker/Dockerfile .
   ```

2. Run the container:
   ```bash
   docker run --rm -it --network host conversational-agent
   ```
   
   Or with custom Qwen endpoint:
   ```bash
   docker run --rm -it -e QWEN_URL=http://your-qwen-server:8000/v1/chat/completions conversational-agent
   ```

## Usage

### Interactive Chat

Start a conversation with the agent:

```powershell
python src/conversational-agent-open-api/main.py
```

Example session:
```
Qwen 2.5 Conversational Agent
Type 'exit' to quit.

You> Hello, what's the latest news about AI?
Qwen> [Agent searches the web and responds with current information]

You> Can you summarize that for me?
Qwen> [Agent uses context from previous response]

You> exit
Goodbye.
```

### Agent-to-Agent Conversation

Run a debate or conversation between two agents:

```python
from main import run_duo_chat
run_duo_chat()
```

This runs a pre-configured 10-turn dialogue between "Alice" and "Bob" with different system prompts.

### Programmatic Usage

```python
from agent import Agent

# Create an agent with a custom system prompt
agent = Agent(
    name="Assistant",
    system_prompt="You are a helpful coding expert."
)

# Send a message
reply = agent.send("How do I reverse a list in Python?")
print(reply)

# Continue the conversation (memory is maintained)
follow_up = agent.send("What about using slicing?")
print(follow_up)
```

## Configuration

### QwenClient Parameters

Edit `qwen_client.py` to customize:

```python
client = QwenClient(
    base_url="http://host.docker.internal:8000/v1/chat/completions"  # Qwen API endpoint
)
```

### Agent Configuration

In `main.py` or `agent.py`:

```python
# Adjust memory size (number of turns to remember)
memory = Memory(max_turns=20)

# Set system prompt for agent personality
agent = Agent(
    name="Smith",
    system_prompt="Your custom system prompt here..."
)
```

### Chat Parameters

Edit the `chat()` method in `qwen_client.py`:

```python
def chat(self, messages, max_tokens=512):  # Adjust max_tokens as needed
    # ...
    "temperature": 0.7,  # Higher = more creative, lower = more focused
    # ...
```

## API Reference

### Agent

```python
Agent(name: str, system_prompt: str = None)
```
- **name**: Agent identifier (for logging/display)
- **system_prompt**: Initial system role definition

Methods:
- `send(message: str) → str`: Send a message and get a response

### QwenClient

```python
QwenClient(base_url: str = "http://host.docker.internal:8000/v1/chat/completions")
```

Methods:
- `chat(messages: list, max_tokens: int = 512) → str`: Send messages to Qwen, handle tool calls
- `real_web_search(query: str) → str`: Search Google and fetch top 3 pages
- `fetch_page_text(url: str) → str`: Extract readable text from a webpage

### Memory

```python
Memory(max_turns: int = 20)
```

Methods:
- `add(role: str, content: str)`: Add a message to memory
- `get() → list`: Retrieve all messages in memory

## Troubleshooting

### "400 Client Error: Bad Request"
- **Cause**: Qwen API rejected the message format
- **Fix**: Ensures messages are properly formatted with content blocks. The client automatically converts plain strings to content blocks.
- **Debug**: Add `print(json.dumps(payload, indent=2))` before the POST request in `qwen_client.py`

### "Connection refused" or "Cannot reach Qwen server"
- **Cause**: Qwen API not running or URL incorrect
- **Fix**: 
  - Start your Qwen server: `ollama serve` (if using Ollama) or equivalent
  - Verify URL in code matches your actual endpoint
  - From Docker, use `--network host` or configure hostname properly

### "Failed to fetch [URL]"
- **Cause**: Web scraping blocked or network issue
- **Fix**: 
  - Some websites block scraping; this is normal
  - Check internet connectivity
  - Verify User-Agent in `fetch_page_text()` is current

### Agent takes too long to respond
- **Cause**: Web search timeout or slow model inference
- **Fix**: Reduce `max_tokens` in `chat()` or increase timeout in `fetch_page_text()`

## Design Philosophy

See [SOUL.md](./src/conversational-agent-open-api/SOUL.md) for the agent's behavioral framework:

- **S**elf: Autonomous entity with clear identity and purpose
- **O**bservations: Grounds all responses in provided context
- **U**nderstanding: Intent-first interpretation with uncertainty handling
- **L**ong-term Tendencies: Consistent, helpful, and ethical behavior

## Dependencies

```
requests          # HTTP client for Qwen API and web requests
beautifulsoup4    # HTML parsing for web scraping
```

## License

[Specify your license here]

## Contributing

Contributions welcome! Areas for enhancement:

- [ ] Support for different LLM backends (not just Qwen)
- [ ] Persistent conversation storage
- [ ] Advanced web scraping (JavaScript rendering)
- [ ] Voice input/output integration
- [ ] Vector database for semantic search
- [ ] Unit and integration tests

## Support

For issues, questions, or suggestions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review [SOUL.md](./src/conversational-agent-open-api/SOUL.md) for design intent
3. Inspect debug output from `qwen_client.py`

---

**Built with Qwen 2.5** | Conversational Agent Framework

