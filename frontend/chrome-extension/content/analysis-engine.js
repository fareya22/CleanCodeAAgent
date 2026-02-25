class AnalysisEngine {
  constructor(apiUrl = 'http://localhost:5000') {
    this.apiUrl = apiUrl;
    this.cache = new Map(); 
  }

  
  async analyzeRepository(repoInfo, files) {
    console.log('[AnalysisEngine] Starting repository analysis...');
    
    const cacheKey = `${repoInfo.username}/${repoInfo.reponame}`;
    
    
    if (this.cache.has(cacheKey)) {
      console.log('[AnalysisEngine] Returning cached results');
      return this.cache.get(cacheKey);
    }

    
    const analyzableFiles = files.filter(f => this.isAnalyzable(f.path));
    console.log(`[AnalysisEngine] Found ${analyzableFiles.length} analyzable files`);

    try {
      
      const filesData = await this._prepareFiles(repoInfo, analyzableFiles);

      
      const results = await this._callAnalysisAPI(cacheKey, filesData);


      this.cache.set(cacheKey, results);

      return results;

    } catch (error) {
      console.error('[AnalysisEngine] Analysis failed:', error);
      throw error;
    }
  }

  
  async analyzeFile(repoInfo, filePath, fileContent) {
    console.log(`[AnalysisEngine] Analyzing file: ${filePath}`);

    try {
      const response = await fetch(`${this.apiUrl}/analyze-file`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          path: filePath,
          content: fileContent
        })
      });

      const result = await response.json();

      if (result.status === 'success') {
        return result.issues || [];
      } else {
        throw new Error(result.message || 'Analysis failed');
      }

    } catch (error) {
      console.error(`[AnalysisEngine] Failed to analyze ${filePath}:`, error);
      return [];
    }
  }

  
  isAnalyzable(filePath) {
    const analyzableExtensions = [
      '.java', '.js', '.jsx', '.ts', '.tsx',
      '.py', '.cpp', '.c', '.h', '.cs',
      '.go', '.rb', '.php', '.swift', '.kt'
    ];

    return analyzableExtensions.some(ext => filePath.toLowerCase().endsWith(ext));
  }

  
  async _prepareFiles(repoInfo, files) {
    const adapter = new GitHubAdapter();
    await adapter.loadToken();
    
    const filesData = [];
    const maxFiles = 20; 

    for (let i = 0; i < Math.min(files.length, maxFiles); i++) {
      const file = files[i];
      
      try {
        const content = await adapter.getFileContent(repoInfo, file.path);
        filesData.push({
          path: file.path,
          content: content
        });
        
        console.log(`[AnalysisEngine] Loaded ${file.path} (${content.length} chars)`);
      } catch (error) {
        console.error(`[AnalysisEngine] Failed to load ${file.path}:`, error);
      }
    }

    return filesData;
  }

  
  async _callAnalysisAPI(repo, filesData) {
    console.log(`[AnalysisEngine] Calling API for ${filesData.length} files...`);

    const response = await fetch(`${this.apiUrl}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        repo: repo,
        files: filesData
      })
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }

    const result = await response.json();

    if (result.status !== 'success') {
      throw new Error(result.message || 'Analysis failed');
    }

    return result.results;
  }

  
  updateTreeWithIssues(tree, analysisResults) {
    console.log('[AnalysisEngine] Updating tree with issues...');

    
    const issueMap = new Map();
    
    analysisResults.forEach(result => {
      if (result.issues && result.issues.length > 0) {
        issueMap.set(result.file, result.issues);
      }
    });

    
    this._updateTreeNodes(tree, issueMap);

    return tree;
  }

  
  _updateTreeNodes(nodes, issueMap) {
    nodes.forEach(node => {
      if (node.type === 'blob' && issueMap.has(node.path)) {
        const issues = issueMap.get(node.path);
        node.issueCount = issues.length;
        node.severity = this._calculateSeverity(issues);
        node.issues = issues;
      }

      if (node.children) {
        this._updateTreeNodes(node.children, issueMap);
        
        
        const childIssueCount = node.children.reduce((sum, child) => sum + (child.issueCount || 0), 0);
        if (childIssueCount > 0) {
          node.issueCount = childIssueCount;
          node.severity = 'folder-with-issues';
        }
      }
    });
  }

  
  _calculateSeverity(issues) {
    if (!issues || issues.length === 0) return 'none';

    const minRank = Math.min(...issues.map(i => i.rank || 999));

    if (minRank <= 2) return 'high';
    if (minRank <= 5) return 'medium';
    return 'low';
  }

 
  getIssueSummary(analysisResults) {
    let totalIssues = 0;
    let highPriority = 0;
    let mediumPriority = 0;
    let lowPriority = 0;

    const issuesByType = {};

    analysisResults.forEach(result => {
      if (result.issues) {
        result.issues.forEach(issue => {
          totalIssues++;

          
          const rank = issue.rank || 999;
          if (rank <= 2) highPriority++;
          else if (rank <= 5) mediumPriority++;
          else lowPriority++;

          
          const refType = issue.refactoring_type || 'unknown';
          issuesByType[refType] = (issuesByType[refType] || 0) + 1;
        });
      }
    });

    return {
      total: totalIssues,
      high: highPriority,
      medium: mediumPriority,
      low: lowPriority,
      byType: issuesByType
    };
  }


  clearCache() {
    this.cache.clear();
    console.log('[AnalysisEngine] Cache cleared');
  }
}
