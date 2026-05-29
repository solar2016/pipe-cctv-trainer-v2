// app.js — 全局工具函数
async function api(url, opts = {}) {
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  return resp.json();
}

// Health check
fetch('/health').then(r => r.json()).then(d => {
  const el = document.getElementById('health-status');
  if (el) el.textContent = `${d.samples} 个样本`;
}).catch(() => {});
