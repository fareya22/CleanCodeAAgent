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
  console.log('[CleanCodeAgent] File tree loaded:', tree.length, 'items');
  
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
  
  // Prepare jsTree data
  const treeData = tree.map(item => ({
    id: item.path,
    text: item.name + (item.issueCount ? ` <span class="issue-badge ${item.severity}">${item.issueCount}</span>` : ''),
    icon: item.type === 'tree' ? 'jstree-folder' : 'jstree-file',
    children: item.type === 'tree' ? true : false,
    data: item
  }));
  
  // Initialize jsTree
  $('#cleancode-tree').jstree({
    core: {
      data: treeData,
      themes: {
        name: 'default',
        responsive: true
      }
    }
  }).on('select_node.jstree', function(e, data) {
    // File click করলে details dekhao
    showFileDetails(data.node.data);
  });
}

async function analyzeRepository(repoInfo, tree) {
  console.log('[CleanCodeAgent] Starting repository analysis...');
  
  // Show analyzing status
  $('#tab-issues .placeholder').text('Analyzing repository...');
  
  try {
    // Get file contents for analyzable files (.java, .js, .py, etc.)
    const analyzableFiles = tree.filter(item => 
      item.type === 'blob' && isAnalyzableFile(item.path)
    );
    
    console.log('[CleanCodeAgent] Analyzable files:', analyzableFiles.length);
    
    // Prepare files for analysis
    const filesData = [];
    for (const file of analyzableFiles.slice(0, 10)) { // First 10 files only for demo
      try {
        const content = await fetchFileContent(repoInfo, file.path);
        filesData.push({
          path: file.path,
          content: content
        });
      } catch (e) {
        console.error(`Failed to fetch ${file.path}:`, e);
      }
    }
    
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
    
    const result = await response.json();
    
    if (result.status === 'success') {
      console.log('[CleanCodeAgent] Analysis complete:', result);
      displayAnalysisResults(result.results);
    } else {
      console.error('[CleanCodeAgent] Analysis failed:', result.message);
      $('#tab-issues .placeholder').text('Analysis failed. Please try again.');
    }
    
  } catch (error) {
    console.error('[CleanCodeAgent] Analysis error:', error);
    $('#tab-issues .placeholder').text('Error connecting to analysis server.');
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

function displayAnalysisResults(results) {
  const $issuesList = $('#cleancode-issues-list');
  $issuesList.empty();
  
  let totalIssues = 0;
  
  results.forEach(fileResult => {
    const issues = fileResult.issues || [];
    totalIssues += issues.length;
    
    if (issues.length === 0) return;
    
    // File header
    $issuesList.append(`
      <div class="file-issues-group">
        <div class="file-header">
          <span class="file-icon">📄</span>
          <span class="file-path">${fileResult.file}</span>
          <span class="issue-count-badge">${issues.length}</span>
        </div>
        <div class="issues-container" id="issues-${fileResult.file.replace(/[^a-zA-Z0-9]/g, '_')}">
        </div>
      </div>
    `);
    
    const $container = $(`#issues-${fileResult.file.replace(/[^a-zA-Z0-9]/g, '_')}`);
    
    // Sort by rank
    issues.sort((a, b) => a.rank - b.rank);
    
    // Display each issue
    issues.forEach(issue => {
      const severityClass = getSeverityClass(issue.rank);
      const severityLabel = getSeverityLabel(issue.rank);
      
      $container.append(`
        <div class="issue-card ${severityClass}">
          <div class="issue-header">
            <span class="severity-badge ${severityClass}">${severityLabel}</span>
            <span class="rank-badge">Rank #${issue.rank}</span>
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

