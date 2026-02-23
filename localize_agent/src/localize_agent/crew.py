from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


def get_llm_with_fallback():
    """
    Build the primary LLM. Gemini is the default (free, reliable JSON output).
    Bedrock is available as alternative by changing MODEL in .env.

    LiteLLM model string format:
      gemini/gemini-2.0-flash   → Google Gemini (needs GEMINI_API_KEY / GOOGLE_API_KEY)
      bedrock/anthropic.claude-3-haiku-20240307-v1:0 → AWS Bedrock (needs AWS creds)
    """
    model = os.getenv("MODEL", "gemini/gemini-2.0-flash")
    print(f"[LLM] Model: {model}")

    # Common LLM settings regardless of provider
    common = dict(
        model=model,
        temperature=0.1,   # deterministic JSON output
        max_tokens=8192,
        timeout=180,
        max_retries=3,
    )

    if model.startswith("gemini/") or model.startswith("google/"):
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_key:
            raise ValueError(
                "MODEL is set to a Gemini model but neither GEMINI_API_KEY nor "
                "GOOGLE_API_KEY is set in .env"
            )
        print(f"[LLM] Provider: Gemini (Google AI)")
        return LLM(**common, api_key=gemini_key)

    elif model.startswith("bedrock/"):
        print(f"[LLM] Provider: AWS Bedrock  region={os.getenv('AWS_REGION','us-east-1')}")
        return LLM(
            **common,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_region_name=os.getenv("AWS_REGION", "us-east-1"),
        )

    else:
        # OpenAI, Anthropic direct, etc. — let LiteLLM pick up the key from env
        print(f"[LLM] Provider: auto (LiteLLM)")
        return LLM(**common)


@CrewBase
class LocalizeAgent:
    """Design Issue Localization Crew with multiple specialized agents and tasks."""
    
    # Paths to your configuration files
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'
    
    def __init__(self):
        """Initialize with LLM configuration"""
        # Don't call super().__init__() - CrewBase handles initialization via metaclass
        self.llm = get_llm_with_fallback()
        self._print_llm_config()
    
    def _print_llm_config(self):
        model = os.getenv("MODEL", "gemini/gemini-2.0-flash")
        print(f"[OK] Active model: {model}")
    
    @agent
    def planning_agent(self) -> Agent:
        def delegate_tasks():
            # Trigger design_issue_identification_agent
            print("Debug: Triggering design_issue_identification_agent...")
            design_issues = self.design_issue_identification_agent.run()
            print(f"Debug: Design issues identified: {design_issues}")

            # Trigger code_analyzer_agent based on design issues
            if design_issues:
                print("Debug: Triggering code_analyzer_agent...")
                analysis_results = self.code_analyzer_agent.run(input_data=design_issues)
                print(f"Debug: Code analysis results: {analysis_results}")

                # Trigger prompt_engineering_agent based on analysis results
                if analysis_results:
                    print("Debug: Triggering prompt_engineering_agent...")
                    prompt = self.prompt_engineering_agent.run(input_data=analysis_results)
                    print(f"Debug: Prompt generated: {prompt}")

            # The rest of the tasks can be executed sequentially
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
        # Tools have been removed from this agent intentionally.
        # Metrics (CountMethods, VariableUsage, FanInFanOut, ClassCoupling) are now
        # pre-computed in Python via _compute_metrics() in batch_analyzer.py and
        # injected as the {metrics} template variable. This eliminates the ReAct
        # tool-call loop that caused Haiku to send the full source code 9 times,
        # which overflowed the context and produced empty LLM responses.
        return Agent(
            config=self.agents_config['code_analyzer_agent'],
            llm=self.llm,
            verbose=True,
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
        """Creates the Code Analysis Crew that orchestrates all agents and tasks.

        planning_task is registered via @task (so CrewBase picks it up) but is
        intentionally excluded from the active task list here.  No downstream task
        uses it as context, so it was a wasted LLM call.  The active pipeline is:
          1. design_issue_identification_task
          2. code_analysis_task
          3. prompt_engineering_task
          4. design_issue_localization_task
          5. ranking_task
        """
        active_tasks = [
            self.design_issue_identification_task(),
            self.code_analysis_task(),
            self.prompt_engineering_task(),
            self.design_issue_localization_task(),
            self.ranking_task(),
        ]
        return Crew(
            agents=self.agents,
            tasks=active_tasks,
            process=Process.sequential,
            verbose=True
        )
