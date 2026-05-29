// workspace.js — 审核工作台
(function() {
  let samples = [];
  let currentSample = null;
  let currentPrediction = null;
  let defectCodesLoaded = false;

  // Load defect codes first, then load samples
  async function init() {
    await loadDefectCodes();
    await loadSamples();
  }

  // Load samples
  async function loadSamples() {
    const data = await api('/api/samples');
    samples = data.samples || [];
    renderSampleList();
  }

  async function loadDefectCodes() {
    if (defectCodesLoaded) return;
    try {
      const d = await api('/api/defects');
      const codes = d.codes || [];
      const filterSelect = document.getElementById('filter-code');
      const correctSelect = document.getElementById('correct-code');
      const anchorSelect = document.getElementById('anchor-code');
      codes.forEach(c => {
        filterSelect.add(new Option(`${c.code} ${c.name}`, c.code));
        correctSelect.add(new Option(`${c.code} ${c.name}`, c.code));
        anchorSelect.add(new Option(`${c.code} ${c.name}`, c.code));
      });
      defectCodesLoaded = true;
    } catch (e) {
      console.error('Failed to load defect codes:', e);
    }
  }

  function renderSampleList() {
    const list = document.getElementById('sample-list');
    const filter = document.getElementById('filter-code').value;
    const search = document.getElementById('search-input').value.toLowerCase();

    console.log('[DEBUG] renderSampleList called, filter=', filter, 'search=', search, 'samples count=', samples.length);

    const filtered = samples.filter(s => {
      if (filter && s.defect_code !== filter) return false;
      if (search && !s.id.includes(search)) return false;
      return true;
    });

    console.log('[DEBUG] filtered count=', filtered.length);

    list.innerHTML = filtered.map(s => {
      const predCode = s.ai_code || '';
      const match = predCode && predCode === s.defect_code;
      const mismatch = predCode && predCode !== s.defect_code && predCode !== 'UNKNOWN';
      const active = currentSample && currentSample.id === s.id ? 'active' : '';
      return `<div class="sample-item ${active}" data-id="${s.id}">
        <span class="sid">${s.id}</span>
        <span class="scode ${match ? 'match' : mismatch ? 'mismatch' : ''}">${s.defect_code || '?'}</span>
        <span style="flex:1;color:var(--text3);font-size:12px">${s.section || ''}</span>
        ${s.status === 'predicted' ? '<span style="font-size:10px;color:var(--brand)">●</span>' : ''}
      </div>`;
    }).join('');

    list.querySelectorAll('.sample-item').forEach(el => {
      el.onclick = () => selectSample(el.dataset.id);
    });
  }

  function selectSample(id) {
    api(`/api/samples/${id}`).then(data => {
      currentSample = data.sample;
      currentPrediction = currentSample.ai_prediction || null;

      document.getElementById('current-sample-id').textContent = `#${currentSample.id} ${currentSample.defect_code || ''}`;
      document.getElementById('btn-predict').disabled = false;
      document.getElementById('btn-predict-fewshot').disabled = false;

      // Show image with bbox overlay
      const viewer = document.getElementById('image-viewer');
      viewer.innerHTML = `
        <div class="image-container">
          <img id="viewer-img" src="/sample-images/${currentSample.id}.png" alt="样本 ${currentSample.id}" onload="window._onViewerImgLoad()">
          <canvas id="bbox-canvas"></canvas>
        </div>`;

      // Show prediction result if exists
      if (currentPrediction) {
        renderPrediction(currentPrediction);
      } else {
        document.getElementById('tab-result').innerHTML = '<div class="empty-state">尚未预测</div>';
      }

      renderSampleList();
    });
  }

  function renderPrediction(pred) {
    const defects = pred.defects || [];
    const obs = pred.observation || {};

    let html = '';

    // Observation
    if (Object.keys(obs).length > 0) {
      html += '<div style="margin-bottom:12px">';
      for (const [key, val] of Object.entries(obs)) {
        if (val) html += `<div class="obs-section"><div class="obs-label">${key}</div><div class="obs-value">${val}</div></div>`;
      }
      html += '</div>';
    }

    // Defects
    defects.forEach(d => {
      html += `<div class="defect-card">
        <div class="dc-header">
          <span class="dc-code">${d.code} ${d.name || ''}</span>
          <span class="dc-conf">${(d.confidence * 100).toFixed(0)}%</span>
        </div>
        <div class="dc-grade">等级: ${d.grade || '-'}</div>
        ${d.bbox ? `<div class="dc-features">bbox: [${d.bbox.join(', ')}]</div>` : ''}
        ${d.defect_ratio ? `<div class="dc-features">占比: ${(d.defect_ratio * 100).toFixed(0)}%</div>` : ''}
        ${(d.visible_features || []).length ? `<div class="dc-features">${d.visible_features.join('; ')}</div>` : ''}
      </div>`;
    });

    document.getElementById('tab-result').innerHTML = html || '<div class="empty-state">无结果</div>';
  }

  // Predict
  document.getElementById('btn-predict').onclick = async () => {
    if (!currentSample) return;
    document.getElementById('tab-result').innerHTML = '<div class="loading">预测中...</div>';
    const data = await api(`/api/predict/${currentSample.id}`, { method: 'POST', body: '{}' });
    if (data.result) {
      currentPrediction = data.result;
      renderPrediction(data.result);
      loadSamples();
    } else {
      document.getElementById('tab-result').innerHTML = `<div class="empty-state">${data.error || '预测失败'}</div>`;
    }
  };

  document.getElementById('btn-predict-fewshot').onclick = async () => {
    if (!currentSample) return;
    document.getElementById('tab-result').innerHTML = '<div class="loading">预测中(fewshot)...</div>';
    const data = await api(`/api/predict/${currentSample.id}`, { method: 'POST', body: '{"use_fewshot":true}' });
    if (data.result) {
      currentPrediction = data.result;
      renderPrediction(data.result);
      loadSamples();
    } else {
      document.getElementById('tab-result').innerHTML = `<div class="empty-state">${data.error || '预测失败'}</div>`;
    }
  };

  // Correct form
  document.getElementById('correct-form').onsubmit = async (e) => {
    e.preventDefault();
    if (!currentSample) return;
    const code = document.getElementById('correct-code').value;
    const grade = document.getElementById('correct-grade').value;
    const reason = document.getElementById('correct-reason').value;
    await api(`/api/correct/${currentSample.id}`, {
      method: 'POST',
      body: JSON.stringify({ code, grade, reason }),
    });
    loadSamples();
    alert('纠正已保存');
  };

  // Anchor form
  document.getElementById('anchor-form').onsubmit = async (e) => {
    e.preventDefault();
    if (!currentSample) return;
    const anchor_type = document.getElementById('anchor-type').value;
    const target_code = document.getElementById('anchor-code').value;
    const note = document.getElementById('anchor-note').value;
    await api(`/api/fewshot/${currentSample.id}`, {
      method: 'POST',
      body: JSON.stringify({ anchor_type, target_code, note }),
    });
    alert('锚点已保存');
  };

  // Tabs
  document.querySelectorAll('.action-tab').forEach(tab => {
    tab.onclick = () => {
      document.querySelectorAll('.action-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.action-content').forEach(c => c.style.display = 'none');
      tab.classList.add('active');
      document.getElementById(`tab-${tab.dataset.tab}`).style.display = '';
    };
  });

  // Filters
  document.getElementById('filter-code').onchange = renderSampleList;
  document.getElementById('search-input').oninput = renderSampleList;

  // File upload
  document.getElementById('file-input').onchange = async (e) => {
    const files = e.target.files;
    for (const file of files) {
      if (file.type.startsWith('video/')) {
        await uploadVideo(file);
      } else {
        await uploadImage(file);
      }
    }
    e.target.value = '';
    loadSamples();
  };

  async function uploadImage(file) {
    // TODO: implement image upload endpoint
    alert('图片上传功能开发中');
  }

  async function uploadVideo(file) {
    const formData = new FormData();
    formData.append('video', file);
    const resp = await fetch('/api/video/extract-frames', { method: 'POST', body: formData });
    const data = await resp.json();
    if (data.ok) {
      showFrameDrawer(data);
    } else {
      alert(data.error || '抽帧失败');
    }
  }

  function showFrameDrawer(data) {
    const drawer = document.getElementById('frame-drawer');
    const list = document.getElementById('frame-list');
    drawer.style.display = '';
    list.innerHTML = data.frames.map((f, i) => `
      <div class="frame-thumb" data-index="${i}">
        <img src="/api/video/frame-image/${data.job_id}/frame_${String(f.frame_index).padStart(6,'0')}.png">
        <div class="frame-ts">${f.timestamp}s</div>
      </div>
    `).join('');

    list.querySelectorAll('.frame-thumb').forEach(el => {
      el.onclick = () => el.classList.toggle('selected');
    });

    document.getElementById('btn-close-drawer').onclick = () => { drawer.style.display = 'none'; };

    document.getElementById('btn-import-frames').onclick = async () => {
      const selected = [...list.querySelectorAll('.frame-thumb.selected')].map(el => parseInt(el.dataset.index));
      if (!selected.length) { alert('请选择帧'); return; }
      const resp = await fetch('/api/video/import-frames', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: data.job_id, frame_ids: selected }),
      });
      const result = await resp.json();
      if (result.ok) {
        alert(`导入 ${result.imported} 个帧为样本`);
        drawer.style.display = 'none';
        loadSamples();
      }
    };
  }

  // Init
  init();

  // ── Bbox overlay drawing ──────────────────────────────────────

  const BBOX_COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6'];

  window._onViewerImgLoad = function() {
    const img = document.getElementById('viewer-img');
    const canvas = document.getElementById('bbox-canvas');
    if (!img || !canvas) return;

    // Size canvas to match displayed image
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    canvas.style.width = img.clientWidth + 'px';
    canvas.style.height = img.clientHeight + 'px';

    // Draw bboxes if prediction exists
    if (currentPrediction) {
      drawBboxes(currentPrediction, img, canvas);
    }
  };

  function drawBboxes(pred, img, canvas) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const defects = pred.defects || [];
    const imgW = img.naturalWidth;
    const imgH = img.naturalHeight;

    defects.forEach((d, i) => {
      const bbox = d.bbox;
      if (!bbox || bbox.length < 4) return;

      let [x1, y1, x2, y2] = bbox;

      // 归一化坐标（0-1）→ 像素坐标
      if (x1 <= 1 && y1 <= 1 && x2 <= 1 && y2 <= 1) {
        x1 *= imgW; y1 *= imgH; x2 *= imgW; y2 *= imgH;
      }

      const color = BBOX_COLORS[i % BBOX_COLORS.length];

      // Draw rectangle
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      // Draw label background
      const label = `${d.code} ${(d.confidence * 100).toFixed(0)}%`;
      ctx.font = 'bold 12px sans-serif';
      const textWidth = ctx.measureText(label).width;
      const labelY = y1 > 22 ? y1 - 20 : y1 + 18;
      ctx.fillStyle = color;
      ctx.fillRect(x1, labelY, textWidth + 8, 20);

      // Draw label text
      ctx.fillStyle = '#fff';
      ctx.fillText(label, x1 + 4, labelY + 14);
    });
  }

  // Redraw bboxes on window resize
  window.addEventListener('resize', () => {
    const img = document.getElementById('viewer-img');
    const canvas = document.getElementById('bbox-canvas');
    if (img && canvas && img.complete) {
      canvas.width = img.clientWidth;
      canvas.height = img.clientHeight;
      canvas.style.width = img.clientWidth + 'px';
      canvas.style.height = img.clientHeight + 'px';
      if (currentPrediction) drawBboxes(currentPrediction, img, canvas);
    }
  });
})();
