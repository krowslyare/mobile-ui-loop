"use strict";

// Session strings are evidence, never markup. All dynamic content uses textContent.
const byId = (id) => document.getElementById(id);
const list = (value) => Array.isArray(value) ? value : [];
const string = (value, fallback = "") => value === null || value === undefined ? fallback : String(value);
const state = { session: null, filter: "all", query: "", selected: new Set(), reviewId: null, captureId: null, proposalId: null, toastTimer: null };

function element(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = string(text);
  return item;
}

function plural(count, word) { return `${count} ${word}${count === 1 ? "" : "s"}`; }
function captures() { return list(state.session && state.session.captures); }
function proposals() { return list(state.session && state.session.proposals); }
function reviews() { return list(state.session && state.session.reviews); }
function selectedReview() { return reviews().find((review) => review.id === state.reviewId) || reviews()[reviews().length - 1] || null; }
function proposalsFor(captureId) { return proposals().filter((proposal) => proposal.capture_id === captureId); }
function visibleCaptures() {
  return captures().filter((capture) => {
    const matchesSource = state.filter === "all" || capture.kind === state.filter;
    const searchable = [capture.id, capture.state_id, capture.title, capture.description].map((item) => string(item)).join(" ").toLowerCase();
    return matchesSource && searchable.includes(state.query);
  });
}

function imageURL(file) {
  // The server also allowlists manifest paths. Avoid browser URL interpretation.
  const parts = string(file).replaceAll("\\", "/").split("/");
  if (!parts.length || parts.some((part) => !part || part === "." || part === "..")) return null;
  return "/files/" + parts.map(encodeURIComponent).join("/");
}

function appendImage(container, file, alt, lazy = true) {
  const url = imageURL(file);
  if (!url) {
    container.append(element("p", "compare-placeholder", "Image path unavailable."));
    return;
  }
  const image = element("img");
  image.alt = alt;
  image.src = url;
  image.decoding = "async";
  if (lazy) image.loading = "lazy";
  image.addEventListener("error", () => {
    image.remove();
    container.append(element("p", "compare-placeholder", "This image is unavailable. Its capture record is preserved."));
  }, { once: true });
  container.append(image);
}

function sourceBadge(kind) {
  const known = kind === "imported" || kind === "observed";
  return element("span", "source-badge " + (known ? "source-" + kind : "source-imported"), kind === "observed" ? "Observed" : kind === "imported" ? "Imported" : "Source unspecified");
}

function emptyState(title, description, symbol = "▦") {
  const empty = element("div", "empty-state");
  const icon = element("span", "empty-symbol", symbol);
  icon.setAttribute("aria-hidden", "true");
  empty.append(icon, element("h3", "", title), element("p", "", description));
  return empty;
}

function renderSummary() {
  const session = state.session;
  const all = captures();
  const observed = all.filter((capture) => capture.kind === "observed").length;
  const imported = all.filter((capture) => capture.kind === "imported").length;
  const inventory = list(session.registered_states);
  const capturedStates = new Set(all.map((capture) => capture.state_id));
  const covered = inventory.filter((item) => capturedStates.has(item.id));
  byId("project-name").textContent = string(session.project_name, "Your app");
  document.title = string(session.project_name, "Your app") + " · Mobile UI Loop";
  byId("session-label").textContent = "SESSION " + string(session.session_id, "Local collection");
  byId("nav-count").textContent = all.length;
  byId("capture-count").textContent = all.length;
  byId("capture-detail").textContent = `${observed} observed · ${imported} imported`;
  byId("coverage-count").textContent = inventory.length ? `${covered.length} / ${inventory.length}` : "—";
  byId("coverage-detail").textContent = inventory.length ? "Expected states supplied by you" : "No expected state inventory";
  byId("proposal-count").textContent = proposals().length;
  byId("review-count").textContent = reviews().length;
  const note = byId("coverage-note");
  note.hidden = false;
  if (inventory.length) {
    const missing = inventory.filter((item) => !capturedStates.has(item.id));
    const missingNames = missing.slice(0, 5).map((item) => string(item.title || item.id)).join(", ");
    const remainder = missing.length > 5 ? `, and ${missing.length - 5} more` : "";
    note.textContent = missing.length
      ? `${plural(missing.length, "expected state")} without a capture: ${missingNames}${remainder}. Coverage applies to your supplied inventory; it does not establish that every app state was reached.`
      : "Every expected state has a capture. Coverage applies to your supplied inventory; it does not establish that every app state was reached. Imported and observed captures retain separate provenance.";
  } else {
    note.textContent = "No expected state inventory supplied. This collection records the states reached during exploration, without claiming complete app coverage.";
  }
}

function renderGallery() {
  const gallery = byId("gallery");
  gallery.replaceChildren();
  const visible = visibleCaptures();
  byId("visible-count").textContent = captures().length
    ? `${plural(visible.length, "capture")}${visible.length !== captures().length ? ` of ${captures().length}` : ""}${visible.length ? " · open one to compare" : ""}`
    : "No captures collected";
  if (!visible.length) {
    gallery.append(captures().length
      ? emptyState("No matching screens", "Try another state name or choose a different capture source.", "⌕")
      : emptyState("Your collection starts with a real screen", "Use the agent or CLI to explore the running app and capture its states. Refresh here when the first captures are ready."));
  }
  for (const capture of visible) {
    const card = element("article", "capture-card" + (state.selected.has(capture.id) ? " selected" : ""));
    const select = element("label", "capture-select");
    const checkbox = element("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selected.has(capture.id);
    checkbox.setAttribute("aria-label", "Select " + string(capture.title || capture.state_id || capture.id));
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.selected.add(capture.id); else state.selected.delete(capture.id);
      card.classList.toggle("selected", checkbox.checked);
      renderSelection();
    });
    select.append(checkbox);
    const open = element("button", "capture-open");
    open.type = "button";
    open.setAttribute("aria-label", "View " + string(capture.title || capture.state_id || capture.id));
    open.addEventListener("click", () => openDetail(capture.id));
    const thumbnail = element("div", "capture-thumbnail");
    appendImage(thumbnail, capture.file, string(capture.title || capture.state_id || "Captured app screen"));
    const info = element("div", "capture-info");
    info.append(element("span", "capture-title", capture.title || capture.state_id || "Untitled capture"), element("span", "capture-id", capture.state_id || capture.id));
    open.append(thumbnail, info);
    const footer = element("div", "capture-footer");
    footer.append(sourceBadge(capture.kind));
    const count = proposalsFor(capture.id).length;
    footer.append(count ? element("span", "proposal-count", plural(count, "proposal")) : element("span", "capture-resolution", list(capture.image_size).join(" × ")));
    card.append(select, open, footer);
    gallery.append(card);
  }
  gallery.setAttribute("aria-busy", "false");
  renderSelection();
}

function renderSelection() {
  const visible = visibleCaptures();
  const selectedVisible = visible.filter((capture) => state.selected.has(capture.id)).length;
  const selectAll = byId("select-all");
  selectAll.checked = Boolean(visible.length && selectedVisible === visible.length);
  selectAll.indeterminate = selectedVisible > 0 && selectedVisible < visible.length;
  selectAll.disabled = !visible.length;
  byId("selection-bar").hidden = !state.selected.size;
  byId("selection-count").textContent = plural(state.selected.size, "capture") + " selected";
}

function briefItem(label, value) {
  const item = element("div");
  item.append(element("span", "brief-label", label), element("p", "brief-value", string(value, "Not supplied")));
  return item;
}

function readable(value, fallback = "Not supplied") {
  if (Array.isArray(value)) return value.map((item) => readable(item, "")).join(", ");
  if (value && typeof value === "object") return Object.entries(value).map(([key, item]) => `${key}: ${readable(item, "")}`).join(" · ");
  return string(value, fallback);
}

function renderReview() {
  const all = reviews();
  const review = selectedReview();
  const picker = byId("review-picker");
  picker.replaceChildren();
  for (const item of all) {
    const option = element("option", "", item.id || "Evaluation");
    option.value = string(item.id);
    option.selected = item === review;
    picker.append(option);
  }
  byId("review-picker-wrap").hidden = all.length < 2;
  const container = byId("review-content");
  container.replaceChildren();
  if (!review) {
    container.append(emptyState("A direction needs context", "Evaluate the collected screens with your app’s theme, audience, and constraints. The evaluation and its per-screen image briefs will appear here.", "✳"));
    return;
  }
  state.reviewId = review.id;
  const layout = element("div", "review-layout");
  const brief = element("article", "review-card");
  brief.append(element("h3", "", "The app brief"));
  const briefGrid = element("div", "brief-grid");
  briefGrid.append(briefItem("Theme / domain", review.theme), briefItem("Who it is for", review.audience));
  brief.append(briefGrid, element("p", "review-summary", review.summary || "No evaluation summary recorded."));
  const direction = element("article", "review-card");
  const visual = review.direction || {};
  direction.append(element("h3", "", "Shared visual direction"), element("p", "direction-name", visual.name || "Direction not recorded"));
  const palette = element("div", "palette");
  const colors = Array.isArray(visual.palette) ? visual.palette : visual.palette && typeof visual.palette === "object" ? Object.entries(visual.palette).map(([name, color]) => ({ name, color })) : [];
  for (const item of colors) {
    const color = typeof item === "string" ? item : item && (item.color || item.hex || item.value);
    const label = typeof item === "string" ? item : readable(item);
    const chip = element("span", "swatch");
    const sample = element("i", "swatch-color");
    if (/^#[0-9a-f]{3,8}$/i.test(string(color))) sample.style.backgroundColor = color;
    chip.append(sample, document.createTextNode(label));
    palette.append(chip);
  }
  if (colors.length) direction.append(palette);
  if (visual.typography) direction.append(element("p", "direction-typography", "Typography · " + readable(visual.typography)));
  const principles = element("ul", "principles");
  for (const principle of list(visual.principles)) principles.append(element("li", "", readable(principle)));
  direction.append(principles);
  layout.append(brief, direction);
  container.append(layout);
  const observations = list(review.observations);
  if (observations.length) {
    const notes = element("div", "observations");
    notes.append(element("h3", "observations-heading", "What to improve · " + plural(observations.length, "observation")));
    for (const observation of observations) {
      const row = element("article", "observation");
      const capture = captures().find((item) => item.id === observation.capture_id);
      const title = element(capture ? "button" : "p", "observation-title", capture ? capture.title || capture.state_id || capture.id : observation.capture_id || "Collection");
      if (capture) { title.type = "button"; title.addEventListener("click", () => openDetail(capture.id)); }
      const issue = element("p");
      issue.append(element("span", "", "Observed issue"), document.createTextNode(readable(observation.issue)));
      const suggestion = element("p");
      suggestion.append(element("span", "", "Suggested change"), document.createTextNode(readable(observation.suggestion)));
      row.append(title, issue, suggestion);
      notes.append(row);
    }
    container.append(notes);
  }
}

function activeCapture() { return captures().find((capture) => capture.id === state.captureId); }
function activeProposal() { return proposalsFor(state.captureId).find((proposal) => proposal.id === state.proposalId) || null; }
function activePrompt() {
  const proposal = activeProposal();
  const review = selectedReview();
  const brief = review && list(review.prompts).find((prompt) => prompt.capture_id === state.captureId);
  return proposal && proposal.prompt ? string(proposal.prompt) : brief ? string(brief.prompt) : "";
}

function renderDetail() {
  const capture = activeCapture();
  if (!capture) { byId("capture-dialog").close(); return; }
  byId("detail-state").textContent = string(capture.state_id || capture.id);
  byId("detail-title").textContent = string(capture.title || "Untitled capture");
  byId("detail-description").textContent = string(capture.description);
  byId("detail-description").hidden = !capture.description;
  const meta = byId("detail-meta");
  meta.replaceChildren(sourceBadge(capture.kind), element("span", "", list(capture.image_size).join(" × ")), element("span", "", "Capture " + string(capture.id)));
  const original = byId("original-image");
  original.replaceChildren();
  appendImage(original, capture.file, "Original: " + string(capture.title || capture.id), false);
  const available = proposalsFor(capture.id);
  if (!available.some((proposal) => proposal.id === state.proposalId)) state.proposalId = available.length ? available[available.length - 1].id : null;
  const picker = byId("proposal-picker");
  picker.replaceChildren();
  for (const proposal of available) {
    const option = element("option", "", string(proposal.id) + " · " + readable(proposal.provider, "Imported"));
    option.value = string(proposal.id);
    option.selected = proposal.id === state.proposalId;
    picker.append(option);
  }
  byId("proposal-picker-wrap").hidden = available.length < 2;
  const proposed = byId("proposal-image");
  proposed.replaceChildren();
  const proposal = activeProposal();
  if (proposal) appendImage(proposed, proposal.file, "Visual proposal for " + string(capture.title || capture.id), false);
  else {
    const placeholder = element("div", "compare-placeholder");
    const symbol = element("span", "", "✳");
    symbol.setAttribute("aria-hidden", "true");
    placeholder.append(symbol, element("p", "", "No proposal for this capture yet. Evaluate the collection, then generate or import a visual concept."));
    proposed.append(placeholder);
  }
  const notes = byId("detail-notes");
  notes.replaceChildren();
  const review = selectedReview();
  for (const observation of review ? list(review.observations).filter((item) => item.capture_id === capture.id) : []) {
    const note = element("article", "detail-note");
    for (const [label, text] of [["Observed issue", observation.issue], ["Suggested change", observation.suggestion]]) {
      const paragraph = element("p");
      paragraph.append(element("strong", "", label), document.createTextNode(readable(text)));
      note.append(paragraph);
    }
    notes.append(note);
  }
  const prompt = activePrompt();
  byId("prompt-section").hidden = !prompt;
  byId("detail-prompt").textContent = prompt;
  byId("prompt-hint").textContent = proposal && proposal.prompt ? "Recorded brief for this proposal. A generated concept is not a verified implementation." : "Evaluation brief for this state. Use it with the original capture and relevant screens from the collection.";
  const context = byId("capture-context");
  context.replaceChildren();
  const fields = [["Capture ID", capture.id], ["State ID", capture.state_id], ["Captured at", capture.captured_at], ["File", capture.file], ["SHA-256", capture.sha256], ["Duplicate of", capture.duplicate_of]];
  for (const [label, value] of fields) {
    if (value !== null && value !== undefined && value !== "") context.append(element("dt", "", label), element("dd", "", value));
  }
  const snapshot = byId("snapshot-context");
  snapshot.hidden = !capture.snapshot || !Object.keys(capture.snapshot).length;
  snapshot.textContent = snapshot.hidden ? "" : JSON.stringify(capture.snapshot, null, 2);
}

function openDetail(captureId) {
  state.captureId = captureId;
  state.proposalId = null;
  renderDetail();
  const dialog = byId("capture-dialog");
  if (!dialog.open) dialog.showModal();
  dialog.querySelector(".dialog-body").scrollTop = 0;
}

function toast(message, duration = 3500) {
  clearTimeout(state.toastTimer);
  byId("toast").textContent = message;
  byId("toast").hidden = false;
  state.toastTimer = setTimeout(() => { byId("toast").hidden = true; }, duration);
}

async function copy(text, success) {
  try {
    await navigator.clipboard.writeText(text);
    toast(success);
  } catch (_) {
    const field = element("textarea", "clipboard-fallback");
    field.value = text;
    field.readOnly = true;
    field.setAttribute("aria-label", "Text to copy manually");
    // Keep the fallback within an open dialog so its focus remains reachable.
    (byId("capture-dialog").open ? byId("capture-dialog") : byId("selection-bar")).append(field);
    field.focus();
    field.select();
    let copied = false;
    try { copied = document.execCommand("copy"); } catch (_) { /* Manual copy remains available. */ }
    if (copied) { field.remove(); toast(success); }
    else toast("Clipboard unavailable. Copy the selected text manually.", 12000);
  }
}

async function refresh() {
  const button = byId("refresh");
  const connection = byId("connection");
  button.disabled = true;
  connection.textContent = "Refreshing";
  connection.className = "connection";
  byId("gallery").setAttribute("aria-busy", "true");
  try {
    const response = await fetch("/api/session", { cache: "no-store" });
    if (!response.ok) throw new Error(`The session could not be read (HTTP ${response.status}). Check the viewer terminal and refresh.`);
    const session = await response.json();
    if (!session || session.schema_version !== 1 || !Array.isArray(session.captures)) throw new Error("Unsupported or incomplete session manifest. Check the viewer terminal.");
    state.session = session;
    const known = new Set(captures().map((capture) => capture.id));
    state.selected = new Set([...state.selected].filter((id) => known.has(id)));
    renderSummary();
    renderGallery();
    renderReview();
    if (byId("capture-dialog").open) renderDetail();
    byId("error").hidden = true;
    connection.textContent = "Local · connected";
    connection.className = "connection connected";
  } catch (error) {
    const message = error instanceof TypeError
      ? "Cannot connect to the local viewer. Check that it is still running, then refresh."
      : error.message || "The local session could not be read. Check the viewer terminal and refresh.";
    byId("error").textContent = state.session ? message + " Previously loaded records are still visible." : message;
    byId("error").hidden = false;
    connection.textContent = "Connection lost";
    connection.className = "connection failed";
    if (!state.session) {
      byId("gallery").replaceChildren(emptyState("The session is unavailable", "Start the local viewer from an existing session and refresh this page."));
      byId("review-content").replaceChildren();
    }
  } finally {
    button.disabled = false;
    byId("gallery").setAttribute("aria-busy", "false");
  }
}

byId("refresh").addEventListener("click", refresh);
byId("search").addEventListener("input", (event) => { state.query = event.target.value.trim().toLowerCase(); renderGallery(); });
for (const button of document.querySelectorAll("[data-filter]")) {
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    for (const tab of document.querySelectorAll("[data-filter]")) {
      const active = tab === button;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-pressed", String(active));
    }
    renderGallery();
  });
}
byId("select-all").addEventListener("change", (event) => {
  for (const capture of visibleCaptures()) {
    if (event.target.checked) state.selected.add(capture.id); else state.selected.delete(capture.id);
  }
  renderGallery();
});
byId("clear-selection").addEventListener("click", () => { state.selected.clear(); renderGallery(); });
byId("copy-selection").addEventListener("click", () => {
  const ids = captures().filter((capture) => state.selected.has(capture.id)).map((capture) => capture.id);
  copy(JSON.stringify(ids, null, 2), "Capture IDs copied as a JSON array");
});
byId("copy-prompt").addEventListener("click", () => copy(activePrompt(), "Image generation brief copied"));
byId("close-detail").addEventListener("click", () => byId("capture-dialog").close());
byId("proposal-picker").addEventListener("change", (event) => { state.proposalId = event.target.value; renderDetail(); });
byId("review-picker").addEventListener("change", (event) => {
  state.reviewId = event.target.value;
  renderReview();
  if (byId("capture-dialog").open) renderDetail();
});
for (const link of document.querySelectorAll(".nav-link")) {
  link.addEventListener("click", () => {
    for (const other of document.querySelectorAll(".nav-link")) other.classList.toggle("active", other === link);
  });
}
refresh();
