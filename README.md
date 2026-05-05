<div align="center">

  <h1>ShiftLeft</h1>
  <h3>The Autonomous OSS Maintenance Agent</h3>
  <p><em>"Moving maintenance to the source"</em></p>

  <br />

  <p>
    <a href="https://python.org">
      <img src="https://img.shields.io/badge/Built_with-Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Built with Python" />
    </a>
    <a href="https://cloud.google.com/vertex-ai">
      <img src="https://img.shields.io/badge/Powered_by-Vertex_AI-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white" alt="Powered by Vertex AI" />
    </a>
   <a href="https://langchain.com">
  <img src="https://img.shields.io/badge/Execution_Engine-LangGraph-000000?style=for-the-badge&logo=chainlink&logoColor=white" alt="LangGraph" />
</a>
    <a href="LICENSE">
      <img src="https://img.shields.io/badge/License-MIT-success?style=for-the-badge" alt="MIT License" />
    </a>
  </p>

  <br />

  <p>
    <b>ShiftLeft</b> acts as a digital co-maintainer that monitors repositories, researches bugs,<br> 
    writes fixes, tests them in an isolated sandbox, and submits verified Pull Requests.
  </p>

  <br />

  <p>
    <a href="#2-technical-architecture">Explore Architecture</a> &nbsp;&nbsp;|&nbsp;&nbsp;
    <a href="https://youtu.be/your-demo-link">Watch Demo</a> &nbsp;&nbsp;|&nbsp;&nbsp;
    <a href="https://github.com/yourusername/shiftleft/issues">Report an Issue</a>
  </p>

</div>

## Key Features

**ShiftLeft** equips maintainers with an AI-driven engineering pipeline that operates at machine speed without compromising code quality.

- **Autonomous Multi-Agent Orchestration:** Decompose complex software maintenance into specialized roles (Triage, Research, Coding, and Auditing) to prevent context degradation and focus the LLM on specific sub-tasks.
- **Self-Correcting Execution Loops:** Features a "Sandbox-to-Coder" feedback loop. If tests fail in the Cloud Run environment, the Auditor agent parses tracebacks and redirects the Coder to refine the logic until verification is achieved.
- **Type-Safe MCP Tooling:** Utilizes Model Context Protocol (MCP) to provide agents with strictly defined "hands." This ensures the agent interacts with GitHub and local files through structured schemas rather than unpredictable shell scraping.
- **Deep Codebase Mapping:** Uses AST (Abstract Syntax Tree) parsing to generate a functional map of the repository. This allows the agent to understand cross-file dependencies and "dead code" before making modifications.
- **Web-Grounded Research:** Integrates high-performance crawling (Crawl4AI) to fetch clean Markdown from live documentation, ensuring the agent uses the latest API standards instead of relying solely on training data.

## Technical Architecture

ShiftLeft utilizes a modular, cloud-native architecture designed for security and scalability:

- **The Brain (Vertex AI):** Powered by **Gemini 1.5 Pro**. The 2M token context window is leveraged to ingest entire repository maps and dependency trees simultaneously.
- **The Orchestrator (LangGraph):** Manages cyclic state transitions. It enforces strict iteration caps and handles the "Human-in-the-Loop" (HITL) handoffs for final PR approvals.
- **The Execution Boundary (Cloud Run):** Acts as the security sandbox. Every proposed fix is deployed into an ephemeral container where unit tests are executed in total isolation from the core system.
- **The Context Bridge (GitHub MCP):** Provides a secure, authenticated interface for repository interaction, allowing the agent to manage branches, issues, and commits through a type-safe protocol.

## Installation & Setup

### Prerequisites

- Python 3.10+
- Google Cloud Project (with Vertex AI enabled)
- GitHub Personal Access Token (PAT)

### Quick Start

1. **Clone and Setup:**

   ```bash
   git clone https://github.com/amareshhebbar/ShiftLeft
   cd ShiftLeft
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment:**
   Create a `.env` file based on the provided documentation and add your credentials.

3. **Execute:**
   ```bash
   python main.py --repo "owner/repo" --issue 42
   ```

## Roadmap

- **Multi-Language Support:** Expanding AST parsing logic to support Go, Rust, and TypeScript.
- **Security Vulnerability Patching:** Integration with GitHub Security Advisories to automatically propose patches for known CVEs.
- **Performance Benchmarking:** Implementing a framework to measure the "Time-to-Fix" (TTF) against manual human maintenance cycles.

## Why It Matters

Maintainer burnout is a systemic risk to the software supply chain. **ShiftLeft** matches the velocity of modern development by automating the "grunt work" of triage and reproduction. By moving verification to the source and utilizing self-correction, we reduce the initial triage time from hours to seconds while maintaining absolute architectural integrity.

```

```
