"""Configure and control the Cloud Scheduler automated run job."""

import streamlit as st
from cloud.scheduler import upsert_job, delete_job, list_jobs

st.title("⏱ Scheduler")
st.markdown(
    "Configure automated ShiftLeft runs via **Google Cloud Scheduler**. "
    "Runs hit your Cloud Run webhook endpoint on the schedule you define."
)

# ── active jobs ────────────────────────────────────────────────────────────
st.subheader("Active jobs")
with st.spinner("Fetching jobs…"):
    try:
        jobs = list_jobs()
    except Exception as e:
        st.error(f"Could not list jobs — is GCP configured? ({e})")
        jobs = []

if not jobs:
    st.info("No ShiftLeft jobs found. Create one below.")
else:
    for j in jobs:
        c1, c2, c3 = st.columns([2, 2, 1])
        c1.markdown(f"**{j['id']}** — `{j['schedule']}`")
        c2.caption(f"Next run: {j['next_run']}")
        badge = ":green[ENABLED]" if j["state"] == "ENABLED" else ":gray[PAUSED]"
        c3.markdown(badge)

st.divider()

# ── create / update ────────────────────────────────────────────────────────
st.subheader("Create or update a schedule")

cron_presets = {
    "Nightly at 2 AM UTC":   "0 2 * * *",
    "Every 6 hours":         "0 */6 * * *",
    "Every Monday at 9 AM":  "0 9 * * 1",
    "Custom":                "",
}
preset = st.selectbox("Schedule preset", list(cron_presets.keys()))
cron   = st.text_input(
    "Cron expression (UTC)",
    value=cron_presets[preset],
    help="Standard Unix cron. 5 fields: minute hour day month weekday.",
)
job_id = st.text_input("Job ID", value="shiftleft-nightly")

c1, c2 = st.columns(2)
if c1.button("💾 Save schedule", type="primary"):
    with st.spinner("Saving…"):
        try:
            name = upsert_job(cron=cron, job_id=job_id)
            st.success(f"Job saved: `{name}`")
        except Exception as e:
            st.error(str(e))

if c2.button("🗑  Delete job"):
    with st.spinner("Deleting…"):
        try:
            delete_job(job_id)
            st.success(f"Job `{job_id}` deleted.")
        except Exception as e:
            st.error(str(e))

st.divider()
st.caption(
    "Alternatively, use **GitHub Actions** for free scheduling "
    "(see `.github/workflows/shiftleft.yml` in the repo)."
)