// prompts.js — Prompt 版本管理
(function() {
  let allPrompts = [];
  let selectedVersions = [];

  async function init() {
    await loadPrompts();
    await loadChangeLogs();
  }

  async function loadPrompts() {
    const data = await api('/api/prompts/details');
    allPrompts = data.prompts || [];
    renderPromptList(allPrompts);
  }

  async function loadChangeLogs() {
    const data = await api('/api/prompts/details');
    const logs = data.change_logs || [];
    renderChangeLogs(logs);
  }

  function renderPromptList(prompts) {
    // 活跃版本
    const active = prompts.find(p => p.is_active);
    if (active) {
      document.getElementById('active-prompt').innerHTML = `
        <div class="active-standard">
          <h3>当前活跃版本: ${active.version}</h3>
          <div style="margin-top:8px;font-size:12px;color:var(--text2)">
            创建: ${active.created_at} | 说明: ${active.reason || '无'} | ${active.prompt_length} 字符
          </div>
          <pre style="white-space:pre-wrap;font-size:12px;margin-top:8px;background:#fff;padding:8px;border-radius:4px;max-height:300px;overflow-y:auto;border:1px solid var(--border)">${active.prompt_preview || '(无内容)'}</pre>
        </div>`;
    }

    // 版本列表
    let html = '';
    prompts.forEach(p => {
      const activeClass = p.is_active ? 'style="border-left:3px solid var(--success)"' : '';
      const activeTag = p.is_active ? '<span style="background:var(--success);color:#fff;padding:1px 6px;border-radius:4px;font-size:10px;margin-left:8px">活跃</span>' : '';
      html += `<div class="standard-item" ${activeClass}>
        <div style="display:flex;align-items:center;gap:8px">
          <input type="checkbox" class="diff-check" data-version="${p.version}" onchange="window._onDiffCheck()">
          <div>
            <div class="std-name">${p.version}${activeTag}</div>
            <div class="std-meta">${p.created_at || ''} | ${p.reason || ''} | ${p.prompt_length} 字符</div>
          </div>
        </div>
        <div class="std-actions">
          ${!p.is_active ? `<button class="btn btn-sm btn-primary" onclick="window._activatePrompt('${p.version}')">激活</button>` : ''}
          <button class="btn btn-sm" onclick="window._viewPrompt('${p.version}')">查看</button>
        </div>
      </div>`;
    });
    document.getElementById('prompt-list').innerHTML = html || '<div class="empty-state">暂无版本</div>';

    // 添加对比按钮
    document.getElementById('prompt-list').insertAdjacentHTML('afterbegin',
      '<div style="margin-bottom:8px"><button class="btn btn-sm" id="btn-diff" onclick="window._compareSelected()" disabled>对比选中版本</button> <span style="font-size:11px;color:var(--text3)">勾选2个版本进行对比</span></div>'
    );
  }

  function renderChangeLogs(logs) {
    if (!logs.length) {
      document.getElementById('change-logs').innerHTML = '<div class="empty-state">暂无变更记录</div>';
      return;
    }
    let html = '';
    logs.forEach(log => {
      html += `<div class="standard-item">
        <div class="std-name">${log.version || ''}</div>
        <div class="std-meta">${log.timestamp || ''} | 基于: ${log.base_version || '未知'}</div>
        <div style="font-size:12px;color:var(--text2);margin-top:4px">
          维度: ${(log.dimensions || []).join(', ')} | 新增 ${log.additions?.length || 0} 段规则 | ${log.fewshot_count || 0} 个 fewshot 建议
        </div>`;
      if (log.additions && log.additions.length > 0) {
        html += `<details style="margin-top:6px"><summary style="font-size:11px;color:var(--brand);cursor:pointer">查看新增内容</summary>
          <pre style="white-space:pre-wrap;font-size:11px;background:#f5f7f9;padding:8px;border-radius:4px;margin-top:4px;max-height:200px;overflow-y:auto">${log.additions.join('\n\n')}</pre>
        </details>`;
      }
      html += '</div>';
    });
    document.getElementById('change-logs').innerHTML = html;
  }

  // 激活版本
  window._activatePrompt = async function(version) {
    try {
      const data = await api(`/api/prompts/${version}/activate`, { method: 'POST' });
      if (data.ok) {
        await loadPrompts();
        alert(`已激活: ${version}`);
      } else {
        alert(data.error || '激活失败');
      }
    } catch (e) {
      alert('激活失败: ' + e.message);
    }
  };

  // 查看 prompt 内容
  window._viewPrompt = async function(version) {
    try {
      const data = await api(`/api/prompts/${version}`);
      if (data.prompt_text) {
        // 用页面内区域展示，不弹新窗口
        let container = document.getElementById('prompt-viewer');
        if (!container) {
          document.getElementById('active-prompt').insertAdjacentHTML('afterend',
            '<div id="prompt-viewer" style="margin-bottom:24px"></div>');
          container = document.getElementById('prompt-viewer');
        }
        container.innerHTML = `
          <div class="defect-card" style="border:2px solid var(--brand)">
            <div class="dc-header">
              <span class="dc-code">${version}</span>
              <span class="dc-conf">${data.reason || ''}</span>
            </div>
            <div style="margin:8px 0;font-size:12px;color:var(--text2)">${data.created_at || ''} | ${data.prompt_text.length} 字符</div>
            <pre style="white-space:pre-wrap;font-size:12px;background:#f8f9fb;padding:12px;border-radius:6px;max-height:500px;overflow-y:auto;border:1px solid var(--border);line-height:1.6">${data.prompt_text}</pre>
            <button class="btn btn-sm" style="margin-top:8px" onclick="document.getElementById('prompt-viewer').innerHTML=''">关闭</button>
          </div>`;
        container.scrollIntoView({ behavior: 'smooth' });
      }
    } catch (e) {
      alert('加载失败: ' + e.message);
    }
  };

  // Diff 勾选
  window._onDiffCheck = function() {
    const checks = document.querySelectorAll('.diff-check:checked');
    const btn = document.getElementById('btn-diff');
    if (btn) btn.disabled = checks.length !== 2;
  };

  // 对比选中版本
  window._compareSelected = async function() {
    const checks = document.querySelectorAll('.diff-check:checked');
    if (checks.length !== 2) { alert('请选择2个版本'); return; }
    const versions = [...checks].map(c => c.dataset.version);

    try {
      const data = await api(`/api/prompts/diff?a=${versions[0]}&b=${versions[1]}`);
      renderDiff(data);
    } catch (e) {
      alert('对比失败: ' + e.message);
    }
  };

  function renderDiff(data) {
    let html = `<div class="defect-card">
      <div class="dc-header">
        <span class="dc-code">${data.version_a} → ${data.version_b}</span>
        <span class="dc-conf">${data.is_newer ? 'B 更新' : 'A 更新'}</span>
      </div>
      <div class="dc-grade">${data.length_a} 字符 → ${data.length_b} 字符 (新增${data.added_lines}行, 删除${data.removed_lines}行)</div>`;

    if (data.added && data.added.length > 0) {
      html += `<div style="margin-top:8px"><strong style="color:var(--success)">新增内容:</strong>
        <pre style="white-space:pre-wrap;font-size:12px;background:#f0f9f0;padding:8px;border-radius:4px;margin-top:4px;max-height:300px;overflow-y:auto;border:1px solid #c3e6cb">${data.added.join('\n')}</pre>
      </div>`;
    }

    if (data.removed && data.removed.length > 0) {
      html += `<div style="margin-top:8px"><strong style="color:var(--danger)">删除内容:</strong>
        <pre style="white-space:pre-wrap;font-size:12px;background:#fdf2f2;padding:8px;border-radius:4px;margin-top:4px;max-height:200px;overflow-y:auto;border:1px solid #f5c6cb">${data.removed.join('\n')}</pre>
      </div>`;
    }

    html += '</div>';
    document.getElementById('diff-result').innerHTML = html;
    document.getElementById('diff-section').style.display = '';
  }

  init();
})();
