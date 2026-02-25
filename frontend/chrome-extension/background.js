/**
 * Background Service Worker
 * Handles extension lifecycle and messaging
 */

console.log('[Background] CleanCodeAgent service worker initialized');

// Extension installed/updated
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[Background] Extension installed');
    
    // Set default settings
    chrome.storage.sync.set({
      apiUrl: 'http://localhost:5000',
      githubToken: ''
    });

    // Open welcome page
    chrome.tabs.create({
      url: 'https://github.com'
    });
  } else if (details.reason === 'update') {
    console.log('[Background] Extension updated');
  }
});

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[Background] Message received:', request);

  if (request.action === 'analyzeRepository') {
    handleAnalyzeRepository(request.data)
      .then(sendResponse)
      .catch(error => sendResponse({ error: error.message }));
    return true; // Keep channel open for async response
  }

  if (request.action === 'getSettings') {
    chrome.storage.sync.get(['githubToken', 'apiUrl'], (result) => {
      sendResponse(result);
    });
    return true;
  }

  if (request.action === 'openSettings') {
    chrome.runtime.openOptionsPage();
    sendResponse({ success: true });
  }
});

/**
 * Handle repository analysis request
 */
async function handleAnalyzeRepository(data) {
  console.log('[Background] Starting analysis for:', data.repo);

  try {
    // Get API URL from settings
    const settings = await new Promise((resolve) => {
      chrome.storage.sync.get(['apiUrl'], resolve);
    });

    const apiUrl = settings.apiUrl || 'http://localhost:5000';

    // Call backend API
    const response = await fetch(`${apiUrl}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        repo: data.repo,
        files: data.files
      })
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    const result = await response.json();
    console.log('[Background] Analysis complete:', result);

    return { success: true, data: result };

  } catch (error) {
    console.error('[Background] Analysis failed:', error);
    return { success: false, error: error.message };
  }
}

// Handle browser action click (extension icon)
chrome.action.onClicked.addListener((tab) => {
  console.log('[Background] Extension icon clicked');
  
  // Toggle sidebar on the current tab
  chrome.tabs.sendMessage(tab.id, {
    action: 'toggleSidebar'
  });
});

// Keep service worker alive
chrome.runtime.onSuspend.addListener(() => {
  console.log('[Background] Service worker suspending...');
});