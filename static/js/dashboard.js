const REFRESH_INTERVAL = 10000;

let dashboardData = null;
let selectedIncidentId = null;

const elements = {
    health: document.getElementById("app-health"),
    uptime: document.getElementById("app-uptime"),
    total: document.getElementById("total-incidents"),
    pending: document.getElementById("pending-jobs"),
    failed: document.getElementById("failed-jobs"),
    errorCounter: document.getElementById("error-counter"),
    requestCounter: document.getElementById("request-counter"),
    aiStatus: document.getElementById("ai-status"),
    table: document.getElementById("incident-table"),
    incidentCount: document.getElementById("incident-count"),
    analysis: document.getElementById("analysis-panel"),
    lastUpdated: document.getElementById("last-updated"),
    refreshButton: document.getElementById("refresh-button"),
    simulateButton: document.getElementById("simulate-button"),
};

function formatDate(value) {
    if (!value) return "Unknown";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return "Unknown";

    return date.toLocaleString();
}

function formatNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toLocaleString() : "—";
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[character]);
}

async function fetchJSON(url) {
    const response = await fetch(url, {
        headers: { Accept: "application/json" },
        cache: "no-store"
    });

    if (!response.ok) {
        throw new Error(`Request failed: ${url} (${response.status})`);
    }

    return response.json();
}

function renderOverview(data) {
    const health = data.health;

    elements.health.textContent = health.status.toUpperCase();
    elements.health.className = `metric-value ${
        health.status === "healthy" ? "health-good" : "health-bad"
    }`;

    elements.uptime.textContent = health.uptime_seconds !== null
        ? `Uptime: ${formatNumber(health.uptime_seconds)} seconds`
        : (health.reason || "Health unavailable");

    elements.total.textContent = formatNumber(data.summary.total_incidents);
    elements.pending.textContent = formatNumber(data.summary.pending_jobs);
    elements.failed.textContent = formatNumber(data.summary.failed_jobs);

    elements.errorCounter.textContent = formatNumber(data.metrics.error_count);
    elements.requestCounter.textContent = formatNumber(data.metrics.request_count);
    elements.aiStatus.textContent = data.summary.ai_status;

    elements.lastUpdated.textContent =
        `Last updated: ${new Date().toLocaleTimeString()}`;
}

function renderIncidents(incidents) {
    elements.incidentCount.textContent = `${incidents.length} records`;

    if (!incidents.length) {
        elements.table.innerHTML =
            '<tr><td colspan="5" class="empty-state">No incidents recorded yet.</td></tr>';
        return;
    }

    elements.table.innerHTML = incidents.map(incident => {
        const statusClass = incident.status === "ANALYZED"
            ? "complete"
            : incident.status === "FAILED"
                ? "failed"
                : "pending";

        const id = escapeHTML(incident.incident_id || "legacy");
        const shortId = id.length > 15 ? `${id.slice(0, 12)}...` : id;

        return `
            <tr data-incident-id="${id}"
                class="${selectedIncidentId === incident.incident_id ? "selected" : ""}">
                <td class="incident-id">${shortId}</td>
                <td>${escapeHTML(incident.service)}</td>
                <td class="type-label">${escapeHTML(incident.type)}</td>
                <td>${escapeHTML(formatDate(incident.timestamp))}</td>
                <td><span class="state-pill ${statusClass}">
                    ${escapeHTML(incident.status)}
                </span></td>
            </tr>
        `;
    }).join("");

    elements.table.querySelectorAll("tr[data-incident-id]").forEach(row => {
        row.addEventListener("click", () => {
            const incident = incidents.find(item =>
                (item.incident_id || "legacy") === row.dataset.incidentId
            );

            if (incident) {
                selectedIncidentId = incident.incident_id || null;
                renderIncidents(incidents);
                renderAnalysis(incident);
            }
        });
    });

    if (selectedIncidentId) {
        const selected = incidents.find(item =>
            item.incident_id === selectedIncidentId
        );

        if (!selected) {
            selectedIncidentId = null;
        }
    }

    if (!selectedIncidentId && incidents.length) {
        const firstWithId = incidents.find(item => item.incident_id);
        if (firstWithId) {
            selectedIncidentId = firstWithId.incident_id;
            renderAnalysis(firstWithId);
        }
    }
}

function renderAnalysis(incident) {
    const analysis = incident.analysis;

    if (!analysis) {
        elements.analysis.innerHTML = `
            <h3>${escapeHTML(incident.type)}</h3>
            <div class="analysis-meta">
                ${escapeHTML(incident.incident_id || "Legacy incident")}
                · ${escapeHTML(formatDate(incident.timestamp))}
            </div>
            <div class="analysis-block">
                <strong>Incident evidence</strong>
                <p>${escapeHTML(incident.evidence)}</p>
            </div>
            <div class="analysis-block">
                <strong>AI analysis</strong>
                <p>${escapeHTML(incident.status === "FAILED"
                    ? "Analysis failed. Review the failed job record."
                    : "Analysis is pending or not available for this incident.")}</p>
            </div>
        `;
        return;
    }

    elements.analysis.innerHTML = `
        <h3>${escapeHTML(incident.type)}
            · ${escapeHTML(analysis.severity || "UNSPECIFIED")}
        </h3>
        <div class="analysis-meta">
            Incident ${escapeHTML(incident.incident_id)}
            · Analyzed ${escapeHTML(formatDate(incident.analyzed_at))}
            · ${escapeHTML(analysis.analysis_mode || "AI")}
        </div>
        <div class="analysis-block">
            <strong>Root-cause hypothesis</strong>
            <p>${escapeHTML(analysis.root_cause_hypothesis)}</p>
        </div>
        <div class="analysis-block">
            <strong>Evidence</strong>
            <p>${escapeHTML(analysis.evidence)}</p>
        </div>
        <div class="analysis-block">
            <strong>Recommended action</strong>
            <p>${escapeHTML(analysis.recommended_action)}</p>
        </div>
        <div class="analysis-meta">
            Automatic remediation: ${analysis.automatic_remediation ? "Enabled" : "Disabled"}
        </div>
    `;
}

async function refreshDashboard() {
    elements.refreshButton.disabled = true;

    try {
        const data = await fetchJSON("/api/dashboard");

        dashboardData = data;

        renderOverview(data);
        renderIncidents(data.incidents);

        if (selectedIncidentId) {
            const selected = data.incidents.find(item =>
                item.incident_id === selectedIncidentId
            );

            if (selected) renderAnalysis(selected);
        }
    } catch (error) {
        console.error("Dashboard refresh failed:", error);
        elements.lastUpdated.textContent = "Unable to refresh dashboard";
    } finally {
        elements.refreshButton.disabled = false;
    }
}

async function simulateIncident() {
    const confirmed = window.confirm(
        "Trigger a controlled application error? This will increment the Prometheus error counter and may create an incident."
    );

    if (!confirmed) return;

    elements.simulateButton.disabled = true;

    try {
        const response = await fetch("/simulate-error", { method: "GET" });

        // HTTP 500 is expected for this controlled simulation.
        if (response.status !== 500) {
            throw new Error(`Unexpected response: HTTP ${response.status}`);
        }

        await refreshDashboard();
        window.alert("Controlled error triggered. The detector will check for it on its next polling cycle.");
    } catch (error) {
        console.error("Incident simulation failed:", error);
        window.alert("Unable to trigger the controlled error.");
    } finally {
        elements.simulateButton.disabled = false;
    }
}

// Sidebar navigation
document.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", () => {
        document.querySelectorAll(".nav-link").forEach(item => {
            item.classList.remove("active");
        });

        link.classList.add("active");
    });
});

elements.refreshButton.addEventListener("click", refreshDashboard);
elements.simulateButton.addEventListener("click", simulateIncident);

refreshDashboard();
setInterval(refreshDashboard, REFRESH_INTERVAL);
