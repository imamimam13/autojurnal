const API_BASE = window.location.origin;

let allPapers = [];
let selectedIndices = new Set();
let collectedPapers = [];
let ideaCollectedPapers = [];
let currentJournal = "";

let templates = [];
let parsedTemplate = null;

let aiCatalog = [];
let aiSettings = {};
let currentAICategory = 'all';
let activeCheckpointData = null;

document.addEventListener("DOMContentLoaded", async () => {
    await loadAISettings();
    await loadProviders();
    await checkActiveCheckpoint();
    restoreSettings();
    updatePlaceholders(document.getElementById("provider").value);
    restoreCollection();
    restoreIdeaCollection();
    updateDraftsBadge();
    await loadTemplateList();

    document.getElementById("mode").addEventListener("change", () => {
        toggleMode();
        saveSettings();
    });

    document.getElementById("provider").addEventListener("change", () => {
        saveSettings();
        const provider = document.getElementById("provider").value;
        const apiKey = document.getElementById("llm-api-key")?.value.trim();
        saveApiKeyToBackend(provider, apiKey);
        updatePlaceholders(provider);
    });

    document.querySelectorAll("#input-card input, #input-card select, #tab-idea select, #tab-idea input").forEach((el) => {
        el.addEventListener("change", saveSettings);
        el.addEventListener("input", saveSettings);
    });

    document.getElementById("paper-title").addEventListener("input", updateGenerateBtn);
    document.getElementById("template-select").addEventListener("change", saveSettings);

    const apiKeyEl = document.getElementById("llm-api-key");
    const providerEl = document.getElementById("provider");
    if (apiKeyEl && providerEl) {
        apiKeyEl.addEventListener("input", () => {
            const provider = providerEl.value;
            const apiKey = apiKeyEl.value.trim();
            saveApiKeyToBackend(provider, apiKey);
        });
    }
});

let _apiKeyTimeout = null;

function toggleDataInput() {
    const checked = document.getElementById("has-data").checked;
    document.getElementById("data-input-section").style.display = checked ? "" : "none";
    if (checked) document.getElementById("data-input-section").scrollIntoView({ behavior: "smooth", block: "center" });
}

document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("data-file-input").addEventListener("change", function (e) {
        const file = e.target.files[0];
        if (!file) return;
        const name = file.name.toLowerCase();
        if (name.endsWith(".xlsx") || name.endsWith(".xls")) {
            const reader = new FileReader();
            reader.onload = function (ev) {
                try {
                    const data = new Uint8Array(ev.target.result);
                    const workbook = XLSX.read(data, { type: "array" });
                    let combined = "";
                    workbook.SheetNames.forEach((sname, i) => {
                        const sheet = workbook.Sheets[sname];
                        const csv = XLSX.utils.sheet_to_csv(sheet);
                        if (workbook.SheetNames.length > 1) {
                            combined += (i > 0 ? "\n\n" : "") + "=== " + sname + " ===\n" + csv;
                        } else {
                            combined = csv;
                        }
                    });
                    document.getElementById("user-data").value = combined;
                } catch (err) {
                    alert("Gagal membaca Excel: " + err.message);
                }
            };
            reader.readAsArrayBuffer(file);
        } else {
            const reader = new FileReader();
            reader.onload = function (ev) {
                document.getElementById("user-data").value = ev.target.result;
            };
            reader.readAsText(file);
        }
    });
});

function toggleMode() {
    const mode = document.getElementById("mode").value;
    const isTextbook = mode === "textbook";
    document.getElementById("target-length-group").style.display = isTextbook ? "none" : "";
    document.getElementById("chapter-count-group").style.display = isTextbook ? "" : "none";
    document.getElementById("multi-agent").closest(".col-md-2").style.display = isTextbook ? "none" : "";
    updateGenerateBtn();
}

function saveSettings() {
    const keys = [
        "openalex-api-key", "llm-api-key", "provider-model", "provider-base-url",
        "theme", "paper-title", "year-range", "max-papers", "language", "provider",
        "multi-agent", "has-data", "user-data", "mode", "num-chapters", "template-select",
        "paradigm", "analysis-method", "idea-paradigm", "idea-analysis-method",
    ];
    const data = {};
    keys.forEach((id) => {
        const el = document.getElementById(id);
        if (el) data[id] = el.value !== undefined ? el.value : el.checked;
    });
    // special handling for checkbox
    data["multi-agent"] = document.getElementById("multi-agent").checked;
    try {
        localStorage.setItem("autojurnal-settings", JSON.stringify(data));
    } catch {}
}

function updatePlaceholders(provider) {
    const baseUrlEl = document.getElementById("provider-base-url");
    const modelEl = document.getElementById("provider-model");
    if (!baseUrlEl || !modelEl) return;

    if (provider === "ollama") {
        baseUrlEl.placeholder = "http://localhost:11434";
        modelEl.placeholder = "gemma3:12b (default)";
    } else if (provider === "openai") {
        baseUrlEl.placeholder = "https://api.openai.com/v1";
        modelEl.placeholder = "gpt-4o-mini (default)";
    } else if (provider === "openai_compatible") {
        baseUrlEl.placeholder = "http://localhost:8080/v1 (e.g. llama.cpp)";
        modelEl.placeholder = "llama3 (default)";
    } else if (provider === "anthropic") {
        baseUrlEl.placeholder = "https://api.anthropic.com/v1";
        modelEl.placeholder = "claude-3-haiku-20240307 (default)";
    } else if (provider === "gemini") {
        baseUrlEl.placeholder = "https://generativelanguage.googleapis.com/v1";
        modelEl.placeholder = "gemini-2.0-flash (default)";
    }
}

function saveApiKeyToBackend(provider, apiKey) {
    const supported = ["ollama", "openai", "anthropic", "gemini", "openai_compatible"];
    if (!supported.includes(provider) || !apiKey) return;
    clearTimeout(_apiKeyTimeout);
    _apiKeyTimeout = setTimeout(() => {
        fetch(`${API_BASE}/api/settings`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider, api_key: apiKey }),
        }).catch(() => {});
    }, 1000);
}

function restoreSettings() {
    try {
        const raw = localStorage.getItem("autojurnal-settings");
        if (!raw) return;
        const data = JSON.parse(raw);
        Object.entries(data).forEach(([id, val]) => {
            const el = document.getElementById(id);
            if (!el) return;
            if (el.type === "checkbox") {
                el.checked = val === true || val === "true";
            } else {
                el.value = val;
            }
        });
        // template-select value is restored by populateTemplateSelect after templates load
        toggleMode();
        toggleDataInput();
    } catch {}
}

async function loadProviders() {
    try {
        const resp = await fetch(`${API_BASE}/api/providers`);
        const providers = await resp.json();
        const sel = document.getElementById("provider");
        const current = sel.value;
        sel.innerHTML = providers
            .map((p) => `<option value="${p.id}">${p.name}</option>`)
            .join("");
        if (current) sel.value = current;
    } catch {}
}

function updateLoading(text, subtext, isError = false) {
    document.getElementById("loading-text").textContent = text;
    document.getElementById("loading-subtext").textContent = subtext || "";
    document.getElementById("loading-subtext").className = isError
        ? "text-danger mb-0"
        : "text-muted mb-0";
}

function showLoading() {
    document.getElementById("loading-section").style.display = "block";
}

function hideLoading() {
    document.getElementById("loading-section").style.display = "none";
    const logEl = document.getElementById("log-display");
    if (logEl) { logEl.style.display = "none"; logEl.innerHTML = ""; }
}

function clearLogs() {
    const el = document.getElementById("log-display");
    if (el) { el.innerHTML = ""; el.style.display = "none"; }
}

function addLogEntry(agent, message, detail) {
    const el = document.getElementById("log-display");
    if (!el) return;
    el.style.display = "block";
    const time = new Date().toLocaleTimeString();
    const line = document.createElement("div");
    line.className = "log-entry";
    const detailText = detail ? ` — ${detail}` : "";
    line.textContent = `[${time}] [${agent}] ${message}${detailText}`;
    el.appendChild(line);
    el.scrollTop = el.scrollHeight;
}

async function searchPapers() {
    const theme = document.getElementById("theme").value.trim();
    if (!theme) {
        alert("Please enter a research theme.");
        return;
    }

    document.getElementById("result-section").style.display = "none";
    showLoading();
    updateLoading("Searching papers on OpenAlex...", "Finding relevant academic papers");

    const yearRange = parseInt(document.getElementById("year-range").value) || 0;
    const maxPapers = parseInt(document.getElementById("max-papers").value) || 15;
    const language = document.getElementById("language").value;
    const openalexApiKey = document.getElementById("openalex-api-key").value.trim() || null;

    const body = {
        theme,
        max_papers: maxPapers,
        language,
        openalex_api_key: openalexApiKey,
    };

    const currentYear = new Date().getFullYear();
    if (yearRange > 0) {
        body.from_year = currentYear - yearRange;
    }

    try {
        updateLoading("Fetching papers from OpenAlex...", "Searching across millions of academic works");
        const resp = await fetch(`${API_BASE}/api/search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });

        if (!resp.ok) {
            const errText = await resp.text();
            throw new Error(errText);
        }

        const data = await resp.json();
        allPapers = data.papers;
        selectedIndices = new Set(allPapers.map((_, i) => i));

        hideLoading();

        if (allPapers.length === 0) {
            document.getElementById("papers-section").style.display = "none";
            showLoading();
            updateLoading(
                "No papers found",
                "Try a broader theme or larger year range",
                true
            );
            setTimeout(hideLoading, 3000);
            return;
        }

        displayPapers(allPapers);
        document.getElementById("papers-section").style.display = "block";
        document.getElementById("papers-section").scrollIntoView({ behavior: "smooth" });

    } catch (err) {
        showLoading();
        updateLoading("Search failed", err.message.substring(0, 200), true);
        setTimeout(() => {
            hideLoading();
        }, 5000);
    }
}

function displayPapers(papers) {
    const container = document.getElementById("papers-list");
    document.getElementById("papers-count").textContent = papers.length;

    container.innerHTML = papers
        .map(
            (p, i) => `
        <div class="paper-item ${selectedIndices.has(i) ? "selected" : ""}" data-index="${i}">
            <div class="d-flex justify-content-between align-items-start">
                <div class="form-check me-3">
                    <input class="form-check-input" type="checkbox" ${selectedIndices.has(i) ? "checked" : ""}
                        id="paper-chk-${i}" onchange="toggleSelectPaper(${i})">
                </div>
                <div class="flex-grow-1 me-3" onclick="togglePaper(${i})" style="cursor:pointer">
                    <div class="paper-title">${escapeHtml(p.title)}</div>
                    <div class="paper-meta">
                        ${(p.authors || []).slice(0, 3).join(", ")}${p.authors.length > 3 ? " et al." : ""}
                        ${p.year ? `(${p.year})` : ""}
                        ${p.source ? `- ${escapeHtml(p.source)}` : ""}
                        ${p.doi ? `<span class="doi-badge" title="${escapeHtml(p.doi)}">DOI: ${escapeHtml(p.doi)}</span>` : `<span class="no-doi">(no DOI)</span>`}
                        ${p.url ? ` <a href="${escapeHtml(p.url)}" target="_blank" class="paper-link" title="Buka paper"><i class="bi bi-file-text"></i></a>` : ""}
                        ${p.openalex_url ? ` <a href="${escapeHtml(p.openalex_url)}" target="_blank" class="oa-link" title="Buka di OpenAlex"><i class="bi bi-box-arrow-up-right"></i></a>` : ""}
                        ${p.cited_by_count ? `| Cited: ${p.cited_by_count}` : ""}
                        ${p.relevance_score ? `| Relevance: ${(p.relevance_score * 100).toFixed(0)}%` : ""}
                    </div>
                    <div class="paper-abstract">
                        ${p.abstract ? escapeHtml(p.abstract.substring(0, 600)) + (p.abstract.length > 600 ? "..." : "") : "<em>No abstract available</em>"}
                    </div>
                </div>
            </div>
        </div>
    `
        )
        .join("");

    updateGenerateBtn();
}

function toggleSelectPaper(index) {
    const el = document.querySelector(`.paper-item[data-index="${index}"]`);
    if (selectedIndices.has(index)) {
        selectedIndices.delete(index);
        el.classList.remove("selected");
    } else {
        selectedIndices.add(index);
        el.classList.add("selected");
    }
    updateGenerateBtn();
}

function updateGenerateBtn() {
    const btn = document.getElementById("generate-btn");
    const count = collectedPapers.length;
    const hasTitle = document.getElementById("paper-title").value.trim().length > 0;
    btn.disabled = count === 0 || !hasTitle;
    const isTextbook = document.getElementById("mode").value === "textbook";
    const icon = isTextbook ? "book" : "journal-text";
    const label = isTextbook ? "Generate Textbook" : "Generate Journal";
    btn.innerHTML = `<i class="bi bi-${icon} me-2"></i>${label} (${count} papers)`;
    const selCount = document.getElementById("selected-count");
    if (selCount) selCount.textContent = selectedIndices.size;
}

function togglePaper(index) {
    const el = document.querySelector(`.paper-item[data-index="${index}"] .paper-abstract`);
    if (el) el.classList.toggle("expanded");
}

function toggleAllPapers() {
    const papers = document.querySelectorAll("#papers-list .paper-item");
    const allChecked = papers.length > 0 && papers.length === document.querySelectorAll("#papers-list .form-check-input:checked").length;
    papers.forEach((el, i) => {
        const chk = el.querySelector(".form-check-input");
        if (!chk) return;
        if (allChecked) {
            chk.checked = false;
            selectedIndices.delete(i);
            el.classList.remove("selected");
        } else {
            chk.checked = true;
            selectedIndices.add(i);
            el.classList.add("selected");
        }
    });
    updateGenerateBtn();
}

function addSelectedToCollection() {
    console.log("addSelectedToCollection called");
    console.log("allPapers:", allPapers.length, "selectedIndices:", selectedIndices.size);
    try {
        const selected = allPapers.filter((_, i) => selectedIndices.has(i));
        console.log("selected papers:", selected.length);
        if (selected.length === 0) {
            alert("No papers selected. Please check some papers first.");
            return;
        }
        const existingKeys = new Set(
            collectedPapers.map(p => p.doi || p.openalex_url || p.title)
        );
        const newPapers = selected.filter(
            p => !existingKeys.has(p.doi || p.openalex_url || p.title)
        );
        console.log("new papers to add:", newPapers.length);
        if (newPapers.length === 0) {
            alert("All selected papers are already in collection.");
            return;
        }
        collectedPapers.push(...newPapers);
        renderCollectedPapers();
        saveCollection();
        alert(`${newPapers.length} paper(s) added to collection!`);

        selectedIndices.clear();
        document.querySelectorAll("#papers-list .paper-item").forEach(el => {
            el.classList.remove("selected");
            const chk = el.querySelector(".form-check-input");
            if (chk) chk.checked = false;
        });
        updateGenerateBtn();
    } catch (e) {
        console.error("addSelectedToCollection error:", e);
        alert("Error: " + e.message);
    }
}

function removeFromCollection(index) {
    collectedPapers.splice(index, 1);
    renderCollectedPapers();
    saveCollection();
    updateGenerateBtn();
}

function clearCollection() {
    if (collectedPapers.length === 0) return;
    collectedPapers = [];
    renderCollectedPapers();
    saveCollection();
    updateGenerateBtn();
    showToast("Collection cleared");
}

function renderCollectedPapers() {
    console.log("renderCollectedPapers, count:", collectedPapers.length);
    const container = document.getElementById("collection-list");
    const count = document.getElementById("collection-count");
    if (!container || !count) {
        console.error("collection-list or collection-count element not found! Page might be cached.");
        return;
    }
    count.textContent = collectedPapers.length;

    if (collectedPapers.length === 0) {
        const section = document.getElementById("collection-section");
        if (section) section.style.display = "none";
        container.innerHTML = "";
        return;
    }

    const section = document.getElementById("collection-section");
    if (!section) {
        console.error("collection-section element not found! Page might be cached.");
        return;
    }
    section.style.display = "block";

    container.innerHTML = collectedPapers
        .map((p, i) => `
            <div class="paper-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1 me-3">
                        <div class="paper-title">${escapeHtml(p.title)}</div>
                        <div class="paper-meta">
                            ${(p.authors || []).slice(0, 3).join(", ")}${p.authors.length > 3 ? " et al." : ""}
                            ${p.year ? ` (${p.year})` : ""}
                            ${p.source ? ` - ${escapeHtml(p.source)}` : ""}
                        </div>
                    </div>
                    <button class="btn btn-sm btn-outline-danger" onclick="removeFromCollection(${i})" title="Remove">
                        <i class="bi bi-x-lg"></i>
                    </button>
                </div>
            </div>
        `)
        .join("");

    updateGenerateBtn();
}

function saveCollection() {
    try {
        localStorage.setItem("autojurnal-collection", JSON.stringify(collectedPapers));
    } catch {}
}

function restoreCollection() {
    try {
        const raw = localStorage.getItem("autojurnal-collection");
        if (raw) {
            collectedPapers = JSON.parse(raw);
            renderCollectedPapers();
        }
    } catch {}
}

async function generateJournal() {
    const theme = document.getElementById("paper-title").value.trim();
    const selectedPapers = collectedPapers;
    if (!theme || selectedPapers.length === 0) {
        alert("Enter a paper title and collect at least one paper first.");
        return;
    }

    const language = document.getElementById("language").value;
    const mode = document.getElementById("mode").value;
    const isTextbook = mode === "textbook";
    const targetLength = isTextbook ? "long" : document.getElementById("target-length").value;
    const multiAgent = isTextbook ? true : document.getElementById("multi-agent").checked;
    const numChapters = isTextbook ? parseInt(document.getElementById("num-chapters").value) || 14 : 0;
    const provider = document.getElementById("provider").value;
    const providerModel =
        document.getElementById("provider-model").value.trim() || null;
    const providerBaseUrl =
        document.getElementById("provider-base-url").value.trim() || null;
    const apiKey =
        document.getElementById("llm-api-key").value.trim() || null;

    const doResearch = document.getElementById("do-research").checked;

    let researchJobId = null;

    // Phase 1: Research (if checkbox is ON)
    if (doResearch) {
        showLoading();
        updateLoading("Starting research...", "Searching Google, Scholar, and PubMed for latest sources");

        try {
            const startResp = await fetch(`${API_BASE}/api/research/start`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ theme, title: theme, language }),
            });
            if (!startResp.ok) throw new Error(await startResp.text());
            const { job_id } = await startResp.json();
            if (!job_id) throw new Error("No job_id returned");

            // Poll for completion
            let done = false;
            let pollCount = 0;
            while (!done && pollCount < 60) {
                await new Promise(r => setTimeout(r, 3000));
                pollCount++;

                const statusResp = await fetch(`${API_BASE}/api/research/status/${job_id}`);
                if (!statusResp.ok) throw new Error(await statusResp.text());
                const status = await statusResp.json();

                updateLoading(
                    `Researching... (${status.progress}%)`,
                    status.progress_detail || "Processing..."
                );

                if (status.status === "done") {
                    researchJobId = job_id;
                    done = true;
                    showToast(`Research complete: ${status.scraped_count} articles scraped from ${status.sources_count} sources`, "success");
                } else if (status.status === "error") {
                    throw new Error(status.error || "Research failed");
                }
            }

            if (!done) throw new Error("Research timed out after 3 minutes");

        } catch (err) {
            updateLoading("Research failed", err.message.substring(0, 300), true);
            setTimeout(hideLoading, 8000);
            return;
        }
    }

    // Phase 2: Generate
    document.getElementById("result-section").style.display = "none";
    showLoading();
    updateLoading(
        isTextbook ? "Generating textbook..." : "Generating journal...",
        `Using ${provider}${providerModel ? ` (${providerModel})` : ""}${isTextbook ? ` · ${numChapters} chapters` : ""}`
    );
    clearLogs();

    const templateId = document.getElementById("template-select").value;
    localStorage.setItem("autojurnal-template-id", templateId);

    const hasData = document.getElementById("has-data").checked;
    const userData = document.getElementById("user-data").value.trim() || null;
    const useLibrary = document.getElementById("use-library").checked;
    const body = {
        theme,
        papers: selectedPapers,
        language,
        target_length: targetLength,
        multi_agent: multiAgent,
        mode,
        provider,
        provider_model: providerModel,
        provider_base_url: providerBaseUrl,
        api_key: apiKey,
        template_id: templateId || null,
        has_data: hasData,
        user_data: userData,
        do_research: doResearch,
        research_job_id: researchJobId,
        library: useLibrary,
        paradigm: document.getElementById("paradigm").value,
        analysis_method: document.getElementById("analysis-method").value,
    };
    if (isTextbook) body.num_chapters = numChapters;

    try {
        // Use SSE streaming for agent/textbook modes, fallback to regular POST for simple mode
        if (multiAgent || isTextbook) {
            await generateJournalStream(body);
        } else {
            await generateJournalSimple(body);
        }
    } catch (err) {
        updateLoading("Generation failed", err.message.substring(0, 300), true);
        setTimeout(hideLoading, 8000);
    }
}

async function generateJournalSimple(body) {
    const resp = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(`[${resp.status}] ${errText}`);
    }
    const data = await resp.json();
    displayResult(data, body.mode);
}

async function generateJournalStream(body) {
    const resp = await fetch(`${API_BASE}/api/generate/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(`[${resp.status}] ${errText}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (!raw) continue;

            try {
                const event = JSON.parse(raw);
                if (event.type === "log") {
                    addLogEntry(event.agent, event.message, event.detail);
                } else if (event.type === "result") {
                    displayResult({
                        journal: event.journal,
                        provider_used: event.provider_used,
                        token_usage: event.token_usage,
                    }, body.mode);
                    return;
                } else if (event.type === "error") {
                    throw new Error(event.message || "Unknown generation error");
                }
                // heartbeat — ignore
            } catch (e) {
                if (e.message?.includes("generation") || e.message?.includes("error")) {
                    throw e;
                }
            }
        }
    }
}

function displayResult(data, mode) {
    currentJournal = data.journal;

    hideLoading();
    document.getElementById("result-section").style.display = "block";
    document.getElementById("result-label").textContent =
        mode === "textbook" ? "Textbook" : "Journal";
    document.getElementById("journal-content").innerHTML =
        renderMarkdown(currentJournal);
    applyParagraphControls();

    if (data.token_usage) {
        const tu = data.token_usage;
        const el = document.getElementById("token-usage");
        if (el) {
            const inTok = tu.input_tokens?.toLocaleString() || "?";
            const outTok = tu.output_tokens?.toLocaleString() || "?";
            const est = tu.estimated ? " (estimated)" : "";
            el.textContent = `Tokens${est} — Input: ${inTok} · Output: ${outTok}`;
            el.style.display = "block";
        }
    }

    // Auto-save generated draft
    saveDraft({
        title: document.getElementById("paper-title")?.value.trim() || document.getElementById("theme")?.value.trim(),
        content: currentJournal,
        mode: mode,
        language: document.getElementById("language")?.value,
        inLibrary: document.getElementById("use-library")?.checked || false,
    }, false);

    document.getElementById("journal-content").scrollIntoView({
        behavior: "smooth",
    });
}

function showToast(msg, type = "success") {
    const toast = document.getElementById("toast-msg");
    document.getElementById("toast-body").textContent = msg;
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    bootstrap.Toast.getOrCreateInstance(toast).show();
}

let mermaidRenderCounter = 0;

function renderMarkdown(text) {
    const html = marked.parse(text);
    // Wrap mermaid code blocks for live rendering and preserve code in data attribute
    const withMermaid = html.replace(
        /<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/g,
        (match, code) => `<div class="mermaid" data-code="${encodeURIComponent(code)}">${code}</div>`
    );
    // Render mermaid after DOM update
    setTimeout(() => {
        if (typeof mermaid !== "undefined") {
            mermaid.run({ 
                nodes: document.querySelectorAll(".mermaid"),
                postRenderCallback: (id) => {
                    setTimeout(convertMermaidToPng, 100);
                }
            });
        }
    }, 100);
    // Schedule fallbacks to convert after they render
    setTimeout(convertMermaidToPng, 500);
    setTimeout(convertMermaidToPng, 1500);
    setTimeout(convertMermaidToPng, 3000);
    return withMermaid;
}

async function svgStringToPngDataUrl(svgString, fallbackWidth = 800, fallbackHeight = 400) {
    return new Promise((resolve) => {
        try {
            if (!svgString) return resolve(null);
            
            // Ensure proper XML namespace
            if (!svgString.includes('xmlns="http://www.w3.org/2000/svg"')) {
                svgString = svgString.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ');
            }

            // Extract dimensions
            let width = fallbackWidth;
            let height = fallbackHeight;

            const wMatch = svgString.match(/width=["']([0-9.]+)(?:px)?["']/i);
            const hMatch = svgString.match(/height=["']([0-9.]+)(?:px)?["']/i);
            if (wMatch && hMatch) {
                width = parseFloat(wMatch[1]);
                height = parseFloat(hMatch[1]);
            } else {
                const vbMatch = svgString.match(/viewBox=["']([0-9.\s-]+)["']/i);
                if (vbMatch) {
                    const parts = vbMatch[1].trim().split(/\s+/);
                    if (parts.length === 4) {
                        width = parseFloat(parts[2]);
                        height = parseFloat(parts[3]);
                    }
                }
            }

            if (!width || width <= 0 || isNaN(width)) width = 800;
            if (!height || height <= 0 || isNaN(height)) height = 400;

            const svgBlob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
            const blobURL = URL.createObjectURL(svgBlob);
            const image = new Image();

            const timer = setTimeout(() => {
                URL.revokeObjectURL(blobURL);
                const b64 = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgString)));
                resolve(b64);
            }, 3000);

            image.onload = () => {
                clearTimeout(timer);
                try {
                    const scale = 2; // Crisp high-DPI scaling
                    const canvas = document.createElement("canvas");
                    canvas.width = Math.max(width * scale, 400);
                    canvas.height = Math.max(height * scale, 200);
                    
                    const context = canvas.getContext("2d");
                    context.scale(scale, scale);

                    // Clean white background for documents
                    context.fillStyle = "#ffffff";
                    context.fillRect(0, 0, width, height);

                    context.drawImage(image, 0, 0, width, height);
                    const pngDataUrl = canvas.toDataURL("image/png");
                    URL.revokeObjectURL(blobURL);
                    resolve(pngDataUrl);
                } catch (e) {
                    console.error("Error drawing SVG to canvas:", e);
                    URL.revokeObjectURL(blobURL);
                    resolve("data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgString))));
                }
            };

            image.onerror = (e) => {
                clearTimeout(timer);
                console.error("Image load error:", e);
                URL.revokeObjectURL(blobURL);
                resolve("data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgString))));
            };

            image.src = blobURL;
        } catch (err) {
            console.error("svgStringToPngDataUrl error:", err);
            resolve(null);
        }
    });
}

async function renderMermaidToPngDataUrl(mermaidCode) {
    if (typeof mermaid === "undefined") return null;
    try {
        let clean = mermaidCode
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&amp;/g, '&')
            .replace(/<br\s*\/?>/gi, '\n')
            .replace(/<[^>]+>/g, '')
            .trim();

        // Strip markdown fences if present
        clean = clean.replace(/^```mermaid\s*/i, '').replace(/```\s*$/, '').trim();
        if (!clean) return null;

        const id = "mermaid-export-" + (++mermaidRenderCounter) + "-" + Date.now();
        const { svg } = await mermaid.render(id, clean);
        if (!svg) return null;

        return await svgStringToPngDataUrl(svg);
    } catch (e) {
        console.error("renderMermaidToPngDataUrl error:", e);
        return null;
    }
}

function convertMermaidToPng() {
    const svgs = document.querySelectorAll(".mermaid svg");
    svgs.forEach(async (svg) => {
        if (svg.dataset.pngConverted) return;
        
        const bbox = svg.getBoundingClientRect();
        if (bbox.width === 0 && bbox.height === 0 && !svg.getAttribute("viewBox")) {
            return;
        }
        
        svg.dataset.pngConverted = "true";
        try {
            const svgString = new XMLSerializer().serializeToString(svg);
            const pngDataUrl = await svgStringToPngDataUrl(svgString, bbox.width, bbox.height);
            if (pngDataUrl) {
                svg.dataset.pngUrl = pngDataUrl;
            }
        } catch (e) {
            console.error("Error in convertMermaidToPng:", e);
        }
    });
}

async function prepareHtmlForClipboard(rawMarkdownOrHtml, elementId = null) {
    let html = "";
    
    // If elementId is provided and exists in the current DOM
    if (elementId) {
        const el = document.getElementById(elementId);
        if (el) {
            const clone = el.cloneNode(true);
            const originalDivs = el.querySelectorAll(".mermaid");
            const cloneDivs = clone.querySelectorAll(".mermaid");
            
            for (let i = 0; i < cloneDivs.length; i++) {
                const origDiv = originalDivs[i];
                const cloneDiv = cloneDivs[i];
                const svg = origDiv?.querySelector("svg");
                
                let pngUrl = svg?.dataset?.pngUrl;
                if (!pngUrl && svg) {
                    const svgString = new XMLSerializer().serializeToString(svg);
                    pngUrl = await svgStringToPngDataUrl(svgString);
                }
                if (!pngUrl) {
                    const code = origDiv?.dataset?.code ? decodeURIComponent(origDiv.dataset.code) : (origDiv?.textContent || "");
                    pngUrl = await renderMermaidToPngDataUrl(code);
                }
                
                if (pngUrl) {
                    const img = document.createElement("img");
                    img.src = pngUrl;
                    img.style.maxWidth = "100%";
                    img.style.border = "1px solid #e4e4e7";
                    img.style.borderRadius = "8px";
                    img.style.display = "block";
                    img.style.margin = "16px auto";
                    
                    const wrapper = document.createElement("div");
                    wrapper.style.textAlign = "center";
                    wrapper.style.margin = "16px 0";
                    wrapper.appendChild(img);
                    
                    cloneDiv.parentNode.replaceChild(wrapper, cloneDiv);
                }
            }
            
            html = clone.innerHTML;
        }
    }
    
    if (!html) {
        // Parse markdown directly
        html = marked.parse(rawMarkdownOrHtml || "");
    }
    
    // Process any remaining mermaid code blocks in html:
    // 1. <pre><code class="language-mermaid">...</code></pre>
    // 2. <div class="mermaid">...</div>
    const mermaidCodeRegex = /<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/gi;
    let match;
    const replacements = [];
    while ((match = mermaidCodeRegex.exec(html)) !== null) {
        replacements.push({ target: match[0], code: match[1] });
    }
    
    const divMermaidRegex = /<div class="mermaid"[^>]*>([\s\S]*?)<\/div>/gi;
    while ((match = divMermaidRegex.exec(html)) !== null) {
        replacements.push({ target: match[0], code: match[1] });
    }
    
    for (const item of replacements) {
        const pngUrl = await renderMermaidToPngDataUrl(item.code);
        if (pngUrl) {
            const imgHtml = `<div style="text-align: center; margin: 16px 0;"><img src="${pngUrl}" style="max-width: 100%; border: 1px solid #e4e4e7; border-radius: 8px; display: inline-block;" alt="Mermaid Diagram"></div>`;
            html = html.replace(item.target, imgHtml);
        }
    }
    
    return html;
}

function stripMarkdown(text) {
    return text
        .replace(/^###+\s*/gm, "")   // ### headings
        .replace(/^##\s*/gm, "")     // ## headings
        .replace(/^#\s*/gm, "")      // # headings
        .replace(/\*\*(.+?)\*\*/g, "$1")  // **bold**
        .replace(/\*(.+?)\*/g, "$1")      // *italic*
        .replace(/`(.+?)`/g, "$1")        // `code`
        .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")  // [text](url)
        .replace(/^[\-\*]\s+/gm, "• ")    // list markers
        .replace(/^\d+\.\s+/gm, (m) => m) // keep numbered lists
        .trim();
}

function _copyFallback(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
        const ok = document.execCommand("copy");
        showToast(ok ? "Copied!" : "Copy failed — select manually", ok ? "success" : "danger");
    } catch {
        showToast("Copy failed — select manually", "danger");
    }
    document.body.removeChild(ta);
}

async function _clipboardWrite(htmlContent, plainText, successMsg = "Copied!") {
    if (navigator.clipboard && navigator.clipboard.write) {
        try {
            const cleanHtml = `<!DOCTYPE html><html><body>${htmlContent}</body></html>`;
            await navigator.clipboard.write([
                new ClipboardItem({
                    "text/html": new Blob([cleanHtml], { type: "text/html" }),
                    "text/plain": new Blob([plainText], { type: "text/plain" }),
                }),
            ]);
            showToast(successMsg, "success");
            return;
        } catch (e) {
            console.warn("Clipboard write failed, falling back to writeText:", e);
        }
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(plainText).then(
            () => showToast(successMsg, "success")
        ).catch(() => _copyFallback(plainText));
    } else {
        _copyFallback(plainText);
    }
}

async function copyJournal() {
    showToast("Menyiapkan naskah & diagram...", "info");
    const rawHtml = await prepareHtmlForClipboard(currentJournal, "journal-content");
    await _clipboardWrite(rawHtml, currentJournal.trim(), "Naskah jurnal berhasil disalin (diagram otomatis jadi gambar)!");
}

function copyPlainText() {
    const plainText = stripMarkdown(currentJournal);
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(plainText).then(() => {
            showToast("Plain text copied!");
        }).catch(() => _copyFallback(plainText));
    } else {
        _copyFallback(plainText);
    }
}

function downloadJournal() {
    // Raw markdown preserves ## structure
    const blob = new Blob([currentJournal.trim()], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `journal-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
}

async function regenerateJournal() {
    const mode = document.getElementById("mode").value;
    if (!confirm(`Regenerate ${mode} with the same settings?`)) return;
    await generateJournal();
}

function applyParagraphControls() {
    const container = document.getElementById("journal-content");
    const paragraphs = container.querySelectorAll("p");
    paragraphs.forEach((p, idx) => {
        if (p.closest(".para-wrapper")) return;
        const wrapper = document.createElement("div");
        wrapper.className = "para-wrapper";
        p.parentNode.insertBefore(wrapper, p);
        wrapper.appendChild(p);

        const text = p.textContent;
        const isLong = text.length > 300;

        if (isLong) {
            p.dataset.fullText = text;
            p.dataset.shortText = text.substring(0, 200) + "...";
            p.textContent = text.substring(0, 200) + "...";
        }

        const controls = document.createElement("div");
        controls.className = "para-controls";
        controls.innerHTML = `
            <button class="btn-para btn-para-expand" onclick="togglePara(this)" title="Expand/shorten paragraph">
                <i class="bi ${isLong ? 'bi-arrows-expand' : 'bi-arrows-collapse'}"></i>
            </button>
            <button class="btn-para btn-para-edit" onclick="editPara(this)" title="Edit paragraph">
                <i class="bi bi-pencil"></i>
            </button>
        `;
        wrapper.appendChild(controls);
        wrapper.dataset.expanded = isLong ? "false" : "true";
    });
}

function togglePara(btn) {
    const wrapper = btn.closest(".para-wrapper");
    const p = wrapper.querySelector("p");
    const expanded = wrapper.dataset.expanded === "true";
    if (expanded) {
        p.textContent = p.dataset.shortText || p.textContent.substring(0, 200) + "...";
        wrapper.dataset.expanded = "false";
        btn.innerHTML = '<i class="bi bi-arrows-expand"></i>';
    } else {
        p.textContent = p.dataset.fullText || p.textContent;
        wrapper.dataset.expanded = "true";
        btn.innerHTML = '<i class="bi bi-arrows-collapse"></i>';
    }
}

function editPara(btn) {
    const wrapper = btn.closest(".para-wrapper");
    const p = wrapper.querySelector("p");
    if (wrapper.dataset.editing === "true") {
        const textarea = wrapper.querySelector("textarea");
        p.textContent = textarea.value;
        p.style.display = "";
        textarea.remove();
        btn.innerHTML = '<i class="bi bi-pencil"></i>';
        wrapper.dataset.editing = "false";
        showToast("Paragraph updated!");
        return;
    }
    const textarea = document.createElement("textarea");
    textarea.className = "form-control para-edit-textarea";
    textarea.value = p.textContent;
    p.style.display = "none";
    p.parentNode.insertBefore(textarea, p.nextSibling);
    textarea.focus();
    btn.innerHTML = '<i class="bi bi-check-lg"></i>';
    wrapper.dataset.editing = "true";
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}


// ---- Template Management ----

async function loadTemplateList() {
    try {
        const resp = await fetch(`${API_BASE}/api/templates`);
        templates = await resp.json();
        populateTemplateSelect();
    } catch (e) {
        console.error("Failed to load templates:", e);
    }
}

const TEMPLATE_CATEGORIES = ["medical", "physics", "chemistry", "mathematics", "general"];
const CATEGORY_LABELS = {
    medical: "Medical",
    physics: "Physics",
    chemistry: "Chemistry",
    mathematics: "Mathematics",
    general: "General",
};
const CATEGORY_COLORS = {
    medical: "bg-danger",
    physics: "bg-primary",
    chemistry: "bg-success",
    mathematics: "bg-warning text-dark",
    general: "bg-secondary",
};

function populateTemplateSelect() {
    const sel = document.getElementById("template-select");
    const rsel = document.getElementById("restructure-template-select");
    const isel = document.getElementById("idea-template");
    const current = sel.value;
    sel.innerHTML = '<option value="">Default (no template)</option>';
    if (rsel) {
        rsel.innerHTML = '<option value="">Select a template...</option>';
    }
    if (isel) {
        isel.innerHTML = '<option value="">Default (IMRAD)</option>';
    }
    const grouped = {};
    templates.forEach((t) => {
        const cat = t.category || "general";
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(t);
    });
    TEMPLATE_CATEGORIES.forEach((cat) => {
        const items = grouped[cat];
        if (!items || items.length === 0) return;
        const og = document.createElement("optgroup");
        og.label = CATEGORY_LABELS[cat] || cat;
        items.forEach((t) => {
            const opt = document.createElement("option");
            opt.value = t.id;
            const label = t.name + (t.builtin ? "" : " (custom)");
            opt.textContent = label;
            if (t.type) opt.dataset.type = t.type;
            og.appendChild(opt);
        });
        sel.appendChild(og);
        if (rsel) {
            const rog = og.cloneNode(true);
            rsel.appendChild(rog);
        }
        if (isel) {
            const iog = og.cloneNode(true);
            isel.appendChild(iog);
        }
    });
    // restore selection
    const saved = localStorage.getItem("autojurnal-template-id");
    if (saved && [...sel.options].some((o) => o.value === saved)) {
        sel.value = saved;
    } else if (current && [...sel.options].some((o) => o.value === current)) {
        sel.value = current;
    }
}

function openTemplateModal() {
    renderTemplateList();
    const modal = new bootstrap.Modal(document.getElementById("templateModal"));
    modal.show();
}

async function renderTemplateList() {
    const container = document.getElementById("template-list");
    if (templates.length === 0) {
        container.innerHTML = '<div class="text-muted text-center py-3">No templates available.</div>';
        return;
    }
    const grouped = {};
    templates.forEach((t) => {
        const cat = t.category || "general";
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(t);
    });
    container.innerHTML = TEMPLATE_CATEGORIES
        .filter((cat) => grouped[cat])
        .map((cat) => {
            const items = grouped[cat]
                .map(
                    (t) => `
            <div class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                <div>
                    <strong>${escapeHtml(t.name)}</strong>
                    <span class="badge ${CATEGORY_COLORS[cat] || "bg-secondary"} ms-2">${CATEGORY_LABELS[cat] || cat}</span>
                    <span class="badge ${t.builtin ? "bg-secondary" : "bg-primary"} ms-1">${t.builtin ? "built-in" : "custom"}</span>
                    <span class="badge bg-info ms-1">${t.type || "journal"}</span>
                    <div class="text-muted small mt-1">
                        ${t.sections ? t.sections.length + " sections" : ""}
                        ${t.chapter_subsections ? t.chapter_subsections.length + " chapter subsections" : ""}
                        ${t.constraints ? "· has constraints" : ""}
                    </div>
                </div>
                <div class="d-flex gap-1">
                    <button class="btn btn-sm btn-outline-info" onclick="previewTemplate('${t.id}')" title="Preview">
                        <i class="bi bi-eye"></i>
                    </button>
                    ${t.builtin ? "" : `<button class="btn btn-sm btn-outline-danger" onclick="deleteTemplate('${t.id}')" title="Delete">
                        <i class="bi bi-trash"></i>
                    </button>`}
                </div>
            </div>
        `
                )
                .join("");
            return `<h6 class="mt-3 mb-2 text-uppercase text-muted small">${CATEGORY_LABELS[cat] || cat}</h6>${items}`;
        })
        .join("");
}

async function previewTemplate(id) {
    const t = templates.find((x) => x.id === id);
    if (!t) return;
    let info = `Name: ${t.name}\nType: ${t.type || "journal"}\n\n`;
    if (t.sections) {
        info += "Sections:\n";
        t.sections.forEach((s, i) => {
            info += `  ${i + 1}. ${s.heading_id}${s.heading_en ? " / " + s.heading_en : ""}\n`;
        });
    }
    if (t.chapter_subsections) {
        info += "Chapter Subsections:\n";
        t.chapter_subsections.forEach((s, i) => {
            info += `  ${i + 1}. ${s.heading_id}${s.heading_en ? " / " + s.heading_en : ""}\n`;
        });
    }
    if (t.constraints) {
        info += "\nConstraints:\n";
        for (const [k, v] of Object.entries(t.constraints)) {
            if (v) info += `  ${k}: ${v}\n`;
        }
    }
    alert(info);
}

async function deleteTemplate(id) {
    if (!confirm(`Delete template "${templates.find((t) => t.id === id)?.name}"?`)) return;
    try {
        const resp = await fetch(`${API_BASE}/api/templates/${id}`, { method: "DELETE" });
        if (!resp.ok) throw new Error(await resp.text());
        templates = templates.filter((t) => t.id !== id);
        renderTemplateList();
        populateTemplateSelect();
        showToast("Template deleted");
    } catch (e) {
        alert("Failed to delete: " + e.message);
    }
}

async function uploadAndParseTemplate() {
    const input = document.getElementById("template-upload");
    const file = input.files?.[0];
    if (!file) {
        alert("Please select a file first.");
        return;
    }

    const loading = document.getElementById("template-parse-loading");
    const loadingText = document.getElementById("template-parse-loading-text");
    const resultDiv = document.getElementById("template-parse-result");
    resultDiv.style.display = "none";
    loading.style.display = "block";
    loadingText.textContent = "Parsing guidelines with AI...";
    parsedTemplate = null;

    try {
        const formData = new FormData();
        formData.append("file", file);
        const resp = await fetch(`${API_BASE}/api/templates/parse`, {
            method: "POST",
            body: formData,
        });
        if (!resp.ok) {
            const err = await resp.text();
            throw new Error(err);
        }
        parsedTemplate = await resp.json();
        loading.style.display = "none";
        const info = document.getElementById("template-parse-info");
        const name = parsedTemplate.name || "Untitled Template";
        const sections = parsedTemplate.sections?.length || 0;
        const subs = parsedTemplate.chapter_subsections?.length || 0;
        info.textContent = `Detected: "${name}" — ${sections} sections${subs ? `, ${subs} chapter subsections` : ""}`;
        resultDiv.style.display = "block";
        showToast("Template parsed successfully. Review and save.");
    } catch (e) {
        loading.style.display = "none";
        alert("Parse failed: " + e.message);
    }
}

async function saveParsedTemplate() {
    if (!parsedTemplate) return;
    const name = parsedTemplate.name || prompt("Template name:") || "Untitled";
    parsedTemplate.name = name;
    try {
        const resp = await fetch(`${API_BASE}/api/templates`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(parsedTemplate),
        });
        if (!resp.ok) throw new Error(await resp.text());
        const saved = await resp.json();
        templates.push(saved);
        parsedTemplate = null;
        document.getElementById("template-parse-result").style.display = "none";
        document.getElementById("template-upload").value = "";
        renderTemplateList();
        populateTemplateSelect();
        // Select the newly saved template
        document.getElementById("template-select").value = saved.id;
        saveSettings();
        showToast("Template saved!");
    } catch (e) {
        alert("Failed to save: " + e.message);
    }
}


// ---- Tab System ----

function showTab(tab) {
    document.getElementById("tab-generate").style.display = tab === "generate" ? "" : "none";
    document.getElementById("tab-restructure").style.display = tab === "restructure" ? "" : "none";
    document.getElementById("tab-review").style.display = tab === "review" ? "" : "none";
    document.getElementById("tab-translate").style.display = tab === "translate" ? "" : "none";
    document.getElementById("tab-idea").style.display = tab === "idea" ? "" : "none";

    document.getElementById("tab-generate-btn").classList.toggle("active", tab === "generate");
    document.getElementById("tab-restructure-btn").classList.toggle("active", tab === "restructure");
    document.getElementById("tab-review-btn").classList.toggle("active", tab === "review");
    document.getElementById("tab-translate-btn").classList.toggle("active", tab === "translate");
    document.getElementById("tab-idea-btn").classList.toggle("active", tab === "idea");

    document.getElementById("tab-generate-btn").classList.toggle("btn-outline-primary", tab !== "generate");
    document.getElementById("tab-restructure-btn").classList.toggle("btn-outline-primary", tab !== "restructure");
    document.getElementById("tab-review-btn").classList.toggle("btn-outline-primary", tab !== "review");
    document.getElementById("tab-translate-btn").classList.toggle("btn-outline-primary", tab !== "translate");
    document.getElementById("tab-idea-btn").classList.toggle("btn-outline-primary", tab !== "idea");
}


// ---- Restructure ----

let restructureSourceText = "";

function parseRestructureSource() {
    const fileInput = document.getElementById("restructure-file");
    const linkInput = document.getElementById("restructure-link").value.trim();

    if (!fileInput.files?.length && !linkInput) {
        alert("Upload a file or paste a Google Drive/Docs link.");
        return;
    }

    showLoading();
    updateLoading("Parsing source document...", "Extracting structure...");

    let url = `${API_BASE}/api/restructure/parse`;
    const opts = { method: "POST" };

    if (fileInput.files?.length) {
        const formData = new FormData();
        formData.append("file", fileInput.files[0]);
        opts.body = formData;
    } else {
        url += `?file_url=${encodeURIComponent(linkInput)}`;
    }

    fetch(url, opts)
        .then(async (resp) => {
            if (!resp.ok) throw new Error(await resp.text());
            return resp.json();
        })
        .then((data) => {
            hideLoading();
            restructureSourceText = data.source_text;
            renderDetectedSections(data.headings || data.sections);
            document.getElementById("restructure-detected-section").style.display = "";
            document.getElementById("restructure-btn").disabled = false;
            showToast(`Found ${data.headings?.length || data.sections?.length || 0} sections`);
        })
        .catch((err) => {
            updateLoading("Parse failed", err.message.substring(0, 300), true);
            setTimeout(hideLoading, 5000);
        });
}

function renderDetectedSections(headings) {
    const container = document.getElementById("restructure-detected-list");
    const count = document.getElementById("restructure-section-count");
    if (!headings || headings.length === 0) {
        container.innerHTML = '<div class="text-muted text-center py-3">No headings detected. Plain text will be used as-is.</div>';
        count.textContent = "0 sections";
        return;
    }
    count.textContent = `${headings.length} sections`;
    container.innerHTML = headings
        .map(
            (h, i) => `
        <div class="list-group-item list-group-item-action d-flex align-items-center gap-2">
            <span class="badge bg-secondary">${"#".repeat(h.level || 2)}</span>
            <span>${escapeHtml(h.heading || "Section " + (i + 1))}</span>
        </div>
    `
        )
        .join("");
}

async function restructureDoc() {
    const templateId = document.getElementById("restructure-template-select").value;
    const language = document.getElementById("restructure-language").value;

    if (!templateId) {
        showToast("Pilih template target terlebih dahulu.", "warning");
        return;
    }
    if (!restructureSourceText) {
        showToast("Parse dokumen sumber terlebih dahulu.", "warning");
        return;
    }

    const loadEl = document.getElementById("restructure-loading");
    const btnEl = document.getElementById("restructure-btn");
    if (loadEl) {
        loadEl.classList.remove("d-none");
        loadEl.classList.add("d-flex");
    }
    if (btnEl) btnEl.disabled = true;

    const provider = document.getElementById("provider").value;
    const providerModel =
        document.getElementById("provider-model").value.trim() || null;
    const providerBaseUrl =
        document.getElementById("provider-base-url").value.trim() || null;
    const apiKey =
        document.getElementById("llm-api-key").value.trim() || null;
    const hasData = document.getElementById("has-data").checked;
    const userData = document.getElementById("user-data").value.trim() || null;

    try {
        const resp = await fetch(`${API_BASE}/api/restructure`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                source_text: restructureSourceText,
                template_id: templateId,
                language: language,
                provider,
                provider_model: providerModel,
                provider_base_url: providerBaseUrl,
                api_key: apiKey,
                has_data: hasData,
                user_data: userData,
            }),
        });

        if (!resp.ok) throw new Error(await resp.text());

        const data = await resp.json();
        if (loadEl) {
            loadEl.classList.add("d-none");
            loadEl.classList.remove("d-flex");
        }
        if (btnEl) btnEl.disabled = false;

        document.getElementById("restructure-result-section").style.display = "";
        const rcEl = document.getElementById("restructured-content");
        rcEl.innerHTML = renderMarkdown(data.restructured_text);
        rcEl.dataset.raw = data.restructured_text;

        if (data.token_usage) {
            const tu = data.token_usage;
            const el = document.getElementById("restructure-token-usage");
            if (el) {
                el.textContent = `Tokens (estimated) — Input: ${(tu.input_tokens || 0).toLocaleString()} · Output: ${(tu.output_tokens || 0).toLocaleString()}`;
                el.style.display = "block";
            }
        }

        document.getElementById("restructure-result-section").scrollIntoView({ behavior: "smooth" });
        showToast("Restrukturisasi dokumen berhasil!", "success");
    } catch (err) {
        if (loadEl) {
            loadEl.classList.add("d-none");
            loadEl.classList.remove("d-flex");
        }
        if (btnEl) btnEl.disabled = false;
        showToast("Restructure failed: " + err.message.substring(0, 300), "danger");
    }
}

async function copyRestructured() {
    const el = document.getElementById("restructured-content");
    const rawMarkdown = el.dataset.raw || el.textContent || "";
    showToast("Menyiapkan naskah & diagram...", "info");
    const rawHtml = await prepareHtmlForClipboard(rawMarkdown, "restructured-content");
    await _clipboardWrite(rawHtml, rawMarkdown.trim(), "Naskah berhasil disalin (diagram otomatis jadi gambar)!");
}

function downloadRestructured() {
    const el = document.getElementById("restructured-content");
    const text = el.dataset.raw || el.textContent || "";
    const blob = new Blob([text], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "restructured.md";
    a.click();
    URL.revokeObjectURL(a.href);
}

// ── Human Review ──────────────────────────────────────────

async function parseReviewedDocument() {
    const fileInput = document.getElementById("review-upload-input");
    const linkInput = document.getElementById("review-link-input").value.trim();
    const file = fileInput.files?.[0];

    if (!file && !linkInput) {
        showToast("Upload a .docx file or paste a Google Docs link.", "warning");
        return;
    }

    updateLoading("Parsing reviewed document...");
    showLoading();

    try {
        let url = `${API_BASE}/api/revise/parse`;
        let body;
        if (file) {
            const form = new FormData();
            form.append("file", file);
            if (linkInput) form.append("file_url", linkInput);
            body = form;
        } else {
            const form = new FormData();
            form.append("file", "");
            form.append("file_url", linkInput);
            body = form;
        }

        const resp = await fetch(url, { method: "POST", body });
        if (!resp.ok) throw new Error(await resp.text());

        const data = await resp.json();
        hideLoading();

        document.getElementById("review-document").value = data.source_text;
        document.getElementById("review-text").value = data.review_text;

        if (data.comment_count > 0) {
            showToast(`Extracted ${data.comment_count} comments from .docx`, "success");
        } else {
            showToast("Document loaded", "success");
        }
    } catch (err) {
        hideLoading();
        showToast("Parse failed: " + err.message.substring(0, 300), "danger");
    }
}

document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("review-upload-input").addEventListener("change", function (e) {
        const file = e.target.files[0];
        if (!file) return;
        const name = file.name.toLowerCase();
        if (name.endsWith(".docx") || name.endsWith(".DOCX")) {
            parseReviewedDocument();
        } else {
            const reader = new FileReader();
            reader.onload = function (ev) {
                document.getElementById("review-document").value = ev.target.result;
            };
            reader.readAsText(file);
        }
    });

    const sourcesInput = document.getElementById("idea-sources-input");
    if (sourcesInput) {
        sourcesInput.addEventListener("change", async function (e) {
            const files = e.target.files;
            if (!files.length) return;

            showToast(`Mengunggah & memproses ${files.length} file sumber manual...`, "info");

            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                const formData = new FormData();
                formData.append("file", file);

                try {
                    const resp = await fetch(`${API_BASE}/api/parse-file`, {
                        method: "POST",
                        body: formData
                    });
                    if (!resp.ok) throw new Error(await resp.text());
                    const data = await resp.json();

                    // Create manual paper object
                    const manualPaper = {
                        title: data.filename,
                        abstract: data.text,
                        authors: ["Manual Upload"],
                        year: new Date().getFullYear(),
                        doi: "manual-" + Math.random().toString(36).substr(2, 9),
                        openalex_url: "",
                        url: "",
                        pdf_url: "",
                        source: "manual",
                        cited_by_count: 0,
                        relevance_score: 1.0
                    };

                    ideaSearchPapers.unshift(manualPaper);
                    showToast(`File "${file.name}" berhasil ditambahkan sebagai sumber!`, "success");
                } catch (err) {
                    showToast(`Gagal memproses "${file.name}": ` + err.message, "danger");
                }
            }

            // Render table
            document.getElementById("idea-references-card").style.display = "";
            renderIdeaReferencesTable();
        });
    }
});

async function reviseWithReview() {
    const sourceText = document.getElementById("review-document").value.trim();
    const reviewText = document.getElementById("review-text").value.trim();
    const language = document.getElementById("review-language").value;
    if (!sourceText) { showToast("Tempelkan teks dokumen asli terlebih dahulu.", "warning"); return; }
    if (!reviewText) { showToast("Tempelkan masukan reviewer terlebih dahulu.", "warning"); return; }

    const loadEl = document.getElementById("review-loading");
    const btnEl = document.getElementById("revise-btn");
    if (loadEl) {
        loadEl.classList.remove("d-none");
        loadEl.classList.add("d-flex");
    }
    if (btnEl) btnEl.disabled = true;
    document.getElementById("review-result-section").style.display = "none";

    const provider = document.getElementById("provider").value;
    const providerModel = document.getElementById("provider-model").value;
    const providerBaseUrl = document.getElementById("provider-base-url").value;
    const apiKey = document.getElementById("llm-api-key").value;

    try {
        const resp = await fetch(`${API_BASE}/api/revise`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                source_text: sourceText,
                review_text: reviewText,
                language,
                provider,
                provider_model: providerModel || null,
                provider_base_url: providerBaseUrl || null,
                api_key: apiKey || null,
            }),
        });

        if (!resp.ok) throw new Error(await resp.text());

        const data = await resp.json();
        if (loadEl) {
            loadEl.classList.add("d-none");
            loadEl.classList.remove("d-flex");
        }
        if (btnEl) btnEl.disabled = false;

        document.getElementById("review-result-section").style.display = "";
        const rcEl = document.getElementById("review-content");
        rcEl.innerHTML = renderMarkdown(data.revised_text);
        rcEl.dataset.raw = data.revised_text;

        document.getElementById("review-result-section").scrollIntoView({ behavior: "smooth" });
        showToast("Revisi dokumen selesai!", "success");
    } catch (err) {
        if (loadEl) {
            loadEl.classList.add("d-none");
            loadEl.classList.remove("d-flex");
        }
        if (btnEl) btnEl.disabled = false;
        showToast("Revise failed: " + err.message.substring(0, 300), "danger");
    }
}

async function copyReviewResult() {
    const el = document.getElementById("review-content");
    const rawMarkdown = el.dataset.raw || el.textContent || "";
    showToast("Menyiapkan naskah & diagram...", "info");
    const rawHtml = await prepareHtmlForClipboard(rawMarkdown, "review-content");
    await _clipboardWrite(rawHtml, rawMarkdown.trim(), "Naskah hasil revisi berhasil disalin!");
}

function downloadReviewResult() {
    const el = document.getElementById("review-content");
    const text = el.dataset.raw || el.textContent || "";
    const blob = new Blob([text], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "revised-document.md";
    a.click();
    URL.revokeObjectURL(a.href);
}


// ---- Translate ----

async function translateDoc() {
    const sourceText = document.getElementById("translate-source-text").value.trim();
    const srcLang = document.getElementById("translate-source-lang").value;
    const tgtLang = document.getElementById("translate-target-lang").value;
    if (!sourceText) { showToast("Tempelkan teks dokumen yang ingin diterjemahkan.", "warning"); return; }
    if (srcLang === tgtLang) { showToast("Bahasa sumber dan target harus berbeda.", "warning"); return; }

    const loadEl = document.getElementById("translate-loading");
    const btnEl = document.getElementById("translate-btn");
    if (loadEl) {
        loadEl.classList.remove("d-none");
        loadEl.classList.add("d-flex");
    }
    if (btnEl) btnEl.disabled = true;
    document.getElementById("translate-result-section").style.display = "none";

    const provider = document.getElementById("provider").value;
    const providerModel = document.getElementById("provider-model").value;
    const providerBaseUrl = document.getElementById("provider-base-url").value;
    const apiKey = document.getElementById("llm-api-key").value;

    try {
        const resp = await fetch(`${API_BASE}/api/translate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                source_text: sourceText,
                source_language: srcLang,
                target_language: tgtLang,
                provider,
                provider_model: providerModel || null,
                provider_base_url: providerBaseUrl || null,
                api_key: apiKey || null,
            }),
        });

        if (!resp.ok) throw new Error(await resp.text());

        const data = await resp.json();
        if (loadEl) {
            loadEl.classList.add("d-none");
            loadEl.classList.remove("d-flex");
        }
        if (btnEl) btnEl.disabled = false;

        document.getElementById("translate-result-section").style.display = "";
        const outEl = document.getElementById("translate-output");
        outEl.innerHTML = renderMarkdown(data.translated_text);
        outEl.dataset.raw = data.translated_text;

        const badge = document.getElementById("translate-token-badge");
        if (data.token_usage) {
            badge.textContent = `in:${data.token_usage.input_tokens} out:${data.token_usage.output_tokens}`;
        } else {
            badge.textContent = "";
        }

        document.getElementById("translate-result-section").scrollIntoView({ behavior: "smooth" });
        showToast("Penerjemahan dokumen selesai!", "success");
    } catch (err) {
        if (loadEl) {
            loadEl.classList.add("d-none");
            loadEl.classList.remove("d-flex");
        }
        if (btnEl) btnEl.disabled = false;
        showToast("Translate failed: " + err.message.substring(0, 300), "danger");
    }
}

async function copyTranslated() {
    const el = document.getElementById("translate-output");
    const rawMarkdown = el.dataset.raw || el.textContent || "";
    showToast("Menyiapkan naskah...", "info");
    const rawHtml = await prepareHtmlForClipboard(rawMarkdown, "translate-output");
    await _clipboardWrite(rawHtml, rawMarkdown.trim(), "Hasil terjemahan berhasil disalin!");
}

function downloadTranslated() {
    const el = document.getElementById("translate-output");
    const text = el.dataset.raw || el.textContent || "";
    a.download = "translated-document.md";
    a.click();
    URL.revokeObjectURL(a.href);
}


// ---- Idea to Journal Mode ----

function toggleIdeaTextbookOptions() {
    const mode = document.getElementById("idea-mode").value;
    const isTextbook = mode === "textbook";
    document.getElementById("idea-target-length-group").classList.toggle("d-none", isTextbook);
    document.getElementById("idea-num-chapters-group").classList.toggle("d-none", !isTextbook);
}

let ideaExtractedText = "";
let ideaSearchPapers = [];

async function analyzeIdea() {
    const fileInput = document.getElementById("idea-file-input");
    const linkInput = document.getElementById("idea-link-input").value.trim();

    if (!fileInput.files?.length && !linkInput) {
        alert("Pilih file draf ide atau tempel link dokumen Google Drive.");
        return;
    }

    showLoading();
    updateLoading("Menganalisis draf ide...", "Mengekstrak konsep dasar...");

    try {
        const url = `${API_BASE}/api/generate/idea/parse`;
        let body;
        
        // Grab shared settings inputs from the UI
        const provider = document.getElementById("provider").value;
        const providerModel = document.getElementById("provider-model").value.trim() || null;
        const providerBaseUrl = document.getElementById("provider-base-url").value.trim() || null;
        const apiKey = document.getElementById("llm-api-key").value.trim() || null;

        if (fileInput.files?.length) {
            const form = new FormData();
            form.append("file", fileInput.files[0]);
            form.append("language", document.getElementById("idea-language").value);
            form.append("provider", provider);
            if (apiKey) form.append("api_key", apiKey);
            if (providerBaseUrl) form.append("provider_base_url", providerBaseUrl);
            if (providerModel) form.append("provider_model", providerModel);
            body = form;
        } else {
            const form = new FormData();
            form.append("file_url", linkInput);
            form.append("language", document.getElementById("idea-language").value);
            form.append("provider", provider);
            if (apiKey) form.append("api_key", apiKey);
            if (providerBaseUrl) form.append("provider_base_url", providerBaseUrl);
            if (providerModel) form.append("provider_model", providerModel);
            body = form;
        }

        const resp = await fetch(url, { method: "POST", body });
        if (!resp.ok) throw new Error(await resp.text());

        const data = await resp.json();
        hideLoading();

        // Populate fields
        document.getElementById("idea-extracted-text").value = data.draft_idea;
        document.getElementById("idea-search-query").value = data.search_query;
        if (document.getElementById("idea-search-topic")) {
            document.getElementById("idea-search-topic").value = data.search_query;
        }
        
        // Show panel
        document.getElementById("idea-analysis-panel").style.display = "";
        showToast("Draf berhasil dianalisis!", "success");

        // Automatically trigger OpenAlex references search with configured filters
        searchIdeaReferences(true);
    } catch (err) {
        hideLoading();
        showToast("Gagal menganalisis draf: " + err.message, "danger");
    }
}

async function searchDirectIdeaPapers() {
    const topicInput = document.getElementById("idea-search-topic");
    const queryInput = document.getElementById("idea-search-query");
    let query = (topicInput?.value || queryInput?.value || "").trim();

    if (!query) {
        const fileInput = document.getElementById("idea-file-input");
        if (fileInput?.files?.length) {
            query = fileInput.files[0].name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
            if (topicInput) topicInput.value = query;
        }
    }

    if (!query) {
        alert("Silakan masukkan topik / kata kunci pencarian terlebih dahulu.");
        topicInput?.focus();
        return;
    }

    if (queryInput) queryInput.value = query;
    if (topicInput) topicInput.value = query;

    // Ensure extracted text has basic topic context if user searched directly without draft analysis
    const extractedEl = document.getElementById("idea-extracted-text");
    if (extractedEl && !extractedEl.value.trim()) {
        extractedEl.value = `Topik Penelitian: ${query}\n(Kajian dan penulisan komprehensif berdasarkan referensi ilmiah terkini)`;
    }

    // Show panel
    document.getElementById("idea-analysis-panel").style.display = "";
    await searchIdeaReferences(true);
}

function renderIdeaReferencesTable() {
    const tableBody = document.getElementById("idea-ref-table").querySelector("tbody");
    document.getElementById("idea-ref-count").textContent = `${ideaSearchPapers.length} ditemukan`;

    if (ideaSearchPapers.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4"><i class="bi bi-info-circle me-1"></i>Tidak ada referensi yang ditemukan. Coba gunakan kata kunci lain atau perpanjang rentang tahun (Year Range).</td></tr>';
        return;
    }

    tableBody.innerHTML = "";
    ideaSearchPapers.forEach((paper, idx) => {
        const tr = document.createElement("tr");

        // Checkbox
        const tdCheck = document.createElement("td");
        tdCheck.className = "text-center align-top pt-3";
        tdCheck.innerHTML = `<input type="checkbox" class="form-check-input idea-paper-checkbox" data-idx="${idx}" checked>`;
        tr.appendChild(tdCheck);

        // Title + Metadata + Collapsible Abstract
        const tdTitle = document.createElement("td");
        tdTitle.className = "align-top py-2";
        
        const firstAuthor = paper.authors?.length ? paper.authors[0] : "Unknown";
        const authorStr = paper.authors?.length > 1 ? `${firstAuthor} et al.` : firstAuthor;
        const yearStr = paper.year ? `(${paper.year})` : "";
        const sourceStr = paper.source ? ` - ${escapeHtml(paper.source)}` : "";
        const doiStr = paper.doi ? `<a href="https://doi.org/${encodeURIComponent(paper.doi)}" target="_blank" class="doi-badge ms-1" title="Open DOI">DOI:${escapeHtml(paper.doi)}</a>` : "";
        const oaStr = paper.openalex_url ? `<a href="${escapeHtml(paper.openalex_url)}" target="_blank" class="oa-link ms-1" title="OpenAlex Link"><i class="bi bi-box-arrow-up-right"></i></a>` : "";
        
        let abstractHtml = "";
        if (paper.abstract) {
            const shortAbs = paper.abstract.length > 250 ? escapeHtml(paper.abstract.substring(0, 250)) + "..." : escapeHtml(paper.abstract);
            const fullAbs = escapeHtml(paper.abstract);
            abstractHtml = `
                <div class="paper-abstract mt-1 text-muted small" id="idea-abs-${idx}" style="cursor: pointer;" onclick="toggleIdeaAbstract(${idx})" title="Klik untuk lihat abstrak lengkap">
                    <span class="idea-abs-short">${shortAbs}</span>
                    <span class="idea-abs-full d-none">${fullAbs}</span>
                    ${paper.abstract.length > 250 ? '<span class="text-primary ms-1 fw-semibold idea-abs-toggle">[+ more]</span>' : ''}
                </div>`;
        } else {
            abstractHtml = '<div class="text-muted small fst-italic mt-1">No abstract available</div>';
        }

        tdTitle.innerHTML = `
            <div class="fw-bold text-primary mb-1">${escapeHtml(paper.title)}</div>
            <div class="paper-meta small text-muted mb-1">
                ${authorStr} ${yearStr}${sourceStr} ${doiStr} ${oaStr}
            </div>
            ${abstractHtml}
        `;
        tr.appendChild(tdTitle);

        // Authors & Year column
        const tdAuthors = document.createElement("td");
        tdAuthors.className = "align-top small py-2";
        tdAuthors.textContent = `${authorStr} ${yearStr}`;
        tr.appendChild(tdAuthors);

        // Citations
        const tdCites = document.createElement("td");
        tdCites.className = "align-top small text-center py-2";
        tdCites.innerHTML = `<span class="badge bg-secondary">${paper.cited_by_count || 0}</span>`;
        tr.appendChild(tdCites);

        // Actions
        const tdActions = document.createElement("td");
        tdActions.className = "align-top text-center py-2";
        if (paper.source === "manual") {
            tdActions.innerHTML = '<span class="badge bg-success"><i class="bi bi-file-earmark-text me-1"></i>Manual</span>';
        } else if (paper.pdf_url) {
            tdActions.innerHTML = `<a href="${paper.pdf_url}" target="_blank" class="btn btn-sm btn-outline-primary py-0"><i class="bi bi-file-earmark-pdf"></i> PDF</a>`;
        } else {
            tdActions.innerHTML = '<span class="text-muted small">No PDF</span>';
        }
        tr.appendChild(tdActions);

        tableBody.appendChild(tr);
    });
}

function toggleIdeaAbstract(idx) {
    const el = document.getElementById(`idea-abs-${idx}`);
    if (!el) return;
    const shortSpan = el.querySelector(".idea-abs-short");
    const fullSpan = el.querySelector(".idea-abs-full");
    const toggleSpan = el.querySelector(".idea-abs-toggle");
    if (shortSpan && fullSpan) {
        const isCollapsed = fullSpan.classList.contains("d-none");
        if (isCollapsed) {
            shortSpan.classList.add("d-none");
            fullSpan.classList.remove("d-none");
            if (toggleSpan) toggleSpan.textContent = "[- less]";
        } else {
            shortSpan.classList.remove("d-none");
            fullSpan.classList.add("d-none");
            if (toggleSpan) toggleSpan.textContent = "[+ more]";
        }
    }
}

async function searchIdeaReferences(scroll = false) {
    const queryEl = document.getElementById("idea-search-query");
    const topicEl = document.getElementById("idea-search-topic");
    let query = (queryEl?.value || topicEl?.value || "").trim();
    
    if (!query) {
        alert("Query pencarian tidak boleh kosong.");
        return;
    }

    if (queryEl) queryEl.value = query;
    if (topicEl) topicEl.value = query;

    const refsCard = document.getElementById("idea-references-card");
    const tableBody = document.getElementById("idea-ref-table").querySelector("tbody");
    tableBody.innerHTML = '<tr><td colspan="5" class="text-center py-4"><div class="spinner-border text-primary spinner-border-sm me-2"></div>Mencari referensi OpenAlex...</td></tr>';
    refsCard.style.display = "";

    if (scroll) {
        refsCard.scrollIntoView({ behavior: "smooth" });
    }

    try {
        const yearRange = parseInt(document.getElementById("idea-year-range")?.value || document.getElementById("year-range")?.value || "3") || 0;
        const maxPapers = parseInt(document.getElementById("idea-max-papers")?.value || document.getElementById("max-papers")?.value || "15") || 15;
        const openalexApiKey = document.getElementById("openalex-api-key")?.value?.trim() || null;
        const language = document.getElementById("idea-language")?.value || "id";

        const body = {
            theme: query,
            max_papers: maxPapers,
            language: language,
            openalex_api_key: openalexApiKey,
        };

        const currentYear = new Date().getFullYear();
        if (yearRange > 0) {
            body.from_year = currentYear - yearRange;
        }

        const resp = await fetch(`${API_BASE}/api/search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });

        if (!resp.ok) throw new Error(await resp.text());

        const data = await resp.json();
        const searchPapers = data.papers || [];
        const manualPapers = ideaSearchPapers.filter(p => p.source === "manual");
        ideaSearchPapers = [...manualPapers, ...searchPapers];

        renderIdeaReferencesTable();
    } catch (err) {
        tableBody.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-4">Gagal memuat referensi: ${err.message}</td></tr>`;
    }
}

function toggleAllIdeaRefs() {
    const selectAllChk = document.getElementById("idea-select-all");
    const checkboxes = document.querySelectorAll(".idea-paper-checkbox");
    const allAreChecked = Array.from(checkboxes).every(cb => cb.checked);
    const newCheckedState = allAreChecked ? false : true;
    
    checkboxes.forEach((cb) => {
        cb.checked = newCheckedState;
    });
    if (selectAllChk) selectAllChk.checked = newCheckedState;
}

async function generateFromIdea() {
    const ideaText = document.getElementById("idea-extracted-text").value.trim();
    if (!ideaText) {
        alert("Rangkuman ide utama tidak boleh kosong.");
        return;
    }

    if (ideaCollectedPapers.length === 0) {
        alert("Koleksi referensi ide kosong. Silakan pilih referensi dari hasil pencarian dan klik 'Masukkan ke Koleksi Ide' terlebih dahulu.");
        return;
    }

    const outputPanel = document.getElementById("idea-output-panel");
    const logsEl = document.getElementById("idea-generation-logs");
    const editor = document.getElementById("idea-output-editor");
    const spinner = document.getElementById("idea-generation-spinner");

    logsEl.innerHTML = "";
    editor.value = "";
    outputPanel.style.display = "";
    spinner.style.display = "";

    logsEl.scrollIntoView({ behavior: "smooth" });

    // Build payload
    const provider = document.getElementById("provider").value;
    const providerModel = document.getElementById("provider-model").value.trim() || null;
    const providerBaseUrl = document.getElementById("provider-base-url").value.trim() || null;
    const apiKey = document.getElementById("llm-api-key").value.trim() || null;

    const payload = {
        theme: document.getElementById("idea-search-query").value.trim(),
        papers: ideaCollectedPapers,
        language: document.getElementById("idea-language").value,
        provider: provider,
        provider_model: providerModel,
        api_key: apiKey,
        provider_base_url: providerBaseUrl,
        target_length: document.getElementById("idea-target-length").value,
        multi_agent: document.getElementById("idea-multi-agent").checked,
        mode: document.getElementById("idea-mode").value,
        num_chapters: parseInt(document.getElementById("idea-num-chapters").value),
        template_id: document.getElementById("idea-template").value || null,
        do_research: document.getElementById("idea-do-research").checked,
        library: document.getElementById("idea-library").checked,
        draft_idea: ideaText,
        paradigm: document.getElementById("idea-paradigm").value,
        analysis_method: document.getElementById("idea-analysis-method").value,
    };

    try {
        const resp = await fetch(`${API_BASE}/api/generate/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!resp.ok) throw new Error(await resp.text());

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop(); // keep partial line

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const clean = line.replace("data: ", "").trim();
                    if (!clean) continue;

                    try {
                        const entry = JSON.parse(clean);

                        if (entry.type === "log") {
                            const p = document.createElement("p");
                            p.className = "mb-1";
                            const timestamp = new Date().toLocaleTimeString();
                            p.innerHTML = `<span class="text-secondary">[${timestamp}]</span> <strong class="text-primary">${entry.agent}:</strong> ${entry.message}`;
                            logsEl.appendChild(p);
                            logsEl.scrollTop = logsEl.scrollHeight;
                        } else if (entry.type === "result") {
                            editor.value = entry.journal;
                            spinner.style.display = "none";
                            showToast("Penulisan naskah selesai!", "success");

                            // Auto-save generated draft
                            saveDraft({
                                title: document.getElementById("idea-search-topic")?.value.trim() || document.getElementById("idea-search-query")?.value.trim() || "Draf Ide",
                                content: entry.journal,
                                mode: `Ide ke Jurnal (${document.getElementById("idea-mode")?.value || "journal"})`,
                                language: document.getElementById("idea-language")?.value || "id",
                                inLibrary: document.getElementById("idea-library")?.checked || false,
                            }, false);

                            editor.scrollIntoView({ behavior: "smooth" });
                        } else if (entry.type === "error") {
                            const p = document.createElement("p");
                            p.className = "text-danger fw-bold mb-1";
                            p.textContent = `[Error] ${entry.message}`;
                            logsEl.appendChild(p);
                            spinner.style.display = "none";
                        }
                    } catch (e) {
                        // ignore heartbeat or parsing issues
                    }
                }
            }
        }
    } catch (err) {
        spinner.style.display = "none";
        const p = document.createElement("p");
        p.className = "text-danger fw-bold mb-1";
        p.textContent = `[Connection Error] ${err.message}`;
        logsEl.appendChild(p);
    }
}

async function copyIdeaResult() {
    const editor = document.getElementById("idea-output-editor");
    const rawMarkdown = editor.value.trim();
    if (!rawMarkdown) {
        showToast("Belum ada naskah yang di-generate", "warning");
        return;
    }
    showToast("Menyiapkan naskah & diagram...", "info");
    const rawHtml = await prepareHtmlForClipboard(rawMarkdown);
    await _clipboardWrite(rawHtml, rawMarkdown, "Naskah draf berhasil disalin (diagram otomatis jadi gambar)!");
}

function downloadIdeaResult() {
    const text = document.getElementById("idea-output-editor").value.trim();
    if (!text) return;
    const blob = new Blob([text], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "jurnal-dari-ide.md";
    a.click();
    URL.revokeObjectURL(a.href);
}

// ---- Idea Collection Helpers ----

function saveIdeaCollection() {
    try {
        localStorage.setItem("autojurnal-idea-collection", JSON.stringify(ideaCollectedPapers));
    } catch {}
}

function restoreIdeaCollection() {
    try {
        const raw = localStorage.getItem("autojurnal-idea-collection");
        if (raw) {
            ideaCollectedPapers = JSON.parse(raw);
            renderIdeaCollectedPapers();
        }
    } catch {}
}

function addSelectedToIdeaCollection() {
    console.log("addSelectedToIdeaCollection called");
    try {
        const checkboxes = document.querySelectorAll(".idea-paper-checkbox:checked");
        if (checkboxes.length === 0) {
            alert("Pilih setidaknya 1 referensi untuk dimasukkan ke koleksi.");
            return;
        }
        const selected = [];
        checkboxes.forEach((cb) => {
            const idx = parseInt(cb.dataset.idx);
            selected.push(ideaSearchPapers[idx]);
        });

        const existingKeys = new Set(
            ideaCollectedPapers.map(p => p.doi || p.openalex_url || p.title)
        );
        const newPapers = selected.filter(
            p => !existingKeys.has(p.doi || p.openalex_url || p.title)
        );

        if (newPapers.length === 0) {
            alert("Semua paper yang dipilih sudah ada di koleksi referensi ide.");
            return;
        }

        ideaCollectedPapers.push(...newPapers);
        renderIdeaCollectedPapers();
        saveIdeaCollection();
        alert(`${newPapers.length} paper berhasil ditambahkan ke koleksi referensi ide!`);

        // Uncheck checkboxes for visual feedback
        document.querySelectorAll(".idea-paper-checkbox").forEach(cb => cb.checked = false);
        const selectAllChk = document.getElementById("idea-select-all");
        if (selectAllChk) selectAllChk.checked = false;
    } catch (e) {
        console.error("addSelectedToIdeaCollection error:", e);
        alert("Error: " + e.message);
    }
}

function removeFromIdeaCollection(index) {
    ideaCollectedPapers.splice(index, 1);
    renderIdeaCollectedPapers();
    saveIdeaCollection();
}

function clearIdeaCollection() {
    if (ideaCollectedPapers.length === 0) return;
    if (confirm("Apakah Anda yakin ingin mengosongkan koleksi referensi ide?")) {
        ideaCollectedPapers = [];
        renderIdeaCollectedPapers();
        saveIdeaCollection();
        showToast("Koleksi referensi ide dikosongkan");
    }
}

function renderIdeaCollectedPapers() {
    console.log("renderIdeaCollectedPapers, count:", ideaCollectedPapers.length);
    const container = document.getElementById("idea-collection-list");
    const count = document.getElementById("idea-collection-count");
    const card = document.getElementById("idea-collection-card");
    const controlCard = document.getElementById("idea-gen-control-card");

    if (!container || !count || !card || !controlCard) return;

    count.textContent = ideaCollectedPapers.length;

    if (ideaCollectedPapers.length === 0) {
        card.style.display = "none";
        controlCard.style.display = "none";
        container.innerHTML = "";
        return;
    }

    card.style.display = "block";
    controlCard.style.display = "block";

    container.innerHTML = ideaCollectedPapers
        .map((p, i) => `
            <div class="paper-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1 me-3">
                        <div class="paper-title">${escapeHtml(p.title)}</div>
                        <div class="paper-meta">
                            ${(p.authors || []).slice(0, 3).join(", ")}${p.authors.length > 3 ? " et al." : ""}
                            ${p.year ? ` (${p.year})` : ""}
                            ${p.source ? ` - ${escapeHtml(p.source)}` : ""}
                            ${p.doi ? `<a href="https://doi.org/${encodeURIComponent(p.doi)}" target="_blank" class="doi-badge ms-1" title="Open DOI">DOI:${escapeHtml(p.doi)}</a>` : ""}
                        </div>
                    </div>
                    <button class="btn btn-sm btn-outline-danger" onclick="removeFromIdeaCollection(${i})" title="Hapus dari koleksi">
                        <i class="bi bi-x-lg"></i>
                    </button>
                </div>
            </div>
        `)
        .join("");
}

// ---- Drafts & AI Library Management ----

function getSavedDrafts() {
    try {
        const raw = localStorage.getItem("autojurnal-saved-drafts");
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
}

function saveDraftsArray(drafts) {
    try {
        localStorage.setItem("autojurnal-saved-drafts", JSON.stringify(drafts));
        updateDraftsBadge();
    } catch (e) {
        console.error("Failed to save drafts array:", e);
    }
}

function updateDraftsBadge() {
    const drafts = getSavedDrafts();
    const badge = document.getElementById("drafts-count-badge");
    if (badge) {
        badge.textContent = drafts.length;
    }
}

function extractTitleFromMarkdown(md, fallback = "Untitled Draft") {
    if (!md) return fallback;
    const match = md.match(/^#+\s+(.+)$/m);
    if (match && match[1]) {
        return match[1].replace(/[*_`]/g, "").trim();
    }
    return fallback;
}

function saveDraft(draftObj, showToastMsg = true) {
    if (!draftObj || !draftObj.content || !draftObj.content.trim()) return null;
    
    const drafts = getSavedDrafts();
    const title = draftObj.title || extractTitleFromMarkdown(draftObj.content, "Draft " + new Date().toLocaleDateString("id-ID"));
    
    // Check if duplicate existing draft by content or ID
    const existingIndex = drafts.findIndex(d => (draftObj.id && d.id === draftObj.id) || d.content.trim() === draftObj.content.trim());
    
    const nowStr = new Date().toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
    const wordsCount = draftObj.content.trim().split(/\s+/).length;
    
    const newRecord = {
        id: (existingIndex >= 0 ? drafts[existingIndex].id : null) || draftObj.id || "draft-" + Date.now() + "-" + Math.random().toString(36).substr(2, 6),
        title: title,
        content: draftObj.content,
        mode: draftObj.mode || "journal",
        language: draftObj.language || "id",
        createdAt: draftObj.createdAt || nowStr,
        wordsCount: wordsCount,
        inLibrary: draftObj.inLibrary || false,
        libraryWorkId: draftObj.libraryWorkId || null,
        paperTitles: draftObj.paperTitles || [],
    };
    
    if (existingIndex >= 0) {
        drafts[existingIndex] = { ...drafts[existingIndex], ...newRecord };
    } else {
        drafts.unshift(newRecord);
    }
    
    if (drafts.length > 100) drafts.pop();
    
    saveDraftsArray(drafts);
    
    if (showToastMsg) {
        showToast(`Draf "${title.substring(0, 35)}..." berhasil disimpan!`, "success");
    }
    
    return newRecord;
}

function saveCurrentJournalDraft() {
    if (!currentJournal || !currentJournal.trim()) {
        showToast("Belum ada jurnal yang di-generate untuk disimpan", "warning");
        return;
    }
    const themeInput = document.getElementById("paper-title")?.value.trim() || document.getElementById("theme")?.value.trim();
    const mode = document.getElementById("mode")?.value || "journal";
    const lang = document.getElementById("language")?.value || "en";
    
    saveDraft({
        title: themeInput || extractTitleFromMarkdown(currentJournal),
        content: currentJournal,
        mode: mode,
        language: lang,
    }, true);
}

function saveCurrentIdeaDraft() {
    const editor = document.getElementById("idea-output-editor");
    const content = editor?.value?.trim();
    if (!content) {
        showToast("Belum ada naskah yang di-generate untuk disimpan", "warning");
        return;
    }
    const themeInput = document.getElementById("idea-search-topic")?.value.trim() || document.getElementById("idea-search-query")?.value.trim();
    const mode = document.getElementById("idea-mode")?.value || "journal";
    const lang = document.getElementById("idea-language")?.value || "id";
    
    saveDraft({
        title: themeInput || extractTitleFromMarkdown(content),
        content: content,
        mode: `Ide ke Jurnal (${mode})`,
        language: lang,
    }, true);
}

async function addCurrentJournalToAiLibrary() {
    if (!currentJournal || !currentJournal.trim()) {
        showToast("Belum ada jurnal yang di-generate", "warning");
        return;
    }
    const theme = document.getElementById("paper-title")?.value.trim() || document.getElementById("theme")?.value.trim() || extractTitleFromMarkdown(currentJournal);
    const mode = document.getElementById("mode")?.value || "journal";
    const lang = document.getElementById("language")?.value || "en";
    const provider = document.getElementById("provider")?.value || "manual";
    const paperTitles = collectedPapers.map(p => p.title || "").filter(Boolean);
    
    try {
        const resp = await fetch(`${API_BASE}/api/works`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                theme: theme,
                content: currentJournal,
                language: lang,
                mode: mode,
                provider: provider,
                paper_titles: paperTitles,
            })
        });
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        
        saveDraft({
            title: theme,
            content: currentJournal,
            mode: mode,
            language: lang,
            inLibrary: true,
            libraryWorkId: data.work_id,
            paperTitles: paperTitles,
        }, false);
        
        showToast("Naskah berhasil didaftarkan ke Library AI! (AI akan otomatis mencegah plagiasi saat 'Librarian' aktif)", "success");
    } catch (e) {
        showToast("Gagal mendaftarkan ke Library AI: " + e.message, "danger");
    }
}

async function addCurrentIdeaToAiLibrary() {
    const editor = document.getElementById("idea-output-editor");
    const content = editor?.value?.trim();
    if (!content) {
        showToast("Belum ada naskah yang di-generate", "warning");
        return;
    }
    const theme = document.getElementById("idea-search-topic")?.value.trim() || document.getElementById("idea-search-query")?.value.trim() || extractTitleFromMarkdown(content);
    const mode = document.getElementById("idea-mode")?.value || "journal";
    const lang = document.getElementById("idea-language")?.value || "id";
    const provider = document.getElementById("provider")?.value || "manual";
    const paperTitles = ideaCollectedPapers.map(p => p.title || "").filter(Boolean);
    
    try {
        const resp = await fetch(`${API_BASE}/api/works`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                theme: theme,
                content: content,
                language: lang,
                mode: mode,
                provider: provider,
                paper_titles: paperTitles,
            })
        });
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        
        saveDraft({
            title: theme,
            content: content,
            mode: `Ide ke Jurnal (${mode})`,
            language: lang,
            inLibrary: true,
            libraryWorkId: data.work_id,
            paperTitles: paperTitles,
        }, false);
        
        showToast("Naskah berhasil didaftarkan ke Library AI! (AI akan otomatis mencegah plagiasi saat 'Librarian' aktif)", "success");
    } catch (e) {
        showToast("Gagal mendaftarkan ke Library AI: " + e.message, "danger");
    }
}

async function syncAiLibraryDrafts() {
    try {
        const resp = await fetch(`${API_BASE}/api/works`);
        if (!resp.ok) return;
        const data = await resp.json();
        const works = data.works || [];
        const drafts = getSavedDrafts();
        
        let addedCount = 0;
        for (const w of works) {
            const exists = drafts.some(d => d.libraryWorkId === w.work_id || d.title === w.theme);
            if (!exists) {
                drafts.push({
                    id: "work-" + w.work_id,
                    title: w.theme,
                    content: w.content || `[Karya dari Library AI: ${w.theme}]`,
                    mode: w.mode || "journal",
                    language: w.language || "id",
                    createdAt: w.created_at ? new Date(w.created_at).toLocaleString("id-ID") : "Sebelumnya",
                    wordsCount: (w.content || "").split(/\s+/).length,
                    inLibrary: true,
                    libraryWorkId: w.work_id,
                    paperTitles: w.paper_titles || [],
                });
                addedCount++;
            }
        }
        
        if (addedCount > 0) {
            saveDraftsArray(drafts);
            showToast(`Sinkronisasi selesai! ${addedCount} karya dari Library AI dimuat.`, "info");
        } else {
            showToast("Library AI sudah tersinkron!", "success");
        }
        
        renderDraftsList();
    } catch (e) {
        console.error("syncAiLibraryDrafts error:", e);
    }
}

async function addDraftToAiLibrary(draftId) {
    const drafts = getSavedDrafts();
    const draft = drafts.find(d => d.id === draftId);
    if (!draft) return;
    
    try {
        const resp = await fetch(`${API_BASE}/api/works`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                theme: draft.title,
                content: draft.content,
                language: draft.language || "id",
                mode: draft.mode || "journal",
                provider: "manual",
                paper_titles: draft.paperTitles || [],
            })
        });
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        
        draft.inLibrary = true;
        draft.libraryWorkId = data.work_id;
        saveDraftsArray(drafts);
        renderDraftsList();
        showToast("Draf berhasil dimasukkan ke Library AI (Anti-Plagiasi aktif)!", "success");
    } catch (e) {
        showToast("Gagal memasukkan ke Library: " + e.message, "danger");
    }
}

async function removeDraftFromAiLibrary(draftId) {
    const drafts = getSavedDrafts();
    const draft = drafts.find(d => d.id === draftId);
    if (!draft) return;
    
    try {
        if (draft.libraryWorkId) {
            await fetch(`${API_BASE}/api/works/${draft.libraryWorkId}`, { method: "DELETE" });
        }
        draft.inLibrary = false;
        draft.libraryWorkId = null;
        saveDraftsArray(drafts);
        renderDraftsList();
        showToast("Draf dikeluarkan dari Library AI.", "info");
    } catch (e) {
        showToast("Gagal menghapus dari Library: " + e.message, "danger");
    }
}

function deleteDraft(draftId) {
    const drafts = getSavedDrafts();
    const draft = drafts.find(d => d.id === draftId);
    if (!draft) return;
    
    if (confirm(`Apakah Anda yakin ingin menghapus draf "${draft.title}"?`)) {
        if (draft.inLibrary && draft.libraryWorkId) {
            fetch(`${API_BASE}/api/works/${draft.libraryWorkId}`, { method: "DELETE" }).catch(() => {});
        }
        const updated = drafts.filter(d => d.id !== draftId);
        saveDraftsArray(updated);
        renderDraftsList();
        showToast("Draf berhasil dihapus", "info");
    }
}

function clearAllDrafts() {
    const drafts = getSavedDrafts();
    if (drafts.length === 0) return;
    if (confirm("Apakah Anda yakin ingin menghapus semua riwayat draf tersimpan?")) {
        localStorage.removeItem("autojurnal-saved-drafts");
        updateDraftsBadge();
        renderDraftsList();
        showToast("Semua riwayat draf telah dikosongkan");
    }
}

function openDraftsModal() {
    renderDraftsList();
    const modalEl = document.getElementById("draftsModal");
    if (modalEl) {
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }
}

function filterDraftsList() {
    const q = document.getElementById("drafts-search-input")?.value.toLowerCase().trim() || "";
    renderDraftsList(q);
}

function renderDraftsList(filterQuery = "") {
    const container = document.getElementById("drafts-list-container");
    if (!container) return;
    
    const drafts = getSavedDrafts();
    const filtered = filterQuery
        ? drafts.filter(d => (d.title && d.title.toLowerCase().includes(filterQuery)) || (d.content && d.content.toLowerCase().includes(filterQuery)))
        : drafts;
        
    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="bi bi-journal-x fs-1 text-secondary d-block mb-2"></i>
                <p class="mb-1">${filterQuery ? "Tidak ada draf yang cocok dengan pencarian." : "Belum ada riwayat draf tersimpan."}</p>
                <small>Draf yang Anda generate akan otomatis tersimpan di sini.</small>
            </div>`;
        return;
    }
    
    container.innerHTML = filtered.map((d) => {
        const preview = d.content ? escapeHtml(d.content.substring(0, 280)) + (d.content.length > 280 ? "..." : "") : "";
        const libBadge = d.inLibrary 
            ? `<span class="badge bg-success me-1" title="Terdaftar di Library AI (Anti-Plagiasi Aktif)"><i class="bi bi-shield-check me-1"></i>Library AI (Anti-Plagiasi)</span>`
            : `<span class="badge bg-secondary me-1" title="Belum didaftarkan ke Library AI"><i class="bi bi-file-earmark me-1"></i>Lokal</span>`;
            
        const libActionBtn = d.inLibrary
            ? `<button class="btn btn-sm btn-outline-warning" onclick="removeDraftFromAiLibrary('${d.id}')" title="Keluarkan dari Library AI"><i class="bi bi-dash-circle me-1"></i>Hapus dr Library AI</button>`
            : `<button class="btn btn-sm btn-outline-info" onclick="addDraftToAiLibrary('${d.id}')" title="Daftarkan ke Library AI agar AI tidak plagiasi pada penulisan serupa berikutnya"><i class="bi bi-shield-plus me-1"></i>Jadikan Library AI</button>`;
            
        return `
            <div class="card mb-3 border-secondary bg-dark-subtle shadow-sm">
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-2">
                        <div class="flex-grow-1 me-2">
                            <h6 class="fw-bold text-primary mb-1">${escapeHtml(d.title)}</h6>
                            <div class="small text-muted d-flex align-items-center flex-wrap gap-2">
                                <span><i class="bi bi-clock me-1"></i>${d.createdAt}</span>
                                <span>•</span>
                                <span><i class="bi bi-file-text me-1"></i>~${d.wordsCount || 0} kata</span>
                                <span>•</span>
                                <span class="badge bg-primary-subtle text-primary border border-primary-subtle">${d.mode || "Journal"}</span>
                                ${libBadge}
                            </div>
                        </div>
                    </div>
                    <div class="p-2 mb-3 bg-dark rounded font-monospace small text-light border border-secondary" style="max-height: 90px; overflow-y: hidden; font-size: 0.8rem; line-height: 1.4;">
                        ${preview}
                    </div>
                    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                        <div class="d-flex gap-1 flex-wrap">
                            <button class="btn btn-sm btn-primary font-semibold" onclick="loadDraftToEditor('${d.id}')" title="Buka draf ini ke editor">
                                <i class="bi bi-box-arrow-in-up-right me-1"></i>Buka Draf
                            </button>
                            <button class="btn btn-sm btn-outline-warning" onclick="regenerateSimilarFromDraft('${d.id}')" title="Generate ulang naskah serupa dengan fitur Anti-Plagiasi AI aktif">
                                <i class="bi bi-arrow-repeat me-1"></i>Regenerate Serupa (Anti-Plagiasi)
                            </button>
                            ${libActionBtn}
                        </div>
                        <div class="d-flex gap-1 flex-wrap">
                            <button class="btn btn-sm btn-outline-secondary" onclick="copyDraftById('${d.id}')" title="Salin naskah beserta diagram">
                                <i class="bi bi-copy me-1"></i>Copy
                            </button>
                            <button class="btn btn-sm btn-outline-secondary" onclick="downloadDraftById('${d.id}')" title="Download Markdown">
                                <i class="bi bi-download me-1"></i>Download
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteDraft('${d.id}')" title="Hapus draf">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

async function loadDraftToEditor(draftId) {
    const drafts = getSavedDrafts();
    const draft = drafts.find(d => d.id === draftId);
    if (!draft) return;
    
    // Close modal
    const modalEl = document.getElementById("draftsModal");
    if (modalEl) {
        bootstrap.Modal.getInstance(modalEl)?.hide();
    }
    
    if (draft.mode && draft.mode.includes("Ide")) {
        showTab("idea");
        const editor = document.getElementById("idea-output-editor");
        if (editor) {
            editor.value = draft.content;
            document.getElementById("idea-output-panel").style.display = "";
            editor.scrollIntoView({ behavior: "smooth" });
        }
    } else {
        showTab("generate");
        currentJournal = draft.content;
        document.getElementById("result-section").style.display = "block";
        document.getElementById("journal-content").innerHTML = renderMarkdown(currentJournal);
        applyParagraphControls();
        document.getElementById("journal-content").scrollIntoView({ behavior: "smooth" });
    }
    
    showToast(`Draf "${draft.title}" dimuat ke editor!`, "success");
}

function regenerateSimilarFromDraft(draftId) {
    const drafts = getSavedDrafts();
    const draft = drafts.find(d => d.id === draftId);
    if (!draft) return;
    
    // Close modal
    const modalEl = document.getElementById("draftsModal");
    if (modalEl) {
        bootstrap.Modal.getInstance(modalEl)?.hide();
    }
    
    if (draft.mode && draft.mode.includes("Ide")) {
        showTab("idea");
        const topicEl = document.getElementById("idea-search-topic");
        if (topicEl) topicEl.value = draft.title;
        const libChk = document.getElementById("idea-library");
        if (libChk) libChk.checked = true; // Enable anti-plagiarism
        document.getElementById("idea-direct-search-btn")?.scrollIntoView({ behavior: "smooth" });
        showToast("Topik disiapkan di tab Ide ke Jurnal dengan mode Library (Anti-Plagiasi) aktif!", "info");
    } else {
        showTab("generate");
        const themeEl = document.getElementById("theme");
        if (themeEl) themeEl.value = draft.title;
        const titleEl = document.getElementById("paper-title");
        if (titleEl) titleEl.value = draft.title;
        const libChk = document.getElementById("use-library");
        if (libChk) libChk.checked = true; // Enable anti-plagiarism
        document.getElementById("search-btn")?.scrollIntoView({ behavior: "smooth" });
        showToast("Tema disiapkan di tab Generate dengan mode Librarian (Anti-Plagiasi) aktif!", "info");
    }
}

async function copyDraftById(draftId) {
    const drafts = getSavedDrafts();
    const draft = drafts.find(d => d.id === draftId);
    if (!draft) return;
    
    showToast("Menyiapkan naskah & diagram...", "info");
    const rawHtml = await prepareHtmlForClipboard(draft.content);
    await _clipboardWrite(rawHtml, draft.content, "Draf berhasil disalin!");
}

function downloadDraftById(draftId) {
    const drafts = getSavedDrafts();
    const draft = drafts.find(d => d.id === draftId);
    if (!draft) return;
    
    const blob = new Blob([draft.content], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${(draft.title || "draft").toLowerCase().replace(/[^a-z0-9]+/g, "-")}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
}


// ==============================================================================
// Checkpoints & Session Resume Handlers
// ==============================================================================

async function checkActiveCheckpoint() {
    try {
        const resp = await fetch(`${API_BASE}/api/checkpoints/active`);
        if (!resp.ok) return;
        const data = await resp.json();
        const banner = document.getElementById("resume-banner");
        if (!banner) return;

        if (data.has_active && data.checkpoint) {
            activeCheckpointData = data.checkpoint;
            const themeEl = document.getElementById("resume-banner-theme");
            const progressEl = document.getElementById("resume-banner-progress");
            if (themeEl) themeEl.textContent = data.checkpoint.theme || "Tanpa Judul";
            if (progressEl) {
                const modeLabel = data.checkpoint.mode === "textbook" ? "Buku Ajar" : "Jurnal Ilmiah";
                const unit = data.checkpoint.mode === "textbook" ? "Bab" : "Bagian";
                progressEl.textContent = `${modeLabel} (${data.checkpoint.current_step}/${data.checkpoint.total_steps} ${unit} selesai · tersimpan ${data.checkpoint.last_updated_human || ''})`;
            }
            banner.style.display = "block";
        } else {
            activeCheckpointData = null;
            banner.style.display = "none";
        }
    } catch (e) {
        console.warn("[Checkpoint] Check failed:", e);
    }
}

async function resumeActiveCheckpoint() {
    if (!activeCheckpointData) return;
    const cp = activeCheckpointData;
    const modeLabel = cp.mode === "textbook" ? "Buku Ajar" : "Jurnal Ilmiah";
    const unit = cp.mode === "textbook" ? "Bab" : "Bagian";

    if (!confirm(`Lanjutkan penulisan ${modeLabel} '${cp.theme}' mulai dari ${unit} ${cp.current_step + 1}?`)) {
        return;
    }

    // Set theme and mode in UI
    const themeEl = document.getElementById("theme");
    if (themeEl) themeEl.value = cp.theme;
    const modeEl = document.getElementById("mode");
    if (modeEl && cp.mode) {
        modeEl.value = cp.mode;
        toggleMode();
    }
    const langEl = document.getElementById("language");
    if (langEl && cp.language) langEl.value = cp.language;

    // Trigger generate stream with resume=true and session_id
    showTab("generate");
    document.getElementById("resume-banner").style.display = "none";

    // Start generation directly in resume mode
    await startResumeGenerationStream(cp);
}

async function discardActiveCheckpoint() {
    if (!activeCheckpointData) return;
    if (!confirm("Hapus draf terputus ini dan mulai baru?")) return;

    try {
        await fetch(`${API_BASE}/api/checkpoints/${activeCheckpointData.session_id}`, {
            method: "DELETE"
        });
        activeCheckpointData = null;
        const banner = document.getElementById("resume-banner");
        if (banner) banner.style.display = "none";
        showToast("Checkpoint berhasil dibatalkan.", "info");
    } catch (e) {
        showToast("Gagal membatalkan checkpoint: " + e.message, "danger");
    }
}

async function startResumeGenerationStream(cp) {
    clearLogs();
    document.getElementById("loading-section").style.display = "block";
    document.getElementById("input-card").style.display = "none";
    document.getElementById("result-card").style.display = "none";

    const logEl = document.getElementById("log-display");
    if (logEl) { logEl.style.display = "block"; logEl.innerHTML = ""; }

    updateLoading(
        `Melanjutkan ${cp.mode === "textbook" ? "Buku Ajar" : "Jurnal"}...`,
        `Memulihkan dari ${cp.mode === "textbook" ? "Bab" : "Bagian"} ${cp.current_step + 1}`
    );

    const provider = document.getElementById("provider").value;
    const providerModel = document.getElementById("provider-model").value.trim() || null;
    const providerBaseUrl = document.getElementById("provider-base-url").value.trim() || null;
    const apiKey = document.getElementById("llm-api-key").value.trim() || null;

    const payload = {
        theme: cp.theme,
        papers: collectedPapers.length ? collectedPapers : (allPapers.length ? allPapers : []),
        language: cp.language || "id",
        provider: provider,
        provider_model: providerModel,
        provider_base_url: providerBaseUrl,
        api_key: apiKey,
        mode: cp.mode || "journal",
        multi_agent: cp.mode !== "textbook",
        num_chapters: cp.total_steps || 14,
        session_id: cp.session_id,
        resume: true,
    };

    try {
        const resp = await fetch(`${API_BASE}/api/generate/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!resp.ok) throw new Error(await resp.text());

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    try {
                        const event = JSON.parse(line.slice(6));
                        handleStreamEvent(event);
                    } catch (e) {
                        console.error("Failed to parse SSE line:", line, e);
                    }
                }
            }
        }
    } catch (err) {
        updateLoading("Generasi Terhenti", err.message, true);
        showToast("Resume failed: " + err.message.substring(0, 200), "danger");
    }
}


// ==============================================================================
// AI Catalog & Multi-Key Router Management Handlers
// ==============================================================================

async function loadAISettings() {
    try {
        const resp = await fetch(`${API_BASE}/api/ai/settings`);
        if (!resp.ok) return;
        const data = await resp.json();
        aiCatalog = data.catalog || [];
        aiSettings = data.providers || {};
    } catch (e) {
        console.warn("[AI Settings] Failed to load settings:", e);
    }
}

async function openAISettingsModal() {
    if (!aiCatalog || aiCatalog.length === 0) {
        await loadAISettings();
    }
    renderAIProviderCards();
    const modalEl = document.getElementById("aiSettingsModal");
    if (modalEl) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
    }
}

function filterAICategory(cat, btnEl) {
    currentAICategory = cat;
    if (btnEl) {
        document.querySelectorAll("#ai-category-filters button").forEach(b => b.classList.remove("active"));
        btnEl.classList.add("active");
    }
    renderAIProviderCards();
}

function filterAIProviderList() {
    renderAIProviderCards();
}

function renderAIProviderCards() {
    const container = document.getElementById("ai-providers-container");
    if (!container) return;

    const searchTerm = (document.getElementById("ai-provider-search")?.value || "").toLowerCase().trim();

    let filtered = aiCatalog.filter(p => {
        if (currentAICategory !== "all" && p.category !== currentAICategory) {
            return false;
        }
        if (searchTerm) {
            const nameMatch = (p.name || "").toLowerCase().includes(searchTerm);
            const idMatch = (p.id || "").toLowerCase().includes(searchTerm);
            const modelMatch = (p.default_model || "").toLowerCase().includes(searchTerm);
            return nameMatch || idMatch || modelMatch;
        }
        return true;
    });

    if (!filtered.length) {
        container.innerHTML = `<div class="col-12 text-center py-4 text-muted">Tidak ada provider AI yang cocok dengan filter.</div>`;
        return;
    }

    container.innerHTML = filtered.map(p => {
        const userCfg = aiSettings[p.id] || {};
        const savedKey = userCfg.api_key || "";
        const savedUrl = userCfg.base_url || p.default_base_url || "";
        const savedModel = userCfg.model || p.default_model || "";
        const hasKey = Boolean(savedKey || p.category === "local");

        const statusBadge = hasKey
            ? `<span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-check-circle me-1"></i>Terkonfigurasi</span>`
            : `<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">Belum Ada Key</span>`;

        const modelOptions = (p.popular_models || []).map(m => `<option value="${m}">${m}</option>`).join("");

        return `
        <div class="col-md-6 col-lg-6">
            <div class="card h-100 shadow-sm border ${hasKey ? 'border-primary-subtle' : 'border-secondary-subtle'}">
                <div class="card-header d-flex justify-content-between align-items-center py-2 bg-body-tertiary">
                    <div class="d-flex align-items-center gap-2">
                        <i class="bi ${p.icon || 'bi-cpu'} fs-5 text-primary"></i>
                        <span class="font-semibold text-light">${p.name}</span>
                        ${p.badge ? `<span class="badge bg-secondary small">${p.badge}</span>` : ''}
                    </div>
                    <div>${statusBadge}</div>
                </div>
                <div class="card-body p-3">
                    <div class="mb-2">
                        <label class="form-label small text-muted mb-1">API Base URL (Endpoint)</label>
                        <input type="text" class="form-control form-control-sm font-monospace" id="ai-url-${p.id}" value="${savedUrl}" placeholder="${p.default_base_url || 'https://...'}">
                    </div>

                    <div class="mb-2">
                        <label class="form-label small text-muted mb-1">Default Model</label>
                        <div class="input-group input-group-sm">
                            <input type="text" class="form-control font-monospace" id="ai-model-${p.id}" value="${savedModel}" placeholder="${p.default_model}">
                            ${p.popular_models && p.popular_models.length ? `
                            <button class="btn btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" title="Pilih Model Populer"></button>
                            <ul class="dropdown-menu dropdown-menu-end">
                                ${p.popular_models.map(m => `<li><a class="dropdown-item small" href="javascript:void(0)" onclick="document.getElementById('ai-model-${p.id}').value='${m}'">${m}</a></li>`).join('')}
                            </ul>
                            ` : ''}
                        </div>
                    </div>

                    <div class="mb-3">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <label class="form-label small text-muted mb-0">
                                API Key(s) <small class="text-warning">— Multi-Key: pisahkan koma/baris baru</small>
                            </label>
                            ${p.doc_url ? `<a href="${p.doc_url}" target="_blank" class="small text-info text-decoration-none"><i class="bi bi-box-arrow-up-right me-1"></i>Get Key</a>` : ''}
                        </div>
                        <textarea class="form-control form-control-sm font-monospace" id="ai-key-${p.id}" rows="2" placeholder="${p.category === 'local' ? 'Tidak butuh key untuk Ollama lokal (opsional jika ada token)' : 'sk-... atau key1, key2, key3'}">${savedKey}</textarea>
                    </div>

                    <div class="d-flex justify-content-between align-items-center pt-1 border-top">
                        <div id="ai-test-result-${p.id}" class="small text-muted">-</div>
                        <button class="btn btn-sm btn-outline-info" id="ai-test-btn-${p.id}" onclick="testAIProviderKey('${p.id}')">
                            <i class="bi bi-activity me-1"></i>Test Ping
                        </button>
                    </div>
                </div>
            </div>
        </div>
        `;
    }).join("");
}

async function testAIProviderKey(pId) {
    const keyEl = document.getElementById(`ai-key-${pId}`);
    const urlEl = document.getElementById(`ai-url-${pId}`);
    const modelEl = document.getElementById(`ai-model-${pId}`);
    const resEl = document.getElementById(`ai-test-result-${pId}`);
    const btnEl = document.getElementById(`ai-test-btn-${pId}`);

    if (btnEl) btnEl.disabled = true;
    if (resEl) resEl.innerHTML = `<span class="spinner-border spinner-border-sm text-info me-1"></span>Menguji...`;

    try {
        const resp = await fetch(`${API_BASE}/api/ai/test`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                provider_id: pId,
                api_key: keyEl ? keyEl.value.trim() : null,
                base_url: urlEl ? urlEl.value.trim() : null,
                model: modelEl ? modelEl.value.trim() : null,
            })
        });

        const data = await resp.json();
        if (btnEl) btnEl.disabled = false;

        if (data.status === "ok") {
            if (resEl) resEl.innerHTML = `<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>Aktif (${data.latency_ms}ms)</span>`;
            showToast(`Koneksi ${pId} berhasil! Latensi: ${data.latency_ms}ms`, "success");
        } else {
            if (resEl) resEl.innerHTML = `<span class="text-danger" title="${escapeHtml(data.error || '')}"><i class="bi bi-x-circle-fill me-1"></i>Error</span>`;
            showToast(`Test ${pId} gagal: ${data.error ? data.error.substring(0, 150) : 'Unknown error'}`, "danger");
        }
    } catch (e) {
        if (btnEl) btnEl.disabled = false;
        if (resEl) resEl.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i>Gagal</span>`;
        showToast("Test request error: " + e.message, "danger");
    }
}

async function saveAllAISettings() {
    const statusEl = document.getElementById("ai-settings-status");
    if (statusEl) statusEl.textContent = "Menyimpan pengaturan...";

    const updatedProviders = {};
    aiCatalog.forEach(p => {
        const keyEl = document.getElementById(`ai-key-${p.id}`);
        const urlEl = document.getElementById(`ai-url-${p.id}`);
        const modelEl = document.getElementById(`ai-model-${p.id}`);

        const apiKey = keyEl ? keyEl.value.trim() : "";
        const baseUrl = urlEl ? urlEl.value.trim() : "";
        const model = modelEl ? modelEl.value.trim() : "";

        if (apiKey || baseUrl || model) {
            updatedProviders[p.id] = {
                api_key: apiKey,
                base_url: baseUrl || p.default_base_url,
                model: model || p.default_model,
            };
        }
    });

    const strategy = document.getElementById("ai-router-strategy")?.value || "round-robin";

    try {
        const resp = await fetch(`${API_BASE}/api/ai/settings`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                providers: updatedProviders,
                router_strategy: strategy,
            })
        });

        if (!resp.ok) throw new Error(await resp.text());

        aiSettings = updatedProviders;
        if (statusEl) statusEl.textContent = "Pengaturan berhasil disimpan!";
        showToast("Pengaturan AI Router & API Key berhasil disimpan!", "success");

        // Reload provider list in dropdown
        await loadProviders();
    } catch (e) {
        if (statusEl) statusEl.textContent = "Gagal menyimpan: " + e.message;
        showToast("Gagal menyimpan pengaturan: " + e.message, "danger");
    }
}

function openInstallModal(platform = 'macos') {
    const modalEl = document.getElementById("installModal");
    if (!modalEl) return;
    const modal = new bootstrap.Modal(modalEl);

    if (platform === 'windows') {
        const winTabBtn = document.getElementById("tab-win-btn");
        if (winTabBtn) {
            const trigger = new bootstrap.Tab(winTabBtn);
            trigger.show();
        }
    } else {
        const macTabBtn = document.getElementById("tab-mac-btn");
        if (macTabBtn) {
            const trigger = new bootstrap.Tab(macTabBtn);
            trigger.show();
        }
    }

    modal.show();
}

