let currentJob = null;
let currentLayout = null;
let currentPage = 0;

const form = document.getElementById("uploadForm");
const statusEl = document.getElementById("status");
const demoSelect = document.getElementById("demoPdf");
const pageList = document.getElementById("pageList");
const pageImage = document.getElementById("pageImage");
const blockEditor = document.getElementById("blockEditor");
const warningsEl = document.getElementById("warnings");
const exportBtn = document.getElementById("exportBtn");
const downloads = document.getElementById("downloads");
const apiKeyBtn = document.getElementById("apiKeyBtn");
const apiKeyDialog = document.getElementById("apiKeyDialog");
const apiKeyForm = document.getElementById("apiKeyForm");
const apiKeyInput = document.getElementById("apiKeyInput");
const apiKeyHelp = document.getElementById("apiKeyHelp");
const clearApiKeyBtn = document.getElementById("clearApiKeyBtn");
const closeApiKeyBtn = document.getElementById("closeApiKeyBtn");
let hasGeminiApiKey = false;

init();

async function init() {
  if (window.location.protocol === "file:") {
    statusEl.textContent = "Open with http://127.0.0.1:8000, not the file path.";
    warningsEl.hidden = false;
    warningsEl.innerHTML = "<div>This is only the template file. Start the FastAPI server and open http://127.0.0.1:8000 for the working app.</div>";
    return;
  }
  const demos = await fetch("/api/demo-pdfs").then(r => r.json());
  for (const demo of demos) {
    const option = document.createElement("option");
    option.value = demo.name;
    option.textContent = demo.name;
    demoSelect.append(option);
  }
  await refreshSettings(true);
}

apiKeyBtn.addEventListener("click", () => {
  apiKeyInput.value = "";
  apiKeyDialog.showModal();
  apiKeyInput.focus();
});

closeApiKeyBtn.addEventListener("click", () => apiKeyDialog.close());

apiKeyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const apiKey = apiKeyInput.value.trim();
  if (!apiKey) {
    apiKeyHelp.textContent = "Paste a Gemini API key first.";
    return;
  }
  const response = await fetch("/api/settings/gemini-key", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  const payload = await response.json();
  if (!response.ok) {
    apiKeyHelp.textContent = payload.detail || "Could not save API key.";
    return;
  }
  apiKeyDialog.close();
  await refreshSettings(false);
});

clearApiKeyBtn.addEventListener("click", async () => {
  await fetch("/api/settings/gemini-key", { method: "DELETE" });
  apiKeyInput.value = "";
  await refreshSettings(false);
  apiKeyDialog.close();
});

async function refreshSettings(openWhenMissing) {
  const settings = await fetch("/api/settings").then(r => r.json());
  hasGeminiApiKey = Boolean(settings.has_gemini_api_key);
  if (settings.has_gemini_api_key) {
    const source = settings.source ? ` (${settings.source})` : "";
    apiKeyBtn.textContent = `API Key: ${settings.masked_gemini_api_key}`;
    apiKeyHelp.textContent = `A Gemini API key is available${source}. Paste a new key to replace the in-app saved key.`;
  } else {
    apiKeyBtn.textContent = "Add Gemini API Key";
    apiKeyHelp.textContent = "Add GEMINI_API_KEY in .env or .env.local, or save it here for this computer.";
    if (openWhenMissing) apiKeyDialog.showModal();
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formDataPreview = new FormData(form);
  if (hasGeminiApiKey && formDataPreview.get("force_demo")) {
    showWarnings(["Demo/reference mode is checked, so Gemini OCR will be skipped. Uncheck it for real OCR."]);
  }
  statusEl.textContent = "Converting...";
  exportBtn.disabled = true;
  downloads.hidden = true;
  const data = new FormData(form);
  if (!data.get("file")?.name) {
    data.delete("file");
  }
  try {
    const response = await fetch("/api/jobs", { method: "POST", body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Conversion failed");
    currentJob = payload.job_id;
    currentLayout = payload.layout;
    currentPage = 0;
    renderJob();
    statusEl.textContent = `Ready: ${currentJob}`;
    exportBtn.disabled = false;
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

exportBtn.addEventListener("click", async () => {
  if (!currentJob) return;
  statusEl.textContent = "Saving edits...";
  collectEdits();
  await fetch(`/api/jobs/${currentJob}/layout`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentLayout),
  });
  statusEl.textContent = "Exporting DOCX...";
  const result = await fetch(`/api/jobs/${currentJob}/export`, { method: "POST" }).then(r => r.json());
  document.getElementById("faithfulLink").href = `/api/jobs/${currentJob}/download/faithful`;
  document.getElementById("editableFaithfulLink").href = `/api/jobs/${currentJob}/download/editable-faithful`;
  document.getElementById("columnLink").href = `/api/jobs/${currentJob}/download/column-ready`;
  document.getElementById("bijoyLink").href = `/api/jobs/${currentJob}/download/bijoy`;
  document.getElementById("bijoyLink").removeAttribute("aria-disabled");
  downloads.hidden = false;
  showWarnings([...(result.warnings || []), ...(result.bijoy_warnings || [])]);
  statusEl.textContent = "Export complete";
});

function renderJob() {
  renderPages();
  renderWarnings();
  renderPage();
}

function renderWarnings() {
  showWarnings(currentLayout.warnings || []);
}

function showWarnings(warnings) {
  if (!warnings.length) {
    warningsEl.hidden = true;
    warningsEl.textContent = "";
    return;
  }
  warningsEl.hidden = false;
  warningsEl.innerHTML = warnings.map(w => `<div>${escapeHtml(w)}</div>`).join("");
}

function renderPages() {
  pageList.innerHTML = "";
  currentLayout.pages.forEach((page, index) => {
    const button = document.createElement("button");
    button.className = "page-item";
    button.textContent = `Page ${index + 1} (${page.blocks.length} blocks)`;
    button.addEventListener("click", () => {
      collectEdits();
      currentPage = index;
      renderPage();
    });
    pageList.append(button);
  });
}

function renderPage() {
  const page = currentLayout.pages[currentPage];
  const imageName = page.image_path.split(/[\\/]/).pop();
  pageImage.src = `/api/jobs/${currentJob}/page/${imageName}`;
  blockEditor.innerHTML = "";
  page.blocks.forEach((block, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "block";
    wrapper.dataset.index = index;
    wrapper.innerHTML = `<header><span>${escapeHtml(block.type)} - ${escapeHtml(block.id)}</span><span>${Math.round((block.confidence || 0) * 100)}%</span></header>`;
    if (block.type === "table" && block.table) {
      wrapper.append(renderTable(block));
    } else if (block.type === "artifact") {
      const note = document.createElement("textarea");
      note.value = block.text || `[${block.artifact_type || "artifact"}]`;
      note.dataset.field = "text";
      wrapper.append(note);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = block.text || "";
      textarea.dataset.field = "text";
      wrapper.append(textarea);
    }
    blockEditor.append(wrapper);
  });
}

function renderTable(block) {
  const table = document.createElement("table");
  const cells = new Map(block.table.cells.map(cell => [`${cell.row}:${cell.col}`, cell]));
  for (let r = 0; r < block.table.row_count; r++) {
    const tr = document.createElement("tr");
    for (let c = 0; c < block.table.col_count; c++) {
      const td = document.createElement("td");
      const textarea = document.createElement("textarea");
      textarea.value = cells.get(`${r}:${c}`)?.text || "";
      textarea.dataset.row = r;
      textarea.dataset.col = c;
      td.append(textarea);
      tr.append(td);
    }
    table.append(tr);
  }
  return table;
}

function collectEdits() {
  if (!currentLayout) return;
  const page = currentLayout.pages[currentPage];
  for (const wrapper of blockEditor.querySelectorAll(".block")) {
    const block = page.blocks[Number(wrapper.dataset.index)];
    if (block.type === "table" && block.table) {
      for (const textarea of wrapper.querySelectorAll("textarea")) {
        const row = Number(textarea.dataset.row);
        const col = Number(textarea.dataset.col);
        let cell = block.table.cells.find(item => item.row === row && item.col === col);
        if (!cell) {
          cell = { row, col, text: "", confidence: 1, row_span: 1, col_span: 1 };
          block.table.cells.push(cell);
        }
        cell.text = textarea.value;
      }
    } else {
      const textarea = wrapper.querySelector("textarea[data-field=text]");
      if (textarea) block.text = textarea.value;
    }
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[ch]));
}
