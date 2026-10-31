
import json
import threading
import time

from database import get_db, utc_now


def execute_task(task_type, payload, attempts=1):

    if task_type == "echo":
        return {
            "message": payload.get("message", "Task completed")
        }

    if task_type == "uppercase":
        return {
            "text": payload["text"].upper()
        }

    if task_type == "report":
        return {
            "title": payload.get("title", "TaskFlow report"),
            "items_received": len(payload.get("items", [])),
            "summary": "Report generated successfully"
        }

    if task_type == "fail_once":
        if attempts == 1:
            raise RuntimeError(
                payload.get("message", "Intentional first-attempt failure")
            )

        return {
            "message": "Recovered after retry",
            "successful_attempt": attempts
        }
    
    if task_type == "always_fail":
            raise RuntimeError(
                "Permanent failure demonstration"
            )

    raise ValueError("Unsupported task type")


class WorkerPool:

    def __init__(self, database_path, worker_count=2, poll_interval=0.5):
        self.database_path = database_path
        self.worker_count = max(1, worker_count)
        self.poll_interval = poll_interval

        self._threads = []
        self._stop = threading.Event()
        self._paused = threading.Event()

    def start(self):
        if self._threads:
            return

        self._stop.clear()

        for number in range(self.worker_count):
            thread = threading.Thread(
                target=self._run,
                name=f"taskflow-worker-{number + 1}",
                daemon=True
            )

            thread.start()
            self._threads.append(thread)

    def stop(self):
        self._stop.set()

        for thread in self._threads:
            thread.join(timeout=2)

        self._threads.clear()

    def pause(self):
        self._paused.set()

    def resume(self):
        self._paused.clear()

    @property
    def is_paused(self):
        return self._paused.is_set()

    def _claim_task(self):
        conn = get_db(self.database_path)

        try:
            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute("""
                SELECT * FROM tasks
                WHERE status = 'pending'
                ORDER BY priority_rank DESC, created_at ASC
                LIMIT 1
            """).fetchone()

            if row is None:
                conn.commit()
                return None

            now = utc_now()

            changed = conn.execute("""
                UPDATE tasks
                SET status = 'processing',
                    attempts = attempts + 1,
                    started_at = COALESCE(started_at, ?),
                    updated_at = ?,
                    error = NULL,
                    picked_order = COALESCE(
                        picked_order,
                        (SELECT COALESCE(MAX(picked_order), 0) + 1
                         FROM tasks)
                    ),
                    worker_name = ?
                WHERE id = ? AND status = 'pending'
            """, (
                now,
                now,
                threading.current_thread().name,
                row["id"]
            )).rowcount

            conn.commit()

            if changed != 1:
                return None

            return dict(row)

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    def _finish(self, task_id, result):
        now = utc_now()

        with get_db(self.database_path) as conn:
            conn.execute("""
                UPDATE tasks
                SET status = 'completed',
                    result = ?,
                    error = NULL,
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ?
            """, (json.dumps(result), now, now, task_id))

    def _fail_or_retry(self, task, error):
        now = utc_now()

        with get_db(self.database_path) as conn:
            current = conn.execute("""
                SELECT attempts, max_retries
                FROM tasks
                WHERE id = ?
            """, (task["id"],)).fetchone()

            if current and current["attempts"] <= current["max_retries"]:
                delay = min(
                    2 ** max(current["attempts"] - 1, 0),
                    4
                )

                conn.execute("""
                    UPDATE tasks
                    SET status = 'pending',
                        error = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (str(error)[:500], now, task["id"]))

            else:
                delay = 0

                conn.execute("""
                    UPDATE tasks
                    SET status = 'failed',
                        error = ?,
                        updated_at = ?,
                        completed_at = ?
                    WHERE id = ?
                """, (str(error)[:500], now, now, task["id"]))

        if delay:
            time.sleep(delay)

    def _run(self):
        while not self._stop.is_set():

            if self._paused.is_set():
                self._stop.wait(self.poll_interval)
                continue

            try:
                task = self._claim_task()

                if task is None:
                    self._stop.wait(self.poll_interval)
                    continue

                payload = json.loads(task["payload"])

                try:
                    result = execute_task(
                        task["task_type"],
                        payload,
                        task["attempts"] + 1
                    )

                    self._finish(task["id"], result)

                except Exception as exc:
                    self._fail_or_retry(task, exc)

            except Exception as exc:
                print(f"Worker error: {exc}")
                self._stop.wait(self.poll_interval)
