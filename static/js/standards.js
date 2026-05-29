// standards.js — 标准文档管理
(function() {
  let standards = [];

  async function loadStandards() {
    const data = await api('/api/standards');
    standards = data.standards || [];
    renderList();
    loadActive();
  }

  async function loadActive() {
    const data = await api('/api/standards/active');
    const info = document.getElementById('active-standard-info');
    if (data.standard) {
      info.innerHTML = `<strong>${data.standard.name}</strong> (${data.standard.defect_count} 个缺陷类型) — 上传于 ${data.standard.uploaded_at}`;
    } else {
      info.textContent = '未激活任何标准';
    }
  }

  function renderList() {
    const el = document.getElementById('standard-list');
    if (!standards.length) {
      el.innerHTML = '<div style="color:var(--text3);text-align:center;padding:40px">暂无标准文档，请上传</div>';
      return;
    }
    el.innerHTML = standards.map(s => `
      <div class="standard-item" data-id="${s.id}">
        <div class="std-name">${s.name || s.source_file}</div>
        <div class="std-meta">${s.defect_count} 个缺陷类型 · ${s.uploaded_at} · ${s.status}</div>
        <div class="std-actions">
          <button class="btn btn-sm btn-primary" onclick="activateStandard('${s.id}')">激活</button>
          <button class="btn btn-sm" onclick="viewStandard('${s.id}')">查看</button>
          <button class="btn btn-sm btn-danger" onclick="deleteStandard('${s.id}')">删除</button>
        </div>
      </div>
    `).join('');
  }

  window.activateStandard = async (id) => {
    await api(`/api/standards/${id}/activate`, { method: 'POST' });
    loadActive();
    alert('标准已激活');
  };

  window.viewStandard = async (id) => {
    const data = await api(`/api/standards/${id}`);
    const modal = document.getElementById('standard-modal');
    document.getElementById('modal-title').textContent = data.name || id;
    const body = document.getElementById('modal-body');

    let html = '<h4>缺陷类型</h4>';
    (data.defects || []).forEach(d => {
      html += `<div class="defect-card">
        <div class="dc-header"><span class="dc-code">${d.code} ${d.name}</span><span class="dc-conf">${d.category}</span></div>
        <div style="font-size:12px;color:var(--text2);margin-top:4px">${d.definition || ''}</div>
        ${d.grades ? Object.entries(d.grades).map(([g, v]) => {
          const desc = typeof v === 'string' ? v : (v.description || '');
          const score = typeof v === 'object' ? v.score : '';
          return `<div style="font-size:12px;margin-top:2px">${g}级: ${desc}${score ? ` (${score}分)` : ''}</div>`;
        }).join('') : ''}
      </div>`;
    });

    if (data.evaluation_formulas) {
      html += '<h4 style="margin-top:16px">评估公式</h4>';
      html += `<pre style="font-size:12px;background:#f5f7f9;padding:8px;border-radius:4px;overflow-x:auto">${JSON.stringify(data.evaluation_formulas, null, 2)}</pre>`;
    }

    body.innerHTML = html;
    modal.style.display = '';
  };

  window.deleteStandard = async (id) => {
    if (!confirm('确定删除此标准？')) return;
    await api(`/api/standards/${id}`, { method: 'DELETE' });
    loadStandards();
  };

  document.getElementById('btn-close-modal').onclick = () => {
    document.getElementById('standard-modal').style.display = 'none';
  };

  // Upload
  document.getElementById('btn-upload-standard').onclick = () => {
    document.getElementById('standard-file-input').click();
  };

  document.getElementById('standard-file-input').onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    const resp = await fetch('/api/standards/upload', { method: 'POST', body: formData });
    const data = await resp.json();
    if (data.ok) {
      alert('标准文档已上传并解析');
      loadStandards();
    } else {
      alert(data.error || '上传失败');
    }
    e.target.value = '';
  };

  loadStandards();
})();
