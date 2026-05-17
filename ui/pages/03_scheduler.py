import streamlit as st

st.set_page_config(page_title="Scheduler — ShiftLeft", layout="wide")
st.title("⏱ Scheduler")
st.markdown("Configure automated ShiftLeft runs via **Google Cloud Scheduler**.")

PRESETS = {
    "Nightly at 2 AM UTC":   "0 2 * * *",
    "Every 6 hours":         "0 */6 * * *",
    "Every Monday 9 AM UTC": "0 9 * * 1",
}
preset = st.selectbox("Preset", list(PRESETS.keys()))
cron   = st.text_input("Cron expression", value=PRESETS[preset])
job_id = st.text_input("Job name", value="shiftleft-nightly")

if st.button("Save schedule", type="primary"):
    st.info(
        f"Schedule `{cron}` saved as `{job_id}`.\n\n"
        "To activate: set `GCP_PROJECT_ID` and `CLOUD_RUN_URL` in secrets, "
        "then redeploy with `cloud/scheduler.py` enabled."
    )

st.divider()
st.subheader("Free alternative: GitHub Actions")
st.code("""# .github/workflows/shiftleft.yml
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
          curl -X POST ${{ secrets.CLOUD_RUN_URL }}/webhook/scheduler \\
               -H "Content-Type: application/json" \\
               -d '{"source":"scheduler"}'
""", language="yaml")
st.caption("Add CLOUD_RUN_URL as a GitHub Actions secret to enable this.")
