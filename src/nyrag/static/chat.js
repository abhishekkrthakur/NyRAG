const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const statsEl = document.getElementById("corpus-stats");

// Settings Modal Elements
const settingsBtn = document.getElementById("settings-btn");
const modal = document.getElementById("settings-modal");
const closeBtn = document.querySelector(".close-btn");
const saveBtn = document.getElementById("save-settings");
const hitsInput = document.getElementById("hits");
const kInput = document.getElementById("k");
const queryKInput = document.getElementById("query_k");

// Settings Modal Logic
settingsBtn.onclick = () => modal.style.display = "block";
closeBtn.onclick = () => modal.style.display = "none";
saveBtn.onclick = () => modal.style.display = "none";

// Crawl Modal Elements
const crawlBtn = document.getElementById("crawl-btn");
const crawlModal = document.getElementById("crawl-modal");
const closeCrawlBtn = document.querySelector(".close-crawl-btn");
const startCrawlBtn = document.getElementById("start-crawl-btn");
const terminalLogs = document.getElementById("terminal-logs");
const crawlConfig = document.getElementById("crawl-config");
const configSelect = document.getElementById("config-select");
const newConfigBtn = document.getElementById("new-config-btn");
const saveConfigBtn = document.getElementById("save-config-btn");

// Tabs & Views
const tabForm = document.getElementById("tab-form");
const tabYaml = document.getElementById("tab-yaml");
const configFormView = document.getElementById("config-form-view");
const configYamlView = document.getElementById("config-yaml-view");
const configScrollContainer = document.getElementById("config-scroll-container");

// Form Fields
const confName = document.getElementById("conf-name");
const confMode = document.getElementById("conf-mode");
const confStartLoc = document.getElementById("conf-start-loc");
const confExclude = document.getElementById("conf-exclude");
const confRobots = document.getElementById("conf-robots");
const confSubdomains = document.getElementById("conf-subdomains");
const confUserAgent = document.getElementById("conf-user-agent");
const confEmbedding = document.getElementById("conf-embedding");
const confChunkSize = document.getElementById("conf-chunk-size");
const confChunkOverlap = document.getElementById("conf-chunk-overlap");

// Doc Params Fields
const detailsCrawl = document.getElementById("details-crawl");
const detailsDocs = document.getElementById("details-docs");
const confRecursive = document.getElementById("conf-recursive");
const confHidden = document.getElementById("conf-hidden");
const confExtensions = document.getElementById("conf-extensions");

let eventSource = null;
let currentView = "form"; // 'form' or 'yaml'

function updateModeVisibility() {
    const mode = confMode.value;
    if (mode === "web") {
        detailsCrawl.style.display = "block";
        detailsDocs.style.display = "none";
    } else {
        detailsCrawl.style.display = "none";
        detailsDocs.style.display = "block";
    }
}

confMode.onchange = updateModeVisibility;

function yamlToForm(yamlStr) {
    try {
        const doc = jsyaml.load(yamlStr) || {};
        
        confName.value = doc.name || "";
        confMode.value = doc.mode || "web";
        confStartLoc.value = doc.start_loc || "";
        
        if (Array.isArray(doc.exclude)) {
            confExclude.value = doc.exclude.join("\n");
        } else {
            confExclude.value = "";
        }

        const crawl = doc.crawl_params || {};
        confRobots.checked = crawl.respect_robots_txt !== false; // default true
        confSubdomains.checked = crawl.follow_subdomains !== false; // default true
        confUserAgent.value = crawl.user_agent_type || "chrome";

        const docs = doc.doc_params || {};
        confRecursive.checked = docs.recursive !== false; // default true
        confHidden.checked = docs.include_hidden === true; // default false
        if (Array.isArray(docs.file_extensions)) {
            confExtensions.value = docs.file_extensions.join(", ");
        } else {
            confExtensions.value = "";
        }

        const rag = doc.rag_params || {};
        confEmbedding.value = rag.embedding_model || "sentence-transformers/all-MiniLM-L6-v2";
        confChunkSize.value = rag.chunk_size || 1024;
        confChunkOverlap.value = rag.chunk_overlap || 50;

        updateModeVisibility();

    } catch (e) {
        console.error("Error parsing YAML for form:", e);
        // If parsing fails, maybe switch to YAML view to show error?
        // For now, just log it.
    }
}

function formToYaml() {
    const mode = confMode.value;
    const doc = {
        name: confName.value,
        mode: mode,
        start_loc: confStartLoc.value,
        exclude: confExclude.value.split("\n").map(s => s.trim()).filter(s => s),
        rag_params: {
            embedding_model: confEmbedding.value,
            chunk_size: parseInt(confChunkSize.value) || 1024,
            chunk_overlap: parseInt(confChunkOverlap.value) || 50
        }
    };

    if (mode === "web") {
        doc.crawl_params = {
            respect_robots_txt: confRobots.checked,
            follow_subdomains: confSubdomains.checked,
            user_agent_type: confUserAgent.value
        };
    } else {
        doc.doc_params = {
            recursive: confRecursive.checked,
            include_hidden: confHidden.checked,
            file_extensions: confExtensions.value.split(",").map(s => s.trim()).filter(s => s)
        };
        if (doc.doc_params.file_extensions.length === 0) {
            delete doc.doc_params.file_extensions;
        }
    }
    
    // Preserve other fields if we had the original object? 
    // For simplicity, we regenerate. Advanced users should use YAML view if they have custom fields.
    return jsyaml.dump(doc);
}

function switchTab(view) {
    if (view === currentView) return;

    if (view === "form") {
        // YAML -> Form
        yamlToForm(crawlConfig.value);
        configYamlView.style.display = "none";
        configScrollContainer.style.display = "block";
        tabYaml.classList.remove("active");
        tabForm.classList.add("active");
    } else {
        // Form -> YAML
        crawlConfig.value = formToYaml();
        configScrollContainer.style.display = "none";
        configYamlView.style.display = "block";
        tabForm.classList.remove("active");
        tabYaml.classList.add("active");
    }
    currentView = view;
}

tabForm.onclick = () => switchTab("form");
tabYaml.onclick = () => switchTab("yaml");

async function loadConfigs() {
    try {
        const res = await fetch("/configs");
        if (res.ok) {
            const configs = await res.json();
            configSelect.innerHTML = '<option value="" disabled selected>Select Config</option>';
            configs.forEach(config => {
                const option = document.createElement("option");
                option.value = config;
                option.textContent = config;
                configSelect.appendChild(option);
            });
        }
    } catch (e) {
        console.error("Failed to load configs", e);
    }
}

configSelect.onchange = async () => {
    const name = configSelect.value;
    if (!name) return;
    try {
        const res = await fetch(`/configs/${name}`);
        if (res.ok) {
            const data = await res.json();
            crawlConfig.value = data.content;
            // If in form view, update form
            if (currentView === "form") {
                yamlToForm(data.content);
            }
        }
    } catch (e) {
        console.error("Failed to load config content", e);
    }
};

newConfigBtn.onclick = () => {
    const name = prompt("Enter new config filename (e.g., my_crawl.yml):");
    if (!name) return;
    
    // Add to select and select it
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    configSelect.appendChild(option);
    configSelect.value = name;
    
    // Default template
    const defaultYaml = `# New Config: ${name}
name: my-project
mode: web
start_loc: https://example.com
exclude: []
crawl_params:
  respect_robots_txt: true
  follow_subdomains: true
  user_agent_type: chrome
rag_params:
  embedding_model: sentence-transformers/all-MiniLM-L6-v2
  chunk_size: 1024
  chunk_overlap: 50
`;
    crawlConfig.value = defaultYaml;
    if (currentView === "form") {
        yamlToForm(defaultYaml);
    }
};

saveConfigBtn.onclick = async () => {
    const name = configSelect.value;
    if (!name) {
        alert("Please select or create a config first.");
        return;
    }
    
    // Sync before saving
    let content = crawlConfig.value;
    if (currentView === "form") {
        content = formToYaml();
        crawlConfig.value = content; // Update textarea too
    }

    try {
        const res = await fetch(`/configs/${name}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content: content })
        });
        if (res.ok) {
            alert("Config saved!");
            await loadConfigs();
            configSelect.value = name;
        } else {
            alert("Failed to save config.");
        }
    } catch (e) {
        console.error("Failed to save config", e);
        alert("Error saving config.");
    }
};

function connectToLogs() {
  if (eventSource) return;

  eventSource = new EventSource("/crawl/logs");

  eventSource.onmessage = (event) => {
    if (event.data === "[PROCESS COMPLETED]") {
      eventSource.close();
      eventSource = null;
      startCrawlBtn.disabled = false;
      startCrawlBtn.textContent = "Start Crawl";
      terminalLogs.appendChild(document.createTextNode("\n[Process Completed]\n"));
      return;
    }
    terminalLogs.appendChild(document.createTextNode(event.data + "\n"));
    terminalLogs.scrollTop = terminalLogs.scrollHeight;
  };

  eventSource.onerror = (err) => {
    // If connection fails (e.g. server restart), close it.
    // We might want to retry, but for now just close.
    eventSource.close();
    eventSource = null;
  };
}

// Crawl Modal Logic
crawlBtn.onclick = async () => {
  crawlModal.style.display = "block";
  connectToLogs();
  await loadConfigs();
};
closeCrawlBtn.onclick = () => crawlModal.style.display = "none";

startCrawlBtn.onclick = async () => {
  startCrawlBtn.disabled = true;
  startCrawlBtn.textContent = "Starting...";
  
  // Sync form to YAML if needed
  let content = crawlConfig.value;
  if (currentView === "form") {
      content = formToYaml();
      crawlConfig.value = content;
  }

  try {
    const res = await fetch("/crawl/start", { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config_yaml: content })
    });
    if (res.ok) {
      startCrawlBtn.textContent = "Crawl Started";
      connectToLogs();
    } else {
      startCrawlBtn.textContent = "Failed to Start";
      startCrawlBtn.disabled = false;
    }
  } catch (e) {
    console.error(e);
    startCrawlBtn.textContent = "Error";
    startCrawlBtn.disabled = false;
  }
};

window.onclick = (event) => {
  if (event.target === modal) {
    modal.style.display = "none";
  }
  if (event.target === crawlModal) {
    crawlModal.style.display = "none";
  }
};

// Maintain conversation history
let conversationHistory = [];

async function refreshStats() {
  if (!statsEl) return;
  try {
    const res = await fetch("/stats", { method: "GET" });
    if (!res.ok) {
      statsEl.textContent = "";
      return;
    }
    const data = await res.json();
    const docs = data?.documents;
    const chunks = data?.chunks;
    if (typeof docs === "number" && typeof chunks === "number") {
      statsEl.textContent = `Indexed: ${docs} documents • ${chunks} chunks`;
    } else if (typeof docs === "number") {
      statsEl.textContent = `Indexed: ${docs} documents`;
    } else {
      statsEl.textContent = "";
    }
  } catch (e) {
    statsEl.textContent = "";
  }
}

refreshStats();

// Auto-resize textarea
inputEl.addEventListener('input', function () {
  this.style.height = 'auto';
  this.style.height = (this.scrollHeight) + 'px';
  if (this.value === '') {
    this.style.height = 'auto';
  }
});

function renderMarkdown(el, text) {
  if (window.marked) {
    const html = window.marked.parse(text || "", {
      breaks: true,
      mangle: false,
      headerIds: false,
    });
    el.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
  } else {
    el.textContent = text;
  }
}

function append(role, text) {
  // Remove welcome message if it exists
  const welcome = document.querySelector('.welcome-message');
  if (welcome) welcome.remove();

  const div = document.createElement("div");
  div.className = role === "You" ? "msg user-msg" : "msg assistant-msg";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (role === "You") {
    bubble.textContent = text;
  } else {
    // For assistant, we might render markdown later, but initial text is fine
    bubble.innerHTML = `<div class="assistant-text">${text}</div>`;
  }

  div.appendChild(bubble);
  chatEl.appendChild(div);

  // Scroll to bottom
  scrollToBottom();
}

function scrollToBottom() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

function appendChunksCollapsible(chunks) {
  if (!chunks || !chunks.length) return;

  // Find the last assistant message to append chunks to
  const msgs = document.querySelectorAll('.msg.assistant-msg');
  const lastMsg = msgs[msgs.length - 1];
  if (!lastMsg) return;

  const bubble = lastMsg.querySelector('.bubble');

  const wrap = document.createElement("details");
  wrap.className = "chunks";
  wrap.open = false;

  const listHtml = chunks
    .map(
      (c) =>
        `<details class="chunk-item">
          <summary>${c.loc} <span class="score">(${c.score ? c.score.toFixed(2) : '0.00'})</span></summary>
          <div class="chunk-content">${c.chunk}</div>
        </details>`
    )
    .join("");

  wrap.innerHTML = `<summary>Relevant sources (${chunks.length})</summary><div class="chunk-list">${listHtml}</div>`;

  bubble.appendChild(wrap);
  scrollToBottom();
}

async function send() {
  const text = inputEl.value.trim();
  if (!text) return;

  append("You", text);
  inputEl.value = "";
  inputEl.style.height = 'auto'; // Reset height

  // Create assistant message placeholder
  const assistantDiv = document.createElement("div");
  assistantDiv.className = "msg assistant-msg";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  const meta = document.createElement("div");
  meta.className = "assistant-meta";

  const assistantText = document.createElement("div");
  assistantText.className = "assistant-text";
  // Add typing indicator
  assistantText.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';

  bubble.appendChild(meta);
  bubble.appendChild(assistantText);
  assistantDiv.appendChild(bubble);
  chatEl.appendChild(assistantDiv);
  scrollToBottom();

  let assistantMd = "";

  try {
    const res = await fetch("/chat-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        history: conversationHistory,
        hits: parseInt(hitsInput.value) || 5,
        k: parseInt(kInput.value) || 3,
        query_k: parseInt(queryKInput.value) || 3
      })
    });

    if (!res.ok || !res.body) {
      const err = await res.text();
      assistantText.textContent = `Error: ${err}`;
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const chunksCache = [];
    const queriesCache = [];
    let thinkingContent = "";
    let thinkingEl = null;
    let thinkingBody = null;
    let statusEl = null;
    let isAnswerPhase = false;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        if (!part.startsWith("data:")) continue;
        const data = part.replace("data:", "").trim();
        if (!data) continue;
        try {
          const evt = JSON.parse(data);
          if (evt.type === "status") {
            if (statusEl) statusEl.remove();
            statusEl = document.createElement("div");
            statusEl.className = "status-line";
            statusEl.textContent = evt.payload;
            meta.appendChild(statusEl);
            scrollToBottom();
            if (evt.payload.includes("Generating answer")) {
              isAnswerPhase = true;
            }
          } else if (evt.type === "thinking") {
            if (!isAnswerPhase) continue;

            if (!thinkingEl) {
              thinkingEl = document.createElement("div");
              thinkingEl.className = "thinking-section";

              const header = document.createElement("div");
              header.className = "thinking-header";
              header.innerHTML = `
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                Thinking Process
              `;
              header.onclick = () => {
                thinkingBody.classList.toggle("collapsed");
              };

              thinkingBody = document.createElement("div");
              thinkingBody.className = "thinking-content";

              thinkingEl.appendChild(header);
              thinkingEl.appendChild(thinkingBody);

              // Insert before assistantText
              bubble.insertBefore(thinkingEl, assistantText);
            }
            thinkingContent += evt.payload;
            thinkingBody.textContent = thinkingContent;
            scrollToBottom();
          } else if (evt.type === "queries") {
            queriesCache.splice(0, queriesCache.length, ...evt.payload);

            const details = document.createElement("details");
            details.className = "meta-details";
            const summary = document.createElement("summary");
            summary.textContent = `Queries (${evt.payload.length})`;
            details.appendChild(summary);

            const ul = document.createElement("ul");
            evt.payload.forEach((q) => {
              const li = document.createElement("li");
              li.textContent = q;
              ul.appendChild(li);
            });
            details.appendChild(ul);
            meta.appendChild(details);
            scrollToBottom();

            // Reset thinking for next phase
            thinkingEl = null;
            thinkingContent = "";
          } else if (evt.type === "chunks") {
            chunksCache.push(...evt.payload);

            // Display Context/Sources (locs only)
            const locs = [...new Set(evt.payload.map(c => c.loc))];

            const details = document.createElement("details");
            details.className = "meta-details";
            const summary = document.createElement("summary");
            summary.textContent = `Sources (${locs.length})`;
            details.appendChild(summary);

            const ul = document.createElement("ul");
            locs.forEach((loc) => {
              const li = document.createElement("li");
              li.textContent = loc;
              ul.appendChild(li);
            });
            details.appendChild(ul);
            meta.appendChild(details);
            scrollToBottom();

            // Reset thinking for next phase
            thinkingEl = null;
            thinkingContent = "";
          } else if (evt.type === "token") {
            assistantMd += evt.payload;
            renderMarkdown(assistantText, assistantMd);
            scrollToBottom();
          } else if (evt.type === "done") {
            if (statusEl) statusEl.remove();
            if (evt.payload && typeof evt.payload === "string") {
              assistantMd = evt.payload;
            }
            renderMarkdown(assistantText, assistantMd);
            if (chunksCache.length) appendChunksCollapsible(chunksCache);
            scrollToBottom();

            // Add this exchange to conversation history
            conversationHistory.push({ role: "user", content: text });
            conversationHistory.push({ role: "assistant", content: assistantMd });
            refreshStats();
          }
        } catch (e) {
          continue;
        }
      }
    }
  } catch (e) {
    assistantText.textContent = e?.message || "Request failed";
  }
}

sendBtn.addEventListener("click", send);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});
