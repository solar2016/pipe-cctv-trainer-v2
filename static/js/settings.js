// settings.js — 系统设置
(async function() {
  const data = await api('/api/settings');
  document.getElementById('set-api-base').value = data.api_base || '';
  document.getElementById('set-model').value = data.model || '';
  document.getElementById('set-video-model').value = data.video_model || '';
  document.getElementById('set-temperature').value = data.temperature || 0.1;
  document.getElementById('set-fewshot-max').value = data.fewshot_max || 8;

  document.getElementById('settings-form').onsubmit = async (e) => {
    e.preventDefault();
    const body = {
      api_base: document.getElementById('set-api-base').value,
      model: document.getElementById('set-model').value,
      video_model: document.getElementById('set-video-model').value,
      temperature: parseFloat(document.getElementById('set-temperature').value),
      fewshot_max: parseInt(document.getElementById('set-fewshot-max').value),
    };
    const apiKey = document.getElementById('set-api-key').value;
    if (apiKey && apiKey !== '***') body.api_key = apiKey;
    await api('/api/settings', { method: 'POST', body: JSON.stringify(body) });
    alert('设置已保存');
  };

  document.getElementById('btn-reset').onclick = async () => {
    if (!confirm('确定恢复默认设置？')) return;
    await api('/api/settings/reset', { method: 'POST' });
    location.reload();
  };
})();
