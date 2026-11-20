import { bars, esc, figure, map, num, renderNotes } from "./notes.js";

const byId = (id) => document.getElementById(id);
const usd = (value) => "$" + num(value);
const percent = (value, digits = 1) => num(100 * value, digits) + "%";
const level = { 2: "Level 2", 3: "DC fast" };
const status = {
  2: "Optimal",
  3: "Infeasible",
  4: "Infeasible or unbounded",
  5: "Unbounded",
  9: "Time limit",
  11: "Interrupted",
  13: "Suboptimal",
};
const oldTabs = new Map([["data/ask", "data/recap"], ["data/review", "data/recap"], ["data/tables", "data/zip-2022"], ["run", "test/baseline"], ["log", "test/trace"], ["results", "recommend"]]);
const state = { steps: [], itinerary: [], route: [], areas: [], work: null, responses: null, lastSnapshot: "" };

async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`HTTP ${response.status} for ${path}`);
  return response;
}

function tableMarkup(title, columns, rows) {
  const header = columns.map(([text, numeric]) =>
    `<th scope="col"${numeric ? ' class="n"' : ""}>${esc(text)}</th>`
  ).join("");
  const body = rows.map((row) => "<tr>" + row.map((value, i) =>
    `<td${columns[i][1] ? ' class="n"' : ""}>${esc(value)}</td>`
  ).join("") + "</tr>").join("");
  return `<table>${title ? `<caption>${esc(title)}</caption>` : ""}<thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`;
}

function sectionTable(title, columns, rows) {
  return `<div class="scroll">${tableMarkup(title, columns, rows)}</div>`;
}

const answerField = byId("response-answer");
const actionButton = byId("page-action");
const dataTable = byId("data-table");
const responseDrafts = new Map();
const savingResponses = new Set();
const responseFailures = new Set();
let responseLoadFailed = false;
let responseLoading = false;
let current = null;
let sourceTable = null;
let shownRows = 0;
let tableFailed = false;
let tableRequest = 0;

function appendRows() {
  if (!sourceTable || shownRows >= sourceTable.rows.length) return;
  const rows = sourceTable.rows.slice(shownRows, shownRows + 50);
  dataTable.querySelector("tbody").insertAdjacentHTML("beforeend", rows.map((row) =>
    "<tr>" + sourceTable.indices.map((i) => `<td>${esc(row[i])}</td>`).join("") + "</tr>"
  ).join(""));
  shownRows += rows.length;
}

async function loadTable(step) {
  const id = step.source;
  const pending = ++tableRequest;
  sourceTable = null;
  shownRows = 0;
  tableFailed = false;
  dataTable.replaceChildren();
  dataTable.scrollTop = dataTable.scrollLeft = 0;
  dataTable.setAttribute("aria-busy", "true");
  byId("data-status").textContent = "Loading rows…";
  byId("data-attribution").hidden = !id.startsWith("zip-");
  renderAction();
  try {
    const source = await (await request(`api/data/${id}`)).json();
    if (pending !== tableRequest) return;
    const first = id === "stations" ? ["Station Name", "ZIP", "Access Code", "Status Code", "EV Level2 EVSE Num", "EV DC Fast Count"] : [];
    const columns = [...first.filter((c) => source.columns.includes(c)), ...source.columns.filter((c) => !first.includes(c))];
    sourceTable = { rows: source.rows, indices: columns.map((c) => source.columns.indexOf(c)) };
    dataTable.innerHTML = tableMarkup("", columns.map((c) => [c]), []);
    appendRows();
    byId("data-status").textContent = `${step.credit} · ${num(source.rows.length)} rows`;
  } catch {
    if (pending !== tableRequest) return;
    tableFailed = true;
    byId("data-status").textContent = "The table could not load.";
  } finally {
    if (pending === tableRequest) {
      dataTable.removeAttribute("aria-busy");
      renderAction();
    }
  }
}

dataTable.addEventListener("scroll", () => {
  if (dataTable.scrollHeight - dataTable.scrollTop - dataTable.clientHeight < 150) appendRows();
});

function forecast(work) {
  const demand = work.demand;
  if (!demand.length) return "";
  const total = demand.reduce((sum, row) => sum + row[1], 0);
  const zipForecasts = demand.map(([zcta, evs]) => [zcta, evs]);
  const highest = [...zipForecasts].sort((a, b) => b[1] - a[1]).slice(0, 10);
  return `<section class="evidence"><h3>EV-equivalent forecast.</h3>
    <p>${num(total)} EVs across ${num(demand.length)} ZIP areas, expressed as a discounted ten-year average.</p>
    ${figure("", "Highest forecasts by ZIP area.", bars(highest),
      `Showing ${highest.length} of ${num(demand.length)} ZIP areas by forecast EV equivalents.`)}
    ${figure("map", "Forecast EVs by ZIP area", map(state.areas, zipForecasts))}</section>`;
}

function formulation(work) {
  if (work.analysis) return `<section class="evidence"><h3>Student analysis code.</h3><pre>${esc(work.analysis)}</pre></section>`;
  const implemented = work.model && !work.model.includes("raise NotImplementedError(");
  const p = work.parameters;
  if (!implemented || !p.PORT_COST) return "";
  const levels = ["2", "3"];
  const rows = [
    ["Install one port", "$ per port", ...levels.map((l) => usd(p.PORT_COST[l]))],
    ["Open a site", "$ per site", ...levels.map((l) => usd(p.SITE_FIXED_COST[l]))],
    ["Ports at one site", "ports", ...levels.map((l) => `${p.MIN_PORTS_PER_SITE[l]}–${p.MAX_PORTS_PER_SITE[l]}`)],
    ["Throughput at full use", "EVs per port per year", ...levels.map((l) => num(p.PEAK_THROUGHPUT_PER_CHARGER[l], 1))],
    ["Gross revenue", "$ per EV served per year", ...levels.map((l) => usd(p.ANNUAL_REVENUE_PER_EV[l]))],
  ];
  return `<section class="evidence"><h3>Model files.</h3>
    <h4>Parameter values.</h4>
      ${sectionTable("", [["Assumption"], ["Units"], ["Level 2", true], ["DC fast", true]], rows)}
      <p>The ten-year discount factor is ${num(p.LIFETIME_REVENUE_FACTOR, 2)} applied to annual revenue.</p>
    <h4>Model code.</h4><pre>${esc(work.model)}</pre></section>`;
}

function outcome(run) {
  const record = run.record;
  if (record.source === "student_analysis" && record.outcome === "checked") return "Plan checked";
  if (record.outcome === "started") return "Running";
  if (record.outcome === "solver_unavailable") return "Gurobi unavailable";
  if (record.outcome === "failed") return "Checks or execution failed";
  if (record.outcome === "no_solution") {
    return status[record.solver_status] ? `No incumbent (${status[record.solver_status]})` : "No incumbent";
  }
  return status[record.solver_status ?? record.status] || (record.outcome === "saved" ? "Saved plan" : "Awaiting status");
}

function totals(run) {
  if (!["checked", "saved"].includes(run.record.outcome)) return ["", "", ""];
  const sum = (field) => run.sites.reduce((total, site) => total + Number(site[field]), 0);
  const score = run.record.source === "student_analysis"
    ? `${run.record.metric}: ${run.record.objective} ${run.record.unit}`
    : `${usd(sum("revenue_npv"))} gross revenue NPV`;
  return [usd(sum("capital")), score, num(sum("count"))];
}

function runTable(title, runs) {
  if (!runs.length) return "";
  return sectionTable(title, [["Scenario"], ["Budget", true], ["Capital", true], ["Score"], ["Ports", true], ["Result"]],
    runs.map((run) => [run.record.scenario || "Revenue model", run.budget == null ? "" : usd(run.budget), ...totals(run), outcome(run)]));
}

function solverLog(run) {
  if (run.log.trim()) {
    const heading = run.record.outcome === "started" ? "Gurobi log (live)." : "Gurobi log.";
    return `<h4>${heading}</h4><pre>${esc(run.log.trim())}</pre>`;
  }
  return run.record.outcome === "started"
    ? '<p class="muted">Waiting for Gurobi output…</p>'
    : "";
}

function planDetails(run) {
  const { record, sites } = run;
  const facts = [];
  const custom = record.source === "student_analysis";
  if (custom) facts.push(record.scenario, record.allocation);
  if (record.outcome === "saved") facts.push("Reference model · ten-year discounted gross revenue · shared demand within each ZIP area · operating costs excluded");
  if (record.mip_gap != null) facts.push(`${percent(record.mip_gap, 3)} gap`);
  if (record.objective_bound != null) facts.push(`${usd(record.objective_bound)} bound`);
  if (record.runtime_seconds != null) facts.push(`${num(record.runtime_seconds, 2)} s solve time`);
  if (record.error_type) facts.push(record.error_type);
  let plan = "";
  if (sites.length) {
    const mapped = sites.map((site) => [site.zcta, Number(site.count), Number(site.level) === 3]);
    const columns = custom
      ? [["ZIP area"], ["Type"], ["Ports", true], ["Capital", true]]
      : [["ZIP area"], ["Type"], ["Ports", true], ["Use", true], ["EVs served/year", true], ["Capital", true], ["Revenue NPV", true]];
    const rows = custom ? sites.map((s) => [s.zcta, level[s.level], s.count, usd(s.capital)]) : [...sites].sort((a, b) => b.revenue_npv - a.revenue_npv).map((site) => [
      site.zcta, level[site.level], site.count, percent(site.utilization, 0), num(site.served, 1), usd(site.capital), usd(site.revenue_npv),
    ]);
    plan = `<h4>Selected sites (${sites.length}).</h4>
      ${figure("map", "Selected ZIP areas", map(state.areas, mapped), "Marker size shows port count. Circles are Level 2 and squares are DC fast.")}
      ${sectionTable("", columns, rows)}
    `;
  } else if (record.outcome === "checked") {
    plan = "<p>The checked plan installs zero ports.</p>";
  }
  return solverLog(run) + (facts.length ? `<p>${esc(facts.join(" · "))}</p>` : "") + plan;
}

function runEvidence(work, view) {
  const { runs, examples } = work;
  if (!runs.length && !examples.length) return "";
  const attempts = [...runs].reverse();
  if (view === "baseline") {
    const baseline = attempts[0];
    return baseline ? runTable("Baseline", [baseline]) + solverLog(baseline) : "";
  }
  if (view === "compare") {
    const latest = runs[0];
    return runTable("Your runs", attempts) + (latest ? solverLog(latest) : "")
      + runTable("Saved reference plans", examples);
  }
  return attempts.map((plan, i) => runTable(`Your run ${i + 1}`, [plan]) + planDetails(plan)).join("")
    + examples.map((plan) => runTable("Saved reference", [plan]) + planDetails(plan)).join("");
}

const evidence = { forecast, model: formulation, baseline: runEvidence, trace: runEvidence, compare: runEvidence };

function solverNotice(solver) {
  if (!solver?.warning) return "";
  return `<section class="solver-warning"><h2>Live statewide solves unavailable.</h2>
    <p>${esc(solver.warning)} You can continue with saved plans during Test.</p>
    <p>Ask your agent for help setting up an academic license if you want to run the statewide model.</p></section>`;
}

function updateContent(id, html) {
  const region = byId(id);
  if (region.renderedHTML === html) return;
  region.innerHTML = html;
  region.renderedHTML = html;
}

async function loadResponses() {
  if (responseLoading) return;
  responseLoading = true;
  responseLoadFailed = false;
  render();
  try {
    state.responses = await (await request("api/responses")).json();
    // Older viewers kept an unsaved observation in the browser tab.
    const key = "data/observe";
    try {
      const legacy = JSON.parse(sessionStorage.getItem("ev-lesson-explore:" + location.pathname));
      if (legacy?.observation && !state.responses[key] && !responseDrafts.has(key)) {
        responseDrafts.set(key, legacy.observation);
      }
    } catch {
      // Saved answers still work without session storage.
    }
  } catch {
    responseLoadFailed = true;
  } finally {
    responseLoading = false;
    render();
  }
}

function nextPage(entry) {
  return state.itinerary.slice(state.itinerary.indexOf(entry) + 1).find((item) => !item.step.previousEdition);
}

function rejectedForecast(key, answer) {
  return key === "forecast/check" && /^No(?:\n|$)/i.test(answer || "");
}

function renderAction() {
  if (!current) return;
  const { key, step } = current;
  const next = nextPage(current);
  const submission = key === "recommend/submit";
  let label = step.nextLabel || next?.step.continueLabel || (next ? `Continue to ${next.step.label}` : "Continue");
  if (rejectedForecast(key, state.responses?.[key])) label = "Continue to Formulate";
  let disabled = false;
  let message = "";
  if (step.source && tableFailed) {
    label = "Retry table";
  } else if (responseLoadFailed) {
    label = "Retry loading answers";
    message = "Your saved answers could not load.";
  } else if (submission) {
    label = "Download responses";
    disabled = !Object.values(state.responses || {}).some(Boolean);
    if (responseLoading) message = "Loading saved answers…";
    else if (disabled) message = "Your saved answers will appear here.";
    else if ([...responseDrafts].some(([k, v]) => v.trim() !== (state.responses[k] || ""))) {
      message = "Some edits are unsaved. Use Back to return to them.";
    }
  } else if (step.response) {
    const saved = state.responses?.[key] || "";
    const draft = responseDrafts.get(key) ?? saved;
    if (step.source && next?.step.source) {
      label = `Read table ${next.tableNumber} · ${next.step.label}`;
    } else if (!step.source && (!saved || draft.trim() !== saved)) {
      label = "Submit response";
    }
    disabled = !state.responses || savingResponses.has(key) || (step.source ? !sourceTable : !draft.trim());
    if (responseLoading) message = "Loading saved answer…";
    else if (savingResponses.has(key)) message = "Submitting…";
    else if (responseFailures.has(key)) message = "Could not save. Try again.";
    else if (draft.trim() !== saved) message = "Unsaved changes";
    else if (saved) message = "Saved";
  }
  actionButton.textContent = label;
  actionButton.disabled = disabled;
  const status = byId("response-status");
  if (status.textContent !== message) status.textContent = message;
}

async function advance(event) {
  event.preventDefault();
  if (!current || actionButton.disabled) return;
  const entry = current;
  const { key, step } = entry;
  if (step.source && tableFailed) return loadTable(step);
  if (responseLoadFailed) return loadResponses();
  if (key === "recommend/submit") {
    window.location.assign("student-responses.md");
    return;
  }
  const next = nextPage(entry);
  const answer = key === "forecast/check" ? (responseDrafts.get(key) ?? state.responses?.[key] ?? "") : answerField.value;
  if (step.response && answer.trim() !== (state.responses?.[key] || "")) {
    const draft = answer;
    savingResponses.add(key);
    responseFailures.delete(key);
    renderAction();
    try {
      const response = await request("api/responses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step: key, answer: draft }),
      });
      state.responses[key] = (await response.json()).answer;
      if (responseDrafts.get(key) !== draft) return;
      responseDrafts.delete(key);
    } catch {
      responseFailures.add(key);
      return;
    } finally {
      savingResponses.delete(key);
      render();
    }
    if (rejectedForecast(key, state.responses[key])) {
      if (entry === current) byId("forecast-pace-note").focus();
      return;
    }
  }
  if (entry === current && next) location.hash = next.hash;
}

function replyForNote(key, note) {
  if (!note || !/^@agent[\s,:]+[^\s,:]/i.test(note.trim())) return "";
  const saved = state.work?.table_replies?.[key];
  return saved?.note === note ? saved.reply : "Your reply will appear here.";
}

function reviewReply(key, note) {
  const reply = replyForNote(key, note);
  return reply ? `<p class="review-reply"><strong>Agent reply</strong><br>${esc(reply)}</p>` : "";
}

function forecastHint() {
  const notes = state.itinerary
    .filter(({ phase, key, step }) => phase.id === "data" && (step.source || key === "data/ask"))
    .map(({ key, step }) => [step.label, state.responses?.[key]?.replace(/^@agent[\s,:]*/i, "").trim()])
    .filter(([, note]) => note);
  if (!notes.length) return "";

  const targets = [
    [/\b(?:revenue|profits?|payback|roi|returns?)\b/i, "financial return, using charging revenue and estimated costs"],
    [/\b(?:usage|utili[sz]ation|sessions?|kwh|throughput)\b/i, "charging use, such as public sessions per day"],
    [/\b(?:ports?|capacity|supply|shortage|underserved)\b/i, "the gap between expected charging demand and available public ports"],
    [/\b(?:registrations?|evs?|vehicles?|adoption|growth)\b/i, "EV registrations in a future year as a proxy for demand"],
  ];
  const text = notes.map(([, note]) => note).join(" ");
  const suggestions = targets.filter(([pattern]) => pattern.test(text)).map(([, target]) => target);
  const list = notes.map(([source, note]) => {
    const excerpt = note.replace(/\s+/g, " ");
    return `<li><strong>${esc(source)}</strong> ${esc(excerpt.length > 160 ? excerpt.slice(0, 157).trimEnd() + "…" : excerpt)}</li>`;
  }).join("");
  const suggestion = suggestions.length
    ? `Your notes suggest you might estimate ${suggestions.slice(0, 2).join(" or ")}.`
    : "Use one observation above to choose a quantity you could estimate for one area.";
  return `<ul>${list}</ul><p>${esc(suggestion)} Pick one target and name the source field and assumption you would use.</p>`;
}

function render() {
  if (!state.itinerary.length) return;
  const hash = location.hash.slice(1);
  const showOverview = !hash || hash === "overview";
  byId("overview").classList.toggle("in-lesson", !showOverview);
  byId("course-overview").hidden = !showOverview;
  byId("series").hidden = showOverview;
  byId("lesson-duration").hidden = !showOverview;
  byId("lesson-position").hidden = showOverview;
  if (showOverview) {
    current = null;
    return;
  }
  const [phaseId, stepId] = (oldTabs.get(hash) || hash).split("/");
  const entry = state.itinerary.find((item) => item.key === `${phaseId}/${stepId}`)
    || state.itinerary.find((item) => item.phase.id === phaseId && !item.step.previousEdition)
    || state.itinerary[0];
  const routeChanged = entry !== current;
  current = entry;
  if (routeChanged) {
    byId("lesson-content").scrollTop = 0;
    const position = state.route.indexOf(entry) + 1;
    byId("step-progress").hidden = position === 0;
    if (position) {
      const progress = byId("lesson-progress");
      const label = `Step ${position} of ${state.route.length}`;
      progress.max = state.route.length;
      progress.value = position;
      progress.setAttribute("aria-valuetext", label);
      byId("progress-position").textContent = label;
      byId("progress-sections").innerHTML = state.steps.map((phase) =>
        `<li${phase === entry.phase ? ' aria-current="step"' : ""}>${esc(phase.name)}</li>`
      ).join("");
    }
    const previous = state.itinerary.slice(0, state.itinerary.indexOf(entry)).reverse().find((item) => !item.step.previousEdition);
    const back = byId("previous-step");
    back.href = previous?.hash || "#overview";
    back.setAttribute("aria-label", previous ? `Back to ${previous.phase.name} · ${previous.step.label}` : "Back to lesson overview");
  }
  const { phase, step, key } = entry;
  const replies = Object.entries(state.work?.agent_replies || {})
    .filter(([replyKey, value]) => replyKey.startsWith(`${phase.id}/`) && state.responses?.[replyKey] === value.answer)
    .sort((a, b) => b[1].updated - a[1].updated);
  const latestReply = replies[0];
  byId("agent-reply").hidden = !latestReply;
  updateContent("agent-reply-text", latestReply ? renderNotes(latestReply[1].reply, state.areas, state.work.figures) : "");
  const submission = key === "recommend/submit";
  byId("lesson-position").textContent = phase.time;
  byId("page-position").textContent = step.source
    ? `${phase.name} · Table ${entry.tableNumber} of ${phase.subsections.filter((item) => item.source).length}`
    : `${phase.name} · ${step.label}`;
  byId("phase-title").textContent = step.title;
  byId("formulation-example").hidden = key !== "formulate/decisions";
  byId("action").hidden = !step.action;
  byId("action").textContent = step.action || "";
  byId("writing-area").classList.toggle("table-with-note", Boolean(step.source));
  byId("raw-data").hidden = !step.source;
  if (step.source && routeChanged) loadTable(step);
  byId("forecast-pace-note").hidden = !rejectedForecast(key, state.responses?.[key]);
  byId("response-fields").hidden = !step.response;
  if (step.response) {
    const choice = key === "forecast/check";
    const savedChoice = choice && Boolean(state.responses?.[key]);
    byId("forecast-choice").hidden = !choice;
    byId("response-label").textContent = choice ? "Suggested change (optional)" : step.response;
    byId("response-label").hidden = choice && (savedChoice || !responseDrafts.get(key)?.startsWith("No"));
    byId("response-hint").textContent = step.source
      ? "Your note saves when you continue. Start with @agent to get a reply alongside your notes."
      : step.hint || "";
    const draft = responseDrafts.get(key) ?? state.responses?.[key] ?? "";
    if (choice) {
      const match = draft.match(/^(Yes|No)(?:\n([\s\S]*))?$/i);
      for (const radio of document.querySelectorAll('input[name="forecast-choice"]')) {
        radio.checked = match?.[1].toLowerCase() === radio.value.toLowerCase();
        radio.disabled = savedChoice;
      }
      answerField.hidden = savedChoice || match?.[1].toLowerCase() !== "no";
      const change = match?.[2] || "";
      if (answerField.value !== change) answerField.value = change;
    } else {
      answerField.hidden = false;
      if (answerField.value !== draft) answerField.value = draft;
    }
  }
  const review = key === "data/recap";
  const tableNotes = review
    ? state.itinerary.filter((item) => item.phase.id === "data" && item.key !== "data/ask" && state.responses?.[item.key])
    : [];
  byId("table-notes").hidden = !tableNotes.length;
  if (tableNotes.length) {
    updateContent("table-notes", "<h3>Your notes</h3><dl>" + tableNotes.map((item) => {
      const note = state.responses[item.key];
      return `<dt>${esc(item.step.label)}</dt><dd>${esc(note)}${item.step.source ? reviewReply(item.key, note) : ""}</dd>`;
    }).join("") + "</dl>");
  }
  const question = review && state.responses?.["data/ask"];
  byId("explore-question").hidden = !question;
  byId("explore-question-text").textContent = question || "";
  const earlierAnswer = step.recall && state.responses?.[step.recall.key];
  byId("earlier-answer").hidden = !earlierAnswer;
  byId("earlier-label").textContent = step.recall?.label || "";
  byId("earlier-text").textContent = earlierAnswer || "";
  const forecastContext = key === "forecast/method" ? forecastHint() : "";
  byId("forecast-hint").hidden = !forecastContext;
  updateContent("forecast-hint-text", forecastContext);
  const showSolver = phase.id === "test" && ["baseline", "trace", "predict", "stress"].includes(step.id);
  updateContent("solver-status", showSolver ? solverNotice(state.work?.solver) : "");
  const text = step.notes && state.work?.notes[phase.id];
  byId("workspace").hidden = !text;
  updateContent("notes", text ? renderNotes(text, state.areas, state.work.figures) : "");
  const show = evidence[step.evidence];
  const available = show && state.work ? show(state.work, step.evidence) : "";
  updateContent("evidence", available || (show && !text ? '<p class="muted">The agent’s results will appear here.</p>' : ""));
  byId("submission").hidden = !submission;
  if (submission) {
    const answers = state.responses || {};
    updateContent("submission", state.itinerary.filter((item) => item.phase.id !== "data" && answers[item.key]).map((item) =>
      `<section class="submission-response"><h3>${esc(item.phase.name)} · ${esc(item.step.label)}</h3><p>${esc(answers[item.key])}</p></section>`
    ).join(""));
  }
  renderAction();
}
function connection(message = "") {
  const notice = byId("connection");
  notice.textContent = message;
  notice.hidden = !message;
}

function showAgentActivity(active) {
  const activity = byId("agent-activity");
  const text = active ? "Agent is thinking…" : "";
  if (activity.textContent !== text) activity.textContent = text;
}

async function poll() {
  try {
    const snapshot = await (await request("api/live")).text();
    if (snapshot !== state.lastSnapshot) {
      state.work = JSON.parse(snapshot);
      render();
      state.lastSnapshot = snapshot;
    }
    showAgentActivity(state.work?.agent_active);
    connection();
  } catch {
    showAgentActivity(false);
    connection("Workspace updates are unavailable. Reconnecting…");
  }
  setTimeout(poll, 1500);
}

async function start() {
  try {
    state.steps = await (await request("api/steps")).json();
    state.itinerary = state.steps.flatMap((phase) => {
      let tableNumber = 0;
      return phase.subsections.map((step) => {
        const key = `${phase.id}/${step.id}`;
        return { phase, step, key, hash: "#" + key, tableNumber: step.source ? ++tableNumber : null };
      });
    });
    state.route = state.itinerary.filter(({ step }) => !step.previousEdition);
    byId("course-outline").innerHTML = state.steps.map((phase) =>
      `<li><div class="course-stage"><strong>${esc(phase.name)}</strong><span>${esc(phase.time)}</span></div><p>${esc(phase.overview)}</p></li>`
    ).join("");
    render();
    loadResponses();
    poll();
  } catch {
    const notice = byId("course-status");
    notice.textContent = "The lesson phases could not load. Refresh the page to try again.";
    notice.hidden = false;
    return;
  }
  try {
    state.areas = await (await request("api/areas")).json();
    render();
  } catch {
    // Tables and notes are available without map coordinates.
  }
}

window.addEventListener("pageshow", (event) => {
  if (!event.persisted) requestAnimationFrame(() => window.scrollTo(0, 0));
}, { once: true });

window.addEventListener("hashchange", () => {
  if (!state.itinerary.length) return;
  render();
  byId(byId("series").hidden ? "overview-title" : "phase-title").focus({ preventScroll: true });
  window.scrollTo(0, 0);
});
answerField.addEventListener("input", () => {
  if (!current?.step.response) return;
  const value = current.key === "forecast/check" ? `No${answerField.value ? `\n${answerField.value}` : ""}` : answerField.value;
  responseDrafts.set(current.key, value);
  responseFailures.delete(current.key);
  renderAction();
});
for (const radio of document.querySelectorAll('input[name="forecast-choice"]')) {
  radio.addEventListener("change", () => {
    if (current?.key !== "forecast/check") return;
    responseDrafts.set(current.key, radio.value);
    responseFailures.delete(current.key);
    render();
  });
}
byId("step-form").addEventListener("submit", advance);
start();
