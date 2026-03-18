const jobsEl = document.getElementById('jobs');
const detailEl = document.getElementById('detail');
const form = document.getElementById('job-form');
const refreshBtn = document.getElementById('refresh-btn');
const helloBtn = document.getElementById('hello-btn');
const helloDisplayEl = document.getElementById('hello-display');
let selectedJobId = null;
let openDetailPanels = new Set();

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

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

function escapeHtml(text = '') {
  return text.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
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
  form.reset();
  await loadJobs();
  await loadDetail();
});

refreshBtn.addEventListener('click', async () => {
  await loadJobs();
  await loadDetail();
});

helloBtn.addEventListener('click', async () => {
  await loadHelloMessage();
});

setInterval(async () => {
  if (selectedJobId) {
    await loadJobs();
    await loadDetail();
  }
}, 3000);

loadJobs();
loadDetail();
window.runJob = runJob;
window.approveJob = approveJob;
