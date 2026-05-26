import os
import sys

import streamlit as st

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

st.set_page_config(page_title="Scheduler — ShiftLeft", layout="wide", page_icon="⏱")
st.title("⏱ Scheduler & Webhook Setup")
st.divider()


def _get(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)


CLOUD_RUN_URL  = _get("CLOUD_RUN_URL", "https://your-cloud-run-url.run.app")
WEBHOOK_SECRET = _get("WEBHOOK_SECRET", "change-me-in-production")

# ── Tab layout ────────────────────────────────────────────────────────────────
tab_webhook, tab_scheduler, tab_actions = st.tabs([
    "🔗 GitLab Webhook (auto-trigger)",
    "⏰ Cloud Scheduler",
    "⚙️ GitHub Actions",
])

# ── Tab 1: GitLab Webhook ─────────────────────────────────────────────────────
with tab_webhook:
    st.subheader("Auto-trigger ShiftLeft on new issues")
    st.markdown(
        "When you add the **`shiftleft`** label to any GitLab issue, "
        "ShiftLeft automatically runs the full pipeline and opens an MR. "
        "No manual intervention needed."
    )

    st.markdown("#### Step 1 — Deploy to Cloud Run")
    st.code("gcloud run deploy shiftleft --source . --region us-central1 --allow-unauthenticated", language="bash")

    st.markdown("#### Step 2 — Configure the GitLab webhook")
    st.markdown(
        "Go to your GitLab project → **Settings → Webhooks → Add new webhook**"
    )
    st.code(f"""\
URL:           {CLOUD_RUN_URL}/webhook/gitlab/issue
Secret token:  {WEBHOOK_SECRET}
Trigger:       ✅ Issues events
SSL:           ✅ Enable SSL verification""")

    st.markdown("#### Step 3 — Label any issue to trigger")
    st.info(
        "Open any GitLab issue in the target repo and add the label `shiftleft`. "
        "ShiftLeft will detect the label, run the 5-agent pipeline, and open an MR "
        "within ~60 seconds."
    )

    st.markdown("#### Push webhook (optional — triggers on every push to main)")
    st.code(f"""\
URL:     {CLOUD_RUN_URL}/webhook/gitlab/push
Secret:  {WEBHOOK_SECRET}
Trigger: ✅ Push events
Branch:  main""")

# ── Tab 2: Cloud Scheduler ────────────────────────────────────────────────────
with tab_scheduler:
    st.subheader("Nightly automated runs via Google Cloud Scheduler")

    PRESETS = {
        "Nightly at 2 AM UTC":   "0 2 * * *",
        "Every 6 hours":         "0 */6 * * *",
        "Every Monday 9 AM UTC": "0 9 * * 1",
    }
    preset = st.selectbox("Preset", list(PRESETS.keys()))
    cron   = st.text_input("Cron expression", value=PRESETS[preset])
    job_id = st.text_input("Job name", value="shiftleft-nightly")

    if st.button("Save schedule", type="primary"):
        try:
            from cloud.scheduler import upsert_job
            name = upsert_job(cron=cron, job_id=job_id)
            st.success(f"Schedule saved: `{name}`")
        except Exception as exc:
            st.info(
                f"Set GCP_PROJECT_ID and CLOUD_RUN_URL in secrets to activate. "
                f"Error: {exc}"
            )

    st.markdown("#### CLI equivalent")
    st.code(f"""\
gcloud scheduler jobs create http {job_id} \\
  --location us-central1 \\
  --schedule "{cron}" \\
  --uri "{CLOUD_RUN_URL}/webhook/scheduler" \\
  --message-body '{{"source":"scheduler"}}' \\
  --oidc-service-account-email shiftleft@PROJECT.iam.gserviceaccount.com""", language="bash")

# ── Tab 3: GitHub Actions ─────────────────────────────────────────────────────
with tab_actions:
    st.subheader("Free alternative: GitHub Actions scheduler")
    st.markdown(
        "If you don't want to use Cloud Scheduler, you can trigger ShiftLeft "
        "nightly from a GitHub Actions workflow for free."
    )
    st.code(f"""\
# .github/workflows/shiftleft-nightly.yml
name: ShiftLeft nightly
on:
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger ShiftLeft
        run: |
          curl -X POST {CLOUD_RUN_URL}/webhook/scheduler \\
               -H "Content-Type: application/json" \\
               -d '{{"source":"github-actions"}}'""", language="yaml")
    st.caption("Add `CLOUD_RUN_URL` as a GitHub Actions secret.")