console.log('[Background] CleanCodeAgent service worker initialized');


chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[Background] Extension installed');
    
    
    chrome.storage.sync.set({
      apiUrl: 'http://localhost:5000',
      githubToken: ''
    });

    
    chrome.tabs.create({
      url: 'https://github.com'
    });
  } else if (details.reason === 'update') {
    console.log('[Background] Extension updated');
  }
});


chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[Background] Message received:', request);

  if (request.action === 'analyzeRepository') {
    handleAnalyzeRepository(request.data)
      .then(sendResponse)
      .catch(error => sendResponse({ error: error.message }));
    return true; 
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



async function handleAnalyzeRepository(data) {
  console.log('[Background] Starting analysis for:', data.repo);

  try {
    
    const settings = await new Promise((resolve) => {
      chrome.storage.sync.get(['apiUrl'], resolve);
    });

    const apiUrl = settings.apiUrl || 'http://localhost:5000';

    
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


chrome.action.onClicked.addListener((tab) => {
  console.log('[Background] Extension icon clicked');
  
  
  chrome.tabs.sendMessage(tab.id, {
    action: 'toggleSidebar'
  });
});


chrome.runtime.onSuspend.addListener(() => {
  console.log('[Background] Service worker suspending...');
});
