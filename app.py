
import os
from flask import Flask, jsonify, render_template, request

from database import (
    init_db,
    get_db,
    create_task,
    get_task,
    list_tasks,
    get_stats
)

from worker import WorkerPool


ALLOWED_TYPES = {
    "echo",
    "uppercase",
    "report",
    "fail_once",
    "always_fail"
}


def create_app(start_workers=False, database_path=None):

    app = Flask(__name__)

    app.config["DATABASE"] = (
        database_path or os.getenv("TASKFLOW_DB", "taskflow.db")
    )

    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    init_db(app.config["DATABASE"])

    pool = WorkerPool(
        app.config["DATABASE"],
        worker_count=int(os.getenv("WORKER_COUNT", "2"))
    )

    app.extensions["worker_pool"] = pool

    if start_workers:
        pool.start()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "service": "TaskFlow"
        })

    @app.post("/api/tasks")
    def submit_task():

        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "error": "Request body must be a JSON object"
            }), 400

        task_type = data.get("task_type", "echo")
        priority = data.get("priority", "medium")
        payload = data.get("payload", {})

        if task_type not in ALLOWED_TYPES:
            return jsonify({
                "error": f"task_type must be one of {sorted(ALLOWED_TYPES)}"
            }), 400

        if priority not in {"low", "medium", "high"}:
            return jsonify({
                "error": "priority must be low, medium, or high"
            }), 400

        if not isinstance(payload, dict):
            return jsonify({
                "error": "payload must be a JSON object"
            }), 400

        if task_type == "uppercase":
            if not isinstance(payload.get("text"), str):
                return jsonify({
                    "error": "uppercase tasks require payload.text as a string"
                }), 400

        if task_type == "fail_once":
            if not isinstance(payload.get("message", "Demo failure"), str):
                return jsonify({
                    "error": "payload.message must be a string"
                }), 400

        task = create_task(
            app.config["DATABASE"],
            task_type,
            priority,
            payload
        )

        return jsonify(task), 201

    @app.get("/api/tasks")
    def tasks():

        status = request.args.get("status")

        if status and status not in {
            "pending",
            "processing",
            "completed",
            "failed"
        }:
            return jsonify({
                "error": "Invalid status filter"
            }), 400

        return jsonify({
            "tasks": list_tasks(app.config["DATABASE"], status)
        })

    @app.get("/api/tasks/<task_id>")
    def task_detail(task_id):

        task = get_task(app.config["DATABASE"], task_id)

        if task is None:
            return jsonify({
                "error": "Task not found"
            }), 404

        return jsonify(task)

    @app.post("/api/workers/pause")
    def pause_workers():
        pool.pause()
        return jsonify({"paused": True})

    @app.post("/api/workers/resume")
    def resume_workers():
        pool.resume()
        return jsonify({"paused": False})

    @app.get("/api/stats")
    def stats():

        data = get_stats(
            app.config["DATABASE"],
            pool.worker_count
        )

        data["paused"] = pool.is_paused

        return jsonify(data)

    return app


app = create_app(
    start_workers=os.getenv(
        "TASKFLOW_START_WORKERS", "true"
    ).lower() == "true"
)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
        use_reloader=False
    )
