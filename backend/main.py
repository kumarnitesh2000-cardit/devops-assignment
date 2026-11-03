import os
from pathlib import Path

from fastapi import FastAPI
from celery.result import AsyncResult
from fastapi.responses import FileResponse
from worker import celery, write_log_celery
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def frontend():
    frontend_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    return FileResponse(frontend_path)


@app.post("/notify/")
async def notify_user(email: str):
    """Endpoint that triggers the background task in Celery."""
    task = write_log_celery.delay(f"Notification sent to {email}")
    # task is a AsyncResult, a promise to a result that will be available later.
    return {"message": f"Email will be sent to {email}", "task_id": task.id}


@app.get("/task_status/{task_id}")
async def get_task_status(task_id: str):
    """Endpoint to check the status of the task."""
    task_result = AsyncResult(task_id, app=celery)
    if task_result.failed():
        return {"task_id": task_id, "status": "failed"}
    if task_result.ready():
        return {"task_id": task_id, "status": "completed", "result": task_result.result}
    return {"task_id": task_id, "status": "in progress"}

@app.get("/health/")
@app.post("/health/", include_in_schema=False)
async def health():
    """Endpoint that checks the health of the application."""
    return {"message": "OK"}