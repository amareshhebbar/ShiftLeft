###  The ShiftLeft Directory Tree

```text
shiftleft/
├── .env                    # Environment variables (API keys, tokens)
├── .gitignore              # Files to ignore in Git (e.g., .env, __pycache__)
├── requirements.txt        # Python dependencies
├── README.md               # The Devpost/Project documentation we wrote
├── main.py                 # The main entry point to run the system
│
├── core/                   # The LangGraph Orchestrator
│   ├── __init__.py
│   ├── state.py            # Defines the data moving between agents
│   └── graph.py            # Connects the agents and defines the routing loop
│
├── agents/                 # The 6 Core Brains
│   ├── __init__.py
│   ├── triage.py           # Evaluates the GitHub issue
│   ├── cartographer.py     # Maps the codebase
│   ├── researcher.py       # Scrapes the web for context
│   ├── coder.py            # Writes the fix
│   ├── auditor.py          # Checks for hallucinations/errors
│   └── hitl.py             # Prepares the summary for human review
│
├── tools/                  # The Hands (Functions the agents call)
│   ├── __init__.py
│   ├── github_tools.py     # MCP interactions (read issues, write PRs)
│   ├── ast_tools.py        # Code parsing and mapping
│   ├── sandbox_tools.py    # Cloud Run and PyTest execution
│   └── web_tools.py        # Crawl4AI and SearXNG integration
│
├── ui/                     # The Human Interface
│   ├── __init__.py
│   └── app.py              # The Streamlit dashboard for HITL approval
│
└── utils/                  # Helper Functions
    ├── __init__.py
    ├── config.py           # Loads Vertex AI / Gemini configurations
    └── logger.py           # Formats terminal logs for easy debugging
```

---

### File-by-File Breakdown & Purpose

#### 1. The Root Level (Configuration)
*   **`.env`**: Crucial for security. Holds your `GITHUB_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS`, and `SEARXNG_URL`. **Never commit this file.**
*   **`requirements.txt`**: Lists your dependencies (`langgraph`, `streamlit`, `google-cloud-aiplatform`, `docker`, `crawl4ai`, etc.) for fast setup.
*   **`main.py`**: The execution script. When you type `python main.py`, it should initialize the LangGraph, grab the latest GitHub issue, and start the flow.

#### 2. The `core/` Directory (The Heartbeat)
*   **`state.py`**: This is where you define your LangGraph `State` class (usually using Python's `TypedDict`). It defines the exact variables that get passed from agent to agent, such as `issue_context`, `repo_map`, `generated_code`, `test_results`, and `error_logs`.
*   **`graph.py`**: The routing logic. This file wires the nodes together. It contains the logic that says: *If the Auditor node outputs "Failed", route back to the Coder node. If "Passed", route to the HITL node.*

#### 3. The `agents/` Directory (The Brains)
Each file here contains the specific system prompt and the LangChain/Vertex AI initialization for that specific agent.
*   **`triage.py`**: Takes the raw issue text, asks Gemini 1.5 Flash to categorize it, and returns the result to the graph state.
*   **`cartographer.py`**: Uses Gemini 1.5 Pro to look at the AST output and summarize the architecture of the files related to the bug.
*   **`researcher.py`**: Uses Gemini 1.5 Flash to summarize the documentation scraped from the web.
*   **`coder.py`**: The heaviest file. Holds the massive system prompt instructing Gemini 1.5 Pro how to write secure, formatted code and tests based on all previous context.
*   **`auditor.py`**: Takes the terminal traceback from the failed test and asks Gemini 1.5 Flash to explain *why* it failed so the Coder can understand it.
*   **`hitl.py`**: Formats the final state variables into a clean markdown summary for the human to read.

#### 4. The `tools/` Directory (The Hands)
These are standard Python functions decorated as tools (e.g., `@tool` in LangChain) that the agents are allowed to trigger.
*   **`github_tools.py`**: Contains functions like `get_issue(repo, issue_number)` and `create_pull_request(branch, title, body)`.
*   **`ast_tools.py`**: Contains `generate_function_map(directory_path)` which uses Python's built-in `ast` library to return a JSON map of the code.
*   **`sandbox_tools.py`**: Contains `deploy_to_cloud_run(code_string)` and `run_pytest(container_id)`. This is the most important tool file for your self-correction loop.
*   **`web_tools.py`**: Contains `scrape_documentation(url)` using Crawl4AI.

#### 5. The `ui/` Directory (The Presentation)
*   **`app.py`**: Your Streamlit frontend. It connects to the LangGraph execution. When the graph pauses at the HITL stage, this file renders the "Approve PR?" button, the summary of what ShiftLeft did, and the UI for the human maintainer.

#### 6. The `utils/` Directory (The Support)
*   **`config.py`**: A central place to load your `.env` variables and initialize the Google Cloud Vertex AI client so you don't have to rewrite the initialization code in every single agent file.
*   **`logger.py`**: Hackathons get messy. A custom logger that prints different agents' actions in different colors in your terminal (e.g., Coder in Blue, Auditor in Red for errors, Triage in Green) will save you hours of debugging time when tracing the LangGraph loops.