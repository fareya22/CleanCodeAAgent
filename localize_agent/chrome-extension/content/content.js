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
        <div class="feedback-section">
          <div class="feedback-toggle" id="feedback-toggle">
             Give feedback
          </div>
          <div class="feedback-form hidden" id="feedback-form">
            <input type="email" id="feedback-email" class="feedback-input" placeholder="Your email" />
            <textarea id="feedback-comment" class="feedback-input feedback-textarea" placeholder="Describe the incorrect detection..."></textarea>
            <div class="feedback-actions">
              <button class="feedback-submit-btn" id="feedback-submit-btn">Send Feedback</button>
              <span class="feedback-status" id="feedback-status"></span>
            </div>
          </div>
        </div>
        <button class="download-pdf-btn" id="download-pdf-btn" title="Download Analysis Report as PDF">
          📄 Download  Report
        </button>
        <span class="powered-by">Powered by CleanCodeAgent</span>
      </div>
    </div>
    
    <div class="cleancode-toggle" id="cleancode-toggle">
      <span class="toggle-icon">◀</span>
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
  
  // PDF Download button handler
  $('#download-pdf-btn').click(function() {
    console.log('[CleanCodeAgent] Generating PDF report...');
    downloadAnalysisReport();
  });

  // Feedback toggle
  $('#feedback-toggle').click(function() {
    $('#feedback-form').toggleClass('hidden');
  });

  // Feedback submit
  $('#feedback-submit-btn').click(function() {
    const email = $('#feedback-email').val().trim();
    const comment = $('#feedback-comment').val().trim();
    if (!email || !comment) {
      $('#feedback-status').text('Please fill in both fields.').css('color', '#cf222e');
      return;
    }
    submitFeedback(email, comment);
  });
  
  // Toggle button click
  $('#cleancode-toggle').click(function() {
    $('body').toggleClass('cleancode-show');
    if ($('body').hasClass('cleancode-show')) {
      $(this).find('.toggle-icon').text('▶');
    } else {
      $(this).find('.toggle-icon').text('◀');
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

function restoreResultsUI(data, repoInfo) {
  const $issuesList = $('#cleancode-issues-list');

  // Set global state
  window.currentRepoInfo = repoInfo;
  window.analysisResults = data;

  // Clear placeholder and prepare list
  $('#tab-issues .placeholder').empty();
  $issuesList.empty();

  // Re-render each file's result using the existing renderer (click handlers reattached)
  data.results.forEach((result, index) => {
    addFileResultToUI({
      file: result.file,
      issues: result.issues || [],
      summary: result.summary || ''
    }, data.results.length, index + 1);
  });

  // Restore summary header and tab badge
  displayFinalSummary(
    data.results,
    data.summary.successfulFiles,
    data.summary.totalIssues,
    data.summary.totalFiles
  );

  // After restoring UI, check if there's a line number in URL hash and scroll to it
  const hashMatch = window.location.hash.match(/L(\d+)/);
  if (hashMatch) {
    const lineNumber = parseInt(hashMatch[1]);
    console.log(`[Restore] Found line ${lineNumber} in URL hash, scrolling...`);
    // Wait longer for GitHub's code rendering and DOM stabilization
    setTimeout(() => {
      scrollToLineNumber(lineNumber);
    }, 800);
  }
}

async function analyzeRepository(repoInfo, tree) {
  console.log('[CleanCodeAgent] Starting repository analysis...');
  console.log('[CleanCodeAgent] Tree structure received:', tree.length, 'top-level items');

  // Store globally so issue cards can build fallback GitHub URLs
  window.currentRepoInfo = repoInfo;

  // If we arrived here via an issue-click navigation, restore previous results instead of re-analyzing
  const savedRestore = sessionStorage.getItem('cleancode_restore');
  if (savedRestore) {
    sessionStorage.removeItem('cleancode_restore'); // consume once
    try {
      const data = JSON.parse(savedRestore);
      console.log('[CleanCodeAgent] Restoring results after navigation — skipping analysis');
      restoreResultsUI(data, repoInfo);
      return;
    } catch (e) {
      console.warn('[CleanCodeAgent] Restore failed, running fresh analysis:', e);
    }
  }

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
    
    updateAnalysisProgress(`Found ${javaFiles.length} Java files. Starting sequential analysis...`);
    
    // Analyze files ONE-BY-ONE with progressive results (limit to first 15 files)
    const maxFiles = 15;
    const filesToAnalyze = javaFiles.slice(0, maxFiles);
    const allResults = [];
    let successfulFiles = 0;
    let totalIssues = 0;
    
    // Initialize results display
    $('#tab-issues .placeholder').empty();
    const $issuesList = $('#cleancode-issues-list');
    $issuesList.empty();
    $issuesList.append(`<div id="live-progress-container" style="padding: 20px;"></div>`);
    
    // Analyze each file sequentially
    for (let i = 0; i < filesToAnalyze.length; i++) {
      const file = filesToAnalyze[i];
      const progressPercent = Math.round((i / filesToAnalyze.length) * 100);
      
      // Show current file being analyzed
      updateAnalysisProgress(`[${i + 1}/${filesToAnalyze.length}] Currently analyzing: ${file.path} (${progressPercent}%)`);
      
      const $progressContainer = $('#live-progress-container');
      $progressContainer.html(`
        <div class="current-file-analysis">
          <div class="progress-info">
            <div class="file-name">📄 ${file.path}</div>
            <div class="progress-bar">
              <div class="progress-fill" style="width: ${progressPercent}%"></div>
            </div>
            <div class="progress-text">${i + 1} of ${filesToAnalyze.length} files (${progressPercent}%)</div>
          </div>
          <div class="spinner" style="margin-top: 15px;"></div>
        </div>
      `);
      
      try {
        // Fetch file content
        console.log(`[CleanCodeAgent] Fetching file ${i + 1}/${filesToAnalyze.length}: ${file.path}`);
        const content = await fetchFileContent(repoInfo, file.path);
        console.log(`[CleanCodeAgent] ✓ Loaded ${file.path} (${content.length} chars)`);
        
        // Analyze single file via API
        console.log(`[CleanCodeAgent] Analyzing ${file.path}...`);
        const response = await fetch(`${API_URL}/analyze-file`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            path: file.path,
            content: content,
            repo: `${repoInfo.username}/${repoInfo.reponame}`,
            branch: repoInfo.branch
          })
        });
        
        if (!response.ok) {
          throw new Error(`Server returned ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        if (result.status === 'success') {
          console.log(`[CleanCodeAgent] ✅ Analysis complete for ${file.path}`);
          allResults.push(result);
          successfulFiles++;
          
          const fileIssues = result.issues || [];
          totalIssues += fileIssues.length;
          
          // Add/update file result in UI immediately (pass summary along with result)
          addFileResultToUI({
            file: result.file,
            issues: result.issues,
            summary: result.summary
          }, filesToAnalyze.length, i + 1);
          
        } else {
          console.error(`[CleanCodeAgent] ⚠️ Analysis failed for ${file.path}:`, result.message);
          allResults.push({
            file: file.path,
            status: 'failed',
            message: result.message,
            issues: []
          });
        }
        
      } catch (e) {
        console.error(`[CleanCodeAgent] ❌ Error analyzing ${file.path}:`, e);
        allResults.push({
          file: file.path,
          status: 'failed',
          message: e.message,
          issues: []
        });
      }
      
      // Add delay between files to avoid rate limiting
      if (i < filesToAnalyze.length - 1) {
        await new Promise(resolve => setTimeout(resolve, 1500));
      }
    }
    
    // Final summary
    console.log(`[CleanCodeAgent] ✅ Analysis complete for all ${filesToAnalyze.length} files`);
    removeCurrentFileIndicator();
    displayFinalSummary(allResults, successfulFiles, totalIssues, filesToAnalyze.length);
    
    // Store results globally for PDF export
    window.analysisResults = {
      repo: `${repoInfo.username}/${repoInfo.reponame}`,
      branch: repoInfo.branch,
      results: allResults,
      summary: {
        totalFiles: filesToAnalyze.length,
        successfulFiles: successfulFiles,
        totalIssues: totalIssues
      },
      timestamp: new Date().toISOString()
    };

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

function removeCurrentFileIndicator() {
  $('#live-progress-container').remove();
}

function addFileResultToUI(fileResult, totalFiles, currentIndex) {
  const $issuesList = $('#cleancode-issues-list');
  const issues = fileResult.issues || [];
  const summary = fileResult.summary || '';
  
  // Create file result container
  const fileId = fileResult.file.replace(/[^a-zA-Z0-9]/g, '_');
  
  let fileHTML = `
    <div class="file-issues-group file-result-${fileId}">
      <div class="file-header" onclick="$(this).next().slideToggle()">
        <span class="file-icon">📄</span>
        <span class="file-path">${fileResult.file}</span>
  `;
  
  if (issues.length > 0) {
    fileHTML += `<span class="issue-count-badge">${issues.length}</span>`;
  } else {
    fileHTML += `<span class="status-badge clean">✓ Clean</span>`;
  }
  
  fileHTML += `
        <span class="expand-icon">▼</span>
      </div>
      <div class="issues-container" id="issues-${fileId}">
  `;
  
  // Show summary if available
  if (summary) {
    fileHTML += `
      <div class="analysis-summary-text" style="background: #f6f8fa; padding: 15px; border-radius: 4px; margin-bottom: 15px; font-size: 14px; line-height: 1.6; color: #57606a;">
        <strong>Analysis Summary:</strong>
        <div style="margin-top: 10px; white-space: pre-wrap;">
          ${summary.split('\n').slice(0, 10).join('\n')}
          ${summary.split('\n').length > 10 ? '\n... (truncated)' : ''}
        </div>
      </div>
    `;
  }
  
  if (issues.length === 0) {
    fileHTML += `<p class="no-issues" style="padding: 10px; color: #28a745;">No issues found in this file</p>`;
  } else {
    // Sort by rank and display each issue
    issues.sort((a, b) => (a.rank || 0) - (b.rank || 0));
    
    fileHTML += `<div style="margin-top: 15px;"><strong style="font-size: 13px; color: #57606a;">Identified Issues:</strong></div>`;
    
    // Track links for click handler attachment
    const linkHandlers = [];
    
    issues.forEach(issue => {
      const severityClass = getSeverityClass(issue.rank);
      const severityLabel = getSeverityLabel(issue.rank);
      
      // Resolve GitHub URL - use issue URL if present, otherwise build from repo info
      let githubUrl = (issue.github_url && issue.github_url.length > 0) ? issue.github_url : '';

      if (!githubUrl && window.currentRepoInfo) {
        const ri = window.currentRepoInfo;
        githubUrl = `https://github.com/${ri.username}/${ri.reponame}/blob/${ri.branch}/${fileResult.file}`;
      }

      console.log(`[Issue Link] ${issue["Class name"]}.${issue["Function name"]} -> ${githubUrl}`);

      // Extract issue type (with fallback parsing from rationale if not present)
      const issueType = issue.issue_type || extractIssueTypeFromRationale(issue.rationale, issue.refactoring_type);

      // Create clickable class.method name — navigation target (line) is embedded in githubUrl hash by backend AST
      const classMethodText = `${issue["Class name"]}.${issue["Function name"]}`;
      const linkId = `issue-link-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const clickableTitle = githubUrl
        ? `<a href="#" id="${linkId}" data-github-url="${githubUrl.replace(/"/g, '&quot;')}" data-line="${issue.line || ''}" style="color: #0969da; text-decoration: none; border-bottom: 1px solid #0969da;">${classMethodText}</a>`
        : classMethodText;

      fileHTML += `
        <div class="issue-card ${severityClass}">
          <div class="issue-header">
            <span class="severity-badge ${severityClass}">${severityLabel}</span>
            <span class="rank-badge">Rank #${issue.rank || 'N/A'}</span>
          </div>
          <div class="issue-type-display">
            <span class="issue-type-badge">${issueType}</span>
          </div>
          <div class="issue-title">
            <strong>${clickableTitle}</strong>
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
      `;
      
      // Store link info for later attachment
      if (githubUrl) {
        linkHandlers.push({ linkId, githubUrl });
      }
    });
  
    // Attach click handlers after DOM insertion
    setTimeout(() => {
      linkHandlers.forEach(({ linkId, githubUrl }) => {
        const link = document.getElementById(linkId);
        if (link) {
          link.addEventListener('click', (e) => {
            e.preventDefault();
            console.log(`[Click] Navigating to: ${githubUrl}`);
            navigateToCode(githubUrl);
          });
        }
      });
    }, 0);
  }
  
  fileHTML += `
      </div>
    </div>
  `;
  
  // Append or update the file result
  if ($issuesList.find(`.file-result-${fileId}`).length > 0) {
    $issuesList.find(`.file-result-${fileId}`).replaceWith(fileHTML);
  } else {
    // Remove progress container if this is the first file result
    if ($issuesList.find('.file-issues-group').length === 0) {
      $issuesList.find('#live-progress-container').remove();
    }
    
    // If there's only the progress container, replace it; otherwise append
    if ($issuesList.children().length === 1 && $issuesList.find('#live-progress-container').length > 0) {
      $issuesList.html(fileHTML);
    } else {
      $issuesList.append(fileHTML);
    }
  }
}

function displayFinalSummary(allResults, successfulFiles, totalIssues, totalFiles) {
  const $issuesList = $('#cleancode-issues-list');
  
  // Create summary card
  const summaryHTML = `
    <div class="analysis-summary" style="margin-bottom: 20px; margin-top: -10px;">
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
      </div>
    </div>
  `;
  
  // Prepend summary
  $issuesList.prepend(summaryHTML);
  
  // Update tab with issue count
  if (totalIssues === 0) {
    $('.tab[data-tab="issues"]').html(`Issues <span class="badge success">0</span>`);
  } else {
    $('.tab[data-tab="issues"]').html(`Issues <span class="badge">${totalIssues}</span>`);
  }
  
  // Switch to issues tab
  $('.tab[data-tab="issues"]').click();
  
  // Update tree with issue counts
  const resultsWithIssues = allResults.filter(r => (r.issues || []).length > 0);
  updateTreeWithIssues(resultsWithIssues);
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
      
      // Resolve GitHub URL - use issue URL if present, otherwise build from repo info
      let githubUrl = (issue.github_url && issue.github_url.length > 0) ? issue.github_url : '';

      if (!githubUrl && window.currentRepoInfo) {
        const ri = window.currentRepoInfo;
        githubUrl = `https://github.com/${ri.username}/${ri.reponame}/blob/${ri.branch}/${fileResult.file}`;
      }

      console.log(`[Issue Link] ${issue["Class name"]}.${issue["Function name"]} -> ${githubUrl}`);

      // Extract issue type (with fallback parsing from rationale if not present)
      const issueType = issue.issue_type || extractIssueTypeFromRationale(issue.rationale, issue.refactoring_type);

      // Create clickable class.method name — navigation target (line) is embedded in githubUrl hash by backend AST
      const classMethodText = `${issue["Class name"]}.${issue["Function name"]}`;
      const linkId = `issue-link-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const clickableTitle = githubUrl
        ? `<a href="#" id="${linkId}" data-github-url="${githubUrl.replace(/"/g, '&quot;')}" data-line="${issue.line || ''}" style="color: #0969da; text-decoration: none; border-bottom: 1px solid #0969da;">${classMethodText}</a>`
        : classMethodText;
      
      $container.append(`
        <div class="issue-card ${severityClass}">
          <div class="issue-header">
            <span class="severity-badge ${severityClass}">${severityLabel}</span>
            <span class="rank-badge">Rank #${issue.rank || 'N/A'}</span>
          </div>
          <div class="issue-type-display">
            <span class="issue-type-badge">${issueType}</span>
          </div>
          <div class="issue-title">
            <strong>${clickableTitle}</strong>
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
      
      // Attach click handler after DOM insertion
      if (githubUrl) {
        setTimeout(() => {
          const link = document.getElementById(linkId);
          if (link) {
            link.addEventListener('click', (e) => {
              e.preventDefault();
              const url = link.getAttribute('data-github-url');
              console.log(`[Click] Navigating to: ${url}`);
              navigateToCode(url);
            });
          }
        }, 0);
      }
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

// ============================================
// ISSUE TYPE EXTRACTION HELPER
// ============================================

/**
 * Extract issue type from rationale text and refactoring_type (fallback if issue_type field missing)
 * This mirrors the logic in tasks.yaml ranking_task
 */
function extractIssueTypeFromRationale(rationale, refactoringType) {
  if (!rationale) return 'Unknown';
  
  const rationaleLC = rationale.toLowerCase();
  const refactoringLC = (refactoringType || '').toLowerCase();
  
  // Priority order (first match wins) - mirrors tasks.yaml ranking_task
  
  // 1. God Class
  if (rationaleLC.includes('god class')) return 'God Class';
  if (refactoringLC === 'extract class' && !rationaleLC.includes('feature envy')) return 'God Class';
  
  // 2. Feature Envy
  if (rationaleLC.includes('feature envy')) return 'Feature Envy';
  if (refactoringLC === 'move method') return 'Feature Envy';
  
  // 3. Complexity (includes inline variable, inline method, parameterize variable, extract method)
  if (refactoringLC === 'inline variable' || 
      refactoringLC === 'inline method' || 
      refactoringLC === 'parameterize variable' ||
      refactoringLC === 'extract method') return 'Complexity';
  if (rationaleLC.includes('complexity') || 
      rationaleLC.includes('cyclomatic') || 
      rationaleLC.includes('nesting') ||
      rationaleLC.includes('hard-coded') ||
      rationaleLC.includes('hardcoded') ||
      rationaleLC.includes('magic number') ||
      rationaleLC.includes('inline') || 
      rationaleLC.includes('trivial') || 
      rationaleLC.includes('single-use')) return 'Complexity';
  
  // 4. Modularity
  if (rationaleLC.includes('modularity') || 
      rationaleLC.includes('separation of concerns')) return 'Modularity';
  
  // 5. Information Hiding
  if (rationaleLC.includes('information hiding') || 
      rationaleLC.includes('public field') || 
      rationaleLC.includes('encapsulation')) return 'Information Hiding';
  
  // Default to Unknown if no match
  console.warn('[Issue Type] Could not determine issue type:', { rationale, refactoringType });
  return 'Unknown';
}

// ============================================
// USER FEEDBACK
// ============================================

function submitFeedback(email, comment) {
  const btn = $('#feedback-submit-btn');
  const status = $('#feedback-status');
  btn.prop('disabled', true).text('Sending...');
  status.text('').css('color', '');

  const apiUrl = API_URL + '/feedback';

  fetch(apiUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, comment })
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === 'success') {
        status.text('Feedback sent!').css('color', '#1a7f37');
        $('#feedback-email').val('');
        $('#feedback-comment').val('');
        setTimeout(() => $('#feedback-form').addClass('hidden'), 1500);
      } else {
        status.text(data.message || 'Error sending feedback.').css('color', '#cf222e');
      }
    })
    .catch(() => {
      status.text('Network error. Please try again.').css('color', '#cf222e');
    })
    .finally(() => {
      btn.prop('disabled', false).text('Send Feedback');
    });
}

// ============================================
// PDF REPORT GENERATION
// ============================================

function downloadAnalysisReport() {
  if (!window.analysisResults) {
    alert('No analysis results available. Please run an analysis first.');
    return;
  }
  
  const data = window.analysisResults;
  const timestamp = new Date(data.timestamp).toLocaleString();
  
  // Generate HTML report
  const reportHTML = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>CleanCodeAgent Analysis Report - ${data.repo}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #24292f;
      padding: 40px;
      background: #ffffff;
    }
    .header {
      border-bottom: 3px solid #24292f;
      padding-bottom: 20px;
      margin-bottom: 30px;
    }
    h1 {
      font-size: 32px;
      color: #24292f;
      margin-bottom: 10px;
    }
    .meta {
      color: #57606a;
      font-size: 14px;
    }
    .meta span {
      margin-right: 20px;
    }
    .summary {
      background: #f6f8fa;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 30px;
      display: flex;
      justify-content: space-around;
    }
    .stat {
      text-align: center;
    }
    .stat-value {
      font-size: 36px;
      font-weight: bold;
      color: #24292f;
      display: block;
    }
    .stat-label {
      color: #57606a;
      font-size: 14px;
      margin-top: 5px;
    }
    .file-section {
      margin-bottom: 40px;
      page-break-inside: avoid;
    }
    .file-header {
      background: #24292f;
      color: white;
      padding: 12px 20px;
      border-radius: 6px 6px 0 0;
      font-weight: 600;
      font-size: 16px;
    }
    .file-status {
      background: #f6f8fa;
      color: #24292f;
      padding: 12px 20px;
      border-radius: 6px;
      margin-bottom: 10px;
      text-align: center;
      font-weight: 600;
      border: 1px solid #d0d7de;
    }
    .issue {
      border: 1px solid #d0d7de;
      border-radius: 6px;
      padding: 16px;
      margin-bottom: 16px;
      background: white;
      page-break-inside: avoid;
    }
    .issue-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 12px;
    }
    .severity {
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      background: #24292f;
      color: white;
    }
    .severity-high {
      background: #24292f;
      color: white;
    }
    .severity-medium {
      background: #57606a;
      color: white;
    }
    .severity-low {
      background: #6e7781;
      color: white;
    }
    .rank {
      background: #f6f8fa;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      color: #57606a;
    }
    .issue-title {
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 8px;
      color: #24292f;
    }
    .issue-signature {
      background: #f6f8fa;
      padding: 8px 12px;
      border-radius: 4px;
      font-family: "Courier New", monospace;
      font-size: 13px;
      margin-bottom: 12px;
      color: #1f2328;
    }
    .refactoring {
      background: #24292f;
      color: white;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      display: inline-block;
      margin-bottom: 12px;
    }
    .rationale {
      color: #57606a;
      font-size: 14px;
      line-height: 1.6;
    }
    .footer {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 1px solid #d0d7de;
      text-align: center;
      color: #57606a;
      font-size: 12px;
    }
    @media print {
      body { padding: 20px; }
      .file-section { page-break-inside: avoid; }
      .issue { page-break-inside: avoid; }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>📊 CleanCodeAgent Analysis Report</h1>
    <div class="meta">
      <span>📦 <strong>Repository:</strong> ${data.repo}</span>
      <span>🌿 <strong>Branch:</strong> ${data.branch}</span>
      <span>📅 <strong>Generated:</strong> ${timestamp}</span>
    </div>
  </div>
  
  <div class="summary">
    <div class="stat">
      <span class="stat-value">${data.summary.totalFiles}</span>
      <span class="stat-label">Files Analyzed</span>
    </div>
    <div class="stat">
      <span class="stat-value">${data.summary.totalIssues}</span>
      <span class="stat-label">Issues Found</span>
    </div>
  </div>
  
  ${generateFileReports(data.results)}
  
  <div class="footer">
    <p>Generated by CleanCodeAgent - AI-Powered Code Quality Analysis</p>
    <p>Powered by AWS Bedrock Claude</p>
  </div>
</body>
</html>
  `;
  
  // Download as HTML file
  const blob = new Blob([reportHTML], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `CleanCodeAgent_Report_${data.repo.replace('/', '_')}_${new Date().toISOString().split('T')[0]}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  
  console.log('[CleanCodeAgent] Report downloaded successfully');
  
  // Show success message
  alert('✅ Report downloaded! Open the HTML file and use your browser\'s "Print to PDF" feature to save as PDF.');
}

function generateFileReports(results) {
  let html = '';
  
  results.forEach(fileResult => {
    const issues = fileResult.issues || [];
    
    html += `<div class="file-section">`;
    html += `<div class="file-header">📄 ${fileResult.file}</div>`;
    
    if (issues.length === 0) {
      html += `<div class="file-status">✅ No issues found - Code is clean!</div>`;
    } else {
      // Sort by rank
      issues.sort((a, b) => (a.rank || 0) - (b.rank || 0));
      
      issues.forEach(issue => {
        const severityClass = getSeverityClass(issue.rank);
        const severityLabel = getSeverityLabel(issue.rank);
        const issueType = issue.issue_type || extractIssueTypeFromRationale(issue.rationale, issue.refactoring_type);
        
        html += `
          <div class="issue">
            <div class="issue-header">
              <span class="severity ${severityClass}">${severityLabel}</span>
              <span class="rank">Rank #${issue.rank || 'N/A'}</span>
            </div>
            <div style="margin-bottom: 8px;">
              <span style="background: #f6f8fa; color: #24292f; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; border: 1px solid #d0d7de;">${issueType}</span>
            </div>
            <div class="issue-title">
              ${issue["Class name"]}.${issue["Function name"]}
            </div>
            <div class="issue-signature">
              ${escapeHtml(issue["Function signature"])}
            </div>
            <div>
              <span class="refactoring">${issue.refactoring_type}</span>
            </div>
            <div class="rationale">
              ${escapeHtml(issue.rationale)}
            </div>
          </div>
        `;
      });
    }
    
    html += `</div>`;
  });
  
  return html;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ============================================
// NAVIGATION HELPERS
// ============================================

/**
 * Navigate to a specific location in a GitHub file.
 * Same file  → scroll + highlight new line (no reload).
 * Other file → save results to sessionStorage, then navigate.
 */
function navigateToCode(githubUrl) {
  let targetUrl;
  try {
    targetUrl = new URL(githubUrl);
  } catch (e) {
    console.error('[Navigation] Invalid URL:', githubUrl);
    return;
  }

  const isOnSameFile = window.location.pathname === targetUrl.pathname;

  // Extract line number from URL hash, e.g. #L42 or #L42-L45
  const hashMatch = targetUrl.hash.match(/L(\d+)/);
  const lineNumber = hashMatch ? parseInt(hashMatch[1]) : null;

  console.log(`[Navigation] url=${githubUrl} sameFile=${isOnSameFile} line=${lineNumber}`);

  if (isOnSameFile) {
    if (lineNumber) {
      console.log(`[Navigation] Same file - updating hash to #L${lineNumber}`);
      // Clear old highlights BEFORE changing hash
      clearCurrentHighlight();
      // Update URL hash
      window.history.replaceState(null, '', `#L${lineNumber}`);
      // GitHub will re-apply .highlighted class, so clear it again and apply ours
      setTimeout(() => {
        clearCurrentHighlight(); // Clear GitHub's auto-highlight from the new hash
        scrollToLineNumber(lineNumber);
      }, 300);
    }
  } else {
    // Save analysis results so the new page can restore them without re-analysing
    if (window.analysisResults) {
      try {
        sessionStorage.setItem('cleancode_restore', JSON.stringify(window.analysisResults));
      } catch (e) {
        console.warn('[Navigation] Could not save results before navigation:', e);
      }
    }
    window.location.href = githubUrl;
  }
}

// Track the currently highlighted line number (not DOM reference, as GitHub may re-render)
let currentHighlightedLine = null;

/**
 * Clear the currently highlighted line by searching for it dynamically
 */
function clearCurrentHighlight() {
  console.log(`[Highlight] Clearing highlights (tracked: ${currentHighlightedLine || 'none'})`);
  
  // 1. Remove our custom highlight class
  const cleanCodeHighlights = document.querySelectorAll('.cleancode-highlight');
  cleanCodeHighlights.forEach(el => {
    el.classList.remove('cleancode-highlight');
    el.style.removeProperty('background-color');
    el.style.removeProperty('display');
    el.style.removeProperty('width');
    
    // If it's a TR, also clear TD backgrounds
    if (el.tagName === 'TR') {
      el.querySelectorAll('td').forEach(td => {
        td.style.removeProperty('background-color');
      });
    }
  });
  
  // 2. Remove GitHub's native .highlighted class (from URL hash navigation)
  const githubHighlights = document.querySelectorAll('.highlighted');
  githubHighlights.forEach(el => {
    el.classList.remove('highlighted');
  });
  
  const totalCleared = cleanCodeHighlights.length + githubHighlights.length;
  if (totalCleared > 0) {
    console.log(`[Highlight] Cleared ${totalCleared} highlighted elements (${cleanCodeHighlights.length} ours, ${githubHighlights.length} GitHub's)`);
  }
  
  currentHighlightedLine = null;
}

/**
 * Scroll to a specific line number on the current GitHub file page
 * and apply a yellow highlight. Call clearCurrentHighlight() before this.
 */
function scrollToLineNumber(lineNumber) {
  console.log(`[Highlight] Scrolling to line ${lineNumber}`);

  // GitHub's new structure uses <div id="LC{n}"> instead of table rows
  const lineElement = document.getElementById(`LC${lineNumber}`);

  if (!lineElement) {
    console.error(`[Highlight] Could not find element LC${lineNumber}`);
    // Try fallback with anchor
    const anchor = document.querySelector(`a[name="L${lineNumber}"]`);
    if (anchor) {
      anchor.scrollIntoView({ behavior: 'smooth', block: 'center' });
      console.warn(`[Highlight] Used anchor fallback for line ${lineNumber}`);
    }
    return;
  }

  console.log(`[Highlight] Found LC${lineNumber}, tag: ${lineElement.tagName}`);

  // Scroll to line
  lineElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
  console.log(`[Highlight] Scrolled to line ${lineNumber}`);

  // For GitHub's new DIV structure, highlight just the LC element itself
  // (parent DIVs are too large and cover multiple lines)
  let highlightTarget = null;

  // Strategy 1: If it's a TR (old table layout), use the TR
  const trParent = lineElement.closest('tr');
  if (trParent) {
    highlightTarget = trParent;
    console.log(`[Highlight] Using TR parent for highlighting`);
    
    // Apply highlight
    highlightTarget.classList.add('cleancode-highlight');
    highlightTarget.style.setProperty('background-color', 'rgba(255, 212, 59, 0.4)', 'important');
    highlightTarget.querySelectorAll('td').forEach(td => {
      td.style.setProperty('background-color', 'rgba(255, 212, 59, 0.4)', 'important');
    });
  } 
  // Strategy 2: DIV structure - highlight just the LC element itself
  else {
    highlightTarget = lineElement;
    console.log(`[Highlight] Highlighting LC element directly (DIV structure)`);
    
    // Apply highlight with strong specificity
    highlightTarget.classList.add('cleancode-highlight');
    highlightTarget.style.setProperty('background-color', 'rgba(255, 212, 59, 0.4)', 'important');
    highlightTarget.style.setProperty('display', 'block', 'important');
    highlightTarget.style.setProperty('width', '100%', 'important');
  }

  if (!highlightTarget) {
    console.error(`[Highlight] Could not determine highlight target`);
    return;
  }
  
  // Store line number for cleanup
  currentHighlightedLine = lineNumber;
  console.log(`[Highlight] Successfully highlighted line ${lineNumber}`);
}