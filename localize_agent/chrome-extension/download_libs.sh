#!/bin/bash

# Create lib directory
mkdir -p lib

# Download jQuery
echo "Downloading jQuery..."
curl -o lib/jquery.min.js https://code.jquery.com/jquery-3.7.1.min.js

# Download jsTree
echo "Downloading jsTree..."
curl -o lib/jstree.min.js https://cdnjs.cloudflare.com/ajax/libs/jstree/3.3.16/jstree.min.js

echo "✅ Libraries downloaded!"
```

Or manually download:
- jQuery: https://code.jquery.com/jquery-3.7.1.min.js
- jsTree: https://cdnjs.cloudflare.com/ajax/libs/jstree/3.3.16/jstree.min.js

## Complete File Checklist
```
✅ manifest.json
✅ background.js
✅ content/content.js
✅ content/github-adapter.js
✅ content/analysis-engine.js
✅ sidebar/sidebar.css
✅ popup/popup.html
✅ popup/popup.js
✅ icons/icon16.png
✅ icons/icon48.png
✅ icons/icon128.png
✅ lib/jquery.min.js
✅ lib/jstree.min.js
✅ README.md