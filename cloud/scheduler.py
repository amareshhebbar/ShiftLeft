from google.cloud import scheduler_v1
from utils.config import GCP_PROJECT_ID, GCP_REGION, CLOUD_RUN_URL
from utils.logger import get_logger

log = get_logger(__name__)

_PARENT = f"projects/{GCP_PROJECT_ID}/locations/{GCP_REGION}"
_SA_EMAIL = f"shiftleft@{GCP_PROJECT_ID}.iam.gserviceaccount.com"


def _client() -> scheduler_v1.CloudSchedulerClient:
    return scheduler_v1.CloudSchedulerClient()


def upsert_job(cron: str = "0 2 * * *", job_id: str = "shiftleft-nightly") -> str:
    client = _client()
    job = scheduler_v1.Job(
        name=f"{_PARENT}/jobs/{job_id}",
        schedule=cron,
        time_zone="UTC",
        http_target=scheduler_v1.HttpTarget(
            uri=f"{CLOUD_RUN_URL}/webhook/scheduler",
            http_method=scheduler_v1.HttpMethod.POST,
            oidc_token=scheduler_v1.OidcToken(
                service_account_email=_SA_EMAIL,
                audience=CLOUD_RUN_URL,
            ),
        ),
    )
    try:
        result = client.update_job(job=job)
        log.info(f"[scheduler] updated job: {result.name}")
    except Exception:
        result = client.create_job(parent=_PARENT, job=job)
        log.info(f"[scheduler] created job: {result.name}")
    return result.name


def delete_job(job_id: str = "shiftleft-nightly") -> None:
    _client().delete_job(name=f"{_PARENT}/jobs/{job_id}")
    log.info(f"[scheduler] deleted: {job_id}")


def list_jobs() -> list:
    return [
        {
            "id":       j.name.split("/")[-1],
            "schedule": j.schedule,
            "state":    scheduler_v1.Job.State(j.state).name,
            "next_run": j.next_schedule_time.isoformat()
                        if j.next_schedule_time else "N/A",
        }
        for j in _client().list_jobs(parent=_PARENT)
        if "shiftleft" in j.name
    ]