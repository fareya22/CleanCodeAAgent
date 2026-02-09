/**
 * Popup Script - Extension settings and configuration
 */

document.addEventListener('DOMContentLoaded', async () => {
  console.log('[Popup] Initializing...');

  // Load saved settings
  await loadSettings();

  // Check server status
  checkServerStatus();

  // Save button click
  document.getElementById('save-btn').addEventListener('click', saveSettings);

  // Auto-save on input change (with debounce)
  const inputs = document.querySelectorAll('input');
  inputs.forEach(input => {
    input.addEventListener('input', debounce(saveSettings, 1000));
  });
});

/**
 * Load settings from Chrome storage
 */
async function loadSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(['githubToken', 'apiUrl'], (result) => {
      // Set GitHub token
      if (result.githubToken) {
        document.getElementById('github-token').value = result.githubToken;
      }

      // Set API URL (default: localhost:5000)
      const apiUrl = result.apiUrl || 'http://localhost:5000';
      document.getElementById('api-url').value = apiUrl;

      console.log('[Popup] Settings loaded');
      resolve();
    });
  });
}

/**
 * Save settings to Chrome storage
 */
async function saveSettings() {
  const githubToken = document.getElementById('github-token').value.trim();
  const apiUrl = document.getElementById('api-url').value.trim();

  // Validate API URL
  if (apiUrl && !isValidUrl(apiUrl)) {
    showStatus('Invalid API URL', 'error');
    return;
  }

  // Save to Chrome storage
  chrome.storage.sync.set({
    githubToken: githubToken,
    apiUrl: apiUrl || 'http://localhost:5000'
  }, () => {
    console.log('[Popup] Settings saved');
    showStatus('Settings saved successfully!', 'success');

    // Notify content script to reload
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, {
          action: 'settingsUpdated',
          githubToken: githubToken,
          apiUrl: apiUrl
        });
      }
    });

    // Recheck server status
    setTimeout(checkServerStatus, 500);
  });
}

/**
 * Check if backend server is running
 */
async function checkServerStatus() {
  const statusEl = document.getElementById('server-status');
  statusEl.textContent = 'Checking...';
  statusEl.style.color = '#57606a';

  try {
    const apiUrl = document.getElementById('api-url').value.trim() || 'http://localhost:5000';
    
    const response = await fetch(`${apiUrl}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(3000) // 3 second timeout
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

/**
 * Show status message
 */
function showStatus(message, type = 'success') {
  const statusEl = document.getElementById('status');
  statusEl.textContent = message;
  statusEl.className = `status ${type} show`;

  // Hide after 3 seconds
  setTimeout(() => {
    statusEl.classList.remove('show');
  }, 3000);
}

/**
 * Validate URL
 */
function isValidUrl(string) {
  try {
    new URL(string);
    return true;
  } catch (_) {
    return false;
  }
}

/**
 * Debounce function
 */
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