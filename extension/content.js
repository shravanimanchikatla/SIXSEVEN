let overlayElement = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "analyze_text" && message.text) {
    showOverlay();
    fetchAnalysis(message.text);
  }
});

function showOverlay() {
  if (overlayElement) {
    document.body.removeChild(overlayElement);
  }

  overlayElement = document.createElement('div');
  overlayElement.id = 'safesphere-overlay-root';
  
  overlayElement.innerHTML = `
    <div class="ss-card">
      <div class="ss-header">
        <div class="ss-title-container">
          <div class="ss-logo-dot"></div>
          <h2 class="ss-title">SafeSphere</h2>
        </div>
        <button class="ss-close-btn" id="ss-close-btn">&times;</button>
      </div>
      <div id="ss-content">
        <div class="ss-loading">
          <div class="ss-spinner"></div>
          <p>Analyzing context...</p>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(overlayElement);

  document.getElementById('ss-close-btn').addEventListener('click', () => {
    if (overlayElement) {
      document.body.removeChild(overlayElement);
      overlayElement = null;
    }
  });
}

async function fetchAnalysis(text) {
  try {
    const response = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({
        action: "proxy_fetch",
        text: text
      }, (res) => {
        if (chrome.runtime.lastError) {
          return reject(new Error(chrome.runtime.lastError.message));
        }
        if (res && res.error) {
          return reject(new Error(res.error));
        }
        resolve(res.data);
      });
    });

    renderResults(response);
  } catch (error) {
    console.error('SafeSphere Analysis Error:', error);
    renderError("Failed to connect to backend: " + error.message);
  }
}

function renderResults(data) {
  const contentDiv = document.getElementById('ss-content');
  if (!contentDiv) return;

  const severityLevel = data.severity?.level || 'UNKNOWN';
  const severityReason = data.severity?.reason || 'No reason provided.';
  const threats = data.threats || [];
  const immediateActions = data.actionItems?.immediateActions || data.actionItems?.immediate || [];

  let threatsHtml = '';
  if (threats.length > 0 && threats[0].label !== 'None') {
    threatsHtml = threats.map(t => `<li class="ss-threat-badge">${t.label} (${t.score}%)</li>`).join('');
  } else {
    threatsHtml = '<li class="ss-threat-badge safe">No Threats Detected</li>';
  }

  let actionsHtml = '';
  if (immediateActions.length > 0) {
    actionsHtml = immediateActions.slice(0, 3).map(a => `<li>${a}</li>`).join('');
  } else {
    actionsHtml = '<li>Stay vigilant.</li>';
  }

  contentDiv.innerHTML = `
    <div class="ss-result-section">
      <h3 class="ss-label">Severity Assessment</h3>
      <h4 class="ss-severity ${severityLevel}">${severityLevel}</h4>
      <p class="ss-reason">${severityReason}</p>
    </div>

    <div class="ss-result-section">
      <h3 class="ss-label">Detected Patterns</h3>
      <ul class="ss-threat-list">
        ${threatsHtml}
      </ul>
    </div>

    <div class="ss-result-section" style="background: rgba(125, 154, 125, 0.05);">
      <h3 class="ss-label">Recommended Actions</h3>
      <ul class="ss-action-list">
        ${actionsHtml}
      </ul>
    </div>
  `;
}

function renderError(message) {
  const contentDiv = document.getElementById('ss-content');
  if (!contentDiv) return;

  contentDiv.innerHTML = `
    <div class="ss-result-section" style="background: #fef2f2; border-color: #fecaca;">
      <h3 class="ss-label" style="color: #b91c1c;">Analysis Failed</h3>
      <p class="ss-reason" style="color: #991b1b;">${message}</p>
    </div>
  `;
}
