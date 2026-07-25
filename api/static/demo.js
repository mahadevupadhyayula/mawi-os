const API = {
  scenarios: "/api/demo/scenarios",
  start: id => `/api/demo/scenarios/${encodeURIComponent(id)}/start`,
  reset: "/api/demo/reset",
  timeline: id => `/api/demo/runs/${encodeURIComponent(id)}/timeline`,
  telemetry: id => `/api/demo/runs/${encodeURIComponent(id)}/telemetry`,
  deal: id => `/api/deals/${encodeURIComponent(id)}`,
  actions: "/api/actions?status=pending_approval",
  approve: "/api/actions/approve",
  edit: "/api/actions/edit",
  reject: "/api/actions/reject"
};
const stageDefinitions = [
  ["Signal","signal_context","Signal detection"], ["Context","deal_context","Deal context assembled"],
  ["Strategy","decision_context","Strategy selected"], ["Action","action_context","Follow-up drafted"],
  ["Approval","action_context","Human review"], ["Execution","execution_context","Simulated tools"],
  ["Evaluation","outcome_context","Outcome evaluated"], ["Memory","outcome_context","Learning write-back"]
];
const $ = id => document.getElementById(id);
let scenarios = [], run = null, deal = null, telemetry = null, action = null;
const text = value => value === null || value === undefined || value === "" ? "—" : String(value);
const esc = value => text(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const pretty = value => JSON.stringify(value ?? {}, null, 2);
const pct = value => typeof value === "number" ? `${Math.round(value * 100)}%` : "—";

async function request(url, options = {}) {
  const token = $("bearer-token")?.value.trim();
  const headers = {"Content-Type":"application/json", ...(token ? {Authorization:`Bearer ${token}`} : {})};
  const response = await fetch(url, {headers, ...options});
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.message || payload.detail || `Request failed (${response.status})`);
  return payload;
}
function feedback(message, error = false) { $("feedback").textContent = message; $("feedback").classList.toggle("error", error); }
function busy(value) { document.querySelectorAll("button").forEach(button => button.disabled = value); }
function selectedScenario() { return scenarios.find(item => item.scenario_id === $("scenario-select").value); }
function updateDescription() { $("scenario-description").textContent = selectedScenario()?.description || "Choose a scenario."; }

async function loadScenarios() {
  try {
    scenarios = (await request(API.scenarios)).scenarios;
    $("scenario-select").innerHTML = scenarios.map(item => `<option value="${esc(item.scenario_id)}">${esc(item.title)}</option>`).join("");
    updateDescription();
  } catch (error) { feedback(`${error.message} Enable MAWI_DEMO_MODE to operate this page.`, true); }
}
async function startScenario() {
  busy(true); feedback("Starting deterministic workflow…");
  try {
    run = await request(API.start($("scenario-select").value), {method:"POST"});
    await refreshRun(); feedback("Workflow started. Review the proposed action below.");
  } catch (error) { feedback(error.message, true); } finally { busy(false); }
}
async function refreshRun() {
  const timelinePayload = await request(API.timeline(run.run_id));
  telemetry = await request(API.telemetry(run.run_id));
  const timeline = timelinePayload.timeline || [];
  const dealId = timeline.find(item => item.summary?.deal_id)?.summary.deal_id;
  deal = await request(API.deal(dealId));
  const pending = (await request(API.actions)).actions || [];
  action = pending.find(item => item.deal_id === dealId) || null;
  render(timeline);
}
function render(timeline) {
  const signal = deal.signal_context || {}, decision = deal.decision_context || {}, actionContext = deal.action_context || {};
  $("runtime-mode").textContent = telemetry.llm_enabled ? "LLM-assisted" : "Deterministic";
  const summary = [["Deal ID",deal.meta?.deal_id],["Workflow ID",telemetry.workflow_id],["Trigger",signal.trigger_reason],["Urgency",signal.urgency],["Current stage",telemetry.current_stage],["Current status",telemetry.current_status],["Confidence",pct(actionContext.confidence || decision.confidence || signal.confidence)],["Approval state",telemetry.approval_state]];
  $("workflow-summary").innerHTML = summary.map(([key,value]) => `<div><dt>${esc(key)}</dt><dd>${esc(value)}</dd></div>`).join("");
  $("status-pill").textContent = text(telemetry.current_status).replaceAll("_"," ");
  $("status-pill").className = `pill ${telemetry.current_status === "completed" ? "success" : telemetry.approval_state === "pending_approval" ? "warning" : "muted"}`;
  renderTimeline(); renderTelemetry(); renderApproval(); renderOutcome();
  $("raw-data").textContent = pretty({run, telemetry, timeline, deal});
}
function badge(value, tone = "muted") { return `<span class="pill ${tone}">${esc(value)}</span>`; }
function renderTelemetry() {
  const mode = telemetry.llm_enabled ? "Enabled" : "Disabled";
  const fallback = telemetry.fallback_detected ? badge("Fallback used", "warning") : badge("No fallback", "success");
  const rows = [
    ["Workflow duration", telemetry.workflow_duration_ms === null ? "—" : `${telemetry.workflow_duration_ms} ms`],
    ["LLM", `${mode}${telemetry.providers?.length ? ` · ${telemetry.providers.join(", ")}` : ""}${telemetry.models?.length ? ` · ${telemetry.models.join(", ")}` : ""}`],
    ["Fallback", fallback, true], ["Fallback reason", telemetry.fallback_reasons?.join(", ")],
    ["Approval decision", telemetry.approval_decision || telemetry.approval_state],
    ["Execution", telemetry.execution_status], ["Tool events", telemetry.tool_event_count],
    ["Retries", telemetry.retry_count], ["Error class", telemetry.error_classes?.join(", ")],
    ["Outcome", telemetry.outcome_label], ["Memory evidence", telemetry.memory_evidence_count],
    ["Memory influence", telemetry.memory_influence_summary]
  ];
  const stages = (telemetry.stage_runs || []).map(stage => `<li><strong>${esc(stage.stage.replaceAll("_"," "))}</strong><span>${esc(stage.duration_ms)} ms · ${esc(stage.status)}${stage.error_class ? ` · ${esc(stage.error_class)}` : ""}</span></li>`).join("");
  $("telemetry").innerHTML = `<dl class="telemetry-grid">${rows.map(([key,value,raw]) => `<div><dt>${esc(key)}</dt><dd>${raw ? value : esc(value)}</dd></div>`).join("")}</dl><div class="stage-durations"><h3>Stage durations</h3>${stages ? `<ul>${stages}</ul>` : `<p class="empty">No prompt-stage timing was recorded.</p>`}</div>`;
}
function renderTimeline() {
  $("timeline").innerHTML = stageDefinitions.map(([name,key,defaultSummary], index) => {
    const context = deal[key];
    const applicable = Boolean(context) || (name === "Approval" && deal.action_context);
    const current = name === "Approval" && telemetry.approval_state === "pending_approval";
    const status = current ? "current" : applicable ? "completed" : "not started";
    let summary = context?.reasoning || defaultSummary;
    if (name === "Memory" && context) summary = "Evaluator insight written to simulated long-term memory.";
    return `<article class="stage ${status.replace(" ","-")}"><h3>${String(index + 1).padStart(2,"0")} · ${esc(name)}</h3><p>${esc(applicable ? summary : "Not reached in this run.")}</p><div class="stage-meta"><span>${esc(status)}</span><span>· ${esc(pct(context?.confidence))}</span><span>· ${telemetry.llm_enabled ? "LLM" : "deterministic"}</span>${telemetry.fallback_detected && index === 0 ? "<span>· fallback used</span>" : ""}</div></article>`;
  }).join("");
}
function renderApproval() {
  const context = deal.action_context || {};
  const show = telemetry.approval_state === "pending_approval" && (action || context.action_id);
  $("approval-panel").classList.toggle("hidden", !show);
  if (!show) return;
  action = action || {action_id:context.action_id};
  $("action-subject").value = action.subject || context.subject || "";
  $("action-body").value = action.body_draft || context.body_draft || "";
  $("action-confidence").textContent = pct(action.confidence ?? context.confidence);
  $("approval-reason").textContent = `Policy review: ${context.reasoning || "This external action requires human approval before simulated execution."}`;
}
function card(title, value, raw = false) { return `<article class="outcome-card"><h3>${esc(title)}</h3>${raw ? `<pre>${esc(pretty(value))}</pre>` : `<p>${esc(value)}</p>`}</article>`; }
function renderOutcome() {
  const execution = deal.execution_context, outcome = deal.outcome_context;
  if (!execution && !outcome) { $("outcome").innerHTML = `<p class="empty">${telemetry.approval_state === "rejected" ? "Action rejected. No simulated tools were executed." : "Execution results will appear here after approval."}</p>`; return; }
  $("outcome").innerHTML = card("Simulated email result", execution?.email_result, true) + card("Simulated CRM result", execution?.crm_result, true) + card("Tool events", execution?.tool_events, true) + card("Outcome label", outcome?.outcome_label) + card("Evaluator insight", outcome?.insight) + card("Recommended adjustment", outcome?.recommended_adjustment) + card("Memory write-back", outcome ? "Evaluator insight stored for future persona-level retrieval." : "No write-back.");
}
async function mutate(url, payload, success) {
  if (!action?.action_id) return feedback("No pending action is available.", true);
  busy(true); feedback("Applying review decision…");
  try { await request(url, {method:"POST", body:JSON.stringify({action_id:action.action_id, approver:"demo-reviewer", workflow:telemetry.workflow_id, ...payload})}); await refreshRun(); feedback(success); }
  catch (error) { feedback(error.message, true); } finally { busy(false); }
}
async function resetDemo() {
  busy(true);
  try { await request(API.reset,{method:"POST"}); run=deal=telemetry=action=null; location.reload(); }
  catch (error) { feedback(error.message,true); busy(false); }
}
$("scenario-select").addEventListener("change", updateDescription);
$("start-button").addEventListener("click", startScenario); $("reset-button").addEventListener("click", resetDemo);
$("approve-button").addEventListener("click", () => mutate(API.approve, {}, "Approved. Simulated execution and evaluation completed."));
$("edit-button").addEventListener("click", () => mutate(API.edit, {body_draft:$("action-body").value}, "Body edit saved. Action remains pending approval."));
$("reject-button").addEventListener("click", () => { const reason=$("rejection-reason").value.trim(); if (!reason) return feedback("Enter a rejection reason.",true); mutate(API.reject,{reason},"Action rejected. No tools were executed."); });
loadScenarios();
