document.addEventListener('DOMContentLoaded', () => {
  // Tab Switching
  const tabs = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tabContents.forEach(tc => tc.classList.remove('active'));

      tab.classList.add('active');
      const target = document.getElementById(`tab-${tab.dataset.tab}`);
      if (target) target.classList.add('active');
    });
  });

  // Accounts Management
  const accountsList = document.getElementById('accountsList');
  const refreshAccountsBtn = document.getElementById('refreshAccountsBtn');
  const resetAccountsBtn = document.getElementById('resetAccountsBtn');

  async function loadAccounts() {
    try {
      const res = await fetch('/api/accounts');
      const data = await res.json();
      renderAccounts(data.accounts || []);
    } catch (e) {
      accountsList.innerHTML = `<div class="card error-card">Failed to load accounts: ${e.message}</div>`;
    }
  }

  function renderAccounts(accounts) {
    if (!accounts.length) {
      accountsList.innerHTML = `
        <div class="card placeholder-card" style="grid-column: 1 / -1; text-align: center; padding: 40px;">
          <div style="font-size: 32px; margin-bottom: 12px;">🔑</div>
          <h3>No Google Accounts Connected</h3>
          <p class="subtitle" style="margin-bottom: 18px;">Click below to authenticate using Google OAuth (Antigravity IDE Client).</p>
          <a href="/oauth/start" class="btn btn-primary">+ Connect Google Account</a>
        </div>
      `;
      return;
    }

    accountsList.innerHTML = accounts.map(acc => `
      <div class="account-card">
        <div class="account-header">
          <div class="account-email">${escapeHtml(acc.email)}</div>
          <span class="status-indicator ${acc.cooldown_active ? 'status-cooldown' : 'status-active'}">
            ${acc.cooldown_active ? '⏳ Cooldown' : '🟢 Ready'}
          </span>
        </div>
        
        <div class="account-stats">
          <div class="stat-item">
            <span class="stat-label">Health Score</span>
            <span class="stat-value" style="color: ${acc.health_score > 70 ? 'var(--success)' : 'var(--warning)'}">${acc.health_score}%</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Project ID</span>
            <span class="stat-value" style="font-size: 0.8rem; font-family: monospace;">${escapeHtml(acc.project_id || 'default')}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Failures</span>
            <span class="stat-value">${acc.consecutive_failures || 0}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">Token Usage</span>
            <span class="stat-value">${(acc.token_usage || 0).toLocaleString()}</span>
          </div>
        </div>

        <div class="account-footer">
          <span>Last used: ${acc.last_used ? new Date(acc.last_used * 1000).toLocaleTimeString() : 'Never'}</span>
          <button class="btn-danger-sm delete-account-btn" data-email="${escapeHtml(acc.email)}">Delete</button>
        </div>
      </div>
    `).join('');

    document.querySelectorAll('.delete-account-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const email = e.target.dataset.email;
        if (confirm(`Remove account ${email}?`)) {
          await fetch(`/api/accounts/${encodeURIComponent(email)}`, { method: 'DELETE' });
          loadAccounts();
        }
      });
    });
  }

  refreshAccountsBtn?.addEventListener('click', loadAccounts);
  resetAccountsBtn?.addEventListener('click', async () => {
    await fetch('/api/accounts/reset', { method: 'POST' });
    loadAccounts();
  });

  // Initial accounts load
  loadAccounts();

  // Nano Banana 2 Image Generation Playground
  const imgPrompt = document.getElementById('imgPrompt');
  const imgModel = document.getElementById('imgModel');
  const imgRatio = document.getElementById('imgRatio');
  const imgFormat = document.getElementById('imgFormat');
  const imgCount = document.getElementById('imgCount');
  const generateImgBtn = document.getElementById('generateImgBtn');
  const imgSpinner = document.getElementById('imgSpinner');
  const imgBtnText = document.getElementById('imgBtnText');
  const previewViewport = document.getElementById('imagePreviewViewport');
  const generationStatus = document.getElementById('generationStatus');

  generateImgBtn?.addEventListener('click', async () => {
    const prompt = imgPrompt.value.trim();
    if (!prompt) {
      alert('Please enter an image description prompt.');
      return;
    }

    imgSpinner.classList.remove('hidden');
    imgBtnText.textContent = 'Generating with Nano Banana 2...';
    generateImgBtn.disabled = true;
    generationStatus.textContent = 'Processing...';

    previewViewport.innerHTML = `
      <div class="placeholder-content">
        <div class="btn-spinner" style="width: 32px; height: 32px; margin-bottom: 16px;"></div>
        <p>Synthesizing image with Nano Banana 2...</p>
        <span class="hint">Contacting Antigravity gemini-3-pro-image engine</span>
      </div>
    `;

    try {
      const response = await fetch('/v1/images/generations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt,
          model: imgModel.value,
          size: imgRatio.value,
          response_format: imgFormat.value,
          n: parseInt(imgCount.value) || 1
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.detail?.error?.message || data?.error?.message || 'Generation failed');
      }

      const items = data.data || [];
      if (!items.length) {
        throw new Error('No image returned by model');
      }

      previewViewport.innerHTML = items.map((item, idx) => {
        const imgSrc = item.url ? item.url : `data:image/png;base64,${item.b64_json}`;
        return `
          <div class="generated-image-card">
            <img src="${imgSrc}" alt="Generated image ${idx + 1}" />
            <div class="image-actions">
              <a href="${imgSrc}" download="nano-banana-2-${Date.now()}.png" class="btn btn-secondary">💾 Download</a>
              <button class="btn btn-secondary copy-link-btn" data-src="${imgSrc}">📋 Copy ${item.url ? 'URL' : 'Data'}</button>
            </div>
          </div>
        `;
      }).join('');

      document.querySelectorAll('.copy-link-btn').forEach(b => {
        b.addEventListener('click', (e) => {
          navigator.clipboard.writeText(e.target.dataset.src);
          e.target.textContent = 'Copied!';
          setTimeout(() => e.target.textContent = '📋 Copy', 2000);
        });
      });

      generationStatus.textContent = 'Complete';
      loadAccounts(); // refresh stats
    } catch (err) {
      generationStatus.textContent = 'Error';
      previewViewport.innerHTML = `
        <div class="placeholder-content" style="color: #f87171;">
          <div style="font-size: 32px; margin-bottom: 8px;">⚠️</div>
          <p>Generation Error</p>
          <span style="font-size: 0.85rem; color: var(--text-secondary); max-width: 400px; display: inline-block;">
            ${escapeHtml(err.message)}
          </span>
        </div>
      `;
    } finally {
      imgSpinner.classList.add('hidden');
      imgBtnText.textContent = '✨ Generate with Nano Banana 2';
      generateImgBtn.disabled = false;
    }
  });

  // Chat Playground
  const chatMessages = document.getElementById('chatMessages');
  const chatInput = document.getElementById('chatInput');
  const sendChatBtn = document.getElementById('sendChatBtn');
  const chatModel = document.getElementById('chatModel');

  async function sendChatMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    chatInput.value = '';
    appendMessage('user', text);

    const assistantMsgElem = appendMessage('assistant', '<div class="btn-spinner" style="width: 14px; height: 14px;"></div> Thinking...');

    try {
      const res = await fetch('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: chatModel.value,
          messages: [{ role: 'user', content: text }],
          stream: false
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail?.error?.message || data?.error?.message || 'Chat request failed');
      }

      const reply = data.choices?.[0]?.message?.content || 'No response content';
      // Format markdown image if any
      const formatted = reply.replace(/!\[(.*?)\]\((.*?)\)/g, '<br><img src="$2" style="max-width: 100%; max-height: 320px; border-radius: 8px; margin-top: 8px;" alt="$1"/><br>');
      assistantMsgElem.querySelector('.message-bubble').innerHTML = formatted;
      loadAccounts();
    } catch (e) {
      assistantMsgElem.querySelector('.message-bubble').innerHTML = `<span style="color: #f87171;">Error: ${escapeHtml(e.message)}</span>`;
    }
  }

  function appendMessage(role, htmlContent) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerHTML = `<div class="message-bubble">${htmlContent}</div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
  }

  sendChatBtn?.addEventListener('click', sendChatMessage);
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
});
