#!/usr/bin/env python
import sys
import warnings
import os
import json
from dotenv import load_dotenv
import litellm
from crewai import LLM

load_dotenv()
os.environ["OTEL_SDK_DISABLED"] = "true"

# Configure LiteLLM settings
litellm.set_verbose = False
litellm.drop_params = True  # Drop unsupported params

# AWS Bedrock Claude as PRIMARY model
PRIMARY_MODEL = "bedrock/anthropic.claude-3-haiku-20240307-v1:0"
FALLBACK_MODEL = "bedrock/anthropic.claude-3-haiku-20240307-v1:0"
os.environ["FALLBACK_MODELS"] = json.dumps([PRIMARY_MODEL, FALLBACK_MODEL])
os.environ["PRIMARY_MODEL"] = PRIMARY_MODEL
os.environ["FALLBACK_MODEL"] = FALLBACK_MODEL
os.environ["USE_FALLBACK_MODEL"] = "false"

print("[OK] Using AWS Bedrock Claude 3 Haiku as primary model")

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def get_file_path(default_path=None):
    """
    Prompt user for file path or use the provided default.
    """
    if default_path and os.path.exists(default_path):
        try:
            use_default = input(f"Use default file path ({default_path})? (y/n): ").lower() == 'y'
            if use_default:
                return default_path
        except EOFError:
            # Auto-accept default when no input available (e.g., piped input)
            print(f"Auto-using default: {default_path}")
            return default_path
    
    while True:
        try:
            file_path = input("Enter the path to your source code file: ")
            if os.path.exists(file_path):
                return file_path
            else:
                print(f"File not found: {file_path}")
        except EOFError:
            if default_path:
                print(f"No input provided, using default: {default_path}")
                return default_path
            raise

def run():
    """
    Run the crew with AWS Bedrock Claude.
    """
    # Use absolute path to avoid working directory issues
    import pathlib
    base_dir = pathlib.Path(__file__).parent
    default_path = base_dir / 'datasets' / 'test_input.java'
    
    file_path = get_file_path(str(default_path))
    
    with open(file_path, 'r') as f:
        source_code = f.read()
    
    inputs = {
        "code": source_code
    }

    try:
        print("[RUN] Running crew with AWS Bedrock Claude...")
        from localize_agent.crew import LocalizeAgent
        LocalizeAgent().crew().kickoff(inputs=inputs)
        print("[OK] Crew execution completed successfully!")
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    file_path = get_file_path()
    
    with open(file_path, 'r') as f:
        source_code = f.read()
    
    inputs = {
        "code": source_code
    }
    try:
        LocalizeAgent().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        LocalizeAgent().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    file_path = get_file_path()
    
    with open(file_path, 'r') as f:
        source_code = f.read()
    
    inputs = {
        "code": source_code
    }
    try:
        LocalizeAgent().crew().test(n_iterations=int(sys.argv[1]), openai_model_name=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")
