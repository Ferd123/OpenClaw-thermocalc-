const jobsEl = document.getElementById('jobs');
const detailEl = document.getElementById('detail');
const form = document.getElementById('job-form');
const refreshBtn = document.getElementById('refresh-btn');
const helloBtn = document.getElementById('hello-btn');
const helloDisplayEl = document.getElementById('hello-display');

const sessionForm = document.getElementById('session-form');
const taskForm = document.getElementById('task-form');
const runForm = document.getElementById('run-form');
const refreshV2Btn = document.getElementById('refresh-v2-btn');
const sessionsListEl = document.getElementById('sessions-list');
const sessionDetailEl = document.getElementById('session-detail');
const tasksListEl = document.getElementById('tasks-list');
const taskDetailEl = document.getElementById('task-detail');
const providersListEl = document.getElementById('providers-list');
const modelsListEl = document.getElementById('models-list');
const metricsSummaryEl = document.getElementById('metrics-summary');

let selectedJobId = null;
let selectedSessionId = null;
let selectedTaskId = null;
let openDetailPanels = new Set();
let activeRunTabId = null;

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function escapeHtml(text = '') {
  return String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function parseCsvList(value) {
  return value.split(',').map(v => v.trim()).filter(Boolean);
}

function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '—';
  return value;
}

function activateTab(tabName) {
  document.querySelectorAll('.tab-button').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });
  document.querySelectorAll('.tab-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `tab-${tabName}`);
  });
}

// -----------------------------
// V2 UI
// -----------------------------

async function loadProviders() {
  const providers = await api('/api/v2/providers');
  providersListEl.innerHTML = providers.map(provider => `
    <div class="list-card compact">
      <div><strong>${escapeHtml(provider.name)}</strong> <span class="pill">${escapeHtml(provider.status)}</span></div>
      <div class="muted">auth: ${escapeHtml(provider.auth_type)}</div>
      <div class="muted">models: ${escapeHtml(provider.available_models.join(', '))}</div>
    </div>
  `).join('') || '<div class="muted">No providers loaded.</div>';
}

async function loadModels() {
  const models = await api('/api/v2/models');
  modelsListEl.innerHTML = models.map(model => `
    <div class="list-card compact">
      <div><strong>${escapeHtml(model.id)}</strong></div>
      <div class="muted">provider: ${escapeHtml(model.provider)} · cost: ${escapeHtml(model.cost_level)} · latency: ${escapeHtml(model.latency_class)}</div>
      <div class="muted">capabilities: ${escapeHtml(model.capabilities.join(', '))}</div>
    </div>
  `).join('') || '<div class="muted">No models loaded.</div>';
}

async function loadMetrics() {
  const metrics = await api('/api/v2/metrics/summary');
  metricsSummaryEl.innerHTML = `
    <div class="stat-card"><div class="muted">Sessions</div><strong>${formatNumber(metrics.sessions)}</strong></div>
    <div class="stat-card"><div class="muted">Tasks</div><strong>${formatNumber(metrics.tasks)}</strong></div>
    <div class="stat-card"><div class="muted">Runs</div><strong>${formatNumber(metrics.runs)}</strong></div>
    <div class="stat-card"><div class="muted">Total cost</div><strong>${formatNumber(metrics.total_cost)}</strong></div>
    <div class="stat-card"><div class="muted">Avg latency ms</div><strong>${formatNumber(metrics.avg_latency_ms)}</strong></div>
  `;
}

async function loadSessions() {
  const sessions = await api('/api/v2/sessions');
  sessionsListEl.innerHTML = sessions.map(session => `
    <div class="list-card ${session.id === selectedSessionId ? 'active' : ''}" data-session-id="${session.id}">
      <div><strong>#${session.id}</strong> ${escapeHtml(session.title)}</div>
      <div class="muted">${escapeHtml(session.work_mode)} · ${escapeHtml(session.output_mode)}</div>
      <div class="muted">default: ${escapeHtml(session.active_model || '—')}</div>
      <div class="muted">created: ${escapeHtml(session.created_at)}</div>
    </div>
  `).join('') || '<div class="muted">No sessions yet.</div>';

  sessionsListEl.querySelectorAll('[data-session-id]').forEach(card => {
    card.addEventListener('click', async () => {
      selectedSessionId = Number(card.dataset.sessionId);
      selectedTaskId = null;
      activeRunTabId = null;
      await loadSessions();
      await loadSessionDetail();
      await loadTasks();
    });
  });
}

async function loadSessionDetail() {
  if (!selectedSessionId) {
    sessionDetailEl.innerHTML = '<div class="muted">Select a session.</div>';
    return;
  }
  const session = await api(`/api/v2/sessions/${selectedSessionId}`);
  const tasks = await api(`/api/v2/tasks?session_id=${selectedSessionId}`);
  sessionDetailEl.innerHTML = `
    <div class="detail-card">
      <h3>${escapeHtml(session.title)}</h3>
      <div class="muted">mode: ${escapeHtml(session.work_mode)} · output: ${escapeHtml(session.output_mode)}</div>
      <div class="muted">default model: ${escapeHtml(session.active_model || '—')}</div>
      <div class="muted">context refs: ${escapeHtml((session.context_refs || []).join(', ') || '—')}</div>
      <div class="muted">tasks: ${tasks.length}</div>
      <div class="muted">updated: ${escapeHtml(session.updated_at)}</div>
    </div>
  `;
}

async function loadTasks() {
  if (!selectedSessionId) {
    tasksListEl.innerHTML = '<div class="muted">Select a session first.</div>';
    taskDetailEl.innerHTML = '<div class="muted">Select a task.</div>';
    return;
  }
  const tasks = await api(`/api/v2/tasks?session_id=${selectedSessionId}`);
  tasksListEl.innerHTML = tasks.map(task => `
    <div class="list-card ${task.id === selectedTaskId ? 'active' : ''}" data-task-id="${task.id}">
      <div><strong>#${task.id}</strong> ${escapeHtml(task.title)}</div>
      <div class="muted">${escapeHtml(task.type)} · <span class="pill">${escapeHtml(task.status)}</span></div>
      <div class="muted">runs requested: ${escapeHtml(String(task.requested_models.length || 0))}</div>
      <div class="muted">selected run: ${escapeHtml(String(task.selected_run_id || '—'))}</div>
    </div>
  `).join('') || '<div class="muted">No tasks yet.</div>';

  tasksListEl.querySelectorAll('[data-task-id]').forEach(card => {
    card.addEventListener('click', async () => {
      selectedTaskId = Number(card.dataset.taskId);
      const task = await api(`/api/v2/tasks/${selectedTaskId}`);
      activeRunTabId = task.selected_run_id || (task.runs[0] && task.runs[0].id) || null;
      await loadTasks();
      await loadTaskDetail();
    });
  });

  if (selectedTaskId) {
    const currentExists = tasks.some(task => task.id === selectedTaskId);
    if (!currentExists) {
      selectedTaskId = null;
      activeRunTabId = null;
      taskDetailEl.innerHTML = '<div class="muted">Select a task.</div>';
    }
  }
}

async function loadTaskDetail() {
  if (!selectedTaskId) {
    taskDetailEl.innerHTML = '<div class="muted">Select a task.</div>';
    return;
  }
  const task = await api(`/api/v2/tasks/${selectedTaskId}`);
  const runs = task.runs || [];
  if (!activeRunTabId && runs.length) activeRunTabId = task.selected_run_id || runs[0].id;
  const activeRun = runs.find(run => run.id === activeRunTabId) || runs[0] || null;

  const runTabs = runs.map(run => `
    <button class="run-tab ${run.id === (activeRun && activeRun.id) ? 'active' : ''}" data-run-tab-id="${run.id}">
      ${escapeHtml(run.model)}
    </button>
  `).join('') || '<div class="muted">No runs yet.</div>';

  const runDetail = activeRun ? `
    <div class="detail-card">
      <div class="section-header">
        <h3>${escapeHtml(activeRun.model)}</h3>
        <button type="button" class="ghost" onclick="selectRun(${task.id}, ${activeRun.id})">Set as selected</button>
      </div>
      <div class="muted">provider: ${escapeHtml(activeRun.provider)} · status: <span class="pill">${escapeHtml(activeRun.status)}</span></div>
      <div class="metrics-list">
        <div><span class="muted">latency</span><strong>${formatNumber(activeRun.latency_ms)}</strong></div>
        <div><span class="muted">cost</span><strong>${formatNumber(activeRun.cost)}</strong></div>
        <div><span class="muted">tokens in</span><strong>${formatNumber(activeRun.tokens_in)}</strong></div>
        <div><span class="muted">tokens out</span><strong>${formatNumber(activeRun.tokens_out)}</strong></div>
        <div><span class="muted">created</span><strong>${formatNumber(activeRun.created_at)}</strong></div>
      </div>
      <details open>
        <summary>Prompt snapshot</summary>
        <pre>${escapeHtml(activeRun.prompt_snapshot || '')}</pre>
      </details>
      <details open>
        <summary>Output</summary>
        <pre>${escapeHtml(activeRun.output || '')}</pre>
      </details>
      ${activeRun.error_message ? `<details open><summary>Error</summary><pre>${escapeHtml(activeRun.error_message)}</pre></details>` : ''}
    </div>
  ` : '<div class="muted">Create a run for this task.</div>';

  taskDetailEl.innerHTML = `
    <div class="detail-card">
      <h3>${escapeHtml(task.title)} <span class="pill">${escapeHtml(task.status)}</span></h3>
      <div class="muted">type: ${escapeHtml(task.type)} · priority: ${escapeHtml(task.priority)} · routing: ${escapeHtml(task.routing_strategy)}</div>
      <div class="muted">selected run: ${escapeHtml(String(task.selected_run_id || '—'))}</div>
      <div class="muted">tags: ${escapeHtml(task.tags.join(', ') || '—')}</div>
      <pre>${escapeHtml(task.input)}</pre>
    </div>
    <div class="run-tabs">${runTabs}</div>
    ${runDetail}
  `;

  taskDetailEl.querySelectorAll('[data-run-tab-id]').forEach(btn => {
    btn.addEventListener('click', () => {
      activeRunTabId = Number(btn.dataset.runTabId);
      loadTaskDetail();
    });
  });
}

async function selectRun(taskId, runId) {
  await api(`/api/v2/tasks/${taskId}/select-run`, { method: 'POST', body: JSON.stringify({ run_id: runId }) });
  activeRunTabId = runId;
  await loadTasks();
  await loadTaskDetail();
  await loadMetrics();
}

// -----------------------------
// Legacy MVP UI
// -----------------------------

async function loadJobs() {
  const jobs = await api('/api/jobs');
  jobsEl.innerHTML = jobs.map(job => `
    <div class="job-card ${job.id === selectedJobId ? 'active' : ''}" data-id="${job.id}">
      <div><strong>#${job.id}</strong> ${job.title}</div>
      <div class="muted">${job.status} · approval: ${job.requires_approval ? 'yes' : 'no'}</div>
    </div>
  `).join('') || '<div class="muted">No jobs yet.</div>';

  jobsEl.querySelectorAll('.job-card').forEach(card => {
    card.addEventListener('click', () => {
      selectedJobId = Number(card.dataset.id);
      loadJobs().then(loadDetail);
    });
  });
}

function captureOpenPanels() {
  openDetailPanels = new Set(
    [...detailEl.querySelectorAll('details[data-panel-key]')]
      .filter((el) => el.open)
      .map((el) => el.dataset.panelKey)
  );
}

function bindDetailPanelPersistence() {
  detailEl.querySelectorAll('details[data-panel-key]').forEach((el) => {
    if (openDetailPanels.has(el.dataset.panelKey)) {
      el.open = true;
    }
    el.addEventListener('toggle', () => {
      if (el.open) openDetailPanels.add(el.dataset.panelKey);
      else openDetailPanels.delete(el.dataset.panelKey);
    });
  });
}

async function loadDetail() {
  if (!selectedJobId) {
    detailEl.innerHTML = '<div class="muted">Select a job.</div>';
    return;
  }
  captureOpenPanels();
  const job = await api(`/api/jobs/${selectedJobId}`);
  detailEl.innerHTML = `
    <h3>${escapeHtml(job.title)} <span class="pill">${job.status}</span></h3>
    <p>${escapeHtml(job.description || '')}</p>
    <div class="actions">
      <button onclick="runJob(${job.id})">Run</button>
      ${job.status === 'waiting_approval' ? `<button onclick="approveJob(${job.id}, true)">Approve step 2</button><button class="danger" onclick="approveJob(${job.id}, false)">Reject</button>` : ''}
    </div>
    <h4>Steps</h4>
    ${job.steps.map(step => `
      <div class="step">
        <div><strong>${step.step_order}. ${escapeHtml(step.name)}</strong> — ${step.agent} — <span class="pill">${step.status}</span></div>
        <details data-panel-key="step-${step.step_order}-prompt"><summary>Prompt</summary><pre>${escapeHtml(step.prompt)}</pre></details>
        <details data-panel-key="step-${step.step_order}-output"><summary>Output</summary><pre>${escapeHtml(step.output || '')}</pre></details>
      </div>
    `).join('')}
    <h4>Logs</h4>
    <pre>${escapeHtml(job.logs.map(l => `[${l.created_at}] ${l.level.toUpperCase()}${l.step_order ? ` step-${l.step_order}` : ''}: ${l.message}`).join('\n'))}</pre>
    <h4>Final result</h4>
    <pre>${escapeHtml(job.final_result || '')}</pre>
  `;
  bindDetailPanelPersistence();
}

async function runJob(id) {
  await api(`/api/jobs/${id}/run`, { method: 'POST', body: JSON.stringify({ reset_failed_steps: true }) });
  await loadJobs();
  await loadDetail();
}

async function approveJob(id, approved) {
  await api(`/api/jobs/${id}/approve`, { method: 'POST', body: JSON.stringify({ approved }) });
  await loadJobs();
  setTimeout(loadDetail, 500);
}

async function loadHelloMessage() {
  const data = await api('/api/hello');
  helloDisplayEl.textContent = data.message;
}

// -----------------------------
// Form handlers
// -----------------------------

sessionForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    title: sessionForm.title.value,
    work_mode: sessionForm.work_mode.value,
    output_mode: sessionForm.output_mode.value,
    active_model: sessionForm.active_model.value || null,
    context_refs: parseCsvList(sessionForm.context_refs.value),
  };
  const session = await api('/api/v2/sessions', { method: 'POST', body: JSON.stringify(payload) });
  selectedSessionId = session.id;
  await loadSessions();
  await loadSessionDetail();
  await loadTasks();
  await loadMetrics();
});

taskForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!selectedSessionId) {
    alert('Select a session first.');
    return;
  }
  const payload = {
    session_id: selectedSessionId,
    title: taskForm.title.value,
    type: taskForm.type.value,
    input: taskForm.input.value,
    tags: parseCsvList(taskForm.tags.value),
    priority: 'normal',
    routing_strategy: taskForm.routing_strategy.value,
    requested_models: parseCsvList(taskForm.requested_models.value),
    approval_required: taskForm.approval_required.checked,
  };
  const task = await api('/api/v2/tasks', { method: 'POST', body: JSON.stringify(payload) });
  selectedTaskId = task.id;
  activeRunTabId = null;
  await loadTasks();
  await loadTaskDetail();
  await loadMetrics();
});

runForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!selectedTaskId) {
    alert('Select a task first.');
    return;
  }
  const payload = {
    provider: runForm.provider.value,
    model: runForm.model.value,
    prompt_snapshot: runForm.prompt_snapshot.value,
    output: runForm.output.value || null,
    error_message: runForm.error_message.value || null,
    latency_ms: runForm.latency_ms.value ? Number(runForm.latency_ms.value) : null,
    cost: runForm.cost.value ? Number(runForm.cost.value) : null,
    tokens_in: runForm.tokens_in.value ? Number(runForm.tokens_in.value) : null,
    tokens_out: runForm.tokens_out.value ? Number(runForm.tokens_out.value) : null,
    score: runForm.score.value ? Number(runForm.score.value) : null,
    status: runForm.status.value,
  };
  const response = await api(`/api/v2/tasks/${selectedTaskId}/runs`, { method: 'POST', body: JSON.stringify(payload) });
  activeRunTabId = response.run_id;
  await loadTasks();
  await loadTaskDetail();
  await loadMetrics();
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = {
    title: form.title.value,
    description: form.description.value,
    requires_approval: form.requires_approval.checked,
    steps: [
      { name: form.step1_name.value, agent: form.step1_agent.value, prompt: form.step1_prompt.value },
      { name: form.step2_name.value, agent: form.step2_agent.value, prompt: form.step2_prompt.value },
    ],
  };
  const job = await api('/api/jobs', { method: 'POST', body: JSON.stringify(data) });
  selectedJobId = job.id;
  await loadJobs();
  await loadDetail();
});

refreshBtn.addEventListener('click', async () => {
  await loadJobs();
  await loadDetail();
});

refreshV2Btn.addEventListener('click', async () => {
  await bootstrapV2();
});

helloBtn.addEventListener('click', async () => {
  await loadHelloMessage();
});

document.querySelectorAll('.tab-button').forEach(btn => {
  btn.addEventListener('click', () => activateTab(btn.dataset.tab));
});

async function bootstrapV2() {
  await Promise.all([loadProviders(), loadModels(), loadMetrics(), loadSessions()]);
  if (selectedSessionId) {
    await loadSessionDetail();
    await loadTasks();
    if (selectedTaskId) await loadTaskDetail();
  }
}

setInterval(async () => {
  if (selectedJobId) {
    await loadJobs();
    await loadDetail();
  }
  if (selectedSessionId) {
    await loadMetrics();
    await loadTasks();
    if (selectedTaskId) await loadTaskDetail();
  }
}, 4000);

bootstrapV2();
loadJobs();
loadDetail();
window.runJob = runJob;
window.approveJob = approveJob;
window.selectRun = selectRun;
