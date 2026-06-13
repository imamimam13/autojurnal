const API_BASE = "http://localhost:8000";

let allPapers = [];
let selectedIndices = new Set();
let currentJournal = "";

document.addEventListener("DOMContentLoaded", async () => {
    await loadProviders();
    restoreSettings();

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

function saveSettings() {
    const keys = [
        "openalex-api-key", "llm-api-key", "provider-model", "provider-base-url",
        "theme", "year-range", "max-papers", "language", "provider", "multi-agent",
    ];
    const data = {};
    keys.forEach((id) => {
        const el = document.getElementById(id);
        if (el) data[id] = el.value;
    });
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
            if (el && val) el.value = val;
        });
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
}

async function searchPapers() {
    const theme = document.getElementById("theme").value.trim();
    if (!theme) {
        alert("Please enter a research theme.");
        return;
    }

    document.getElementById("result-section").style.display = "none";
    document.getElementById("generate-btn").disabled = true;
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
        document.getElementById("generate-btn").disabled = false;
        document.getElementById("generate-btn").scrollIntoView({ behavior: "smooth" });

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
    const count = selectedIndices.size;
    btn.disabled = count === 0;
    btn.innerHTML = `<i class="bi bi-journal-text me-2"></i>Generate Journal (${count} papers)`;
    const selCount = document.getElementById("selected-count");
    if (selCount) selCount.textContent = count;
}

function togglePaper(index) {
    const el = document.querySelector(`.paper-item[data-index="${index}"] .paper-abstract`);
    if (el) el.classList.toggle("expanded");
}

function toggleAllPapers() {
    const allChecked = document.querySelectorAll(".paper-item .form-check-input:checked").length === allPapers.length;
    document.querySelectorAll(".paper-item").forEach((el, i) => {
        const chk = el.querySelector(".form-check-input");
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

async function generateJournal() {
    const theme = document.getElementById("theme").value.trim();
    const selectedPapers = allPapers.filter((_, i) => selectedIndices.has(i));
    if (!theme || selectedPapers.length === 0) {
        alert("Select at least one paper first.");
        return;
    }

    const language = document.getElementById("language").value;
    const targetLength = document.getElementById("target-length").value;
    const multiAgent = document.getElementById("multi-agent").checked;
    const provider = document.getElementById("provider").value;
    const providerModel =
        document.getElementById("provider-model").value.trim() || null;
    const providerBaseUrl =
        document.getElementById("provider-base-url").value.trim() || null;
    const apiKey =
        document.getElementById("llm-api-key").value.trim() || null;

    document.getElementById("result-section").style.display = "none";
    showLoading();
    updateLoading(
        "Generating journal...",
        `Using ${provider}${providerModel ? ` (${providerModel})` : ""}`
    );

    try {
        const resp = await fetch(`${API_BASE}/api/generate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                theme,
                papers: selectedPapers,
                language,
                target_length: targetLength,
                multi_agent: multiAgent,
                provider,
                provider_model: providerModel,
                provider_base_url: providerBaseUrl,
                api_key: apiKey,
            }),
        });

        if (!resp.ok) {
            const errText = await resp.text();
            throw new Error(`[${resp.status}] ${errText}`);
        }

        const data = await resp.json();
        currentJournal = data.journal;

        hideLoading();
        document.getElementById("result-section").style.display = "block";
        document.getElementById("journal-content").innerHTML =
            marked.parse(currentJournal);
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

    } catch (err) {
        updateLoading("Generation failed", err.message.substring(0, 300), true);
        setTimeout(hideLoading, 8000);
    }
}

function showToast(msg, type = "success") {
    const toast = document.getElementById("toast-msg");
    document.getElementById("toast-body").textContent = msg;
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    bootstrap.Toast.getOrCreateInstance(toast).show();
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

function copyJournal() {
    const rendered = document.getElementById("journal-content").innerHTML;
    const style = document.querySelector("style").innerHTML;
    const cleanHtml = rendered
        .replace(/<button[\s\S]*?<\/button>/g, "")
        .replace(/<div class="para-controls">[\s\S]*?<\/div>/g, "");
    const styledHtml = `<html><head><style>${style}</style></head><body>${cleanHtml}</body></html>`;
    const plainText = stripMarkdown(currentJournal);

    navigator.clipboard.write([
        new ClipboardItem({
            "text/html": new Blob([styledHtml], { type: "text/html" }),
            "text/plain": new Blob([plainText], { type: "text/plain" }),
        }),
    ]).then(() => showToast("Copied with rich text formatting!")).catch(() => {
        navigator.clipboard.writeText(plainText).then(() => {
            showToast("Copied as plain text!");
        });
    });
}

function copyPlainText() {
    const plainText = stripMarkdown(currentJournal);
    navigator.clipboard.writeText(plainText).then(() => {
        showToast("Plain text copied!");
    });
}

function downloadJournal() {
    const plainText = stripMarkdown(currentJournal);
    const blob = new Blob([plainText], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `journal-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
}

async function regenerateJournal() {
    if (!confirm("Regenerate journal with the same settings?")) return;
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
