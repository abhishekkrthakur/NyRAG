const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const statsEl = document.getElementById("corpus-stats");

// Settings Modal
const settingsBtn = document.getElementById("settings-btn");
const modal = document.getElementById("settings-modal");
const closeBtn = document.querySelector(".close-btn");
const saveBtn = document.getElementById("save-settings");

settingsBtn.onclick = () => modal.style.display = "block";
closeBtn.onclick = () => modal.style.display = "none";
saveBtn.onclick = () => modal.style.display = "none";

// Crawl Modal
const crawlBtn = document.getElementById("crawl-btn");
const crawlModal = document.getElementById("crawl-modal");
const closeCrawlBtn = document.querySelector(".close-crawl-btn");
const startCrawlBtn = document.getElementById("start-crawl-btn");
const terminalLogs = document.getElementById("terminal-logs");
const terminalStatus = document.getElementById("terminal-status");
const yamlContainer = document.getElementById("interactive-yaml-container");
const exampleSelect = document.getElementById("example-select");

// Internal Config State
let currentConfig = {};
let configOptions = {}; // Schema loaded from API
let exampleConfigs = {}; // Example configs from API

// Fallback Default if file is empty
const FALLBACK_CONFIG = {
  name: "new-project",
  mode: "web",
  start_loc: "https://example.com",
  exclude: [],
  crawl_params: {
    respect_robots_txt: true,
    follow_subdomains: true,
    user_agent_type: "chrome",
    aggressive: false,
    strict_mode: false,
    custom_user_agent: "",
    allowed_domains: []
  },
  doc_params: {
    recursive: true,
    include_hidden: false,
    follow_symlinks: false,
    max_file_size_mb: 10,
    file_extensions: [".pdf", ".docx", ".txt", ".md"]
  },
  rag_params: {
    embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
    embedding_dim: 384,
    chunk_size: 1024,
    chunk_overlap: 50,
    distance_metric: "angular"
  },
  llm_config: {
    base_url: "https://openrouter.ai/api/v1",
    model: "gpt-4",
    api_key: ""
  }
};

// =========================================================================
// RENDERER: The Core "Magic" Function
// =========================================================================
function renderConfigEditor() {
  yamlContainer.innerHTML = '';
  if (!configOptions || Object.keys(configOptions).length === 0) {
    yamlContainer.innerHTML = '<div style="color: #666; padding: 1rem;">Loading options...</div>';
    return;
  }

  // Recursive render function
  function renderField(key, schemaItem, value, indentLevel, parentObj) {
    const line = document.createElement('div');
    line.className = 'yaml-line';

    // Indentation
    const indentSpan = document.createElement('span');
    indentSpan.className = 'yaml-indent';
    indentSpan.innerHTML = '&nbsp;'.repeat(indentLevel * 2);
    line.appendChild(indentSpan);

    // Key
    const keySpan = document.createElement('span');
    keySpan.className = 'yaml-key';
    keySpan.textContent = key + ':';
    line.appendChild(keySpan);

    // Value Control
    if (schemaItem.type === 'nested') {
      yamlContainer.appendChild(line);

      // Ensure object exists
      if (value === undefined || value === null) {
        // If it's a nested object but missing in config, maybe init it?
        // For now, let's just skip unless we want to force it.
        // But usually deepMerge handles init.
        return;
      }

      const fields = schemaItem.fields || {};
      Object.keys(fields).forEach(subKey => {
        const subSchema = fields[subKey];
        renderField(subKey, subSchema, value[subKey], indentLevel + 1, value);
      });
      return;
    }

    if (schemaItem.type === 'string' || schemaItem.type === 'number') {
      const input = document.createElement('input');
      input.type = schemaItem.type === 'number' ? 'number' : (schemaItem.masked ? 'password' : 'text');
      input.value = value !== undefined ? value : '';
      input.className = 'yaml-input';

      // Dynamic Placeholder
      if (key === 'start_location') {
        input.placeholder = currentConfig.mode === 'web' ? 'https://example.com' : '/path/to/docs';
      } else {
        input.placeholder = 'null';
      }

      input.onchange = (e) => {
        let val = e.target.value;
        if (schemaItem.type === 'number') val = parseFloat(val);
        parentObj[key] = val;
      };
      line.appendChild(input);
    } else if (schemaItem.type === 'boolean') {
      const select = document.createElement('select');
      select.className = 'yaml-select ' + (value ? 'bool-true' : 'bool-false');

      const optTrue = new Option('true', 'true');
      const optFalse = new Option('false', 'false');
      select.add(optTrue);
      select.add(optFalse);
      select.value = !!value;

      select.onchange = (e) => {
        const val = e.target.value === 'true';
        parentObj[key] = val;
        select.className = 'yaml-select ' + (val ? 'bool-true' : 'bool-false');
      };
      line.appendChild(select);
    } else if (schemaItem.type === 'select') {
      const select = document.createElement('select');
      select.className = 'yaml-select';
      (schemaItem.options || []).forEach(optVal => {
        select.add(new Option(optVal, optVal));
      });
      select.value = value || schemaItem.options[0];
      select.onchange = async (e) => {
        parentObj[key] = e.target.value;
        // TRIGGER RE-FETCH if mode changes
        if (key === 'mode') {
          await loadSchema(e.target.value);
          renderConfigEditor();
        }
      };
      line.appendChild(select);
    } else if (schemaItem.type === 'list') {
      yamlContainer.appendChild(line);

      const list = Array.isArray(value) ? value : [];
      parentObj[key] = list; // ensure array reference

      const listContainer = document.createElement('div');

      const renderList = () => {
        listContainer.innerHTML = '';
        list.forEach((item, idx) => {
          const itemLine = document.createElement('div');
          itemLine.className = 'yaml-line';

          const iSpan = document.createElement('span');
          iSpan.className = 'yaml-indent';
          iSpan.innerHTML = '&nbsp;'.repeat((indentLevel + 1) * 2);

          const dash = document.createElement('span');
          dash.className = 'yaml-dash';
          dash.textContent = '- ';

          const input = document.createElement('input');
          input.className = 'yaml-input';
          input.value = item;
          // width handled by flex
          input.onchange = (e) => {
            list[idx] = e.target.value;
          };

          const delBtn = document.createElement('span');
          delBtn.innerHTML = '&times;';
          delBtn.style.color = '#ff5555';
          delBtn.style.cursor = 'pointer';
          delBtn.style.marginLeft = '8px';
          delBtn.onclick = () => {
            list.splice(idx, 1);
            renderList();
          };

          itemLine.appendChild(iSpan);
          itemLine.appendChild(dash);
          itemLine.appendChild(input);
          itemLine.appendChild(delBtn);
          listContainer.appendChild(itemLine);
        });

        const newLine = document.createElement('div');
        newLine.className = 'yaml-line';
        const niSpan = document.createElement('span');
        niSpan.className = 'yaml-indent';
        niSpan.innerHTML = '&nbsp;'.repeat((indentLevel + 1) * 2);

        const nDash = document.createElement('span');
        nDash.className = 'yaml-dash';
        nDash.textContent = '+ ';
        nDash.style.opacity = '0.5';
        nDash.style.cursor = 'pointer';

        const nInput = document.createElement('input');
        nInput.className = 'yaml-input';
        nInput.placeholder = '(add item)';
        nInput.onchange = (e) => {
          if (e.target.value) {
            list.push(e.target.value);
            renderList();
            nInput.focus();
          }
        };

        newLine.appendChild(niSpan);
        newLine.appendChild(nDash);
        newLine.appendChild(nInput);
        listContainer.appendChild(newLine);
      };

      renderList();
      yamlContainer.appendChild(listContainer);
      return;
    }

    yamlContainer.appendChild(line);
  }

  Object.keys(configOptions).forEach(key => {
    // Top-level render
    renderField(key, configOptions[key], currentConfig[key], 0, currentConfig);
  });
}

// API Interactions
async function loadSchema(mode) {
  try {
    const res = await fetch(`/config/options?mode=${mode}`);
    configOptions = await res.json();
  } catch (e) {
    console.error("Failed to load schema options", e);
    terminalLogs.textContent = "Error loading schema: " + e.message;
  }
}

async function loadProjectConfig() {
  try {
    const res = await fetch("/config");
    const data = await res.json();

    let parsed = {};
    if (data.content) {
      parsed = jsyaml.load(data.content);
    }

    // Merge with fallback to ensure structure
    currentConfig = deepMerge(JSON.parse(JSON.stringify(FALLBACK_CONFIG)), parsed);

    // Determine mode to load correct schema
    const mode = currentConfig.mode || "web";
    await loadSchema(mode);

    renderConfigEditor();
    terminalStatus.textContent = "Ready";
    terminalStatus.style.color = "var(--accent-color)";

  } catch (e) {
    console.error("Failed to load project config", e);
    terminalStatus.textContent = "Load Error";
    terminalStatus.style.color = "#ef4444";
  }
}

async function saveProjectConfig() {
  const yamlStr = jsyaml.dump(currentConfig);
  await fetch("/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: yamlStr })
  });
}

// Load and populate example configs
async function loadExamples() {
  try {
    const res = await fetch("/config/examples");
    exampleConfigs = await res.json();

    // Populate dropdown
    exampleSelect.innerHTML = '<option value="">-- Select an example --</option>';
    Object.keys(exampleConfigs).forEach(name => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      exampleSelect.appendChild(opt);
    });
  } catch (e) {
    console.error("Failed to load examples", e);
  }
}

// Handle example selection
exampleSelect.onchange = async () => {
  const name = exampleSelect.value;
  if (!name || !exampleConfigs[name]) return;

  try {
    const parsed = jsyaml.load(exampleConfigs[name]);
    // Merge: start with defaults, then override with example values
    currentConfig = deepMerge(JSON.parse(JSON.stringify(FALLBACK_CONFIG)), parsed);

    const mode = currentConfig.mode || "web";
    await loadSchema(mode);
    renderConfigEditor();

    terminalStatus.textContent = `Loaded: ${name}`;
    terminalStatus.style.color = "#10b981";
  } catch (e) {
    console.error("Failed to parse example", e);
  }
};

// Crawl Modal Logic
crawlBtn.onclick = () => {
  crawlModal.style.display = "block";
  loadExamples();
  loadProjectConfig();
};
closeCrawlBtn.onclick = () => crawlModal.style.display = "none";
window.onclick = (e) => {
  if (e.target == modal) modal.style.display = "none";
  if (e.target == crawlModal) crawlModal.style.display = "none";
};

startCrawlBtn.onclick = async () => {
  terminalLogs.textContent = "";
  terminalStatus.textContent = "Saving...";
  terminalStatus.style.color = "#fbbf24"; // Amber

  try {
    // 1. Save Config First
    await saveProjectConfig();

    terminalStatus.textContent = "Running...";
    terminalStatus.style.color = "var(--accent-color)";

    // 2. Start Crawl with the YAML content
    // We send the YAML content directly to be safe, or we could tell backend to read file.
    // Given the previous pattern, let's send the content to ensure sync.
    const yamlStr = jsyaml.dump(currentConfig);

    const res = await fetch("/crawl/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config_yaml: yamlStr })
    });

    if (!res.ok) {
      terminalLogs.textContent += `Error starting crawl: ${res.statusText}\n`;
      terminalStatus.textContent = "Failed";
      terminalStatus.style.color = "#ef4444";
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const text = decoder.decode(value);
      terminalLogs.textContent += text;
      terminalLogs.scrollTop = terminalLogs.scrollHeight;
    }

    terminalStatus.textContent = "Completed";
    terminalStatus.style.color = "#10b981"; // Green

  } catch (e) {
    terminalLogs.textContent += `Connection error: ${e.message}\n`;
    terminalStatus.textContent = "Error";
    terminalStatus.style.color = "#ef4444";
  }
};

// Simple Deep Merge Helper
// (Same as before)
function deepMerge(target, source) {
  if (!source) return target;
  for (const key in source) {
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
      if (!target[key]) Object.assign(target, { [key]: {} });
      deepMerge(target[key], source[key]);
    } else {
      Object.assign(target, { [key]: source[key] });
    }
  }
  return target;
}

// ... Chat Message Logic (Unchanged)
async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text) return;

  addMessage("user", text);
  inputEl.value = "";

  const assistantId = addMessage("assistant", "...");
  const assistantContent = document.getElementById(assistantId).querySelector(".assistant-text");

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }) // Updated key to match ChatRequest model
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullResponse = "";

    assistantContent.innerHTML = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      fullResponse += chunk;
      assistantContent.innerHTML = DOMPurify.sanitize(marked.parse(fullResponse));
      chatEl.scrollTop = chatEl.scrollHeight;
    }

  } catch (e) {
    assistantContent.textContent = "Error: " + e.message;
  }
}

sendBtn.onclick = sendMessage;
inputEl.onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
};

function addMessage(role, text) {
  const id = "msg-" + Date.now();
  const div = document.createElement("div");
  div.className = `msg ${role}-msg`;
  div.id = id;

  div.innerHTML = `
        <div class="bubble">
            <div class="assistant-text">${role === 'user' ? text : '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>'}</div>
        </div>
    `;
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return id;
}

fetch("/stats").then(r => r.json()).then(data => {
  if (data.documents) {
    statsEl.textContent = `${data.documents} documents indexed`;
  }
}).catch(() => { });
