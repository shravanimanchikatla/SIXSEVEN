chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "safesphere-inspect",
    title: "Inspect with SafeSphere",
    contexts: ["selection"],
    documentUrlPatterns: ["*://*.reddit.com/*"]
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "safesphere-inspect" && info.selectionText) {
    chrome.tabs.sendMessage(tab.id, {
      action: "analyze_text",
      text: info.selectionText
    });
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "proxy_fetch") {
    fetch('http://127.0.0.1:8080/api/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        text: message.text
      })
    })
    .then(async (response) => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Network error');
      sendResponse({ data: data });
    })
    .catch((error) => {
      sendResponse({ error: error.message });
    });
    
    return true; // Keep the messaging channel open for the async response
  }
});
