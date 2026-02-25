class GitHubAdapter {
  constructor() {
    this.apiUrl = 'https://api.github.com';
    this.token = null; 
    this._defaultBranch = {};
  }

  


  async getRepoInfo() {
    
    const match = window.location.pathname.match(/([^\/]+)\/([^\/]+)(?:\/([^\/]+))?(?:\/([^\/]+))?/);
    
    if (!match) {
      throw new Error('Not a valid GitHub repository page');
    }

    const username = match[1];
    const reponame = match[2];
    const type = match[3]; 
    const typeId = match[4];

    
    let branch = await this.detectBranch(username, reponame, type, typeId);

    return {
      username,
      reponame,
      branch,
      type,
      typeId
    };
  }

  


  async detectBranch(username, reponame, type, typeId) {
    
    const branchDropdown = $('.branch-select-menu summary');
    const branchInTitle = branchDropdown.attr('title');
    const branchInSpan = branchDropdown.find('span').text();
    
    const branchFromDOM = 
      branchInTitle && branchInTitle.toLowerCase().startsWith('switch branches')
        ? branchInSpan
        : branchInTitle;

    if (branchFromDOM) {
      return branchFromDOM;
    }

    
    if (this._defaultBranch[`${username}/${reponame}`]) {
      return this._defaultBranch[`${username}/${reponame}`];
    }

    try {
      const data = await this._apiGet(`/repos/${username}/${reponame}`);
      const defaultBranch = data.default_branch || 'main';
      this._defaultBranch[`${username}/${reponame}`] = defaultBranch;
      return defaultBranch;
    } catch (e) {
      console.error('Failed to get default branch:', e);
      return 'main'; 
    }
  }

  


  async loadFileTree(repoInfo) {
    console.log('[GitHubAdapter] Loading file tree...');
    
    const { username, reponame, branch } = repoInfo;
    const encodedBranch = encodeURIComponent(branch);

    try {
      
      const tree = await this._apiGet(
        `/repos/${username}/${reponame}/git/trees/${encodedBranch}?recursive=1`
      );

      if (tree.truncated) {
        console.warn('[GitHubAdapter] Tree is truncated (too large). Using non-recursive fetch.');
        return await this._loadTreeNonRecursive(repoInfo);
      }

      
      const items = tree.tree.map(item => this._transformTreeItem(item, repoInfo));
      
      
      return this._buildHierarchy(items);

    } catch (error) {
      console.error('[GitHubAdapter] Failed to load tree:', error);
      throw error;
    }
  }

  


  async _loadTreeNonRecursive(repoInfo, path = '') {
    const { username, reponame, branch } = repoInfo;
    const encodedBranch = encodeURIComponent(branch);
    const encodedPath = path ? encodeURIComponent(path) : '';

    const tree = await this._apiGet(
      `/repos/${username}/${reponame}/git/trees/${encodedBranch}:${encodedPath}`
    );

    const items = [];
    
    for (const item of tree.tree) {
      const fullPath = path ? `${path}/${item.path}` : item.path;
      const transformed = this._transformTreeItem(item, repoInfo, fullPath);
      items.push(transformed);

      
      if (item.type === 'tree') {
        const children = await this._loadTreeNonRecursive(repoInfo, fullPath);
        transformed.children = children;
      }
    }

    return items;
  }

  


  _transformTreeItem(item, repoInfo, fullPath = null) {
    const path = fullPath || item.path;
    const name = path.split('/').pop();
    const type = item.type; 

    return {
      path: path,
      name: name,
      type: type,
      sha: item.sha,
      size: item.size,
      url: this._getItemUrl(repoInfo, type, path),
      issueCount: 0, 
      severity: 'none'
    };
  }

  


  _buildHierarchy(items) {
    const root = [];
    const folders = { '': root };

    
    items.sort((a, b) => {
      const depthA = a.path.split('/').length;
      const depthB = b.path.split('/').length;
      return depthA - depthB;
    });

    items.forEach(item => {
      const parts = item.path.split('/');
      const parentPath = parts.slice(0, -1).join('/');
      
      
      if (!folders[parentPath]) {
        folders[parentPath] = [];
      }

      
      folders[parentPath].push(item);

      
      if (item.type === 'tree') {
        item.children = [];
        folders[item.path] = item.children;
      }
    });

    return root;
  }

  


  _getItemUrl(repoInfo, type, path) {
    const { username, reponame, branch } = repoInfo;
    const encodedBranch = encodeURIComponent(branch);
    const encodedPath = path.split('/').map(encodeURIComponent).join('/');

    return `https://github.com/${username}/${reponame}/${type}/${encodedBranch}/${encodedPath}`;
  }

  


  async getFileContent(repoInfo, filePath) {
    const { username, reponame, branch } = repoInfo;
    
    try {
      const data = await this._apiGet(
        `/repos/${username}/${reponame}/contents/${filePath}?ref=${branch}`
      );

      
      return atob(data.content.replace(/\n/g, ''));
    } catch (error) {
      console.error(`[GitHubAdapter] Failed to fetch ${filePath}:`, error);
      throw error;
    }
  }

  


  async _apiGet(path) {
    const url = `${this.apiUrl}${path}`;
    const headers = {
      'Accept': 'application/vnd.github.v3+json'
    };

    
    if (this.token) {
      headers['Authorization'] = `token ${this.token}`;
    }

    const response = await fetch(url, { headers });

    if (!response.ok) {
      await this._handleError(response);
    }

    return await response.json();
  }

  


  async _handleError(response) {
    let errorMsg = 'GitHub API Error';
    let detailMsg = '';

    switch (response.status) {
      case 401:
        errorMsg = 'Invalid GitHub Token';
        detailMsg = 'Please check your GitHub personal access token in settings.';
        break;
      case 403:
        if (response.headers.get('X-RateLimit-Remaining') === '0') {
          errorMsg = 'API Rate Limit Exceeded';
          detailMsg = 'GitHub API rate limit exceeded. Please add a personal access token or wait for the limit to reset.';
        } else {
          errorMsg = 'Access Forbidden';
          detailMsg = 'You may need a GitHub token to access this private repository.';
        }
        break;
      case 404:
        errorMsg = 'Repository Not Found';
        detailMsg = 'The repository may be private or does not exist.';
        break;
      default:
        detailMsg = await response.text();
    }

    throw new Error(`${errorMsg}: ${detailMsg}`);
  }

  


  setToken(token) {
    this.token = token;
    console.log('[GitHubAdapter] Token set');
  }

  


  async loadToken() {
    return new Promise((resolve) => {
      chrome.storage.sync.get(['githubToken'], (result) => {
        if (result.githubToken) {
          this.token = result.githubToken;
          console.log('[GitHubAdapter] Token loaded from storage');
        }
        resolve(this.token);
      });
    });
  }
}
