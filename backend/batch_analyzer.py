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
    from localize_agent.tools.custom_tools import CountMethods, VariableUsage, FanInFanOutAnalysis, ClassCouplingAnalysis
except ModuleNotFoundError:
    from crew import LocalizeAgent
    from tools.custom_tools import CountMethods, VariableUsage, FanInFanOutAnalysis, ClassCouplingAnalysis
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback


def _compute_metrics(code_content: str) -> str:
    """
    Run all static analysis tools ONCE in Python and return a compact summary string.
    This avoids the ReAct tool-call loop that caused Haiku to return empty responses
    (agents were calling tools 9 times, re-sending the full source code each time).
    """
    parts = []
    try:
        parts.append(CountMethods()._run(code_content))
    except Exception as e:
        parts.append(f"CountMethods error: {e}")
    try:
        parts.append(VariableUsage()._run(code_content))
    except Exception as e:
        parts.append(f"VariableUsage error: {e}")
    try:
        parts.append(FanInFanOutAnalysis()._run(code_content))
    except Exception as e:
        parts.append(f"FanInFanOutAnalysis error: {e}")
    try:
        parts.append(ClassCouplingAnalysis()._run(code_content))
    except Exception as e:
        parts.append(f"ClassCouplingAnalysis error: {e}")
    return "\n".join(parts)


class BatchAnalyzer:
    """Analyze multiple Java files from a repository"""
    
    def __init__(self, max_workers=1, delay_between_files=2, max_retries=3, retry_backoff=2, repo_info=None, enable_consistency_check=False):
        """
        Initialize batch analyzer

        Args:
            max_workers: Maximum number of parallel analysis workers (default 1 to avoid rate limits)
            delay_between_files: Seconds to wait between file analyses (reduced from 5 to 2)
            max_retries: Maximum number of retries for failed LLM calls (reduced from 5 to 3)
            retry_backoff: Backoff multiplier for retry delays (reduced from 3 to 2; total wait: 1+2=3s)
            repo_info: Optional dict with 'owner', 'repo', 'branch' for GitHub URL generation (default None)
            enable_consistency_check: If True, run analysis twice and compare results to detect inconsistency
        """
        self.max_workers = max_workers
        self.delay_between_files = delay_between_files
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.results = []
        self.analysis_cache = {}
        self.repo_info = repo_info
        self.enable_consistency_check = enable_consistency_check
    
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
                print(f"     Waiting {self.delay_between_files}s to avoid rate limits...")
                time.sleep(self.delay_between_files)
            
            try:
                issues = self.analyze_single_file(code_content, file_path)
                
                # Add GitHub URLs to issues if repo_info is provided
                if self.repo_info:
                    for issue in issues:
                        if 'line' in issue:
                            issue['github_url'] = self._generate_github_url(file_path, issue['line'])
                
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
                    
                    # Add GitHub URLs to fallback issues if repo_info is provided
                    if self.repo_info:
                        for issue in fallback_issues:
                            if 'line' in issue:
                                issue['github_url'] = self._generate_github_url(file_path, issue['line'])
                    
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
        
        # print(f"\n{'='*70}")
        # print(f" ANALYSIS SUMMARY")
        # print(f"{'='*70}")
        # print(f" Successful: {successful}/{len(java_files)}")
        # print(f" Total issues found: {total_issues}")
        # print(f" Cache size: {len(self.analysis_cache)} entries")
        # print(f"{'='*70}\n")
        
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
        
        # Consistency check: run analysis twice and compare if enabled
        if self.enable_consistency_check:
            print(f"    🔬 CONSISTENCY CHECK ENABLED - Running analysis twice...")
            first_result = self._run_single_analysis(code_content, file_path, cache_key, check_mode=True)
            time.sleep(2)  # Small delay between runs
            second_result = self._run_single_analysis(code_content, file_path, cache_key, check_mode=True)
            
            # Compare results
            if len(first_result) != len(second_result):
                print(f"    ⚠️  INCONSISTENCY DETECTED: Run 1 found {len(first_result)} issues, Run 2 found {len(second_result)} issues")
            else:
                print(f"    ✅ CONSISTENCY CHECK PASSED: Both runs found {len(first_result)} issues")
            
            # Use the run with more issues (safer choice)
            result = first_result if len(first_result) >= len(second_result) else second_result
            self.analysis_cache[cache_key] = result
            return result
        else:
            return self._run_single_analysis(code_content, file_path, cache_key, check_mode=False)
    
    def _run_single_analysis(self, code_content: str, file_path: str, cache_key: int, check_mode: bool = False) -> List[Dict[str, Any]]:
        """
        Internal method to run a single analysis attempt with retry logic
        
        Args:
            code_content: Java source code
            file_path: File path for reference
            cache_key: Hash key for caching
            check_mode: If True, don't cache results (used for consistency checking)
        
        Returns:
            List of issues with rankings
        """
        last_error = None

        _stale_files = [
            'ranking_report.md', 'localization_report.md', 'prompt_report.md',
            'analysis_report.md', 'issue_report.md', 'planning_report.md'
        ]
        for _f in _stale_files:
            _p = Path(_f)
            if _p.exists():
                try:
                    _p.unlink()
                    if not check_mode:
                        print(f"    [CLEAN] Deleted stale {_f}")
                except Exception:
                    pass

        # Retry logic with exponential backoff
        for attempt in range(1, self.max_retries + 1):
            try:
                if not check_mode:
                    print(f"    [Attempt {attempt}/{self.max_retries}] Running crew analysis...")


                metrics_summary = _compute_metrics(code_content)
                if not check_mode:
                    print(f"    [METRICS] Pre-computed static analysis:\n{metrics_summary[:200]}...")

                # Prepare input for crew
                inputs = {
                    "code": code_content,
                    "metrics": metrics_summary
                }

               
                crew = LocalizeAgent().crew()
                result = crew.kickoff(inputs=inputs)

               
                if not check_mode:
                    self._print_pipeline_summary(file_path)

                
                raw_issues = self._parse_crew_output(result, file_path)
                if not check_mode:
                    print(f"    [FILTER] Parsed {len(raw_issues)} raw issues from LLM")

             
                if not raw_issues:
                    if not check_mode:
                        print(f"    [PARSE] LLM returned no parseable issues — running heuristic fallback...")
                    raw_issues = self._create_basic_issues(code_content, file_path)
                
               
                filtered_issues = self._filter_and_validate_issues(raw_issues, code_content, file_path)
                if not check_mode:
                    print(f"    [FILTER] After validation: {len(filtered_issues)} issues remain")

                if self.repo_info:
                    for issue in filtered_issues:
                        if not issue.get('github_url'):
                            line_num = issue.get('line') or self._find_function_line(code_content, issue)
                            issue['github_url'] = self._generate_github_url(file_path, line_num)

                
                if not check_mode:
                    self.analysis_cache[cache_key] = filtered_issues

                return filtered_issues
                
            except Exception as e:
                last_error = str(e)
                print(f"    ⚠️  Attempt {attempt} failed: {last_error}")

                if attempt < self.max_retries:
                    if self._is_rate_limit_error(last_error):
                       
                        wait_time = 60
                        print(f"    Rate limit detected. Waiting {wait_time}s for quota refill...")
                        time.sleep(wait_time)
                    elif self._is_llm_error(last_error):
                        
                        backoff_time = self.retry_backoff ** (attempt - 1)
                        print(f"     LLM error detected. Retrying in {backoff_time}s...")
                        time.sleep(backoff_time)
                    else:
                        
                        break
                    continue
                else:
                    break
        
        
        print(f"    [FALLBACK] All retries exhausted. Using heuristic analysis...")
        try:
            fallback_issues = self._create_basic_issues(code_content, file_path)
           
            if self.repo_info:
                for issue in fallback_issues:
                    if not issue.get('github_url'):
                        line_num = issue.get('line') or self._find_function_line(code_content, issue)
                        issue['github_url'] = self._generate_github_url(file_path, line_num)
            
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

    def _is_rate_limit_error(self, error_msg: str) -> bool:
        """
        Detect rate-limit / quota-exhausted errors that need a long wait (60s)
        rather than the standard short backoff.
        Covers Gemini, OpenAI, Bedrock, and generic HTTP 429 patterns.
        """
        rate_limit_keywords = [
            '429',
            'rate limit',
            'ratelimit',
            'quota',
            'resource_exhausted',
            'resource exhausted',
            'too many requests',
            'requests per minute',
            'tokens per minute',
            'model is overloaded',
            'capacity',
            'overloaded',
            'retry after',
        ]
        error_lower = error_msg.lower()
        return any(kw in error_lower for kw in rate_limit_keywords)
    
    def _parse_crew_output(self, result, file_path: str) -> List[Dict[str, Any]]:
        """Parse CrewAI output to extract issues.

        Priority:
        1. result.raw  — in-memory output of the last task (ranking_task)
        2. ranking_report.md — disk copy of ranking_task output
        3. localization_report.md — disk copy of localization_task output
           (ranking_task may have failed; localization output is still valid)
        """
        try:
            
            if hasattr(result, 'raw'):
                result_text = result.raw
            elif hasattr(result, 'json'):
                result_text = result.json
            else:
                result_text = str(result)

            
            if not result_text or result_text.strip() == '' or result_text == 'None':
                print(f"    [PARSE] Empty response from LLM, trying file fallbacks...")
                return self._parse_report_files()

            
            try:
                issues = json.loads(result_text) if isinstance(result_text, str) else result_text

                if isinstance(issues, list) and len(issues) > 0:
                    print(f"    [PARSE] ✅ Successfully parsed {len(issues)} issues from LLM output")
                    return issues
            except json.JSONDecodeError:
                print(f"    [PARSE] JSON decode failed, trying regex extraction...")
                import re
                match = re.search(r'(\[\s*\{[\s\S]*\}\s*\])', result_text)
                if match:
                    try:
                        issues = json.loads(match.group(1))
                        if isinstance(issues, list) and len(issues) > 0:
                            print(f"    [PARSE] ✅ Extracted {len(issues)} issues from response")
                            return issues
                    except:
                        pass

            
            print(f"    [PARSE] Falling back to report file parsing...")
            return self._parse_report_files()

        except Exception as e:
            print(f"    [PARSE ERROR] {str(e)}")
            return self._parse_report_files()

    def _parse_report_files(self) -> List[Dict[str, Any]]:
        """
        Fallback parser: try ranking_report.md first, then localization_report.md.
        ranking_report.md = ranking_task output (ranked issues, ideal)
        localization_report.md = localization_task output (unranked — still useful)
        """
        import re

        for report_name in ['ranking_report.md', 'localization_report.md']:
            report_file = Path(report_name)
            if not report_file.exists():
                continue
            try:
                content = report_file.read_text(encoding='utf-8')
                match = re.search(r'(\[\s*\{[\s\S]*\}\s*\])', content)
                if match:
                    issues = json.loads(match.group(1))
                    if isinstance(issues, list) and len(issues) > 0:
                        print(f"    [PARSE] ✅ Loaded {len(issues)} issues from {report_name}")
                        # Ensure every issue has a rank field
                        for i, issue in enumerate(issues, 1):
                            if 'rank' not in issue:
                                issue['rank'] = i
                        return issues
            except Exception as e:
                print(f"    [PARSE] Failed to read {report_name}: {e}")
                continue

        print("[WARN] No valid report files found")
        return []

    def _print_pipeline_summary(self, file_path: str) -> None:
        """
        Print a combined terminal report showing what each pipeline stage found.
        Reads the intermediate .md files written by the crew tasks.
        """
        import re

        sep = "=" * 60
        print(f"\n{sep}")
        print(f"  PIPELINE SUMMARY — {file_path}")
        print(sep)

       
        print("\n[STAGE 1] Design Issue Identification (issue_report.md)")
        try:
            content = Path("issue_report.md").read_text(encoding="utf-8")
            
            m = re.search(r'\{[\s\S]*?"design_issues"[\s\S]*?\}', content)
            if m:
                identified = json.loads(m.group(0))
                issues_found = identified.get("design_issues", [])
                ref_types = identified.get("refactoring_types", identified.get("refactoring", []))
                print(f"  Issues identified : {issues_found}")
                print(f"  Refactoring types : {ref_types}")
            else:
                print(f"  (raw): {content[:300].strip()}")
        except Exception as e:
            print(f"  (not available: {e})")

        
        print("\n[STAGE 2] Code Analysis (analysis_report.md)")
        try:
            content = Path("analysis_report.md").read_text(encoding="utf-8")
          
            print(f"  {content[:400].strip()}")
        except Exception as e:
            print(f"  (not available: {e})")

        
        print("\n[STAGE 3] Issue Localization (localization_report.md)")
        try:
            content = Path("localization_report.md").read_text(encoding="utf-8")
            m = re.search(r'(\[\s*\{[\s\S]*\}\s*\])', content)
            if m:
                loc_issues = json.loads(m.group(1))
                print(f"  Localized {len(loc_issues)} issue(s):")
                for item in loc_issues:
                    cname    = item.get("Class name", "?")
                    fname    = item.get("Function name", "?")
                    rtype    = item.get("refactoring_type", "?")
                    line     = item.get("line", "?")
                    rat      = item.get("rationale", "")
                    category = self._infer_issue_category(rat, rtype)
                    print(f"    • {cname}.{fname}  [Category: {category}]  [{rtype}]  line {line}")
            else:
                print(f"  (raw): {content[:300].strip()}")
        except Exception as e:
            print(f"  (not available: {e})")

        
        print("\n[STAGE 4] Ranked Issues (ranking_report.md)")
        try:
            content = Path("ranking_report.md").read_text(encoding="utf-8")
            m = re.search(r'(\[\s*\{[\s\S]*\}\s*\])', content)
            if m:
                ranked = json.loads(m.group(1))
                print(f"  Final ranking ({len(ranked)} issue(s)):")
                for item in sorted(ranked, key=lambda x: x.get("rank", 99)):
                    rank     = item.get("rank", "?")
                    cname    = item.get("Class name", "?")
                    fname    = item.get("Function name", "?")
                    rtype    = item.get("refactoring_type", "?")
                    line     = item.get("line", "?")
                    rat      = item.get("rationale", "")
                    category = self._infer_issue_category(rat, rtype)
                    print(f"    #{rank}  {cname}.{fname}  line {line}")
                    print(f"         Category  : {category}")
                    print(f"         Refactoring: {rtype}")
                    print(f"         Rationale  : {rat[:120]}")
            else:
                print(f"  (raw): {content[:300].strip()}")
        except Exception as e:
            print(f"  (not available: {e})")

        print(f"\n{sep}\n")

    def _infer_issue_category(self, rationale: str, refactoring_type: str) -> str:
        """
        Infer the design issue category from the rationale text and refactoring type.
        Returns one of: god class, feature envy, complexity, modularity, information hiding, unknown.
        """
        rat_lower = rationale.lower()
        ref_lower = refactoring_type.lower()

        if "god class" in rat_lower or "god class" in ref_lower:
            return "god class"
        if "feature envy" in rat_lower or "feature envy" in ref_lower:
            return "feature envy"
        if any(kw in rat_lower for kw in [
            "information hiding", "public field", "encapsulation",
            "public instance field", "bypasses encapsulation",
            "exposes public", "direct assignment", "dot-notation"
        ]):
            return "information hiding"
        if any(kw in rat_lower for kw in [
            "complexity", "inline variable", "inline method",
            "cyclomatic", "nesting", "single-use", "trivial",
            "long method", "extract method"
        ]) or ref_lower in ("inline variable", "inline method", "extract method"):
            return "complexity"
        if any(kw in rat_lower for kw in [
            "modularity", "separation of concerns", "cohesion",
            "tight coupling", "multiple responsibilit"
        ]):
            return "modularity"
        return "unknown"

    def _create_basic_issues(self, code_content: str, file_path: str) -> List[Dict[str, Any]]:
        """Create basic issues using heuristics when LLM fails"""
        import re

        issues = []
        lines = code_content.split('\n')
        class_name = file_path.split('/')[-1].replace('.java', '')

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
                            "rationale": f"Method has {method_line_count} lines. Consider extracting smaller methods.",
                            "rank": len(issues) + 1,
                            "severity": "medium",
                            "line": method_start_line
                        })
                    in_method = False

        method_decl_re = re.compile(
            r'\b(?:public|private|protected)\s+(?:static\s+)?(?:\w+(?:<[^>]*>)?)\s+(\w+)\s*\('
        )
        all_method_names = method_decl_re.findall(code_content)
        business_methods = [
            m for m in all_method_names
            if not (
                (m.startswith('get') and len(m) > 3) or
                (m.startswith('set') and len(m) > 3) or
                (m.lower().startswith('is') and len(m) > 2)
            )
        ]
        method_count = len(business_methods)
        if method_count > 5:
            issues.append({
                "Class name": class_name,
                "Function name": "N/A",
                "Function signature": "class-level",
                "refactoring_type": "extract class",
                "rationale": f"Class has {method_count} methods. Consider splitting responsibilities.",
                "rank": len(issues) + 1,
                "severity": "high",
                "line": 1
            })


        inline_pattern = re.compile(
            r'^\s*(int|long|double|float|boolean|String)\s+(\w+)\s*=\s*.+;'
        )
        for i, line in enumerate(lines):
            m = inline_pattern.match(line)
            if not m:
                continue
            var_name = m.group(2)
           
            next_chunk = '\n'.join(lines[i + 1: i + 4])
            usage_count = len(re.findall(r'\b' + re.escape(var_name) + r'\b', next_chunk))
           
            total_usages = len(re.findall(
                r'\b' + re.escape(var_name) + r'\b',
                '\n'.join(lines[i + 1:])
            ))
            if usage_count == 1 and total_usages == 1:
                issues.append({
                    "Class name": class_name,
                    "Function name": "main",
                    "Function signature": "main(String[] args)",
                    "refactoring_type": "inline variable",
                    "rationale": (
                        f"Variable '{var_name}' is assigned once and used exactly once "
                        "immediately after — it can be inlined to remove unnecessary indirection."
                    ),
                    "rank": len(issues) + 1,
                    "severity": "low",
                    "line": i + 1
                })


        pub_field_pattern = re.compile(r'\b(\w+)\.([a-z]\w*)\s*=\s*')
        seen_objects: set = set()
        for i, line in enumerate(lines, 1):
            for m in pub_field_pattern.finditer(line):
                obj_name = m.group(1)
                field_name = m.group(2)
              
                if obj_name == 'this' or obj_name in seen_objects:
                    continue
               
                if obj_name[0].isupper():   
                    continue
                seen_objects.add(obj_name)
                issues.append({
                    "Class name": class_name,
                    "Function name": "main",
                    "Function signature": "main(String[] args)",
                    "refactoring_type": "extract class",
                    "rationale": (
                        f"Direct assignment to public field '{obj_name}.{field_name}' "
                        "bypasses encapsulation. The target class should expose a "
                        "constructor or setter instead of public fields."
                    ),
                    "rank": len(issues) + 1,
                    "severity": "medium",
                    "line": i
                })


        pub_field_decl_re = re.compile(
            r'^\s*public\s+(?!(?:static\s+)?(?:class|interface|enum)\b)'
            r'(?:(?:static|final)\s+)*'
            r'(?!void\b)(\w+(?:<[^>]*>)?)\s+(\w+)\s*;'
        )
        pub_fields_found = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('*'):
                continue
            m = pub_field_decl_re.match(line)
            if m:
                pub_fields_found.append((m.group(2), i))

        if pub_fields_found:
            field_list = ', '.join(f"'{f}'" for f, _ in pub_fields_found[:5])
            suffix = f" and {len(pub_fields_found) - 5} more" if len(pub_fields_found) > 5 else ""
            issues.append({
                "Class name": class_name,
                "Function name": "N/A",
                "Function signature": "class-level",
                "refactoring_type": "extract class",
                "rationale": (
                    f"Information hiding violation: {len(pub_fields_found)} public instance "
                    f"field(s) found ({field_list}{suffix}). Fields should be private with "
                    "getter/setter access to preserve encapsulation."
                ),
                "rank": len(issues) + 1,
                "severity": "medium",
                "line": pub_fields_found[0][1]
            })

        return issues
    
    def _find_function_line(self, code_content: str, issue: dict) -> int:
        """
        Find the EXACT line number of a function or class using AST.
        Returns the declaration line number from javalang AST.
        Falls back to text search only if AST fails.
        """
        import javalang
        import re
        
        func_name = issue.get('Function name', '')
        class_name = issue.get('Class name', '')
        
       
        if not func_name or func_name in ('N/A', ''):
            return self._find_class_line(code_content, class_name)
        
        try:
          
            clean_code = re.sub(r"//.*?$|/\*.*?\*/", "", code_content, flags=re.MULTILINE)
            
            
            tree = javalang.parse.parse(clean_code)
            
          
            for type_decl in tree.types:
               
                if hasattr(type_decl, 'name') and type_decl.name == class_name:
                    if hasattr(type_decl, 'methods'):
                        for method in type_decl.methods:
                            if method.name == func_name:
                               
                                if hasattr(method, 'position') and method.position:
                                    return method.position.line
        except Exception as e:
            print(f"         AST parse failed for {func_name}: {e}")
        
        
        lines = code_content.split('\n')
        for i, line in enumerate(lines, 1):
            
            if func_name in line and '(' in line:
                # Avoid matching comments or method calls
                if '//' not in line[:line.index(func_name)] and '/*' not in line[:line.index(func_name)]:
                    # Check if this looks like a method declaration (has visibility modifier or return type before it)
                    if any(keyword in line for keyword in ['public', 'private', 'protected', 'void', 'int', 'String', 'boolean']):
                        return i
        
        return 1  # Last resort fallback
    
    def _find_class_line(self, code_content: str, class_name: str) -> int:
        """
        Find the EXACT line number of a class declaration using AST.
        """
        import javalang
        import re
        
        if not class_name:
            return 1
        
        try:
            # Clean code for parsing
            clean_code = re.sub(r"//.*?$|/\*.*?\*/", "", code_content, flags=re.MULTILINE)
            
            # Parse AST
            tree = javalang.parse.parse(clean_code)
            
            # Search for class in AST
            for type_decl in tree.types:
                if hasattr(type_decl, 'name') and type_decl.name == class_name:
                    if hasattr(type_decl, 'position') and type_decl.position:
                        return type_decl.position.line
        except Exception as e:
            print(f"       ⚠️  AST parse failed for class {class_name}: {e}")
        
        # Fallback: Text search for class declaration.
        # Do NOT require a specific access modifier — the declaration may have
        # extra modifiers between the access level and the keyword, e.g.
        # "public final class Foo", "public abstract class Foo", "class Foo".
        lines = code_content.split('\n')
        class_pattern = re.compile(rf'\b(?:class|interface|enum)\s+{re.escape(class_name)}\b')
        for i, line in enumerate(lines, 1):
            if class_pattern.search(line):
                return i
        
        return 1

    def _generate_github_url(self, file_path: str, line_number=None) -> str:
        """
        Generate a GitHub URL pointing to a file (and optionally a specific line).

        Args:
            file_path: File path in repository
            line_number: Line number (optional). When None or 0, the URL points to
                         the file without a line anchor.

        Returns:
            GitHub URL string, or empty string when repo_info is unavailable.
        """
        if not self.repo_info:
            return ""

        owner = self.repo_info.get('owner', '')
        repo = self.repo_info.get('repo', '')
        branch = self.repo_info.get('branch', 'main')

        if not owner or not repo:
            return ""

        url = f"https://github.com/{owner}/{repo}/blob/{branch}/{file_path}"
        if line_number:
            url += f"#L{line_number}"
        return url
    
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
            
            # Filter 1: Skip getter/setter methods flagged for information_hiding ONLY.
            # Do NOT filter move_method — a method like getGreeting() that starts with
            # "get" may still be a real business-logic method that belongs elsewhere.
            if self._is_getter_setter(func_name):
                if 'information hiding' in refactoring_type.lower() or 'information hiding' in rationale:
                    skip_reason = f"Getter/Setter with info hiding: {func_name}"
            
            # Filter 2: Validate class name exists in code
            if class_name and class_name not in actual_classes:
                # Check if it's a hallucinated class (e.g., OrderLogic when only Order exists)
                skip_reason = f"Class '{class_name}' not found in code (hallucination)"
            
            # Filter 3: Skip god class issues on model/DTO classes
            if is_model_class and 'god class' in rationale:
                skip_reason = f"God class on Model/DTO class"
            
            # Filter 4: Skip feature envy ONLY when the method accesses fields from its
            # OWN class (which is not feature envy at all).
            # OLD BUG: checked `class_name in rationale` — the class name always appears
            # in any rationale, so this was silencing valid issues like OrderManager.placeOrder.
            # FIX: only block when the rationale explicitly says the method uses its own fields.
            if 'feature envy' in refactoring_type.lower() or 'feature envy' in rationale:
                own_field_phrases = [
                    'own field', 'its own field', 'same class', 'accesses its own',
                    "this class's own", 'from its own', 'uses its own'
                ]
                if any(phrase in rationale for phrase in own_field_phrases):
                    skip_reason = "Feature envy on own class fields"
            
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
        """
        Check if method name is a getter or setter
        
        IMPORTANT: This is a conservative check. We only treat simple field accessors
        as getters/setters, NOT business logic methods that happen to start with "get".
        
        Examples:
        - getName() -> True (simple getter)
        - setName() -> True (simple setter)
        - isActive() -> True (boolean getter)
        - getGreeting() -> False (generates greeting, not a simple field accessor)
        - getCustomerStatus() -> False (computes status, not a simple field accessor)
        """
        if not method_name or method_name == 'N/A':
            return False
        
        method_lower = method_name.lower()
        
        # Business logic method patterns (NOT getters/setters)
        # These methods do computation, not simple field access
        business_logic_keywords = [
            'greeting', 'status', 'report', 'calculate', 'compute', 'generate',
            'process', 'validate', 'check', 'update', 'create', 'build',
            'confirm', 'send', 'email', 'tier', 'points', 'price', 'total'
        ]
        
        for keyword in business_logic_keywords:
            if keyword in method_lower:
                return False  # This is business logic, not a simple getter/setter
        
        # Standard getter/setter patterns (only if NOT business logic)
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