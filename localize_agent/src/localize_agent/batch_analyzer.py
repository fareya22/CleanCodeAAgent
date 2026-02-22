"""
Batch analyzer for analyzing multiple files from a repository
"""
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any
try:
    from localize_agent.crew import LocalizeAgent
except ModuleNotFoundError:
    from crew import LocalizeAgent
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback


class BatchAnalyzer:
    """Analyze multiple Java files from a repository"""
    
    def __init__(self, max_workers=1, delay_between_files=5, max_retries=5, retry_backoff=3):
        """
        Initialize batch analyzer
        
        Args:
            max_workers: Maximum number of parallel analysis workers (default 1 to avoid rate limits)
            delay_between_files: Seconds to wait between file analyses (default 5 to avoid rate limits)
            max_retries: Maximum number of retries for failed LLM calls (default 5 for AWS stability)
            retry_backoff: Backoff multiplier for retry delays (default 3 for aggressive backoff)
        """
        self.max_workers = max_workers
        self.delay_between_files = delay_between_files
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.results = []
        self.analysis_cache = {}
    
    def analyze_repository(self, files: List[Dict[str, str]], repo_name: str = "unknown") -> List[Dict[str, Any]]:
        """
        Analyze all files in a repository
        
        Args:
            files: List of dicts with 'path' and 'content' keys
            repo_name: Repository name for logging
        
        Returns:
            List of analysis results for each file
        """
        print(f"\n{'='*70}")
        print(f"📦 BATCH ANALYSIS: {repo_name}")
        print(f"📄 Total files: {len(files)}")
        print(f"⚙️  Workers: {self.max_workers}")
        print(f"🔄 Max retries: {self.max_retries}")
        print(f"⏳ Retry backoff: {self.retry_backoff}s")
        print(f"{'='*70}\n")
        
        results = []
        
        # Filter only Java files for now
        java_files = [f for f in files if f['path'].endswith('.java')]
        
        print(f"☕ Java files to analyze: {len(java_files)}")
        
        if not java_files:
            print("⚠️  No Java files found in repository")
            return []
        
        # Analyze each file with delays to avoid rate limiting
        for idx, file_info in enumerate(java_files, 1):
            file_path = file_info['path']
            code_content = file_info['content']
            
            print(f"\n[{idx}/{len(java_files)}] 🔍 Analyzing: {file_path}")
            print(f"    📏 Size: {len(code_content)} characters")
            
            # Add delay between files to avoid AWS rate limiting
            if idx > 1:
                print(f"    ⏳ Waiting {self.delay_between_files}s to avoid rate limits...")
                time.sleep(self.delay_between_files)
            
            try:
                issues = self.analyze_single_file(code_content, file_path)
                
                results.append({
                    "file": file_path,
                    "issues": issues,
                    "status": "success"
                })
                
                print(f"    ✅ Found {len(issues)} issues")
                
            except Exception as e:
                error_msg = str(e)
                print(f"    ❌ Error: {error_msg}")
                
                # Try fallback heuristic analysis as last resort
                print(f"    🔄 Attempting fallback heuristic analysis...")
                try:
                    fallback_issues = self._create_basic_issues(code_content, file_path)
                    results.append({
                        "file": file_path,
                        "issues": fallback_issues,
                        "status": "success",
                        "method": "fallback_heuristic"
                    })
                    print(f"    ✅ Found {len(fallback_issues)} issues (heuristic analysis)")
                except Exception as fb_error:
                    print(f"    ❌ Fallback also failed: {fb_error}")
                    results.append({
                        "file": file_path,
                        "issues": [],
                        "status": "error",
                        "error": error_msg,
                        "fallback_error": str(fb_error)
                    })
        
        # Summary
        total_issues = sum(len(r.get('issues', [])) for r in results)
        successful = len([r for r in results if r['status'] == 'success'])
        
        print(f"\n{'='*70}")
        print(f"📊 ANALYSIS SUMMARY")
        print(f"{'='*70}")
        print(f"✅ Successful: {successful}/{len(java_files)}")
        print(f"🐛 Total issues found: {total_issues}")
        print(f"💾 Cache size: {len(self.analysis_cache)} entries")
        print(f"{'='*70}\n")
        
        return results
    
    def analyze_single_file(self, code_content: str, file_path: str = "unknown.java") -> List[Dict[str, Any]]:
        """
        Analyze a single file using CrewAI agents with retry logic
        
        Args:
            code_content: Java source code
            file_path: File path for reference
        
        Returns:
            List of issues with rankings
        """
        # Check cache first
        cache_key = hash(code_content)
        if cache_key in self.analysis_cache:
            print(f"    💾 Using cached results for {file_path}")
            return self.analysis_cache[cache_key]
        
        last_error = None
        
        # Retry logic with exponential backoff
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"    [Attempt {attempt}/{self.max_retries}] Running crew analysis...")
                
                # Prepare input for crew
                inputs = {
                    "code": code_content
                }
                
                # Run LocalizeAgent crew
                crew = LocalizeAgent().crew()
                result = crew.kickoff(inputs=inputs)
                
                # Parse result
                raw_issues = self._parse_crew_output(result, file_path)
                print(f"    [FILTER] Parsed {len(raw_issues)} raw issues from LLM")
                
                # Filter and validate issues
                filtered_issues = self._filter_and_validate_issues(raw_issues, code_content, file_path)
                print(f"    [FILTER] After validation: {len(filtered_issues)} issues remain")
                
                # Cache successful result
                self.analysis_cache[cache_key] = filtered_issues
                
                return filtered_issues
                
            except Exception as e:
                last_error = str(e)
                print(f"    ⚠️  Attempt {attempt} failed: {last_error}")
                
                # Check if this is an LLM connection error
                if attempt < self.max_retries and self._is_llm_error(last_error):
                    # Calculate backoff time
                    backoff_time = self.retry_backoff ** (attempt - 1)
                    print(f"    ⏳ LLM error detected. Retrying in {backoff_time}s...")
                    time.sleep(backoff_time)
                    continue
                else:
                    # No more retries or not an LLM error
                    break
        
        # All retries exhausted or other error - use fallback
        print(f"    [FALLBACK] All retries exhausted. Using heuristic analysis...")
        try:
            fallback_issues = self._create_basic_issues(code_content, file_path)
            # Cache fallback result
            self.analysis_cache[cache_key] = fallback_issues
            return fallback_issues
        except Exception as fb_error:
            print(f"    ❌ Fallback analysis also failed: {str(fb_error)}")
            return []
    
    def _is_llm_error(self, error_msg: str) -> bool:
        """
        Detect if this is an LLM/connection error that warrants retry
        """
        llm_error_keywords = [
            'llm',
            'empty',
            'timeout',
            'connection',
            'bedrock',
            'aws',
            'credentials',
            'http',
            'connection refused',
            'no response',
            'rate limit'
        ]
        
        error_lower = error_msg.lower()
        return any(keyword in error_lower for keyword in llm_error_keywords)
    
    def _parse_crew_output(self, result, file_path: str) -> List[Dict[str, Any]]:
        """Parse CrewAI output to extract issues"""
        try:
            # Try to get data from CrewOutput
            if hasattr(result, 'raw'):
                result_text = result.raw
            elif hasattr(result, 'json'):
                result_text = result.json
            else:
                result_text = str(result)
            
            # Validate we have content
            if not result_text or result_text.strip() == '' or result_text == 'None':
                print(f"    [PARSE] Empty response from LLM, trying fallback...")
                return self._parse_ranking_report()
            
            # Try to parse as JSON
            try:
                issues = json.loads(result_text) if isinstance(result_text, str) else result_text
                
                if isinstance(issues, list) and len(issues) > 0:
                    print(f"    [PARSE] ✅ Successfully parsed {len(issues)} issues from LLM output")
                    return issues
            except json.JSONDecodeError:
                print(f"    [PARSE] JSON decode failed, trying regex extraction...")
                # Try to extract JSON from response
                import re
                match = re.search(r'(\[\s*\{[\s\S]*?\}\s*\])', result_text)
                if match:
                    try:
                        issues = json.loads(match.group(1))
                        if isinstance(issues, list) and len(issues) > 0:
                            print(f"    [PARSE] ✅ Extracted {len(issues)} issues from response")
                            return issues
                    except:
                        pass
            
            # Fallback: read from ranking_report.md
            print(f"    [PARSE] Falling back to ranking_report.md parsing...")
            return self._parse_ranking_report()
            
        except Exception as e:
            print(f"    [PARSE ERROR] {str(e)}")
            return self._parse_ranking_report()
    
    def _parse_ranking_report(self) -> List[Dict[str, Any]]:
        """Parse ranking_report.md file"""
        import re
        
        try:
            ranking_file = Path("ranking_report.md")
            
            if not ranking_file.exists():
                print("[WARN] ranking_report.md not found")
                return []
            
            with open(ranking_file, 'r', encoding='utf-8') as f:
                report_content = f.read()
            
            # Try to find JSON array
            match = re.search(r'(\[\s*\{[\s\S]*?\}\s*\])', report_content)
            
            if match:
                json_str = match.group(1)
                issues = json.loads(json_str)
                
                if isinstance(issues, list):
                    return issues
            
            return []
            
        except Exception as e:
            print(f"[REPORT PARSE ERROR] {str(e)}")
            return []
    
    def _create_basic_issues(self, code_content: str, file_path: str) -> List[Dict[str, Any]]:
        """Create basic issues using heuristics when LLM fails"""
        issues = []
        
        lines = code_content.split('\n')
        class_name = file_path.split('/')[-1].replace('.java', '')
        
        # Check for long methods
        in_method = False
        method_line_count = 0
        method_name = ""
        method_start_line = 0
        
        for i, line in enumerate(lines, 1):
            if 'public ' in line and '(' in line and '{' in line:
                in_method = True
                method_name = line.split('(')[0].split()[-1]
                method_line_count = 0
                method_start_line = i
            elif in_method:
                method_line_count += 1
                if '}' in line:
                    if method_line_count > 25:
                        issues.append({
                            "Class name": class_name,
                            "Function name": method_name,
                            "Function signature": f"{method_name}(...)",
                            "refactoring_type": "extract method",
                            "rationale": f"Method has {method_line_count} lines. Consider extracting smaller methods for better readability.",
                            "rank": len(issues) + 1,
                            "severity": "medium",
                            "line": method_start_line
                        })
                    in_method = False
        
        # Check for god class
        method_count = code_content.count('public ') + code_content.count('private ')
        if method_count > 12:
            issues.append({
                "Class name": class_name,
                "Function name": "N/A",
                "Function signature": "class-level",
                "refactoring_type": "extract class",
                "rationale": f"Class has {method_count} methods. Consider splitting responsibilities into multiple classes.",
                "rank": len(issues) + 1,
                "severity": "high",
                "line": 1
            })
        
        return issues    
    def _filter_and_validate_issues(self, issues: List[Dict[str, Any]], code_content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Filter out false positives and validate issues
        
        Filters:
        1. Skip getter/setter methods
        2. Skip model/DTO classes with only getters/setters
        3. Validate class names exist in code
        4. Skip feature envy on own class fields
        5. Skip information hiding on getter/setter methods
        """
        import re
        
        print(f"\n    🔍 VALIDATION START for {file_path}")
        print(f"       Input issues: {len(issues)}")
        
        # Extract actual class names from code
        actual_classes = set()
        class_pattern = r'\b(?:public\s+)?(?:class|interface|enum)\s+(\w+)'
        for line in code_content.split('\n'):
            match = re.search(class_pattern, line)
            if match:
                actual_classes.add(match.group(1))
        
        print(f"       Classes found in code: {actual_classes}")
        
        # Check if this is a model/DTO class (mostly getters/setters)
        is_model_class = self._is_model_class(code_content, file_path)
        if is_model_class:
            print(f"       ⚠️  Detected as Model/DTO class - will skip god class issues")
        
        filtered_issues = []
        skipped_count = 0
        
        for issue in issues:
            func_name = issue.get('Function name', '')
            class_name = issue.get('Class name', '')
            refactoring_type = issue.get('refactoring_type', '')
            rationale = issue.get('rationale', '').lower()
            
            skip_reason = None
            
            # Filter 1: Skip getter/setter methods flagged for information hiding
            if self._is_getter_setter(func_name):
                if 'information hiding' in refactoring_type.lower() or 'information hiding' in rationale:
                    skip_reason = f"Getter/Setter with info hiding: {func_name}"
                elif 'move method' in refactoring_type.lower():
                    skip_reason = f"Getter/Setter with move method: {func_name}"
            
            # Filter 2: Validate class name exists in code
            if class_name and class_name not in actual_classes:
                # Check if it's a hallucinated class (e.g., OrderLogic when only Order exists)
                skip_reason = f"Class '{class_name}' not found in code (hallucination)"
            
            # Filter 3: Skip god class issues on model/DTO classes
            if is_model_class and 'god class' in rationale:
                skip_reason = f"God class on Model/DTO class"
            
            # Filter 4: Skip feature envy on own class (not on another class)
            if 'feature envy' in refactoring_type.lower() or 'feature envy' in rationale:
                # Check if rationale mentions accessing fields from the SAME class
                if class_name and (f'{class_name}' in rationale or 'same class' in rationale):
                    skip_reason = f"Feature envy on own class fields"
                # Also check if rationale says "uses own fields" or similar
                if any(keyword in rationale for keyword in ['own field', 'its own', 'same class']):
                    skip_reason = f"Feature envy on own fields"
            
            # Filter 5: Skip if rationale talks about "exposes public fields" but method is getter/setter
            if 'exposes public fields' in rationale and self._is_getter_setter(func_name):
                skip_reason = f"Public field warning on getter/setter: {func_name}"
            
            if skip_reason:
                print(f"       🚫 SKIP: {skip_reason}")
                skipped_count += 1
            else:
                filtered_issues.append(issue)
        
        print(f"       Output issues: {len(filtered_issues)}")
        print(f"       Rejected: {skipped_count}")
        print(f"    🔍 VALIDATION END\n")
        
        return filtered_issues
    
    def _is_getter_setter(self, method_name: str) -> bool:
        """Check if method name is a getter or setter"""
        if not method_name or method_name == 'N/A':
            return False
        
        method_lower = method_name.lower()
        
        # Standard getter/setter patterns
        if method_lower.startswith('get') and len(method_name) > 3:
            return True
        if method_lower.startswith('set') and len(method_name) > 3:
            return True
        if method_lower.startswith('is') and len(method_name) > 2:
            return True
        
        return False
    
    def _is_model_class(self, code_content: str, file_path: str) -> bool:
        """
        Detect if this is a model/DTO/entity class
        
        Criteria:
        - File path contains "model", "entity", "dto", "domain"
        - Mostly getters/setters (80%+ of methods)
        - Few or no business logic methods
        """
        import re
        
        # Check file path
        file_lower = file_path.lower()
        if any(keyword in file_lower for keyword in ['model', 'entity', 'dto', 'domain', 'pojo']):
            return True
        
        # Count methods
        lines = code_content.split('\n')
        total_methods = 0
        getter_setter_methods = 0
        
        for line in lines:
            # Match method declarations
            if re.search(r'\b(?:public|private|protected)\s+\w+\s+(\w+)\s*\(', line):
                method_match = re.search(r'\b(?:public|private|protected)\s+\w+\s+(\w+)\s*\(', line)
                if method_match:
                    method_name = method_match.group(1)
                    total_methods += 1
                    
                    if self._is_getter_setter(method_name):
                        getter_setter_methods += 1
        
        # If 80%+ methods are getters/setters, it's a model class
        if total_methods > 0:
            ratio = getter_setter_methods / total_methods
            if ratio >= 0.8:
                return True
        
        return False