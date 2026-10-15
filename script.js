"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  const state = {
    goal: "",
    files: [],
    plan: [],
    approved: false,
    running: false,
    completed: false,
    retries: 0,
    events: [],
    verification: [],
    report: "",
    runId: 0
  };

  const pageNames = {
    home: "Home",
    plan: "Dynamic Plan",
    execution: "Live Execution",
    results: "Results & Verification",
    tools: "Tools & Activity"
  };

  const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

  function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, char => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    })[char]);
  }

  function timestamp() {
    return new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
  }

  let toastTimer;

  function toast(message) {
    $("#toast-message").textContent = message;
    $("#toast").classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => $("#toast").classList.remove("show"), 3000);
  }

  function navigate(page) {
    if (!pageNames[page]) return;

    $$(".page").forEach(section => {
      section.classList.toggle("active", section.id === `page-${page}`);
    });

    $$(".nav-item").forEach(button => {
      const active = button.dataset.page === page;
      button.classList.toggle("active", active);
      button.setAttribute("aria-current", active ? "page" : "false");
    });

    $("#breadcrumb-current").textContent = pageNames[page];
    $("#sidebar").classList.remove("open");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function addEvent(title, description, type = "info") {
    const event = { title, description, type, time: timestamp() };
    state.events.unshift(event);

    const activity = $("#activity-log");
    const empty = activity.querySelector(".log-empty");
    if (empty) empty.remove();

    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.innerHTML = `
      <span class="log-bullet ${escapeHTML(type)}"></span>
      <div>
        <strong>${escapeHTML(title)}</strong>
        <p>${escapeHTML(description)}</p>
        <span class="log-time">${escapeHTML(event.time)}</span>
      </div>`;
    activity.prepend(entry);

    renderAuditTrail();
  }

  function renderAuditTrail() {
    const container = $("#audit-trail");

    if (!state.events.length) {
      container.innerHTML = '<div class="log-empty">No events recorded yet.</div>';
      return;
    }

    container.innerHTML = state.events.map(event => `
      <div class="audit-row">
        <time>${escapeHTML(event.time)}</time>
        <div>
          <strong>${escapeHTML(event.title)}</strong>
          <p>${escapeHTML(event.description)}</p>
        </div>
        <span class="audit-type">${escapeHTML(event.type.toUpperCase())}</span>
      </div>`).join("");
  }

  function renderFiles() {
    const container = $("#file-list");
    container.innerHTML = "";

    state.files.forEach((file, index) => {
      const item = document.createElement("div");
      item.className = "file-item";
      item.innerHTML = `
        <span>▧</span>
        <span>${escapeHTML(file.name)}</span>
        <button class="file-remove" type="button"
          aria-label="Remove ${escapeHTML(file.name)}"
          data-remove-file="${index}">×</button>`;
      container.appendChild(item);
    });
  }

  function invalidatePlan() {
    state.plan = [];
    state.approved = false;
    state.running = false;
    state.completed = false;
    state.verification = [];
    state.report = "";

    $("#approve-plan").disabled = true;
    $("#run-demo").disabled = true;
    $("#download-report").disabled = true;

    $("#plan-status").textContent = "AWAITING REVIEW";
    $("#plan-status").className = "status-badge status-planned";
    $("#plan-steps").innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">◇</span>
        <strong>Your plan will appear here</strong>
        <p>Enter a goal on Home and select Generate plan.</p>
      </div>`;

    $("#execution-steps").innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">◉</span>
        <strong>Nothing running yet</strong>
        <p>Generate and approve a plan before starting execution.</p>
      </div>`;

    $("#execution-status").textContent = "Not started";
    $("#completed-count").innerHTML = '0 <small>/ 4</small>';
    $("#retry-count").textContent = "0";
    $("#execution-footer").textContent = "Approve a plan to enable execution.";

    $("#result-icon").textContent = "◈";
    $("#result-title").textContent = "Results are waiting";
    $("#result-subtitle").textContent =
      "Run the workflow to generate a demo result and verification summary.";
    $("#result-status").textContent = "NOT RUN";
    $("#result-status").className = "status-badge status-planned";

    $("#verification-count").textContent = "0 CHECKS";
    $("#verification-list").innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">✓</span>
        <strong>No verification yet</strong>
        <p>Verification details will appear after execution.</p>
      </div>`;

    $("#report-preview").innerHTML =
      '<div class="report-placeholder">Your generated report will appear here.</div>';

    $("#plan-description").textContent = "A suggested workflow for your goal.";
    $("#plan-step-count").textContent = "4 STEPS";
  }

  function makePlan(goal) {
    const normalizedGoal = goal.trim();
    const lower = normalizedGoal.toLowerCase();

    let steps;

    if (/research|competitor|market|compare/.test(lower)) {
      steps = [
        ["Define the research scope", "Identify the key questions, comparison criteria, and desired outcome.", "Analysis"],
        ["Collect relevant information", "Outline the information sources and evidence needed for the comparison.", "Research"],
        ["Analyze and organize findings", "Compare the findings, identify patterns, and summarize key differences.", "Synthesis"],
        ["Prepare the final report", "Organize the findings into a clear report with conclusions and next steps.", "Reporting"]
      ];
    } else if (/data|sales|spreadsheet|analy[sz]e|dataset/.test(lower)) {
      steps = [
        ["Inspect the data", "Define the relevant fields, scope, and questions to investigate.", "Inspection"],
        ["Prepare the analysis", "Outline data-quality checks and the calculations needed.", "Preparation"],
        ["Identify patterns", "Summarize potential trends, comparisons, and notable findings.", "Analysis"],
        ["Present the results", "Prepare a concise summary of findings and recommended next steps.", "Reporting"]
      ];
    } else if (/plan|project|schedule|milestone|organize/.test(lower)) {
      steps = [
        ["Clarify the desired outcome", "Identify the project objective and what success should look like.", "Scoping"],
        ["Break down the work", "Outline the tasks, dependencies, and milestones.", "Planning"],
        ["Prioritize the steps", "Organize work by importance and logical order.", "Prioritization"],
        ["Create the action plan", "Summarize milestones, priorities, and immediate next steps.", "Delivery"]
      ];
    } else {
      steps = [
        ["Understand the goal", "Identify the desired outcome and the criteria for success.", "Analysis"],
        ["Design an approach", "Break the goal into manageable tasks and identify dependencies.", "Planning"],
        ["Work through the steps", "Process the proposed tasks and review progress along the way.", "Execution"],
        ["Review the outcome", "Summarize the result, check the completion criteria, and identify next steps.", "Verification"]
      ];
    }

    return steps.map((step, index) => ({
      id: index + 1,
      title: step[0],
      description: step[1],
      category: step[2],
      status: "planned"
    }));
  }

  function renderPlan() {
    $("#plan-goal").textContent = state.goal;
    $("#plan-step-count").textContent = `${state.plan.length} STEPS`;

    $("#plan-description").textContent =
      "A four-step suggested workflow. Review it before approving execution.";

    $("#plan-steps").innerHTML = state.plan.map(step => `
      <div class="timeline-step">
        <div class="step-node">${step.id.toString().padStart(2, "0")}</div>
        <div class="step-content">
          <h4>${escapeHTML(step.title)}</h4>
          <p>${escapeHTML(step.description)}</p>
          <div class="step-meta"><span>${escapeHTML(step.category)}</span></div>
        </div>
        <span class="step-state">PLANNED</span>
      </div>`).join("");

    $("#plan-status").textContent = "AWAITING REVIEW";
    $("#plan-status").className = "status-badge status-planned";
    $("#approve-plan").disabled = false;
  }

  $("#goal-input").addEventListener("input", () => {
    const goal = $("#goal-input").value.trim();

    if (state.plan.length && goal !== state.goal) {
      invalidatePlan();
    }
  });

  $$(".nav-item").forEach(button => {
    button.addEventListener("click", () => navigate(button.dataset.page));
  });

  document.querySelector(".brand").addEventListener("click", event => {
    event.preventDefault();
    navigate("home");
  });

  $("#mobile-menu").addEventListener("click", () => {
    $("#sidebar").classList.toggle("open");
  });

  $$(".prompt-chip").forEach(button => {
    button.addEventListener("click", () => {
      $("#goal-input").value = button.dataset.prompt;
      $("#goal-input").dispatchEvent(new Event("input", { bubbles: true }));
      $("#goal-input").focus();
    });
  });

  $("#file-input").addEventListener("change", event => {
    const incoming = [...event.target.files];

    incoming.forEach(file => {
      const duplicate = state.files.some(existing =>
        existing.name === file.name &&
        existing.size === file.size &&
        existing.lastModified === file.lastModified
      );
      if (!duplicate) state.files.push(file);
    });

    renderFiles();
    event.target.value = "";

    if (incoming.length) {
      addEvent("Files selected", `${incoming.length} file(s) added to the local interface.`);
      toast("Files added to the workspace");
    }
  });

  $("#file-list").addEventListener("click", event => {
    const button = event.target.closest("[data-remove-file]");
    if (!button) return;

    const index = Number(button.dataset.removeFile);
    const file = state.files[index];
    if (!file) return;

    state.files.splice(index, 1);
    renderFiles();
    addEvent("File removed", `${file.name} was removed from the selected files.`);
  });

  $("#generate-plan").addEventListener("click", () => {
    const goal = $("#goal-input").value.trim();

    if (!goal) {
      toast("Enter a goal before generating a plan.");
      $("#goal-input").focus();
      return;
    }

    state.runId++;
    state.goal = goal;
    state.plan = makePlan(goal);
    state.approved = false;
    state.running = false;
    state.completed = false;
    state.retries = 0;
    state.verification = [];
    state.report = "";

    invalidatePlan();
    // invalidatePlan clears the previous plan; restore the newly created one.
    state.plan = makePlan(goal);
    renderPlan();

    addEvent("Plan generated", "A sample workflow was created for your goal.");
    if (state.files.length) {
      addEvent(
        "Attachments noted",
        `${state.files.length} selected file(s) are listed but are not read or analyzed in this demo.`
      );
    }

    navigate("plan");
    toast("Your proposed plan is ready to review.");
  });

  $("#approve-plan").addEventListener("click", () => {
    if (!state.plan.length) {
      toast("Generate a plan first.");
      return;
    }

    state.approved = true;
    $("#plan-status").textContent = "APPROVED";
    $("#plan-status").className = "status-badge status-success";
    $("#approve-plan").disabled = true;
    $("#run-demo").disabled = false;
    $("#execution-footer").textContent = "Plan approved. You can start the demo run.";

    addEvent("Plan approved", "You approved the proposed workflow.");
    toast("Plan approved. Ready to run.");
    navigate("execution");

    renderExecutionSteps();
  });

  function renderExecutionSteps() {
    if (!state.plan.length) return;

    $("#execution-steps").innerHTML = state.plan.map(step => {
      let nodeClass = "";
      let stateClass = "";
      let label = "QUEUED";
      let symbol = step.id.toString().padStart(2, "0");

      if (step.status === "complete") {
        nodeClass = "complete";
        stateClass = "complete";
        label = "COMPLETE";
        symbol = "✓";
      } else if (step.status === "running") {
        nodeClass = "running";
        stateClass = "running";
        label = "IN PROGRESS";
        symbol = "↻";
      } else if (step.status === "error") {
        nodeClass = "error";
        stateClass = "error";
        label = "RECOVERY";
        symbol = "!";
      }

      return `
        <div class="timeline-step">
          <div class="step-node ${nodeClass}">${symbol}</div>
          <div class="step-content">
            <h4>${escapeHTML(step.title)}</h4>
            <p>${escapeHTML(step.description)}</p>
            <div class="step-meta"><span>${escapeHTML(step.category)}</span></div>
          </div>
          <span class="step-state ${stateClass}">${label}</span>
        </div>`;
    }).join("");
  }

  async function runExecution() {
    if (!state.approved || state.running || state.completed) return;

    state.running = true;
    state.retries = 0;
    const thisRun = state.runId;

    $("#run-demo").disabled = true;
    $("#run-demo").querySelector("span:first-child").textContent = "Running...";
    $("#execution-status").textContent = "In progress";
    $("#execution-footer").textContent = "The demo workflow is running.";
    $("#plan-status").textContent = "EXECUTING";
    $("#plan-status").className = "status-badge status-running";

    state.plan.forEach(step => { step.status = "planned"; });
    renderExecutionSteps();

    addEvent("Execution started", "The approved four-step demo workflow has started.");
    toast("Demo execution started.");

    for (let index = 0; index < state.plan.length; index++) {
      if (thisRun !== state.runId) return;

      const step = state.plan[index];
      step.status = "running";
      renderExecutionSteps();
      $("#completed-count").innerHTML = `${index} <small>/ ${state.plan.length}</small>`;

      addEvent("Step started", `${step.title} is now in progress.`);
      await wait(1000);

      if (thisRun !== state.runId) return;

      // Demonstrate one recovery event during the second step.
      if (index === 1) {
        step.status = "error";
        state.retries++;
        $("#retry-count").textContent = String(state.retries);
        renderExecutionSteps();

        addEvent(
          "Recovery triggered",
          "A simulated issue was detected. The workflow is adjusting its approach.",
          "warning"
        );
        await wait(750);

        if (thisRun !== state.runId) return;

        step.status = "running";
        renderExecutionSteps();
        addEvent("Recovery complete", "The simulated retry succeeded and the workflow continued.", "success");
        await wait(650);
      }

      if (thisRun !== state.runId) return;

      step.status = "complete";
      renderExecutionSteps();
      $("#completed-count").innerHTML = `${index + 1} <small>/ ${state.plan.length}</small>`;
      addEvent("Step completed", `${step.title} finished in the demo.`, "success");
      await wait(500);
    }

    if (thisRun !== state.runId) return;

    state.running = false;
    state.completed = true;
    $("#execution-status").textContent = "Completed";
    $("#execution-footer").textContent = "Demo run complete. Review the verification results.";
    $("#run-demo").querySelector("span:first-child").textContent = "Execution complete";
    $("#plan-status").textContent = "COMPLETED";
    $("#plan-status").className = "status-badge status-success";

    addEvent("Execution completed", "All simulated workflow steps finished successfully.", "success");
    createDemoResults();
    toast("Demo run complete. Results are ready.");
  }

  $("#run-demo").addEventListener("click", runExecution);

  function createDemoResults() {
    state.verification = [
      {
        title: "Goal captured",
        description: "The submitted goal is available in the current demo session.",
        passed: true
      },
      {
        title: "Workflow steps completed",
        description: `${state.plan.length} simulated steps reached the completed state.`,
        passed: state.plan.every(step => step.status === "complete")
      },
      {
        title: "Recovery path demonstrated",
        description: "The demo displayed a simulated recovery and retry event.",
        passed: state.retries > 0
      },
      {
        title: "Report prepared",
        description: "A local Markdown summary was generated for export.",
        passed: true
      }
    ];

    renderResults();

    const reportLines = [
      "# OmniWeave Demo Execution Report",
      "",
      `Generated: ${new Date().toLocaleString()}`,
      "",
      "## Goal",
      state.goal,
      "",
      "## Execution summary",
      "- Mode: Frontend simulation",
      `- Steps completed: ${state.plan.filter(step => step.status === "complete").length}/${state.plan.length}`,
      `- Simulated recovery events: ${state.retries}`,
      "- Overall demo status: Completed",
      "",
      "## Workflow steps",
      ...state.plan.map(step =>
        `${step.id}. ${step.title} — ${step.status === "complete" ? "Completed (simulated)" : step.status}`
      ),
      "",
      "## Verification",
      ...state.verification.map(item =>
        `- [${item.passed ? "x" : " "}] ${item.title}: ${item.description}`
      ),
      "",
      "## Limitations",
      "This report describes a browser-based simulation. No external AI model, tools, or APIs were invoked.",
      "Selected attachments were listed in the UI but were not read or analyzed."
    ];

    state.report = reportLines.join("\n");
    $("#download-report").disabled = false;

    addEvent("Verification prepared", "The demo verification checklist and report are ready.", "success");
  }

  function renderResults() {
    const passed = state.verification.filter(item => item.passed).length;
    const total = state.verification.length;

    $("#result-icon").textContent = "✓";
    $("#result-title").textContent = "Demo workflow completed";
    $("#result-subtitle").textContent =
      "The simulated workflow finished. Review the checklist and remember that no real task was executed.";
    $("#result-status").textContent = passed === total ? "DEMO CHECKS PASSED" : "REVIEW NEEDED";
    $("#result-status").className =
      `status-badge ${passed === total ? "status-success" : "status-planned"}`;

    $("#verification-count").textContent = `${passed}/${total} CHECKS`;
    $("#verification-list").innerHTML = state.verification.map(item => `
      <div class="verification-item">
        <span class="check-icon ${item.passed ? "" : "pending"}">${item.passed ? "✓" : "–"}</span>
        <div>
          <strong>${escapeHTML(item.title)}</strong>
          <p>${escapeHTML(item.description)}</p>
        </div>
      </div>`).join("");

    $("#report-preview").innerHTML = `
      <h4>OmniWeave Demo Report</h4>
      <p><strong>Goal:</strong> ${escapeHTML(state.goal)}</p>
      <h5>Execution summary</h5>
      <p>${state.plan.length} of ${state.plan.length} simulated steps completed.</p>
      <p>${state.retries} simulated recovery event(s).</p>
      <h5>Verification</h5>
      <p>${passed} of ${total} demo checks passed.</p>
      <h5>Important limitation</h5>
      <p>This is a simulated result. The system did not perform the requested task using an AI model or external tools.</p>`;
  }

  $("#download-report").addEventListener("click", () => {
    if (!state.report) {
      toast("Run the workflow to generate a report first.");
      return;
    }

    const blob = new Blob([state.report], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = "omniweave_demo_report.md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);

    addEvent("Report downloaded", "The Markdown report was downloaded to your device.", "success");
    toast("Report downloaded.");
  });

  $("#clear-log").addEventListener("click", () => {
    state.events = [];
    $("#activity-log").innerHTML = '<div class="log-empty">Your activity will appear here.</div>';
    renderAuditTrail();
    toast("Audit trail cleared.");
  });

  function resetWorkspace() {
    state.runId++;
    state.goal = "";
    state.files = [];
    state.plan = [];
    state.approved = false;
    state.running = false;
    state.completed = false;
    state.retries = 0;
    state.events = [];
    state.verification = [];
    state.report = "";

    $("#goal-input").value = "";
    $("#file-input").value = "";
    renderFiles();
    invalidatePlan();

    $("#activity-log").innerHTML = '<div class="log-empty">Your activity will appear here.</div>';
    renderAuditTrail();

    $("#run-demo").querySelector("span:first-child").textContent = "Run execution";
    $("#run-demo").disabled = true;
    $("#approve-plan").disabled = true;

    navigate("home");
    toast("Workspace reset.");
  }

  $("#reset-workspace").addEventListener("click", resetWorkspace);

  // Initial interface state.
  invalidatePlan();
  renderFiles();
  renderAuditTrail();
});