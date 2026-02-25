document.addEventListener('DOMContentLoaded', async () => {
  console.log('[Popup] Initializing...');

  
  await loadSettings();

  
  checkServerStatus();

  
  document.getElementById('save-btn').addEventListener('click', saveSettings);

  
  const inputs = document.querySelectorAll('input');
  inputs.forEach(input => {
    input.addEventListener('input', debounce(saveSettings, 1000));
  });
});



async function loadSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(['githubToken', 'apiUrl'], (result) => {
      
      if (result.githubToken) {
        document.getElementById('github-token').value = result.githubToken;
      }

      
      const apiUrl = result.apiUrl || 'http://localhost:5000';
      document.getElementById('api-url').value = apiUrl;

      console.log('[Popup] Settings loaded');
      resolve();
    });
  });
}



async function saveSettings() {
  const githubToken = document.getElementById('github-token').value.trim();
  const apiUrl = document.getElementById('api-url').value.trim();

  
  if (apiUrl && !isValidUrl(apiUrl)) {
    showStatus('Invalid API URL', 'error');
    return;
  }

  
  chrome.storage.sync.set({
    githubToken: githubToken,
    apiUrl: apiUrl || 'http://localhost:5000'
  }, () => {
    console.log('[Popup] Settings saved');
    showStatus('Settings saved successfully!', 'success');

    
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, {
          action: 'settingsUpdated',
          githubToken: githubToken,
          apiUrl: apiUrl
        });
      }
    });

    
    setTimeout(checkServerStatus, 500);
  });
}



async function checkServerStatus() {
  const statusEl = document.getElementById('server-status');
  statusEl.textContent = 'Checking...';
  statusEl.style.color = '#57606a';

  try {
    const apiUrl = document.getElementById('api-url').value.trim() || 'http://localhost:5000';
    
    const response = await fetch(`${apiUrl}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(3000) 
    });

    if (response.ok) {
      const data = await response.json();
      statusEl.textContent = '✓ Connected';
      statusEl.style.color = '#1a7f37';
      console.log('[Popup] Server status:', data);
    } else {
      throw new Error('Server responded with error');
    }
  } catch (error) {
    statusEl.textContent = '✗ Offline';
    statusEl.style.color = '#d73a49';
    console.error('[Popup] Server check failed:', error);
  }
}



function showStatus(message, type = 'success') {
  const statusEl = document.getElementById('status');
  statusEl.textContent = message;
  statusEl.className = `status ${type} show`;

  
  setTimeout(() => {
    statusEl.classList.remove('show');
  }, 3000);
}



function isValidUrl(string) {
  try {
    new URL(string);
    return true;
  } catch (_) {
    return false;
  }
}



function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
