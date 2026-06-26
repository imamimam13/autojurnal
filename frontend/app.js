const API_BASE = window.location.origin;

let allPapers = [];
let selectedIndices = new Set();
let collectedPapers = [];
let currentJournal = "";

let templates = [];
let parsedTemplate = null;

document.addEventListener("DOMContentLoaded", async () => {
    await loadProviders();
    restoreSettings();
    restoreCollection();
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
    });

    document.querySelectorAll("#input-card input, #input-card select").forEach((el) => {
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

function saveApiKeyToBackend(provider, apiKey) {
    const supported = ["ollama", "openai", "anthropic", "gemini"];
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

function renderMarkdown(text) {
    const html = marked.parse(text);
    // Wrap mermaid code blocks for live rendering
    const withMermaid = html.replace(
        /<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/g,
        '<div class="mermaid">$1</div>'
    );
    // Render mermaid after DOM update
    setTimeout(() => {
        if (typeof mermaid !== "undefined") {
            mermaid.run({ nodes: document.querySelectorAll(".mermaid") });
        }
    }, 100);
    return withMermaid;
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

function _cleanHtmlClipboard(html) {
    // Strip base64 images (bloat clipboard, fail paste)
    // Keep Markdown tables (converted to <table> by marked.js) — Word/Docs can render them
    return html
        .replace(/<img[^>]*src="data:image[^>]*>/gi, "")
        .replace(/<div class="mermaid">[\s\S]*?<\/div>/gi, "");
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
        document.execCommand("copy");
        showToast("Copied!");
    } catch {
        showToast("Copy failed — select manually", "danger");
    }
    document.body.removeChild(ta);
}

function _clipboardWrite(htmlContent, plainText, successMsg = "Copied!") {
    if (navigator.clipboard && navigator.clipboard.write) {
        try {
            const cleanHtml = `<html><body>${_cleanHtmlClipboard(htmlContent)}</body></html>`;
            navigator.clipboard.write([
                new ClipboardItem({
                    "text/html": new Blob([cleanHtml], { type: "text/html" }),
                    "text/plain": new Blob([plainText], { type: "text/plain" }),
                }),
            ]).then(() => showToast(successMsg)).catch(() => {
                navigator.clipboard.writeText(plainText).then(
                    () => showToast(successMsg)
                ).catch(() => _copyFallback(plainText));
            });
        } catch {
            _copyFallback(plainText);
        }
    } else {
        _copyFallback(plainText);
    }
}

function copyJournal() {
    const rawHtml = renderMarkdown(currentJournal);
    _clipboardWrite(rawHtml, currentJournal.trim());
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
    const current = sel.value;
    sel.innerHTML = '<option value="">Default (no template)</option>';
    if (rsel) {
        rsel.innerHTML = '<option value="">Select a template...</option>';
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
    document.getElementById("tab-generate-btn").classList.toggle("active", tab === "generate");
    document.getElementById("tab-restructure-btn").classList.toggle("active", tab === "restructure");
    document.getElementById("tab-review-btn").classList.toggle("active", tab === "review");
    document.getElementById("tab-translate-btn").classList.toggle("active", tab === "translate");
    document.getElementById("tab-generate-btn").classList.toggle("btn-outline-primary", tab !== "generate");
    document.getElementById("tab-restructure-btn").classList.toggle("btn-outline-primary", tab !== "restructure");
    document.getElementById("tab-review-btn").classList.toggle("btn-outline-primary", tab !== "review");
    document.getElementById("tab-translate-btn").classList.toggle("btn-outline-primary", tab !== "translate");
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
        alert("Select a target template.");
        return;
    }
    if (!restructureSourceText) {
        alert("Parse a source document first.");
        return;
    }

    showLoading();
    updateLoading("Restructuring document...", `Using template: ${templates.find(t => t.id === templateId)?.name || templateId}`);

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
        hideLoading();

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

        document.getElementById("restructured-content").scrollIntoView({ behavior: "smooth" });
    } catch (err) {
        updateLoading("Restructure failed", err.message.substring(0, 300), true);
        setTimeout(hideLoading, 8000);
    }
}

function copyRestructured() {
    const el = document.getElementById("restructured-content");
    const rawMarkdown = el.dataset.raw || el.textContent || "";
    const rawHtml = renderMarkdown(rawMarkdown);
    _clipboardWrite(rawHtml, rawMarkdown.trim());
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
});

async function reviseWithReview() {
    const sourceText = document.getElementById("review-document").value.trim();
    const reviewText = document.getElementById("review-text").value.trim();
    const language = document.getElementById("review-language").value;
    if (!sourceText) { showToast("Please paste the original document first.", "warning"); return; }
    if (!reviewText) { showToast("Please paste the reviewer feedback.", "warning"); return; }

    const provider = document.getElementById("provider").value;
    const providerModel = document.getElementById("provider-model").value;
    const providerBaseUrl = document.getElementById("provider-base-url").value;
    const apiKey = document.getElementById("llm-api-key").value;

    updateLoading("Revising document based on reviewer feedback...");
    showLoading();
    document.getElementById("review-result-section").style.display = "none";

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
        hideLoading();

        document.getElementById("review-result-section").style.display = "";
        const rcEl = document.getElementById("review-content");
        rcEl.innerHTML = renderMarkdown(data.revised_text);
        rcEl.dataset.raw = data.revised_text;

        document.getElementById("review-content").scrollIntoView({ behavior: "smooth" });
    } catch (err) {
        hideLoading();
        showToast("Revise failed: " + err.message.substring(0, 300), "danger");
    }
}

function copyReviewResult() {
    const el = document.getElementById("review-content");
    const rawMarkdown = el.dataset.raw || el.textContent || "";
    const rawHtml = renderMarkdown(rawMarkdown);
    _clipboardWrite(rawHtml, rawMarkdown.trim());
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
    if (!sourceText) { showToast("Please paste the document text to translate.", "warning"); return; }
    if (srcLang === tgtLang) { showToast("Source and target languages must differ.", "warning"); return; }

    const provider = document.getElementById("provider").value;
    const providerModel = document.getElementById("provider-model").value;
    const providerBaseUrl = document.getElementById("provider-base-url").value;
    const apiKey = document.getElementById("llm-api-key").value;

    updateLoading("Translating...");
    showLoading();
    document.getElementById("translate-result-section").style.display = "none";

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
        hideLoading();

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

        outEl.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
        hideLoading();
        showToast("Translation failed: " + err.message.substring(0, 300), "danger");
    }
}

function copyTranslated() {
    const el = document.getElementById("translate-output");
    const rawMarkdown = el.dataset.raw || el.textContent || "";
    const rawHtml = renderMarkdown(rawMarkdown);
    const cleanHtml = `<html><body>${_cleanHtmlClipboard(rawHtml)}</body></html>`;
    const plainText = rawMarkdown.trim();

    _clipboardWrite(rawHtml, rawMarkdown.trim());
}

function downloadTranslated() {
    const el = document.getElementById("translate-output");
    const text = el.dataset.raw || el.textContent || "";
    const blob = new Blob([text], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "translated-document.md";
    a.click();
    URL.revokeObjectURL(a.href);
}
