from smolagents import CodeAgent, LiteLLMModel
from twitter_agent import twitter_agent 
from reddit_agent import reddit_agent
from web_agent import web_agent
from config import ANTHROPIC_API_KEY

manager_agent = CodeAgent(
    model=LiteLLMModel(
        model_id="anthropic/claude-3-5-sonnet-latest",
        api_key=ANTHROPIC_API_KEY,
    ),
    tools=[],
    managed_agents=[web_agent, twitter_agent, reddit_agent],
    planning_interval=5,
    verbosity_level=2,
    final_answer_checks=[],
    max_steps=15,
)

url = "https://corolair.com/"
manager_agent.run(url)