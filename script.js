const $ = (id) => document.getElementById(id);

const state = {
  goal: "",
  files: [],
  planCreated: false,
  approved: false,
  running: false,
  finished: false,
  cancelled: false,
  retries: 0,
  completed: 0,
  logs: [],
  results: [],
  timerIds: []
};

const steps = [
  {
    title: "Read the input file",
    description: "Locate and prepare the supplied data for analysis.",
    tool: "read_file",
    output: "Input preparation"
  },
  {
    title: "Analyze the data",
    description: "Identify trends and calculate the largest sales declines.",
    tool: "analyze_csv",
    output: "Analysis summary"
  },
  {
    title: "Create the report",
    description: "Compile the findings, explanations, and supporting evidence.",
    tool: "create_report",
    output: "Report draft"
  },
  {
    title: "Verify and save results",
    description: "Check the expected output and prepare the report for download.",
    tool: "read_saved_report",
    output: "Verification summary"
  }
];

const criteria = [
  "A report preview is available.",
  "The requested findings are included in the report.",
  "Verification checks have been completed.",
  "The report can be downloaded."
];

function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[char]);
}

function toast(message) {
  const element = $("toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => element.classList.remove("show"), 2800);
}

function showPage(page) {
  const pages = {
    home: "Welcome to OmniWeave",
    plan: "Dynamic Plan",
    execution: "Live Execution",
    results: "Results & Verification",
    tools: "Tools & Activity"
  };

  document.querySelectorAll(".page").forEach((element) => {
    element.classList.toggle("active", element.id === `page-${page}`);
  });

  document.querySelectorAll(".nav-item").forEach((element) => {
    element.classList.toggle("active", element.dataset.page === page);
  });

  $("page-heading").textContent = pages[page] || "OmniWeave";
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => showPage(button.dataset.page));
});

document.querySelector(".brand").addEventListener("click", (event) => {
  event.preventDefault();
  showPage("home");
});

$("goal-input").addEventListener("input", () => {
  $("char-count").textContent =
    `${$("goal-input").value.length} characters`;
});

$("file-input").addEventListener("change", (event) => {
  state.files = Array.from(event.target.files || []);

  $("file-list").innerHTML = state.files.map((file) =>
    `<span class="file-chip">▤ ${escapeHTML(file.name)} · ${formatBytes(file.size)}</span>`
  ).join("");

  if (state.files.length) {
    addLog(`Selected ${state.files.length} file(s) for the demo.`);
  }
});

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function addLog(message) {
  const entry = {
    time: new Date().toLocaleTimeString(),
    message
  };

  state.logs.unshift(entry);
  renderLogs();
}

function renderLogs() {
  $("activity-log").innerHTML = state.logs.length
    ? state.logs.map((entry) =>
        `<p class="log-line"><span class="log-time">${escapeHTML(entry.time)}</span><span>●</span>${escapeHTML(entry.message)}</p>`
      ).join("")
    : '<div class="empty-state">No activity recorded yet.</div>';

  $("audit-trail").innerHTML = state.logs.length
    ? state.logs.map((entry) =>
        `<div class="audit-entry"><time>${escapeHTML(entry.time)}</time><p>${escapeHTML(entry.message)}</p></div>`
      ).join("")
    : '<div class="empty-state">No activity recorded yet.</div>';

  $("audit-count").textContent = state.logs.length;
}

function createPlan() {
  const goal = $("goal-input").value.trim();

  if (!goal) {
    toast("Please enter a goal first.");
    $("goal-input").focus();
    return;
  }

  if (state.running) {
    toast("Wait for the current demo to finish.");
    return;
  }

  clearTimers();

  state.goal = goal;
  state.planCreated = true;
  state.approved = false;
  state.finished = false;
  state.cancelled = false;
  state.completed = 0;
  state.retries = 0;
  state.results = [];

  $("plan-goal").textContent = state.goal;
  $("plan-status").textContent = "Draft";
  $("step-count").textContent = `${steps.length} steps`;

  $("plan-steps").innerHTML = steps.map((step, index) => `
    <article class="workflow-step">
      <div class="step-number">${String(index + 1).padStart(2, "0")}</div>
      <div class="step-body">
        <h4>${escapeHTML(step.title)}</h4>
        <p>${escapeHTML(step.description)}</p>
        <div class="step-meta">
          <span class="tool-tag">⌘ ${escapeHTML(step.tool)}</span>
          <span class="pill">Expected: ${escapeHTML(step.output)}</span>
        </div>
      </div>
      <span class="pill">Pending</span>
    </article>
  `).join("");

  $("criteria-list").innerHTML = criteria.map((criterion) =>
    `<li>${escapeHTML(criterion)}</li>`
  ).join("");

  $("approve-plan").disabled = false;
  $("run-demo").disabled = true;
  $("execution-status").textContent = "Idle";

  updateProgress();
  renderExecutionSteps();
  resetResults();

  addLog("A draft plan was created from the submitted goal.");
  showPage("plan");
  toast("Demo plan created. Review it before approving.");
}

function resetResults() {
  $("result-symbol").textContent = "◌";
  $("result-heading").textContent = "No results yet";
  $("result-description").textContent =
    "Run the demo execution to see verification results.";

  $("verification-list").innerHTML =
    '<div class="empty-state">Verification checks will appear after demo execution.</div>';

  $("report-preview").textContent =
    "Your demo report will appear here after execution.";

  $("download-report").disabled = true;
}

$("generate-plan").addEventListener("click", createPlan);

$("edit-plan").addEventListener("click", () => {
  showPage("home");
  $("goal-input").focus();
});

$("cancel-plan").addEventListener("click", () => {
  if (state.running) {
    toast("Reset the demo before cancelling an active run.");
    return;
  }

  state.planCreated = false;
  state.approved = false;
  state.cancelled = true;

  $("plan-status").textContent = "Cancelled";
  $("approve-plan").disabled = true;
  $("run-demo").disabled = true;

  addLog("The draft plan was cancelled.");
  toast("Plan cancelled.");
});

$("approve-plan").addEventListener("click", () => {
  if (!state.planCreated || state.cancelled) {
    toast("Generate a plan first.");
    return;
  }

  state.approved = true;
  $("plan-status").textContent = "Approved";
  $("execution-status").textContent = "Ready";
  $("run-demo").disabled = false;

  addLog("Plan approved by the user.");
  renderExecutionSteps();
  showPage("execution");
  toast("Plan approved. Start the demo when ready.");
});

function renderExecutionSteps() {
  $("execution-steps").innerHTML = steps.map((step, index) => {
    let status = "Pending";
    let number = String(index + 1).padStart(2, "0");

    if (index < state.completed) {
      status = "Completed";
      number = "✓";
    } else if (state.running && index === state.completed) {
      status = "Running";
      number = "↻";
    } else if (state.finished && state.completed === steps.length) {
      status = "Completed";
      number = "✓";
    }

    return `
      <article class="workflow-step">
        <div class="step-number">${number}</div>
        <div class="step-body">
          <h4>${escapeHTML(step.title)}</h4>
          <p>${escapeHTML(step.description)}</p>
          <div class="step-meta"><span class="tool-tag">${escapeHTML(step.tool)}</span></div>
        </div>
        <span class="pill">${status}</span>
      </article>
    `;
  }).join("");
}

function updateProgress() {
  const percent = Math.round((state.completed / steps.length) * 100);

  $("progress-number").textContent = `${percent}%`;
  $("progress-bar").style.width = `${percent}%`;
  $("completed-number").textContent = `${state.completed} / ${steps.length}`;
  $("recovery-number").textContent = state.retries;
}

function wait(ms, callback) {
  const timer = setTimeout(() => {
    state.timerIds = state.timerIds.filter((id) => id !== timer);
    callback();
  }, ms);

  state.timerIds.push(timer);
}

function clearTimers() {
  state.timerIds.forEach(clearTimeout);
  state.timerIds = [];
}

function runStep(index) {
  if (!state.running) return;

  if (index >= steps.length) {
    finishExecution();
    return;
  }

  const step = steps[index];

  renderExecutionSteps();
  $("execution-status").textContent = "Running";
  addLog(`Started step ${index + 1}: ${step.title} (${step.tool}).`);

  // Demonstrate recovery once on the analysis step.
  if (index === 1 && state.retries === 0) {
    wait(900, () => {
      if (!state.running) return;

      state.retries = 1;
      updateProgress();
      addLog("Simulated tool failure: temporary analysis error.");
      addLog("Recovery: retrying the analysis step.");

      wait(1000, () => {
        if (!state.running) return;
        completeStep(index);
      });
    });
    return;
  }

  wait(1100, () => {
    if (!state.running) return;
    completeStep(index);
  });
}

function completeStep(index) {
  if (!state.running) return;

  state.completed = index + 1;
  updateProgress();
  renderExecutionSteps();
  addLog(`Completed step ${index + 1}: ${steps[index].title}.`);

  runStep(index + 1);
}

function finishExecution() {
  state.running = false;
  state.finished = true;

  $("execution-status").textContent = "Completed";
  $("run-demo").disabled = true;

  updateProgress();
  renderExecutionSteps();

  addLog("All demo steps completed.");
  addLog("Verification checks completed in demo mode.");

  createDemoResults();
  showPage("results");
  toast("Demo finished. Review the results and verification.");
}

function createDemoResults() {
  $("result-symbol").textContent = "✓";
  $("result-heading").textContent = "Demo completed";
  $("result-description").textContent =
    "The simulated workflow finished. The following checks represent demo evidence, not real analysis of your uploaded files.";

  $("verification-list").innerHTML = criteria.map((criterion) => `
    <div class="verify-row">
      <span class="verify-symbol">✓</span>
      <div>
        <strong>${escapeHTML(criterion)}</strong>
        <p>Passed in the front-end demonstration. This is not an independent backend verification.</p>
      </div>
    </div>
  `).join("");

  const report = [
    "# OmniWeave Demo Report",
    "",
    "## Submitted goal",
    state.goal,
    "",
    "## Workflow status",
    "Demo steps completed: 4 of 4",
    `Simulated recovery events: ${state.retries}`,
    "",
    "## Findings",
    "This is a demonstration report. No uploaded dataset was analyzed.",
    "Connect the Python analysis backend to generate real findings.",
    "",
    "## Verification",
    ...criteria.map((criterion) => `- [x] ${criterion} (simulated)`),
    "",
    "## Audit",
    ...state.logs.slice().reverse().map((entry) =>
      `- ${entry.time}: ${entry.message}`
    )
  ].join("\n");

  $("report-preview").textContent = report;
  $("download-report").disabled = false;
}

$("run-demo").addEventListener("click", () => {
  if (!state.approved || state.running) return;

  state.running = true;
  state.finished = false;
  state.completed = 0;
  state.retries = 0;

  $("run-demo").disabled = true;
  $("execution-status").textContent = "Running";

  updateProgress();
  renderExecutionSteps();

  addLog("Demo execution started.");
  runStep(0);
});

$("reset-demo").addEventListener("click", () => {
  clearTimers();

  state.running = false;
  state.finished = false;
  state.approved = false;
  state.completed = 0;
  state.retries = 0;
  state.results = [];

  $("run-demo").disabled = true;
  $("approve-plan").disabled = !state.planCreated;
  $("execution-status").textContent = "Idle";

  updateProgress();
  renderExecutionSteps();
  resetResults();

  addLog("Demo execution state reset.");
  toast("Execution reset. You can approve and run the plan again.");
});

$("download-report").addEventListener("click", () => {
  if (!state.finished) return;

  const report = $("report-preview").textContent;
  const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = "sales_analysis_report.md";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);

  addLog("Downloaded the demo report.");
  toast("Demo report downloaded.");
});

$("clear-log").addEventListener("click", () => {
  state.logs = [];
  renderLogs();
  toast("Audit trail cleared.");
});

renderLogs();
updateProgress();