"""
Flask API Server for CleanCodeAgent Chrome Extension
Wraps your existing CrewAI multi-agent system
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import traceback
from pathlib import Path

# Import your existing crew
from localize_agent.crew import LocalizeAgent

app = Flask(__name__)
CORS(app)  # Allow Chrome extension to call this API

# Store analysis results temporarily
analysis_cache = {}

@app.route('/health', methods=['GET'])
def health_check():
    """Check if server is running"""
    return jsonify({
        "status": "ok",
        "message": "CleanCodeAgent API is running",
        "version": "1.0.0"
    })

@app.route('/analyze', methods=['POST'])
def analyze_repository():
    """
    Analyze multiple files from a repository
    
    Request JSON:
    {
        "repo": "username/reponame",
        "files": [
            {"path": "src/Main.java", "content": "...code..."},
            {"path": "src/User.java", "content": "...code..."}
        ]
    }
    
    Response JSON:
    {
        "status": "success",
        "repo": "username/reponame",
        "results": [
            {
                "file": "src/Main.java",
                "issues": [...]
            }
        ]
    }
    """
    try:
        data = request.json
        repo = data.get('repo', 'unknown')
        files = data.get('files', [])
        
        if not files:
            return jsonify({
                "status": "error",
                "message": "No files provided"
            }), 400
        
        print(f"\n{'='*60}")
        print(f"[API] Analyzing repository: {repo}")
        print(f"[API] Number of files: {len(files)}")
        print(f"{'='*60}\n")
        
        all_results = []
        
        # Analyze each file
        for idx, file_info in enumerate(files, 1):
            file_path = file_info.get('path')
            code_content = file_info.get('content')
            
            if not code_content:
                print(f"[API] Skipping {file_path} - no content")
                continue
            
            print(f"\n[API] [{idx}/{len(files)}] Analyzing: {file_path}")
            print(f"[API] Code length: {len(code_content)} characters")
            
            try:
                # Run your CrewAI agents
                issues = analyze_single_file(code_content, file_path)
                
                all_results.append({
                    "file": file_path,
                    "issues": issues,
                    "status": "success"
                })
                
                print(f"[API] ✓ Found {len(issues)} issues in {file_path}")
                
            except Exception as e:
                print(f"[API] ✗ Error analyzing {file_path}: {str(e)}")
                traceback.print_exc()
                
                all_results.append({
                    "file": file_path,
                    "issues": [],
                    "status": "error",
                    "error": str(e)
                })
        
        # Cache results
        cache_key = repo
        analysis_cache[cache_key] = all_results
        
        print(f"\n{'='*60}")
        print(f"[API] Analysis complete for {repo}")
        print(f"[API] Total files analyzed: {len(all_results)}")
        total_issues = sum(len(r.get('issues', [])) for r in all_results)
        print(f"[API] Total issues found: {total_issues}")
        print(f"{'='*60}\n")
        
        return jsonify({
            "status": "success",
            "repo": repo,
            "results": all_results,
            "summary": {
                "total_files": len(all_results),
                "total_issues": total_issues
            }
        })
        
    except Exception as e:
        print(f"[API] ERROR: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/analyze-file', methods=['POST'])
def analyze_file():
    """
    Analyze a single file
    
    Request JSON:
    {
        "path": "src/Main.java",
        "content": "...code..."
    }
    
    Response JSON:
    {
        "status": "success",
        "file": "src/Main.java",
        "issues": [...]
    }
    """
    try:
        data = request.json
        file_path = data.get('path', 'unknown.java')
        code_content = data.get('content')
        
        if not code_content:
            return jsonify({
                "status": "error",
                "message": "No code content provided"
            }), 400
        
        print(f"\n[API] Analyzing single file: {file_path}")
        print(f"[API] Code length: {len(code_content)} characters")
        
        # Run analysis
        issues = analyze_single_file(code_content, file_path)
        
        print(f"[API] Found {len(issues)} issues")
        
        return jsonify({
            "status": "success",
            "file": file_path,
            "issues": issues
        })
        
    except Exception as e:
        print(f"[API] ERROR: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

def analyze_single_file(code_content, file_path="unknown"):
    """
    Run your CrewAI agents on a single file
    Returns list of issues with ranking
    """
    print(f"[CREW] Starting analysis...")
    print(f"[CREW] Code length: {len(code_content)} characters")
    
    try:
        # Prepare input for your crew
        inputs = {
            "code": code_content
        }
        
        # Run your LocalizeAgent crew
        print(f"[CREW] Running LocalizeAgent crew...")
        crew = LocalizeAgent().crew()
        
        print(f"[CREW] Kicking off crew execution...")
        result = crew.kickoff(inputs=inputs)
        
        print(f"[CREW] Crew execution completed")
        print(f"[CREW] Result type: {type(result)}")
        print(f"[CREW] Result: {result}")
        
        # Parse the ranking_report.md file
        ranking_file = Path("ranking_report.md")
        
        if not ranking_file.exists():
            print(f"[CREW] WARNING: ranking_report.md not found")
            print(f"[CREW] Attempting to use fallback analysis...")
            return create_fallback_issues(code_content, file_path)
        
        with open(ranking_file, 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        print(f"[CREW] Reading ranking report...")
        print(f"[CREW] Report length: {len(report_content)} characters")
        
        # Extract JSON from the report
        issues = parse_ranking_report(report_content)
        
        print(f"[CREW] Parsed {len(issues)} issues from report")
        
        if not issues:
            print(f"[CREW] No issues found in report, using fallback...")
            return create_fallback_issues(code_content, file_path)
        
        return issues
        
    except Exception as e:
        print(f"[CREW] ERROR: {str(e)}")
        traceback.print_exc()
        print(f"[CREW] Returning fallback issues due to error...")
        return create_fallback_issues(code_content, file_path)

def create_fallback_issues(code_content, file_path):
    """
    Create basic fallback issues when LLM fails
    This helps debug and shows user something is working
    """
    issues = []
    
    # Simple heuristics for common issues
    lines = code_content.split('\n')
    
    # Check for long methods
    in_method = False
    method_line_count = 0
    method_name = ""
    
    for i, line in enumerate(lines, 1):
        # Very simple Java method detection
        if 'public ' in line and '(' in line and '{' in line:
            in_method = True
            method_name = line.split('(')[0].split()[-1]
            method_line_count = 0
        elif in_method:
            method_line_count += 1
            if '}' in line:
                if method_line_count > 30:
                    issues.append({
                        "Class name": file_path.split('/')[-1].replace('.java', ''),
                        "Function name": method_name,
                        "Function signature": f"{method_name}(...)",
                        "refactoring_type": "extract method",
                        "rationale": f"Method is too long ({method_line_count} lines). Consider extracting smaller methods.",
                        "rank": len(issues) + 1,
                        "severity": "high",
                        "line": i - method_line_count
                    })
                in_method = False
    
    # Check for god class (too many methods/fields)
    method_count = code_content.count('public ') + code_content.count('private ')
    if method_count > 15:
        issues.append({
            "Class name": file_path.split('/')[-1].replace('.java', ''),
            "Function name": "N/A",
            "Function signature": "class-level",
            "refactoring_type": "extract class",
            "rationale": f"Class has too many methods ({method_count}). Consider splitting into multiple classes.",
            "rank": len(issues) + 1,
            "severity": "high",
            "line": 1
        })
    
    print(f"[FALLBACK] Created {len(issues)} basic issues using heuristics")
    return issues

def parse_ranking_report(report_text):
    """
    Parse the ranking_report.md and extract issues
    """
    import re
    
    try:
        # Try to find JSON array in the report
        # Look for pattern: [{"Class name": ..., "Function name": ..., ...}]
        
        # Method 1: Direct JSON match
        json_match = re.search(r'\[[\s\S]*?\{[\s\S]*?"Class name"[\s\S]*?\}[\s\S]*?\]', report_text)
        
        if json_match:
            json_str = json_match.group(0)
            issues = json.loads(json_str)
            return issues
        
        # Method 2: Look for code blocks
        code_block_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', report_text)
        
        if code_block_match:
            json_str = code_block_match.group(1)
            issues = json.loads(json_str)
            return issues
        
        print("[PARSE] Could not find JSON in report")
        return []
        
    except json.JSONDecodeError as e:
        print(f"[PARSE] JSON parse error: {e}")
        return []
    except Exception as e:
        print(f"[PARSE] Error: {e}")
        return []

if __name__ == '__main__':
    print("="*60)
    print("  CleanCodeAgent API Server")
    print("="*60)
    print()
    print("  Server URL: http://localhost:5000")
    print("  Health Check: http://localhost:5000/health")
    print()
    print("  Endpoints:")
    print("    POST /analyze       - Analyze multiple files")
    print("    POST /analyze-file  - Analyze single file")
    print()
    print("="*60)
    print()
    
    # Run Flask server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )