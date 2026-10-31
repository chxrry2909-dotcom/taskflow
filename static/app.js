const $ = (id) => document.getElementById(id);

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[c]));

function updatePayloadLabel() {
  const type = $("taskType").value;

  $("payloadLabel").firstChild.textContent =
    type === "uppercase" ? "Text" :
    type === "report" ? "Report title" : "Message";

  $("payload").placeholder =
    type === "uppercase" ? "text to convert" : "Enter task details";
}

$("taskType").addEventListener("change", updatePayloadLabel);

$("taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();

  const type = $("taskType").value;
  const value = $("payload").value.trim();
  let payload = {};

  if (type === "uppercase") {
    payload = { text: value };
  } else if (type === "report") {
    payload = {
      title: value || "Daily report",
      items: ["orders", "customers", "inventory"]
    };
  } else {
    payload = { message: value || "Hello from TaskFlow" };
  }

  const response = await fetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task_type: type,
      priority: $("priority").value,
      payload
    })
  });

  const data = await response.json();

  $("notice").textContent = response.ok
    ? `Task ${data.id.slice(0, 8)} added to the queue.`
    : data.error;

  if (response.ok) await refresh();
});

$("filter").addEventListener("change", refresh);
$("refreshBtn").addEventListener("click", refresh);

$("workerToggle").addEventListener("click", async () => {
  const isPaused = $("workerToggle").dataset.paused === "true";
  const action = isPaused ? "resume" : "pause";

  await fetch(`/api/workers/${action}`, {
    method: "POST"
  });

  await refresh();
});

async function refresh() {
  try {
    const [statsResponse, tasksResponse] = await Promise.all([
      fetch("/api/stats"),
      fetch("/api/tasks" + (
        $("filter").value ? "?status=" + $("filter").value : ""
      ))
    ]);

    const stats = await statsResponse.json();
    const data = await tasksResponse.json();

    ["pending", "processing", "completed", "failed"].forEach(key => {
      $(key).textContent = stats[key];
    });

    $("workerCount").textContent = `${stats.workers} workers`;

    $("workerToggle").dataset.paused = String(stats.paused);
    $("workerToggle").textContent = stats.paused
      ? "▶ Resume Workers"
      : "Ⅱ Pause Workers";

    $("taskRows").innerHTML = data.tasks.length
      ? data.tasks.map(task => {
          const output = task.result
            ? JSON.stringify(task.result)
            : (task.error || "—");

          return `<tr>
            <td><span class="task-id">${esc(task.id.slice(0, 8))}</span></td>
            <td>${esc(task.task_type)}</td>
            <td><span class="priority-tag">${esc(task.priority)}</span></td>
            <td>${task.picked_order ?? "Waiting"}</td>
            <td>${esc(task.worker_name || "—")}</td>
            <td><span class="status ${esc(task.status)}">${esc(task.status)}</span></td>
            <td>${task.attempts}/${task.max_retries + 1}</td>
            <td>${esc(output).slice(0, 90)}</td>
          </tr>`;
        }).join("")
      : '<tr><td colspan="8" class="empty">No tasks found. Submit your first job above.</td></tr>';

  } catch {
    $("notice").textContent =
      "Unable to reach the server. Check that TaskFlow is running.";
  }
}

refresh();
setInterval(refresh, 3000);