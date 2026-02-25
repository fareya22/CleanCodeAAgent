import javalang  
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import re

class CodeAnalysisInput(BaseModel):
    source_code: str = Field(..., description="The Java source code to analyze.")

class CountMethods(BaseTool):
    name: str = "CountMethods"
    description: str = "Counts the number of methods in a given Java source code."
    args_schema: Type[BaseModel] = CodeAnalysisInput

    def _run(self, source_code: str) -> str:
        try:
            print("Debug: Starting to clean up the Java source code.")
           
            source_code = re.sub(r"//.*?$|/\*.*?\*/|^\s*import\s+.*?;", "", source_code, flags=re.DOTALL | re.MULTILINE)
            print("Debug: Cleaned up the Java source code.")

            print("Debug: Starting to parse the Java source code.")
            
            tree = javalang.parse.parse(source_code)
            print("Debug: Successfully parsed the Java source code.")

            method_count = 0
            for type_decl in tree.types:
                print(f"Debug: Processing type declaration: {type_decl.name if hasattr(type_decl, 'name') else 'Unknown'}")
                
                if hasattr(type_decl, 'methods'):
                    method_count += len(type_decl.methods)
                    print(f"Debug: Found {len(type_decl.methods)} methods in {type_decl.name if hasattr(type_decl, 'name') else 'Unknown'}.")

            print(f"Debug: Total methods counted: {method_count}")
            return f"The source code contains {method_count} methods."
        except Exception as e:
            print(f"Debug: Error encountered - {e}")
            return f"Error processing Java source code: {e}"

class VariableUsage(BaseTool):
    name: str = "VariableUsage"
    description: str = "Analyzes variable usage and identifies inline variable candidates (variables assigned once and used once immediately after)."
    args_schema: Type[BaseModel] = CodeAnalysisInput

    def _run(self, source_code: str) -> str:
        try:
            source_code_clean = re.sub(r"//.*?$|/\*.*?\*/|^\s*import\s+.*?;", "", source_code, flags=re.DOTALL | re.MULTILINE)

            tree = javalang.parse.parse(source_code_clean)

            variable_usage = {
                "global": 0,
                "methods": {},
                "inline_variable_candidates": []
            }

            for type_decl in tree.types:
                if hasattr(type_decl, 'fields'):
                    for field_decl in type_decl.fields:
                        variable_usage["global"] += len(field_decl.declarators)

                if hasattr(type_decl, 'methods'):
                    for method in type_decl.methods:
                        method_name = method.name
                        method_var_count = 0

                        for _, node in method.filter(javalang.tree.LocalVariableDeclaration):
                            method_var_count += len(node.declarators)

                        variable_usage["methods"][method_name] = method_var_count
            
            lines = source_code.split('\n')
            for i in range(len(lines) - 1):
                line = lines[i].strip()
                next_line = lines[i + 1].strip()
                
                var_decl_match = re.match(r'^\s*([\w<>]+)\s+(\w+)\s*=\s*(.+?);', line)
                if var_decl_match:
                    var_name = var_decl_match.group(2)
                    if var_name in next_line and next_line.count(var_name) == 1:
                        if not re.match(r'^\s*[\w<>]+\s+' + var_name, next_line):
                            variable_usage["inline_variable_candidates"].append({
                                "variable": var_name,
                                "line": i + 1,
                                "declaration": line,
                                "usage": next_line
                            })

            inline_count = len(variable_usage["inline_variable_candidates"])
            result = f"Variable Usage: Global fields: {variable_usage['global']}, "
            result += f"Methods: {variable_usage['methods']}, "
            result += f"**INLINE VARIABLE CANDIDATES: {inline_count}** "
            if inline_count > 0:
                result += f"(Variables: {', '.join([c['variable'] for c in variable_usage['inline_variable_candidates']])})"
            
            return result
        except Exception as e:
            return f"Error processing Java source code: {e}"

class FanInFanOutAnalysis(BaseTool):
    name: str = "FanInFanOutAnalysis"
    description: str = (
        "Analyzes methods in the Java source code and computes a naive fan-in/fan-out."
        " Fan-out = number of distinct methods that a method calls; "
        " Fan-in = number of times a method is called by other methods in the same file."
    )
    args_schema: Type[BaseModel] = CodeAnalysisInput

    def _run(self, source_code: str) -> str:
        try:
           
            source_code = re.sub(
                r"//.*?$|/\*.*?\*/|^\s*import\s+.*?;",
                "",
                source_code,
                flags=re.DOTALL | re.MULTILINE
            )

            tree = javalang.parse.parse(source_code)

            method_calls = {}

            for type_decl in tree.types:
                if hasattr(type_decl, 'methods'):
                    for method in type_decl.methods:
                        class_and_method = f"{type_decl.name}.{method.name}"
                        method_calls[class_and_method] = set()

                        for _, node in method.filter(javalang.tree.MethodInvocation):
                            method_calls[class_and_method].add(node.member)

            fan_metrics = {}
            for method_key in method_calls.keys():
                fan_metrics[method_key] = {
                    "fanIn": 0,
                    "fanOut": 0
                }

            for method_key, calls in method_calls.items():
                fan_metrics[method_key]["fanOut"] = len(calls)

            for caller, called_methods in method_calls.items():
                for called_m in called_methods:
                    possible_targets = [
                        k for k in method_calls.keys() 
                        if k.endswith("." + called_m)
                    ]
                    if len(possible_targets) == 1:
                        callee_key = possible_targets[0]
                        fan_metrics[callee_key]["fanIn"] += 1

            lines = ["Fan-In / Fan-Out Analysis:"]
            for m_key, data in fan_metrics.items():
                lines.append(
                    f"Method {m_key}: fanIn={data['fanIn']}, fanOut={data['fanOut']}"
                )

            return "\n".join(lines)

        except Exception as e:
            return f"Error processing Java source code: {e}"
        
class ClassCouplingAnalysis(BaseTool):
    name: str = "ClassCouplingAnalysis"
    description: str = (
        "By assessing class dependencies, this analysis provides insights into system"
        " modularity and potential areas for improving design quality. This tool identifies"
        " each class in the source file and detects the other classes it references."
    )
    args_schema: Type[BaseModel] = CodeAnalysisInput

    def _run(self, source_code: str) -> str:
        try:
            source_code = re.sub(
                r"//.*?$|/\*.*?\*/|^\s*import\s+.*?;",
                "",
                source_code,
                flags=re.DOTALL | re.MULTILINE
            )

            tree = javalang.parse.parse(source_code)

            class_references = {}

            for type_decl in tree.types:
                if not hasattr(type_decl, 'name'):
                    continue

                current_class_name = type_decl.name
                class_references[current_class_name] = set()

                for _, node in type_decl.filter(javalang.tree.Type):
                    if node.name and (node.name != current_class_name):
                        class_references[current_class_name].add(node.name)

            lines = ["Class Coupling Analysis:"]
            for class_name, references in class_references.items():
                coupling_count = len(references)
                lines.append(
                    f"  - Class {class_name} references: {sorted(list(references)) or 'None'}"
                    f" -> Coupling = {coupling_count}"
                )

            return "\n".join(lines)

        except Exception as e:
            return f"Error processing Java source code: {e}"
