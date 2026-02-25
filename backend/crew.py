from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
try:
    from localize_agent.tools.custom_tools import CountMethods, VariableUsage, FanInFanOutAnalysis, ClassCouplingAnalysis
except ModuleNotFoundError:
    from tools.custom_tools import CountMethods, VariableUsage, FanInFanOutAnalysis, ClassCouplingAnalysis
import os
import json
from dotenv import load_dotenv

load_dotenv()

def get_llm_with_fallback():
    import boto3
    
    session = boto3.Session(
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
    )
    
    try:
        bedrock = session.client('bedrock-runtime')
        print(f"✅ AWS Bedrock connection successful")
    except Exception as e:
        print(f"❌ AWS Bedrock connection failed: {e}")
    
    model = os.getenv("MODEL", "bedrock/anthropic.claude-3-haiku-20240307-v1:0")
    
    print(f"[LLM] Model: {model}")
    print(f"[LLM] AWS Region: {os.getenv('AWS_REGION', 'us-east-1')}")
    
    return LLM(
        model=model,
        temperature=0.0,  
        max_tokens=8000,  
        timeout=180,  
        max_retries=5,  
        seed=42,  
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        aws_region_name=os.getenv('AWS_REGION', 'us-east-1')
    )

@CrewBase
class LocalizeAgent:
    
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    
    def __init__(self):
        
        self.llm = get_llm_with_fallback()
        self._print_llm_config()
    
    def _print_llm_config(self):
        model = os.getenv("PRIMARY_MODEL", "bedrock/anthropic.claude-3-haiku-20240307-v1:0")
        
        print(f"[OK] Primary Model: {model}")
        print(f"[OK] AWS Region: {os.getenv('AWS_REGION', 'us-east-1')}")
        print(f"[INFO] Using AWS Bedrock (Gemini disabled)")
    
    @agent
    def planning_agent(self) -> Agent:
        def delegate_tasks():
           
            print("Debug: Triggering design_issue_identification_agent...")
            design_issues = self.design_issue_identification_agent.run()
            print(f"Debug: Design issues identified: {design_issues}")

            if design_issues:
                print("Debug: Triggering code_analyzer_agent...")
                analysis_results = self.code_analyzer_agent.run(input_data=design_issues)
                print(f"Debug: Code analysis results: {analysis_results}")

                if analysis_results:
                    print("Debug: Triggering prompt_engineering_agent...")
                    prompt = self.prompt_engineering_agent.run(input_data=analysis_results)
                    print(f"Debug: Prompt generated: {prompt}")

            print("Debug: Triggering remaining tasks sequentially...")
            self.design_issue_localization_agent.run()
            self.ranking_agent.run()

        return Agent(
            config=self.agents_config['planning_agent'],
            llm=self.llm,
            delegate=delegate_tasks,
            verbose=True
        )
    
    @agent
    def design_issue_identification_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['design_issue_identification_agent'],
            llm=self.llm,
            verbose=False
        )
    
    @agent
    def code_analyzer_agent(self) -> Agent:
        
        return Agent(
            config=self.agents_config['code_analyzer_agent'],
            llm=self.llm,
            verbose=True,
            max_iter=3,
            allow_delegation=False
        )
    
    @agent
    def prompt_engineering_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['prompt_engineering_agent'],
            llm=self.llm,
            verbose=True
        )
    
    @agent
    def design_issue_localization_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['design_issue_localization_agent'],
            llm=self.llm,
            verbose=False
        )
    
    @agent
    def ranking_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['ranking_agent'],
            llm=self.llm,
            verbose=False
        )
    
    @task
    def planning_task(self) -> Task:
        return Task(
            config=self.tasks_config['planning_task'],
            output_file='planning_report.md',
        )
    
    @task
    def design_issue_identification_task(self) -> Task:
        return Task(
            config=self.tasks_config['design_issue_identification_task'],
            output_file='issue_report.md'
        )
    
    @task
    def code_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config['code_analysis_task'],
            output_file='analysis_report.md'
        )
    
    @task
    def prompt_engineering_task(self) -> Task:
        return Task(
            config=self.tasks_config['prompt_engineering_task'],
            output_file='prompt_report.md'
        )
    
    @task
    def design_issue_localization_task(self) -> Task:
        return Task(
            config=self.tasks_config['design_issue_localization_task'],
            output_file='localization_report.md'
        )
    
    @task
    def ranking_task(self) -> Task:
        return Task(
            config=self.tasks_config['ranking_task'],
            output_file='ranking_report.md'
        )
    
    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,    
            tasks=self.tasks,      
            process=Process.sequential,
            verbose=True
        )
