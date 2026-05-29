// evaluation.js — 评测 + 报告 + Agent + 优先级 + 优化 + 回归验证
(function() {
  let currentEvalId = null;
  let currentReport = null;

  // 自动获取最新评测ID
  async function ensureEvalId() {
    if (currentEvalId) return currentEvalId;
    try {
      const list = await api('/api/evaluations');
      const evals = list.evaluations || [];
      if (evals.length > 0) {
        currentEvalId = evals[0].id;
        return currentEvalId;
      }
    } catch(e) {}
    return null;
  }

  // 运行评测
  document.getElementById('btn-run-eval').onclick = async () => {
    document.getElementById('btn-run-eval').disabled = true;
    document.getElementById('btn-run-eval').textContent = '评测中...';
    try {
      const data = await api('/api/evaluate/run', { method: 'POST', body: '{}' });
      if (data.ok) {
        currentEvalId = data.evaluation_id;
        document.getElementById('stat-total').textContent = data.total || 0;
        document.getElementById('stat-accuracy').textContent = ((data.type_accuracy || 0) * 100).toFixed(1) + '%';
        document.getElementById('stat-grade').textContent = ((data.grade_accuracy || 0) * 100).toFixed(1) + '%';
        document.getElementById('stat-unknown').textContent = ((data.unknown_rate || 0) * 100).toFixed(1) + '%';
        document.getElementById('eval-summary').style.display = '';
        loadReportList();
      } else {
        alert(data.error || '评测失败');
      }
    } catch (e) {
      alert('评测失败: ' + e.message);
    }
    document.getElementById('btn-run-eval').disabled = false;
    document.getElementById('btn-run-eval').textContent = '运行评测';
  };

  // 生成报告
  document.getElementById('btn-generate-report').onclick = async () => {
    document.getElementById('btn-generate-report').disabled = true;
    document.getElementById('btn-generate-report').textContent = '生成中...';
    try {
      const body = currentEvalId ? JSON.stringify({ evaluation_id: currentEvalId }) : '{}';
      const data = await api('/api/report/generate', { method: 'POST', body });
      if (data.ok) {
        currentReport = data.report;
        currentEvalId = data.report.evaluation_id;
        renderReport(data.report);
      } else {
        alert(data.error || '报告生成失败');
      }
    } catch (e) {
      alert('报告生成失败: ' + e.message);
    }
    document.getElementById('btn-generate-report').disabled = false;
    document.getElementById('btn-generate-report').textContent = '生成报告';
  };

  // Agent 分析
  document.getElementById('btn-run-agent').onclick = async () => {
    if (!currentEvalId) await ensureEvalId();
    if (!currentEvalId) { alert('没有评测数据，请先运行评测'); return; }
    document.getElementById('btn-run-agent').disabled = true;
    document.getElementById('btn-run-agent').textContent = '分析中...';
    try {
      const data = await api(`/api/report/agent/${currentEvalId}`);
      if (data.ok) renderAgentResults(data.agent_results);
      else alert(data.error || 'Agent 分析失败');
    } catch (e) { alert('Agent 分析失败: ' + e.message); }
    document.getElementById('btn-run-agent').disabled = false;
    document.getElementById('btn-run-agent').textContent = 'Agent 分析';
  };

  // 优先级分析（大模型）
  document.getElementById('btn-show-priorities').onclick = async () => {
    if (!currentEvalId) await ensureEvalId();
    if (!currentEvalId) { alert('没有评测数据，请先运行评测'); return; }
    document.getElementById('btn-show-priorities').disabled = true;
    document.getElementById('btn-show-priorities').textContent = '分析中...';
    try {
      const data = await api(`/api/report/priorities/${currentEvalId}`, { method: 'POST' });
      if (data.ok) renderPriorities(data.priorities);
      else alert(data.error || '优先级分析失败');
    } catch (e) { alert('优先级分析失败: ' + e.message); }
    document.getElementById('btn-show-priorities').disabled = false;
    document.getElementById('btn-show-priorities').textContent = '优先级分析';
  };

  // 定向优化
  document.getElementById('btn-optimize').onclick = async () => {
    if (!currentEvalId) await ensureEvalId();
    if (!currentEvalId) { alert('没有评测数据，请先运行评测'); return; }
    document.getElementById('btn-optimize').disabled = true;
    document.getElementById('btn-optimize').textContent = '优化中...';
    try {
      const data = await api(`/api/report/optimize/${currentEvalId}`, { method: 'POST' });
      if (data.ok) renderOptimizations(data);
      else alert(data.error || '优化失败');
    } catch (e) { alert('优化失败: ' + e.message); }
    document.getElementById('btn-optimize').disabled = false;
    document.getElementById('btn-optimize').textContent = '定向优化';
  };

  // 应用到 Prompt
  document.getElementById('btn-apply-prompt').onclick = async () => {
    if (!currentEvalId) await ensureEvalId();
    if (!currentEvalId) { alert('没有评测数据，请先运行评测'); return; }
    document.getElementById('btn-apply-prompt').disabled = true;
    document.getElementById('btn-apply-prompt').textContent = '应用中...';
    try {
      const data = await api(`/api/report/apply-prompt/${currentEvalId}`, { method: 'POST' });
      if (data.ok) {
        renderPromptChange(data);
      } else {
        alert(data.error || '应用失败');
      }
    } catch (e) { alert('应用失败: ' + e.message); }
    document.getElementById('btn-apply-prompt').disabled = false;
  };

  // 回归验证
  document.getElementById('btn-regression').onclick = async () => {
    if (!currentEvalId) await ensureEvalId();
    if (!currentEvalId) { alert('没有评测数据，请先运行评测'); return; }
    if (!confirm('确认进行回归验证？将重新运行评测并对比结果。')) return;
    document.getElementById('btn-regression').disabled = true;
    document.getElementById('btn-regression').textContent = '验证中...';
    try {
      const data = await api(`/api/report/regression/${currentEvalId}`, { method: 'POST' });
      if (data.ok) renderRegression(data);
      else alert(data.error || '回归验证失败');
    } catch (e) { alert('回归验证失败: ' + e.message); }
    document.getElementById('btn-regression').disabled = false;
    document.getElementById('btn-regression').textContent = '回归验证';
  };

  // ── 渲染函数 ──

  function renderReport(report) {
    document.getElementById('report-text').textContent = report.summary || '无摘要';
    document.getElementById('report-summary').style.display = '';
    renderConfusionMatrix(report.confusion_matrix || {});
    document.getElementById('confusion-section').style.display = '';
    renderMetrics(report.metrics || {});
    document.getElementById('metrics-section').style.display = '';
  }

  function renderConfusionMatrix(matrix) {
    const codes = new Set();
    for (const [true_code, preds] of Object.entries(matrix)) {
      codes.add(true_code);
      for (const pred_code of Object.keys(preds)) codes.add(pred_code);
    }
    const sorted = [...codes].sort();
    if (sorted.length === 0) {
      document.getElementById('confusion-matrix').innerHTML = '<div class="empty-state">无混淆矩阵数据</div>';
      return;
    }
    let html = '<table class="confusion-table"><tr><th>真实\\预测</th>';
    sorted.forEach(c => { html += `<th>${c}</th>`; });
    html += '</tr>';
    sorted.forEach(true_code => {
      html += `<tr><th>${true_code}</th>`;
      sorted.forEach(pred_code => {
        const count = (matrix[true_code] || {})[pred_code] || 0;
        const isError = count > 0 && true_code !== pred_code;
        html += `<td class="${isError ? 'error' : ''}">${count || ''}</td>`;
      });
      html += '</tr>';
    });
    html += '</table>';
    document.getElementById('confusion-matrix').innerHTML = html;
  }

  function renderMetrics(metrics) {
    let html = '<table class="confusion-table"><tr><th>类别</th><th>支持度</th><th>精确率</th><th>召回率</th><th>F1</th></tr>';
    for (const [code, m] of Object.entries(metrics)) {
      if (code === 'macro_avg' || !m.support) continue;
      html += `<tr>
        <td><strong>${code}</strong></td><td>${m.support}</td>
        <td>${(m.precision * 100).toFixed(1)}%</td>
        <td>${(m.recall * 100).toFixed(1)}%</td>
        <td>${(m.f1 * 100).toFixed(1)}%</td>
      </tr>`;
    }
    const avg = metrics.macro_avg;
    if (avg) {
      html += `<tr style="font-weight:700;border-top:2px solid var(--border)">
        <td>宏平均</td><td>-</td>
        <td>${(avg.precision * 100).toFixed(1)}%</td>
        <td>${(avg.recall * 100).toFixed(1)}%</td>
        <td>${(avg.f1 * 100).toFixed(1)}%</td>
      </tr>`;
    }
    html += '</table>';
    document.getElementById('per-code-stats').innerHTML = html;
  }

  function renderAgentResults(results) {
    let html = '';
    const sc = results.self_consistency;
    if (sc) {
      html += `<div class="defect-card">
        <div class="dc-header"><span class="dc-code">自洽性校验</span><span class="dc-conf">得分: ${(sc.score * 100).toFixed(1)}%</span></div>
        <div class="dc-grade">检查 ${sc.checked} 个样本，发现 ${sc.issue_count} 个问题</div>`;
      if (sc.issues && sc.issues.length > 0) {
        html += '<div class="dc-features">';
        sc.issues.slice(0, 5).forEach(i => { html += `<div>- ${i.description} (${i.sample_id})</div>`; });
        html += '</div>';
      }
      html += '</div>';
    }
    const ac = results.adversarial_confusion;
    if (ac) {
      html += `<div class="defect-card"><div class="dc-header"><span class="dc-code">对抗性混淆</span></div>`;
      if (ac.high_risk_pairs && ac.high_risk_pairs.length > 0) {
        html += '<div class="dc-features"><strong>高风险混淆对:</strong>';
        ac.high_risk_pairs.slice(0, 5).forEach(p => { html += `<div>- ${p.description}</div>`; });
        html += '</div>';
      }
      if (ac.focus_codes && ac.focus_codes.length > 0) {
        html += '<div class="dc-features" style="margin-top:8px"><strong>需关注:</strong>';
        ac.focus_codes.forEach(c => { html += `<div>- ${c.description}</div>`; });
        html += '</div>';
      }
      html += '</div>';
    }
    const hr = results.historical_regression;
    if (hr) {
      html += `<div class="defect-card">
        <div class="dc-header"><span class="dc-code">历史回归</span><span class="dc-conf">趋势: ${hr.trend || '未知'}</span></div>
        <div class="dc-grade" style="white-space:pre-wrap">${hr.summary || ''}</div></div>`;
    }
    document.getElementById('agent-results').innerHTML = html || '<div class="empty-state">无分析结果</div>';
    document.getElementById('agent-section').style.display = '';
  }

  function renderPriorities(priorities) {
    let html = '';
    const dims = priorities.focus_dimensions || [];
    if (dims.length > 0) {
      html += '<div style="margin-bottom:12px"><strong>重点维度:</strong></div>';
      dims.forEach(d => {
        const color = d.severity === 'high' ? 'var(--danger)' : d.severity === 'medium' ? 'var(--warn)' : 'var(--text3)';
        html += `<div class="defect-card" style="border-left:3px solid ${color}">
          <div class="dc-header"><span class="dc-code">${d.dimension}</span><span class="dc-conf">${d.severity || ''}</span></div>
          <div class="dc-grade">${d.evidence || ''}</div>
          <div class="dc-features"><strong>策略:</strong> ${d.strategy || ''}</div>
          <div class="dc-features"><strong>预期效果:</strong> ${d.expected_impact || ''}</div>
          ${d.affected_codes ? `<div class="dc-features">涉及: ${d.affected_codes.join(', ')}</div>` : ''}
        </div>`;
      });
    }
    if (priorities.summary) {
      html += `<div class="active-standard" style="margin-top:12px"><h3>总结</h3><p style="margin-top:8px">${priorities.summary}</p></div>`;
    }
    document.getElementById('priority-results').innerHTML = html || '<div class="empty-state">无优先级数据</div>';
    document.getElementById('priority-section').style.display = '';
  }

  function renderOptimizations(data) {
    let html = '';
    const opt = data;
    if (opt.message) {
      html += `<div class="active-standard"><h3>${opt.message}</h3></div>`;
    }
    if (opt.optimizations && opt.optimizations.length > 0) {
      html += `<div style="margin-bottom:8px">应用了 ${opt.applied_count} 项优化:</div>`;
      opt.optimizations.forEach(o => {
        html += `<div class="defect-card">
          <div class="dc-header"><span class="dc-code">${o.dimension}</span><span class="dc-conf">${o.status}</span></div>`;
        if (o.prompt_addition) {
          html += `<div class="dc-features" style="margin-top:4px"><strong>Prompt 补充:</strong><pre style="white-space:pre-wrap;font-size:12px;margin-top:4px;background:#f5f7f9;padding:8px;border-radius:4px">${o.prompt_addition}</pre></div>`;
        }
        if (o.fewshot_suggestions && o.fewshot_suggestions.length > 0) {
          // 按 target_code 分组
          const grouped = {};
          o.fewshot_suggestions.forEach(s => {
            if (!grouped[s.target_code]) grouped[s.target_code] = [];
            grouped[s.target_code].push(s);
          });
          html += '<div style="margin-top:8px">';
          for (const [code, suggestions] of Object.entries(grouped)) {
            html += `<div style="margin-bottom:16px">`;
            html += `<div style="font-weight:600;font-size:13px;margin-bottom:6px">${code} Fewshot 建议</div>`;

            // 显示图例
            html += `<div style="display:flex;gap:12px;margin-bottom:8px;font-size:11px">`;
            const types = [...new Set(suggestions.map(s => s.anchor_type))];
            types.forEach(t => {
              const label = {positive: '正例', hard: '困难例', negative: '反例', boundary: '边界例'}[t] || t;
              const color = {positive: 'var(--success)', hard: 'var(--warn)', negative: 'var(--danger)', boundary: 'var(--text3)'}[t] || 'var(--text3)';
              html += `<span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:2px;background:${color};display:inline-block"></span>${label}</span>`;
            });
            html += `</div>`;

            // 候选样本网格
            html += `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px">`;
            suggestions.forEach(s => {
              const color = {positive: 'var(--success)', hard: 'var(--warn)', negative: 'var(--danger)', boundary: 'var(--text3)'}[s.anchor_type] || 'var(--text3)';
              const label = {positive: '正例', hard: '困难例', negative: '反例', boundary: '边界例'}[s.anchor_type] || s.anchor_type;
              html += `<div class="anchor-candidate-card" style="border:1px solid var(--border);border-radius:6px;overflow:hidden;cursor:pointer;transition:.12s;border-top:3px solid ${color}"
                onmouseenter="this.style.borderColor='${color}'" onmouseleave="this.style.borderColor='var(--border)'"
                onclick="window._confirmAnchor('${s.sample_id}', '${s.anchor_type}', '${code}', this)">
                <img src="${s.image_path}" style="width:100%;height:100px;object-fit:cover;display:block;background:#f0f0f0" onerror="this.style.height='60px';this.style.display='flex';this.style.alignItems='center';this.style.justifyContent='center';this.textContent='无图'">
                <div style="padding:6px 8px">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-weight:600;font-size:12px">#${s.sample_id}</span>
                    <span style="font-size:10px;color:${color};font-weight:600">${label}</span>
                  </div>
                  <div style="font-size:11px;color:var(--text3);margin-top:2px">${s.note || ''}</div>
                  <div style="font-size:11px;color:var(--text3)">置信度: ${(s.confidence * 100).toFixed(0)}%</div>
                </div>
              </div>`;
            });
            html += `</div></div>`;
          }
          html += '</div>';
        }
        html += '</div>';
      });
    }
    document.getElementById('optimize-results').innerHTML = html || '<div class="empty-state">无优化结果</div>';
    document.getElementById('optimize-section').style.display = '';
  }

  // 确认创建锚点
  window._confirmAnchor = async function(sampleId, anchorType, targetCode, cardEl) {
    const typeLabel = {positive: '正例', hard: '困难例', negative: '反例', boundary: '边界例'}[anchorType] || anchorType;
    const note = prompt(`确认将 #${sampleId} 设为 ${targetCode} 的${typeLabel}？\n\n可选备注（留空跳过）：`);
    if (note === null) return;

    try {
      const data = await api(`/api/fewshot/${sampleId}`, {
        method: 'POST',
        body: JSON.stringify({ anchor_type: anchorType, target_code: targetCode, note }),
      });
      if (data.ok) {
        cardEl.style.opacity = '0.4';
        cardEl.style.pointerEvents = 'none';
        cardEl.style.position = 'relative';
        cardEl.insertAdjacentHTML('beforeend', '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:var(--success);color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">已添加</div>');
      } else {
        alert(data.error || '添加失败');
      }
    } catch (e) {
      alert('添加失败: ' + e.message);
    }
  };

  function renderPromptChange(data) {
    let html = `<div class="active-standard">
      <h3>Prompt 版本已更新</h3>
      <div style="margin-top:8px;font-size:13px">
        <div><strong>新版本:</strong> ${data.new_version}</div>
        <div><strong>基于:</strong> ${data.base_version}</div>
        <div><strong>变更维度:</strong> ${(data.dimensions || []).join(', ')}</div>
        <div><strong>说明:</strong> ${data.reason || ''}</div>
      </div>`;
    if (data.prompt_preview) {
      html += `<div style="margin-top:12px"><strong>新增内容预览:</strong>
        <pre style="white-space:pre-wrap;font-size:12px;margin-top:4px;background:#f5f7f9;padding:8px;border-radius:4px;max-height:200px;overflow-y:auto">${data.prompt_preview}</pre>
      </div>`;
    }
    html += `<div style="margin-top:12px;font-size:12px;color:var(--text3)">
      注意：新版本已保存但未激活。请在 Prompt 管理页面查看并激活。
    </div></div>`;

    document.getElementById('optimize-section').insertAdjacentHTML('beforeend', html);
  }

  function renderRegression(data) {
    const c = data.comparison;
    let html = `<div class="defect-card">
      <div class="dc-header"><span class="dc-code">回归验证</span><span class="dc-conf">${data.improved ? '改善' : '未改善'}</span></div>
      <div class="dc-grade">新评测 ID: ${data.new_evaluation_id}</div>
      <div class="dc-features">
        旧宏平均 F1: ${c.old_overall_f1.toFixed(3)} → 新: ${c.new_overall_f1.toFixed(3)} (变化: ${(c.overall_delta >= 0 ? '+' : '') + c.overall_delta.toFixed(3)})
      </div>
      <div class="dc-features">改善 ${c.improved_count} 项, 退化 ${c.degraded_count} 项</div>`;
    if (c.changes && c.changes.length > 0) {
      html += '<div class="dc-features" style="margin-top:8px"><strong>详细变化:</strong>';
      c.changes.forEach(ch => {
        const icon = ch.direction === 'improved' ? '↑' : '↓';
        const color = ch.direction === 'improved' ? 'var(--success)' : 'var(--danger)';
        html += `<div style="color:${color}">${icon} ${ch.code}: ${ch.old_f1.toFixed(3)} → ${ch.new_f1.toFixed(3)} (${ch.dimension})</div>`;
      });
      html += '</div>';
    }
    html += '</div>';
    document.getElementById('regression-results').innerHTML = html;
    document.getElementById('regression-section').style.display = '';
  }

  // ── 历史报告 ──

  async function loadReportList() {
    try {
      const data = await api('/api/report/list');
      const list = data.reports || [];
      if (list.length === 0) {
        document.getElementById('report-list').innerHTML = '<div class="empty-state">暂无报告</div>';
        return;
      }
      let html = '';
      list.forEach(r => {
        html += `<div class="standard-item" onclick="window._loadReport('${r.id}')">
          <div class="std-name">报告 #${r.id}</div>
          <div class="std-meta">${r.time || ''} | 准确率: ${(r.accuracy * 100).toFixed(1)}% | 混淆对: ${r.confusion_count}</div>
        </div>`;
      });
      document.getElementById('report-list').innerHTML = html;
    } catch (e) {
      console.error('Failed to load reports:', e);
    }
  }

  window._loadReport = async function(evalId) {
    currentEvalId = evalId;
    try {
      const data = await api('/api/report/generate', { method: 'POST', body: JSON.stringify({ evaluation_id: evalId }) });
      if (data.ok) {
        currentReport = data.report;
        renderReport(data.report);
      }
    } catch (e) {
      console.error('Failed to load report:', e);
    }
  };

  loadReportList();
})();
