// CleanCodeAgent - Main Content Script

console.log('[CleanCodeAgent] Initializing...');

// API server URL
const API_URL = 'http://localhost:5000';

// Check if we're on a GitHub repository page
function isGitHubRepoPage() {
  const path = window.location.pathname;
  const match = path.match(/^\/([^\/]+)\/([^\/]+)/);
  return match && !['settings', 'notifications', 'pulls', 'issues'].includes(match[1]);
}

// Initialize extension when on repo page
if (isGitHubRepoPage()) {
  console.log('[CleanCodeAgent] GitHub repo page detected');
  
  // Wait for DOM to be ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initExtension);
  } else {
    initExtension();
  }
}

async function initExtension() {
  console.log('[CleanCodeAgent] Initializing extension...');
  
  // Create sidebar
  createSidebar();
  
  // Initialize GitHub adapter
  const adapter = new GitHubAdapter();
  
  // Get repository info
  const repoInfo = await adapter.getRepoInfo();
  console.log('[CleanCodeAgent] Repo:', repoInfo);
  
  // Load file tree
  const tree = await adapter.loadFileTree(repoInfo);
  console.log('[CleanCodeAgent] File tree loaded:', tree.length, 'top-level items');
  
  // Debug: Count total items recursively
  const totalItems = flattenTree(tree).length;
  console.log(`[CleanCodeAgent] Total items (flattened): ${totalItems}`);
  
  // Render tree in sidebar
  renderFileTree(tree);
  
  // Start analysis
  analyzeRepository(repoInfo, tree);
}

function createSidebar() {
  // Create sidebar HTML structure (similar to Octotree)
  const sidebarHTML = `
    <div class="cleancode-sidebar" id="cleancode-sidebar">
      <div class="cleancode-header">
        <div class="cleancode-repo-info">
          <span class="repo-icon">📦</span>
          <span class="repo-name" id="cleancode-repo-name">Loading...</span>
        </div>
        <div class="cleancode-branch-info">
          <span class="branch-icon">🌿</span>
          <span class="branch-name" id="cleancode-branch-name">main</span>
          <button class="cache-clear-btn" id="cache-clear-btn" title="Clear cache and re-analyze">🔄</button>
        </div>
      </div>
      
      <div class="cleancode-tabs">
        <button class="tab active" data-tab="tree">Files</button>
        <button class="tab" data-tab="issues">Issues</button>
      </div>
      
      <div class="cleancode-content">
        <div class="tab-content active" id="tab-tree">
          <div class="cleancode-loading">
            <div class="spinner"></div>
            <p>Loading repository...</p>
          </div>
          <div id="cleancode-tree" class="cleancode-tree"></div>
        </div>
        
        <div class="tab-content" id="tab-issues">
          <div id="cleancode-issues-list" class="issues-list">
            <p class="placeholder">Analyzing code...</p>
          </div>
        </div>
      </div>
      
      <div class="cleancode-footer">
        <span class="powered-by">Powered by CleanCodeAgent</span>
      </div>
    </div>
    
    <div class="cleancode-toggle" id="cleancode-toggle">
      <span class="toggle-icon">▶</span>
      <span class="toggle-text">CleanCode</span>
    </div>
  `;
  
  $('body').append(sidebarHTML);
  
  // Cache clear button handler
  $('#cache-clear-btn').click(function() {
    console.log('[CleanCodeAgent] Clearing cache...');
    if (window.analysisEngine) {
      window.analysisEngine.clearCache();
    }
    // Reload the page to re-analyze
    window.location.reload();
  });
  
  // Toggle button click
  $('#cleancode-toggle').click(function() {
    $('body').toggleClass('cleancode-show');
    if ($('body').hasClass('cleancode-show')) {
      $(this).find('.toggle-icon').text('◀');
    } else {
      $(this).find('.toggle-icon').text('▶');
    }
  });
  
  // Tab switching
  $('.cleancode-tabs .tab').click(function() {
    const tabName = $(this).data('tab');
    $('.cleancode-tabs .tab').removeClass('active');
    $(this).addClass('active');
    $('.tab-content').removeClass('active');
    $(`#tab-${tabName}`).addClass('active');
  });
}

function renderFileTree(tree) {
  // Hide loading
  $('.cleancode-loading').hide();
  
  // Convert hierarchical tree to jsTree format recursively
  function toJsTreeFormat(items) {
    if (!items || items.length === 0) return [];
    
    return items.map(item => {
      const node = {
        id: item.path,
        text: item.name + (item.issueCount ? ` <span class="issue-badge ${item.severity}">${item.issueCount}</span>` : ''),
        icon: item.type === 'tree' ? 'jstree-folder' : 'jstree-file',
        data: item
      };
      
      // If it's a folder and has children, recursively convert them
      if (item.type === 'tree' && item.children && item.children.length > 0) {
        node.children = toJsTreeFormat(item.children);
      }
      
      return node;
    });
  }
  
  const treeData = toJsTreeFormat(tree);
  
  console.log('[CleanCodeAgent] Rendering tree with', treeData.length, 'root items');
  
  // Initialize jsTree with worker disabled to avoid CSP violations
  try {
    $('#cleancode-tree').jstree({
      core: {
        data: treeData,
        themes: {
          name: 'default',
          responsive: true
        },
        worker: false  // Disable web workers to comply with GitHub CSP
      }
    }).on('select_node.jstree', function(e, data) {
      // File click করলে details dekhao
      showFileDetails(data.node.data);
    });
  } catch (error) {
    console.error('[CleanCodeAgent] Error initializing jsTree:', error);
    // Fallback: show simple file list if jsTree fails
    showSimpleFileList(tree);
  }
}

function showSimpleFileList(tree) {
  console.log('[CleanCodeAgent] Using fallback simple file list');
  
  // Flatten tree for simple display
  const allItems = flattenTree(tree);
  
  const listHTML = allItems.map(item => 
    `<div class="file-item" data-path="${item.path}">
      ${item.type === 'tree' ? '📁' : '📄'} ${item.path}
      ${item.issueCount ? `<span class="badge">${item.issueCount}</span>` : ''}
    </div>`
  ).join('');
  
  $('#cleancode-tree').html(`<div class="simple-file-list">${listHTML}</div>`);
  
  $('.file-item').click(function() {
    const path = $(this).data('path');
    const item = allItems.find(t => t.path === path);
    if (item) showFileDetails(item);
  });
}

// Helper function to flatten hierarchical tree into a flat array
function flattenTree(tree) {
  const result = [];
  
  function traverse(items) {
    if (!items) return;
    
    for (const item of items) {
      result.push(item);
      
      // Recursively traverse children if it's a folder
      if (item.type === 'tree' && item.children) {
        traverse(item.children);
      }
    }
  }
  
  traverse(tree);
  return result;
}

async function analyzeRepository(repoInfo, tree) {
  console.log('[CleanCodeAgent] Starting repository analysis...');
  console.log('[CleanCodeAgent] Tree structure received:', tree.length, 'top-level items');
  
  // Show analyzing status
  $('#tab-issues .placeholder').html(`
    <div class="analyzing-status">
      <div class="spinner"></div>
      <h3>Analyzing Repository...</h3>
      <p id="analysis-progress">Fetching Java files...</p>
    </div>
  `);
  
  try {
    // Create global analysis engine instance
    if (!window.analysisEngine) {
      window.analysisEngine = new AnalysisEngine(API_URL);
    }
    
    // Flatten the hierarchical tree to get all files (including subdirectories)
    const allFiles = flattenTree(tree);
    console.log(`[CleanCodeAgent] Total files after flattening: ${allFiles.length}`);
    
    // Filter only Java files from ALL files (including subdirectories)
    const javaFiles = allFiles.filter(item => 
      item.type === 'blob' && item.path.endsWith('.java')
    );
    
    console.log(`[CleanCodeAgent] Found ${javaFiles.length} Java files`);
    
    // Debug: Log first 10 Java files found
    if (javaFiles.length > 0) {
      console.log('[CleanCodeAgent] Sample Java files found:');
      javaFiles.slice(0, 10).forEach(file => {
        console.log(`  - ${file.path}`);
      });
    }
    
    if (javaFiles.length === 0) {
      // Show all files to help debug
      console.log('[CleanCodeAgent] No Java files found. All files in repo:');
      allFiles.slice(0, 20).forEach(file => {
        console.log(`  - ${file.path} (${file.type})`);
      });
      
      $('#tab-issues .placeholder').html(`
        <div class="no-files-message">
          <div class="info-icon">ℹ️</div>
          <h3>No Java Files Found</h3>
          <p>This repository doesn't contain any Java source files (.java) to analyze.</p>
          <p class="error-hint">Total files found: ${allFiles.length}</p>
          <p class="error-hint">Check browser console for file list.</p>
        </div>
      `);
      return;
    }
    
    updateAnalysisProgress(`Found ${javaFiles.length} Java files. Fetching content...`);
    
    // Fetch file contents (limit to first 15 files for performance)
    const maxFiles = 15;
    const filesToAnalyze = javaFiles.slice(0, maxFiles);
    const filesData = [];
    
    for (let i = 0; i < filesToAnalyze.length; i++) {
      const file = filesToAnalyze[i];
      updateAnalysisProgress(`Fetching file ${i + 1}/${filesToAnalyze.length}: ${file.path}`);
      
      try {
        const content = await fetchFileContent(repoInfo, file.path);
        filesData.push({
          path: file.path,
          content: content
        });
        console.log(`[CleanCodeAgent] ✓ Loaded ${file.path} (${content.length} chars)`);
      } catch (e) {
        console.error(`[CleanCodeAgent] ✗ Failed to fetch ${file.path}:`, e);
      }
    }
    
    if (filesData.length === 0) {
      throw new Error('Failed to fetch any file content');
    }
    
    console.log(`[CleanCodeAgent] Successfully loaded ${filesData.length} files`);
    updateAnalysisProgress(`Sending ${filesData.length} files to analysis server...`);
    
    // Call backend API
    const response = await fetch(`${API_URL}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        repo: `${repoInfo.username}/${repoInfo.reponame}`,
        files: filesData
      })
    });
    
    if (!response.ok) {
      throw new Error(`Server returned ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    
    if (result.status === 'success') {
      console.log('[CleanCodeAgent] ✅ Analysis complete:', result);
      displayAnalysisResults(result.results, result.summary);
      
      // Update tree with issue counts
      updateTreeWithIssues(result.results);
    } else {
      throw new Error(result.message || 'Analysis failed');
    }
    
  } catch (error) {
    console.error('[CleanCodeAgent] ❌ Analysis error:', error);
    $('#tab-issues .placeholder').html(`
      <div class="error-message">
        <div class="error-icon">❌</div>
        <h3>Analysis Failed</h3>
        <p>${error.message}</p>
        <p class="error-hint">Make sure the backend server is running at ${API_URL}</p>
        <button class="retry-btn" onclick="window.location.reload()">Retry</button>
      </div>
    `);
  }
}

function updateAnalysisProgress(message) {
  const $progress = $('#analysis-progress');
  if ($progress.length) {
    $progress.text(message);
  }
}

function isAnalyzableFile(path) {
  const extensions = ['.java', '.js', '.py', '.ts', '.cpp', '.c', '.cs', '.go'];
  return extensions.some(ext => path.endsWith(ext));
}

async function fetchFileContent(repoInfo, filePath) {
  const url = `https://api.github.com/repos/${repoInfo.username}/${repoInfo.reponame}/contents/${filePath}?ref=${repoInfo.branch}`;
  
  const response = await fetch(url);
  const data = await response.json();
  
  // Decode base64 content
  return atob(data.content);
}

function displayAnalysisResults(results, summary) {
  const $issuesList = $('#cleancode-issues-list');
  $issuesList.empty();
  
  // Check if we have any results
  if (!results || results.length === 0) {
    $issuesList.html('<p class="placeholder">No files analyzed.</p>');
    return;
  }
  
  // Add summary header
  const totalIssues = summary?.total_issues || 0;
  const successfulFiles = summary?.successful_files || 0;
  const totalFiles = summary?.total_files || 0;
  
  $issuesList.append(`
    <div class="analysis-summary">
      <h3>📊 Analysis Summary</h3>
      <div class="summary-stats">
        <div class="stat">
          <span class="stat-value">${totalFiles}</span>
          <span class="stat-label">Files Analyzed</span>
        </div>
        <div class="stat">
          <span class="stat-value">${totalIssues}</span>
          <span class="stat-label">Issues Found</span>
        </div>
        <div class="stat">
          <span class="stat-value">${successfulFiles}</span>
          <span class="stat-label">Successful</span>
        </div>
      </div>
    </div>
  `);
  
  // Show message if no issues found
  if (totalIssues === 0) {
    $issuesList.append(`
      <div class="no-issues-message">
        <div class="success-icon">✅</div>
        <h3>No Design Issues Found</h3>
        <p>Excellent! The analyzed Java files appear to be well-structured.</p>
      </div>
    `);
    $('.tab[data-tab="issues"]').html('Issues <span class="badge success">0</span>');
    return;
  }
  
  // Display results for each file
  results.forEach(fileResult => {
    const issues = fileResult.issues || [];
    
    if (issues.length === 0) return;
    
    // File header
    const fileId = fileResult.file.replace(/[^a-zA-Z0-9]/g, '_');
    $issuesList.append(`
      <div class="file-issues-group">
        <div class="file-header" onclick="$(this).next().slideToggle()">
          <span class="file-icon">📄</span>
          <span class="file-path">${fileResult.file}</span>
          <span class="issue-count-badge">${issues.length}</span>
          <span class="expand-icon">▼</span>
        </div>
        <div class="issues-container" id="issues-${fileId}">
        </div>
      </div>
    `);
    
    const $container = $(`#issues-${fileId}`);
    
    // Sort by rank
    issues.sort((a, b) => (a.rank || 0) - (b.rank || 0));
    
    // Display each issue
    issues.forEach(issue => {
      const severityClass = getSeverityClass(issue.rank);
      const severityLabel = getSeverityLabel(issue.rank);
      
      $container.append(`
        <div class="issue-card ${severityClass}">
          <div class="issue-header">
            <span class="severity-badge ${severityClass}">${severityLabel}</span>
            <span class="rank-badge">Rank #${issue.rank || 'N/A'}</span>
          </div>
          <div class="issue-title">
            <strong>${issue["Class name"]}.${issue["Function name"]}</strong>
          </div>
          <div class="issue-signature">
            <code>${issue["Function signature"]}</code>
          </div>
          <div class="issue-refactoring">
            <span class="refactoring-badge">${issue.refactoring_type}</span>
          </div>
          <div class="issue-rationale">
            ${issue.rationale}
          </div>
        </div>
      `);
    });
  });
  
  // Update tab with count
  $('.tab[data-tab="issues"]').html(`Issues <span class="badge">${totalIssues}</span>`);
  
  // Auto-switch to issues tab
  $('.tab[data-tab="issues"]').click();
}

function updateTreeWithIssues(results) {
  // Add issue counts to file tree
  results.forEach(fileResult => {
    const issueCount = fileResult.issues?.length || 0;
    if (issueCount > 0) {
      const fileElem = $(`.file-item[data-path="${fileResult.file}"]`);
      if (fileElem.length) {
        fileElem.append(`<span class="badge issue-badge">${issueCount}</span>`);
      }
    }
  });
}

function getSeverityClass(rank) {
  if (rank <= 2) return 'severity-high';
  if (rank <= 5) return 'severity-medium';
  return 'severity-low';
}

function getSeverityLabel(rank) {
  if (rank <= 2) return 'High Priority';
  if (rank <= 5) return 'Medium';
  return 'Low';
}

function showFileDetails(fileData) {
  console.log('[CleanCodeAgent] File selected:', fileData);
  // TODO: Show file details in a panel
}

