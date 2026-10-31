# TaskFlow – Background Task Queue & Worker Monitoring System

TaskFlow is a full-stack Python application that accepts background jobs, schedules them by priority, executes them using concurrent worker threads, persists task state in SQLite, and retries failed jobs.

> **Scope:** This is an educational, single-machine multi-worker prototype. It demonstrates queue scheduling, concurrency, persistence, retry handling and API design. It is not a production distributed queue and does not provide multi-host coordination, exactly-once execution or a broker-backed delivery guarantee.

## Features

- REST API for task submission and status retrieval
- High / medium / low priority scheduling
- Multiple background worker threads
- Atomic task claiming using SQLite transactions
- Persistent task records and execution attempts
- Automatic retries with a small exponential backoff
- Dashboard with live status counts and task history
- Allow-listed task handlers (echo, uppercase, report, fail-once and permanent-failure demos)
- Input validation and API tests
- Pause and resume controls for background workers
- Execution pick-order and worker-name tracking
- Permanent failure handling after retry exhaustion
## Architecture

Browser dashboard → Flask REST API → SQLite task store → concurrent worker threads → result / retry state.

Workers claim tasks in a short `BEGIN IMMEDIATE` transaction. This prevents two worker threads in this application from claiming the same pending database row at the same time. The queue query orders by priority rank descending and creation time ascending.

## Tech stack

- Python 3
- Flask
- SQLite
- HTML, CSS, JavaScript
- Python threading and unittest

## Run locally

```bash
git clone https://github.com/YOUR-USERNAME/taskflow.git
cd taskflow

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000.

By default, the local app starts two background workers. Set `WORKER_COUNT=3` to change the number of worker threads.

## API examples

### Submit a task

```bash
curl -X POST http://127.0.0.1:5000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_type":"uppercase","priority":"high","payload":{"text":"hello amazon"}}'
```

### List tasks

```bash
curl http://127.0.0.1:5000/api/tasks
```

### Get one task

```bash
curl http://127.0.0.1:5000/api/tasks/TASK_ID
```

### Statistics and health

```bash
curl http://127.0.0.1:5000/api/stats
curl http://127.0.0.1:5000/api/health
```

### Demonstrate retry

Submit a `fail_once` task. Its first attempt intentionally fails; the worker returns it to pending and retries it. The next attempt succeeds.

### Demonstrate permanent failure

Submit an `always_fail` task. It fails on every attempt and is marked as failed after exhausting the configured retry limit.

## Run tests

```bash
python -m unittest discover -s tests -v
```

The tests cover health checks, task creation, validation, listing, task retrieval and missing-task handling. Worker scheduling and retry behavior should also be manually verified using the dashboard.

## Deployment notes

For a simple Render web-service demo:

1. Push this repository to GitHub.
2. Create a new **Web Service** in Render and connect the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn --workers 1 --threads 4 --bind 0.0.0.0:$PORT app:app`
5. Set environment variables:
   - `TASKFLOW_START_WORKERS=true`
   - `WORKER_COUNT=2`
   - `TASKFLOW_DB=/tmp/taskflow.db`

The one-worker Gunicorn setting is intentional: this prototype starts worker threads inside the web process. Running multiple web-server processes would start multiple independent worker pools. `/tmp` storage may be ephemeral on hosted platforms, so task data can be lost on redeploy/restart. Use a managed persistent database and a separate worker service for a more robust deployment.

## Engineering trade-offs and next steps

- Replace SQLite polling with Redis + a broker-backed queue such as RabbitMQ or Amazon SQS.
- Run API and workers as separate services.
- Add task leases / recovery for workers that stop after claiming a task.
- Add authentication, rate limiting, structured logs and metrics.
- Add idempotency keys to make retry-safe task handlers.
- Add integration tests for concurrent claims, priority ordering and retry exhaustion.
- Use PostgreSQL for concurrent multi-service deployments.

## Suggested demo checklist

- Submit high-, medium- and low-priority tasks.
- Submit an uppercase task and inspect its result.
- Submit a fail-once task and observe its retry count.
- Refresh the page and confirm task records remain available while the database file persists.
- Run the unit tests.
- Pause workers and submit tasks with different priorities.
- Resume workers and inspect picked order and worker names.
- Submit an always-fail task and observe retry exhaustion.

## Resume project description

**TaskFlow – Background Task Queue & Worker Monitoring System** | Python, Flask, SQLite, REST APIs, Multithreading

- Built a full-stack task processing application with REST APIs, priority-based scheduling and a live monitoring dashboard.
- Implemented concurrent background workers with atomic task claiming, persistent task states and automatic retry handling.
- Designed SQLite schemas and indexed queue queries to support priority ordering, task tracking and execution statistics.
- Added input validation and automated API tests for reliable task submission and retrieval.

Only include features and test results you have personally run and verified.
