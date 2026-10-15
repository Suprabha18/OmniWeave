
"use strict";

const API_BASE = "";

const state = {
    plan: null,
    running: false,
    backendOnline: false,
    selectedFiles: []
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error("The server returned an invalid response.");
    }

    if (!response.ok) {
        throw new Error(data.message || data.error || `Request failed (${response.status}).`);
    }

    return data;
}

function setText(id, value) {
    const element = $(id);
    if (element) element.textContent = value ?? "";
}

function showMessage(message) {
    const log = $("activity-log");

    if (log) {
        const item = document.createElement("div");
        item.className = "activity-item";
        item.textContent = `${new Date().toLocaleTimeString()} — ${message}`;
        log.prepend(item);
    }

    console.log(`[OmniWeave] ${message}`);
}

function setBackendStatus(online) {
    state.backendOnline = online;

    const connection = document.querySelector(".connection");

    if (connection) {
        connection.classList.toggle("online", online);
        connection.classList.toggle("offline", !online);
        connection.setAttribute("title", online ? "Backend connected" : "Backend unavailable");
    }

    const label = document.querySelector(".backend-label");
    if (label) {
        label.textContent = online ? "Backend connected" : "Backend offline";
    }
}

async function checkBackend() {
    try {
        const result = await api("/api/health");
        setBackendStatus(result.status === "online" || result.success === true);
        showMessage("Backend connection checked.");
    } catch (error) {
        setBackendStatus(false);
        showMessage(`Backend unavailable: ${error.message}`);
    }
}

function getGoal() {
    return ($("goal-input")?.value || "").trim();
}

function setBusy(busy) {
    state.running = busy;

    ["generate-plan", "approve-plan", "run-demo", "reset-demo"].forEach((id) => {
        const button = $(id);
        if (button) button.disabled = busy;
    });
}

function renderPlan(plan) {
    state.plan = plan;

    const steps = plan?.steps || [];

    setText("plan-goal", plan?.goal || getGoal());
    setText("plan-status", plan?.status || "ready");
    setText("step-count", String(steps.length));

    const container = $("plan-steps");

    if (container) {
        container.replaceChildren();

        steps.forEach((step, index) => {
            const card = document.createElement("div");
            card.className = "step-card";

            const heading = document.createElement("h4");
            heading.textContent =
                `${index + 1}. ${step.purpose || step.description || step.tool_name || step.id || step.step_id || "Workflow step"}`;

            const detail = document.createElement("p");
            detail.textContent = `Tool: ${step.tool_name || "Not specified"}`;

            const dependencies = document.createElement("p");
            dependencies.textContent = `Dependencies: ${(step.dependencies || []).join(", ") || "None"}`;

            card.append(heading, detail, dependencies);
            container.appendChild(card);
        });
    }

    const criteria = $("criteria-list");

    if (criteria) {
        criteria.replaceChildren();

        const allCriteria = steps.flatMap(
            (step) => step.acceptance_criteria || []
        );

        (allCriteria.length ? allCriteria : [
            "Workflow plan received from the backend.",
            "Tool execution results will be checked.",
            "Generated report will be verified."
        ]).forEach((criterion) => {
            const item = document.createElement("li");
            item.textContent = criterion;
            criteria.appendChild(item);
        });
    }

    showMessage(`Plan generated with ${steps.length} steps.`);
}

async function createPlan() {
    const goal = getGoal();

    if (!goal) {
        showMessage("Enter a goal before generating a plan.");
        $("goal-input")?.focus();
        return;
    }

    setBusy(true);

    try {
        const result = await api("/api/plan", {
            method: "POST",
            body: JSON.stringify({ goal })
        });

        if (!result.success || !result.plan) {
            throw new Error(result.message || "The backend did not return a plan.");
        }

        renderPlan(result.plan);

        if ($("plan-status")) {
            $("plan-status").textContent = "Ready for approval";
        }

        showMessage("Review the generated plan, then approve it to execute.");
    } catch (error) {
        showMessage(`Plan generation failed: ${error.message}`);
        alert(`Could not generate plan.\n\n${error.message}`);
    } finally {
        setBusy(false);
    }
}

function renderExecution(result) {
    const execution = result.execution || result;
    const steps = execution.steps || result.step_results || [];
    const events = result.events || execution.events || [];
    const completed = execution.completed_step_ids?.length
        ?? execution.completed_steps
        ?? steps.filter((step) => step.status === "completed" || step.success).length;

    setText("execution-status", execution.status || result.status || "Completed");
    setText("completed-number", String(completed));
    setText("progress-number", `${completed}/${steps.length || state.plan?.steps?.length || 0}`);

    const total = steps.length || state.plan?.steps?.length || 1;
    const percent = Math.min(100, Math.round((Number(completed) / total) * 100));

    const bar = $("progress-bar");
    if (bar) {
        bar.style.width = `${percent}%`;
        bar.setAttribute("aria-valuenow", String(percent));
    }

    const container = $("execution-steps");

    if (container) {
        container.replaceChildren();

        steps.forEach((step, index) => {
            const card = document.createElement("div");
            card.className = "execution-step";

            const heading = document.createElement("h4");
            heading.textContent =
                `${index + 1}. ${step.tool_name || step.id || step.step_id || step.name || "Step"}`;

            const detail = document.createElement("p");
            detail.textContent =
                `Status: ${step.status || (step.success ? "completed" : "processed")}`;

            card.append(heading, detail);
            container.appendChild(card);
        });

        if (!steps.length) {
            const message = document.createElement("p");
            message.textContent = "Execution response received from backend.";
            container.appendChild(message);
        }
    }

    const activity = $("activity-log");

    if (activity && events.length) {
        activity.replaceChildren();

        events.forEach((event) => {
            const item = document.createElement("div");
            item.className = "activity-item";
            item.textContent = typeof event === "string"
                ? event
                : JSON.stringify(event);

            activity.appendChild(item);
        });
    }

    renderResults(result);
}

function renderResults(result) {
    const verified = result.report_verified === true ||
        result.verification?.success === true;

    setText("result-heading", verified ? "Workflow verified" : "Workflow finished");
    setText(
        "result-description",
        verified
            ? "The backend reports that the generated report passed verification."
            : "Review the execution output and report below."
    );

    const symbol = $("result-symbol");
    if (symbol) symbol.textContent = verified ? "✓" : "•";

    const checks = $("verification-list");

    if (checks) {
        checks.replaceChildren();

        [
            ["Execution completed", result.execution?.status === "completed" || result.status === "completed"],
            ["Report verified", verified],
            ["Report content available", Boolean(result.report)]
        ].forEach(([label, passed]) => {
            const item = document.createElement("li");
            item.textContent = `${passed ? "✓" : "○"} ${label}`;
            checks.appendChild(item);
        });
    }

    const preview = $("report-preview");
    if (preview) {
        preview.textContent = result.report ||
            "No report content was returned. Check the backend terminal and output folder.";
    }

    const download = $("download-report");

    if (download) {
        download.disabled = !result.report;

        download.onclick = () => {
            if (!result.report) return;

            const blob = new Blob([result.report], {
                type: "text/plain;charset=utf-8"
            });

            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");

            link.href = url;
            link.download = "omniweave_report.txt";
            link.click();

            URL.revokeObjectURL(url);
        };
    }
}

async function runWorkflow() {
    const goal = getGoal();

    if (!goal) {
        showMessage("Enter a goal first.");
        return;
    }

    if (!state.plan) {
        showMessage("Generate and review a plan before execution.");
        return;
    }

    setBusy(true);
    showMessage("Sending workflow to the backend for execution.");

    try {
        const result = await api("/api/run", {
            method: "POST",
            body: JSON.stringify({ goal })
        });

        renderExecution(result);

        if (result.success === false) {
            showMessage(result.message || "The backend reported an execution failure.");
        } else {
            showMessage("Backend execution response received.");
        }
    } catch (error) {
        showMessage(`Execution failed: ${error.message}`);
        alert(`Workflow execution failed.\n\n${error.message}`);
    } finally {
        setBusy(false);
    }
}

function resetDemo() {
    state.plan = null;

    const goal = $("goal-input");
    if (goal) goal.value = "";

    [
        "plan-goal",
        "plan-steps",
        "criteria-list",
        "execution-steps",
        "report-preview",
        "verification-list",
        "activity-log"
    ].forEach((id) => {
        const element = $(id);
        if (element) {
            if (id === "plan-steps" || id === "criteria-list" ||
                id === "execution-steps" || id === "verification-list" ||
                id === "activity-log") {
                element.replaceChildren();
            } else {
                element.textContent = "";
            }
        }
    });

    setText("plan-status", "Not started");
    setText("step-count", "0");
    setText("completed-number", "0");
    setText("progress-number", "0/0");
    setText("execution-status", "Idle");
    setText("result-heading", "Awaiting execution");
    setText("result-description", "Generate a plan to begin.");

    const bar = $("progress-bar");
    if (bar) bar.style.width = "0%";

    showMessage("Dashboard reset. Backend data and saved reports have not been deleted.");
}

function setupFilePicker() {
    const picker = $("file-input");
    const list = $("file-list");

    if (!picker) return;

    picker.addEventListener("change", () => {
        state.selectedFiles = Array.from(picker.files || []);

        if (list) {
            list.replaceChildren();

            state.selectedFiles.forEach((file) => {
                const item = document.createElement("div");
                item.textContent = `${file.name} (${Math.ceil(file.size / 1024)} KB)`;
                list.appendChild(item);
            });
        }

        if (state.selectedFiles.length) {
            showMessage(
                "Files selected in the browser. This version does not upload them; the backend uses its configured dataset."
            );
        }
    });
}

function setupNavigation() {
    document.querySelectorAll("[data-page]").forEach((element) => {
        element.addEventListener("click", () => {
            const page = element.dataset.page;

            document.querySelectorAll("[data-page]").forEach((nav) => {
                nav.classList.toggle("active", nav === element);
            });

            document.querySelectorAll(".page").forEach((section) => {
                section.classList.toggle(
                    "active",
                    section.id === page || section.id === `page-${page}`
                );
            });
        });
    });
}

function setupCharacterCount() {
    const input = $("goal-input");
    const count = $("char-count");

    if (!input || !count) return;

    const update = () => {
        count.textContent = String(input.value.length);
    };

    input.addEventListener("input", update);
    update();
}

document.addEventListener("DOMContentLoaded", () => {
    $("generate-plan")?.addEventListener("click", createPlan);
    $("approve-plan")?.addEventListener("click", runWorkflow);
    $("run-demo")?.addEventListener("click", runWorkflow);
    $("reset-demo")?.addEventListener("click", resetDemo);

    $("edit-plan")?.addEventListener("click", () => {
        $("goal-input")?.focus();
        showMessage("Edit the goal and generate the plan again.");
    });

    $("cancel-plan")?.addEventListener("click", () => {
        state.plan = null;
        showMessage("Plan approval cancelled.");
    });

    $("clear-log")?.addEventListener("click", () => {
        $("audit-trail")?.replaceChildren();
        $("activity-log")?.replaceChildren();
        showMessage("Visible activity log cleared.");
    });

    setupFilePicker();
    setupNavigation();
    setupCharacterCount();

    checkBackend();
});
