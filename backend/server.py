from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import traceback
from pathlib import Path
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

try:
    from localize_agent.crew import LocalizeAgent
    from localize_agent.batch_analyzer import BatchAnalyzer
except ModuleNotFoundError:
    
    from crew import LocalizeAgent
    from batch_analyzer import BatchAnalyzer

app = Flask(__name__)
CORS(app)  

analysis_cache = {}

MONGO_URI = os.environ.get("MONGO_URI")
_mongo_client = None
_feedback_collection = None

def get_feedback_collection():
    global _mongo_client, _feedback_collection
    if _feedback_collection is None:
        _mongo_client = MongoClient(MONGO_URI)
        db = _mongo_client["cleancode_agent"]
        _feedback_collection = db["feedback"]
    return _feedback_collection

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "message": "CleanCodeAgent API is running",
        "version": "1.0.0"
    })

@app.route('/feedback', methods=['GET', 'POST'])
def submit_feedback():
    try:
        if request.method == 'GET':
            return jsonify({
                "status": "info",
                "message": "Feedback endpoint is active. Send a POST request with {email, comment}."
            })

        data = request.json
        email = (data.get('email') or '').strip()
        comment = (data.get('comment') or '').strip()

        if not email or not comment:
            return jsonify({
                "status": "error",
                "message": "email and comment are required"
            }), 400

        doc = {
            "email": email,
            "comment": comment,
            "created_at": datetime.now(timezone.utc)
        }

        collection = get_feedback_collection()
        result = collection.insert_one(doc)

        print(f"[FEEDBACK] Saved feedback from {email} (id={result.inserted_id})")

        return jsonify({
            "status": "success",
            "message": "Feedback submitted successfully"
        })

    except Exception as e:
        print(f"[FEEDBACK] ERROR: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/analyze', methods=['POST'])
def analyze_repository():
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
        print(f"[API] 📦 Analyzing repository: {repo}")
        print(f"[API] 📄 Number of files: {len(files)}")
        print(f"{'='*60}\n")
        
        branch = data.get('branch', 'main')
        repo_info = None
        if repo and '/' in repo:
            parts = repo.split('/')
            if len(parts) >= 2:
                repo_info = {
                    'owner': parts[0],
                    'repo': parts[1],
                    'branch': branch
                }
                print(f"[API] 🔗 GitHub links enabled: {repo} (branch: {branch})")
        
        enable_check = os.getenv('ENABLE_CONSISTENCY_CHECK', 'false').lower() == 'true'
        batch_analyzer = BatchAnalyzer(max_workers=1, repo_info=repo_info, enable_consistency_check=enable_check)
        all_results = batch_analyzer.analyze_repository(files, repo)
        
        cache_key = repo
        analysis_cache[cache_key] = all_results
        
        total_issues = sum(len(r.get('issues', [])) for r in all_results)
        successful = len([r for r in all_results if r['status'] == 'success'])
        
        print(f"\n{'='*60}")
        print(f"[API]  Analysis complete for {repo}")
        print(f"[API]  Successful: {successful}/{len(all_results)}")
        print(f"[API]  Total issues: {total_issues}")
        print(f"{'='*60}\n")
        
        return jsonify({
            "status": "success",
            "repo": repo,
            "results": all_results,
            "summary": {
                "total_files": len(all_results),
                "successful_files": successful,
                "total_issues": total_issues
            }
        })
        
    except Exception as e:
        print(f"[API] ❌ ERROR: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/analyze-file', methods=['POST'])
def analyze_file():
    try:
        data = request.json
        file_path = data.get('path', 'unknown.java')
        code_content = data.get('content')
        repo = data.get('repo')
        branch = data.get('branch', 'main')
        
        if not code_content:
            return jsonify({
                "status": "error",
                "message": "No code content provided"
            }), 400
        
        print(f"\n[API] Analyzing single file: {file_path}")
        print(f"[API] Code length: {len(code_content)} characters")
        
        repo_info = None
        if repo and '/' in repo:
            parts = repo.split('/')
            if len(parts) >= 2:
                repo_info = {
                    'owner': parts[0],
                    'repo': parts[1],
                    'branch': branch
                }
                print(f"[API] 🔗 GitHub links enabled: {repo} (branch: {branch})")
        
        result = analyze_single_file(code_content, file_path, repo_info)
        
        issues = result.get('issues', [])
        summary = result.get('summary', '')
        
        print(f"[API] Found {len(issues)} issues")
        
        return jsonify({
            "status": "success",
            "file": file_path,
            "issues": issues,
            "summary": summary
        })
        
    except Exception as e:
        print(f"[API] ERROR: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

def analyze_single_file(code_content, file_path="unknown", repo_info=None):
    print(f"[CREW] Starting analysis...")
    print(f"[CREW] Code length: {len(code_content)} characters")
    
    if not code_content or len(code_content.strip()) == 0:
        print(f"[CREW] ERROR: Empty code content provided")
        return {
            "issues": [],
            "summary": "Error: No code content to analyze."
        }
    
    enable_check = os.getenv('ENABLE_CONSISTENCY_CHECK', 'false').lower() == 'true'
    batch_analyzer = BatchAnalyzer(max_workers=1, delay_between_files=0, repo_info=repo_info, enable_consistency_check=enable_check)
    
    try:
        
        issues = batch_analyzer.analyze_single_file(code_content, file_path)
        
        print(f"[CREW] ✅ Analysis complete: {len(issues)} issues found")
        
        return {
            "issues": issues,
            "summary": f"Analysis completed successfully. Found {len(issues)} issues."
        }
        
    except Exception as e:
        print(f"[CREW] ERROR: {str(e)}")
        traceback.print_exc()
        print(f"[CREW] Returning fallback issues due to error...")
        return create_fallback_issues(code_content, file_path, repo_info)

def create_fallback_issues(code_content, file_path, repo_info=None):
    issues = []
    
    lines = code_content.split('\n')
    
    in_method = False
    method_line_count = 0
    method_name = ""
    
    for i, line in enumerate(lines, 1):
    
        if 'public ' in line and '(' in line and '{' in line:
            in_method = True
            method_name = line.split('(')[0].split()[-1]
            method_line_count = 0
        elif in_method:
            method_line_count += 1
            if '}' in line:
                if method_line_count > 30:
                    issue = {
                        "Class name": file_path.split('/')[-1].replace('.java', ''),
                        "Function name": method_name,
                        "Function signature": f"{method_name}(...)",
                        "refactoring_type": "extract method",
                        "rationale": f"Method is too long ({method_line_count} lines). Consider extracting smaller methods.",
                        "rank": len(issues) + 1,
                        "severity": "high",
                        "line": i - method_line_count
                    }
                    
                    if repo_info and repo_info.get('owner') and repo_info.get('repo'):
                        owner = repo_info['owner']
                        repo = repo_info['repo']
                        branch = repo_info.get('branch', 'main')
                        issue['github_url'] = f"https://github.com/{owner}/{repo}/blob/{branch}/{file_path}#L{issue['line']}"
                    issues.append(issue)
                in_method = False
    
    method_count = code_content.count('public ') + code_content.count('private ')
    if method_count > 15:
        issue = {
            "Class name": file_path.split('/')[-1].replace('.java', ''),
            "Function name": "N/A",
            "Function signature": "class-level",
            "refactoring_type": "extract class",
            "rationale": f"Class has too many methods ({method_count}). Consider splitting into multiple classes.",
            "rank": len(issues) + 1,
            "severity": "high",
            "line": 1
        }
        
        if repo_info and repo_info.get('owner') and repo_info.get('repo'):
            owner = repo_info['owner']
            repo = repo_info['repo']
            branch = repo_info.get('branch', 'main')
            issue['github_url'] = f"https://github.com/{owner}/{repo}/blob/{branch}/{file_path}#L{issue['line']}"
        issues.append(issue)
    
    print(f"[FALLBACK] Created {len(issues)} basic issues using heuristics")
    return {
        "issues": issues,
        "summary": "Issues detected using fallback heuristic analysis (LLM analysis not available)."
    }

def parse_ranking_report(report_text):
    import re
    
    try:
        
        clean_text = report_text.strip()
        
        match = re.search(r'^(\[\s*\{[\s\S]*?\}\s*\])', clean_text, re.MULTILINE)
        
        if match:
            json_str = match.group(1)
            print(f"[PARSE] Found JSON array (length: {len(json_str)})")
            try:
                issues = json.loads(json_str)
                if isinstance(issues, list):
                    print(f"[PARSE] ✅ Successfully parsed {len(issues)} issues")
                    return issues
            except json.JSONDecodeError as e:
                print(f"[PARSE] JSON decode error: {e}")
                
                json_str = json_str.replace('\n', ' ').replace('\r', '')
                try:
                    issues = json.loads(json_str)
                    return issues
                except:
                    pass
        
        code_block_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', report_text)
        
        if code_block_match:
            json_str = code_block_match.group(1)
            print(f"[PARSE] Found JSON in code block")
            issues = json.loads(json_str)
            return issues
        
        issues = []
        issue_pattern = r'\{[^}]*"Class name"[^}]*"Function name"[^}]*"refactoring_type"[^}]*\}'
        matches = re.finditer(issue_pattern, report_text, re.DOTALL)
        
        for match in matches:
            try:
                issue_str = match.group(0)
                issue = json.loads(issue_str)
                issues.append(issue)
            except:
                continue
        
        if issues:
            print(f"[PARSE] Extracted {len(issues)} issues using pattern matching")
            return issues
        
        print("[PARSE] Could not find valid JSON in report")
        return []
        
    except json.JSONDecodeError as e:
        print(f"[PARSE] JSON parse error: {e}")
        return []
    except Exception as e:
        print(f"[PARSE] Error: {e}")
        traceback.print_exc()
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
    print("    POST /feedback      - Submit user feedback")
    print()
    print("="*60)
    print()
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
