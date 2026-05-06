### 1. Environment Configuration

Create a `.env` file in the root directory of your project and paste the following configuration exactly as you provided. Ensure you replace the placeholder values with your actual credentials:

```bash
GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/gcp-service-account-key.json"
GCP_PROJECT_ID="shiftleft-hackathon-12345"
GCP_REGION="us-central1"

GITHUB_TOKEN="github_pat_11AXXXXX..."
GITHUB_TARGET_REPO="your-github-username/your-mock-repo-name"

SEARXNG_URL="http://localhost:8080"

LANGCHAIN_TRACING_V2="true"
LANGCHAIN_API_KEY="ls__XXXXX..."
LANGCHAIN_PROJECT="shiftleft-dev"
```

### 2. Installation & Setup

Ensure you have Python 3.10+ installed. Open your terminal in the root directory of the project and set up your virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

### 2.5 Docker Setup
ShiftLeft is using with the SearXng, for the web search
```bash
docker run -d -p 8080:8080 docker.io/searxng/searxng
```

### 3. Execution Options

ShiftLeft is designed with two entry points depending on what you are testing: the backend autonomous loop or the Human-in-the-Loop (HITL) interface.

**Option A: Running the Autonomous Loop (CLI)**
To test the core multi-agent logic, the mapping process, and the sandbox self-correction loop in your terminal without the UI:

```bash
python main.py
```
*What to expect:* You will see color-coded logs printing in the terminal as the `triage` agent hands off to the `cartographer`, then the `coder`, and finally the `sandbox` auditor. 

**Option B: Running the Full Human-in-the-Loop UI**
To run the full workflow including the Streamlit dashboard that pauses the graph execution to ask for human PR approval:

```bash
streamlit run ui/app.py
```
*What to expect:* This will spin up a local web server (usually at `http://localhost:8501`). You can trigger a repository scan from the UI, watch the agent state update on the screen, and eventually click the "Approve & Merge PR" button when the `hitl` agent halts the workflow.




--
# WHile creating the token in github trhese permission are necessarey

asic Token Setup
Token name: ShiftLeft-Hackathon-Agent (or something similar).

Expiration: Set this to 7 or 30 days. Never set agent tokens to no expiration.

Repository access (Crucial Step): Do NOT select "All repositories". Select Only select repositories, and choose the specific mock repository you created for this project (e.g., your-github-username/your-mock-repo-name).


. The Required Permissions
Scroll down to the Repository permissions section. You need to expand the menus and change the access levels for the following specific categories:

Contents

Access Level: Read and write

Why ShiftLeft needs it: The Cartographer agent needs to read your codebase to map it, and the Coder agent needs to create new branches and push commits with the bug fixes.

Issues

Access Level: Read and write

Why ShiftLeft needs it: The Triage agent needs to read the incoming bug report to trigger the workflow.

Pull Requests

Access Level: Read and write

Why ShiftLeft needs it: The HITL (Human-in-the-Loop) agent needs to open the final Pull Request detailing the fix so you can review it.

Metadata

Access Level: Read-only

Note: GitHub will automatically set this to Read-only the moment you change any of the above permissions. This is required and perfectly fine.

