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

# Import your existing crew - handle both direct run and package import
try:
    from localize_agent.crew import LocalizeAgent
    from localize_agent.batch_analyzer import BatchAnalyzer
except ModuleNotFoundError:
    # Running directly from src/localize_agent directory
    from crew import LocalizeAgent
    from batch_analyzer import BatchAnalyzer

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
    Analyze multiple files from a repository using batch analyzer
    
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
        print(f"[API] 📦 Analyzing repository: {repo}")
        print(f"[API] 📄 Number of files: {len(files)}")
        print(f"{'='*60}\n")
        
        # Use BatchAnalyzer with conservative settings to avoid rate limits
        # max_workers=1: Sequential processing (no parallel to avoid rate limits)
        # delay_between_files=3: 3 seconds between each file
        batch_analyzer = BatchAnalyzer(max_workers=1, delay_between_files=3)
        all_results = batch_analyzer.analyze_repository(files, repo)
        
        # Cache results
        cache_key = repo
        analysis_cache[cache_key] = all_results
        
        # Calculate summary
        total_issues = sum(len(r.get('issues', [])) for r in all_results)
        successful = len([r for r in all_results if r['status'] == 'success'])
        
        print(f"\n{'='*60}")
        print(f"[API] ✅ Analysis complete for {repo}")
        print(f"[API] 📊 Successful: {successful}/{len(all_results)}")
        print(f"[API] 🐛 Total issues: {total_issues}")
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
        
        # Try to get data directly from CrewOutput
        try:
            # CrewOutput has a raw property or can be converted to string
            if hasattr(result, 'raw'):
                result_text = result.raw
            elif hasattr(result, 'json'):
                result_text = result.json
            else:
                result_text = str(result)
            
            print(f"[CREW] Result text length: {len(result_text)} characters")
            
            # Try to parse as JSON directly
            issues = json.loads(result_text) if isinstance(result_text, str) else result_text
            
            if isinstance(issues, list) and len(issues) > 0:
                print(f"[CREW] ✅ Successfully parsed {len(issues)} issues from CrewOutput")
                return issues
            else:
                print(f"[CREW] CrewOutput parse unsuccessful, trying file-based parsing...")
                
        except Exception as parse_error:
            print(f"[CREW] Direct parsing failed: {parse_error}")
            print(f"[CREW] Falling back to file-based parsing...")
        
        # Fallback: Parse the ranking_report.md file
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
        # Clean up the report text - remove markdown formatting
        clean_text = report_text.strip()
        
        # Method 1: Try to find JSON array at the start
        # Look for [ at the beginning and ] followed by explanatory text
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
                # Try to fix common issues
                json_str = json_str.replace('\n', ' ').replace('\r', '')
                try:
                    issues = json.loads(json_str)
                    return issues
                except:
                    pass
        
        # Method 2: Look for JSON in code blocks
        code_block_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', report_text)
        
        if code_block_match:
            json_str = code_block_match.group(1)
            print(f"[PARSE] Found JSON in code block")
            issues = json.loads(json_str)
            return issues
        
        # Method 3: Try to extract individual issue objects
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