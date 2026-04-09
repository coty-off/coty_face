# api/celery_app.py
from celery import Celery


app = Celery("diplom")

app.conf.imports = [
    "api.tasks",  # Задачи process_diplom и process_colors
]

app.conf.update(
    broker_url="redis://redis:6379/0",
    result_backend="redis://redis:6379/1",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
)