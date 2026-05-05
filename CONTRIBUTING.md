# Contributing to ShiftLeft

First off, thank you for considering contributing to ShiftLeft! It's people like you that make open-source software such a great community.

## Development Setup

To set up the project locally for development:

1. **Fork & Clone:** Fork the repo and clone it locally.
2. **Environment:** Create a Python virtual environment (`python -m venv venv`) and activate it.
3. **Install Dependencies:** Run `pip install -r requirements.txt`.
4. **Keys:** Copy `.env.example` to `.env` (do not commit this) and add your GCP Vertex AI, GitHub MCP, and SearXNG credentials.

## How Can I Contribute?

### 1. Adding New Tools (The "Hands")
We are always looking to expand the capabilities of our agents. If you want to build a new tool (e.g., a new AST parser, a different Sandbox environment, or a new MCP integration):
* Add your tool logic in the `/tools` directory.
* Ensure it is fully typed and includes error handling so the LLM doesn't crash on exceptions.

### 2. Improving Agent Prompts (The "Brains")
If you find the Coder Agent hallucinating or the Sandbox Auditor missing tracebacks, contributions to the system prompts in the `/agents` directory are highly encouraged.

### 3. Reporting Bugs
Use the GitHub Issues tab. Please include:
* Your OS and Python version.
* The exact LangGraph error trace.
* The specific issue ShiftLeft was trying to solve when it failed.

## Pull Request Process

1. Create a new branch (`git checkout -b feature/amazing-new-tool`).
2. Make your changes and test them locally to ensure the LangGraph execution loop doesn't break.
3. Commit your changes (`git commit -m 'Add amazing new tool'`).
4. Push to the branch (`git push origin feature/amazing-new-tool`).
5. Open a Pull Request and provide a clear summary of what your change does.