from smolagents import ToolCallingAgent, LiteLLMModel, tool
import yaml
import os
import json
from typing import Dict, List, Any

# Set up your Anthropic API key
os.environ["ANTHROPIC_API_KEY"] = "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"

# Load prompt templates
def load_prompts():
    """Load all prompt files from the prompts directory."""
    prompts = {}
    
    # Load platforms agent prompts
    with open('prompts/platforms_agent_prompts.yaml', 'r') as f:
        prompts['platforms_agent'] = yaml.safe_load(f)
    
    # Load platform-specific prompts
    platform_files = {
        'tiktok_agent': 'prompts/tiktok_prompts.yaml',
        'linkedin_agent': 'prompts/linkedin_prompts.yaml',
        'reddit_agent': 'prompts/reddit_prompts.yaml',
        'twitter_agent': 'prompts/twitter_prompts.yaml',
        'instagram_agent': 'prompts/instagram_prompts.yaml'
    }
    
    for agent_key, file_path in platform_files.items():
        with open(file_path, 'r') as f:
            prompts[agent_key] = yaml.safe_load(f)
    
    return prompts

prompt_templates = load_prompts()

# Create our LiteLLM model for Anthropic Claude 3.5 Sonnet
model = LiteLLMModel(
    model_id="anthropic/claude-opus-4-20250514",
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_tokens=4096,
    temperature=0.5,
)

@tool
def create_platform_content(platform: str, company_description: str, target_audience: str) -> str:
    """
    Creates content strategy for a specific social media platform.
    
    Args:
        platform: The social media platform (e.g., "TikTok", "LinkedIn", "Reddit")
        company_description: Description of the company
        target_audience: Target audience description
    
    Returns:
        str: Content strategy for the platform
    """
    
    # Map platform names to agent keys
    platform_map = {
        "tiktok": "tiktok_agent",
        "linkedin": "linkedin_agent", 
        "reddit": "reddit_agent",
        "twitter": "twitter_agent",
        "x": "twitter_agent",
        "twitter/x": "twitter_agent",
        "instagram": "instagram_agent",
    }
    
    platform_key = platform_map.get(platform.lower())
    if not platform_key:
        return f"Error: Platform '{platform}' not supported. Available: {list(platform_map.keys())}"
    
    # Get platform-specific prompts
    agent_prompts = prompt_templates.get(platform_key, {})
    system_prompt = agent_prompts.get('system_prompt', f"You are a {platform} content strategist.")
    content_prompt = agent_prompts.get('content_prompt', 
        f"Create 3 content ideas for {platform}.\nCOMPANY: {company_description}\nAUDIENCE: {target_audience}")
    
    # Format the prompt
    formatted_prompt = content_prompt.format(
        company_description=company_description,
        target_audience=target_audience,
    )
    
    # Create and run platform agent
    platform_agent = ToolCallingAgent(
        tools=[],
        model=model
    )
    
    # Combine system prompt with user prompt
    full_prompt = f"{system_prompt}\n\n{formatted_prompt}"
    
    return platform_agent.run(full_prompt)

def select_platforms(company_description: str, target_audience: str) -> Dict[str, Any]:
    """Select 3 optimal social media platforms for the company and audience."""
    
    # Create platform selector agent
    selector_agent = ToolCallingAgent(
        tools=[],
        model=model
    )
    
    # Format selection prompt
    selection_prompt = prompt_templates['platforms_agent']['selection_prompt'].format(
        company_description=company_description,
        target_audience=target_audience
    )
    
    # Combine system prompt with selection prompt
    full_prompt = f"{prompt_templates['platforms_agent']['system_prompt']}\n\n{selection_prompt}"
    
    result = selector_agent.run(full_prompt)
    
    # Parse JSON from result
    try:
        start_idx = result.find('{')
        end_idx = result.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = result[start_idx:end_idx]
            return json.loads(json_str)
        else:
            return {"error": "Could not parse platform selection", "raw_response": result}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in platform selection", "raw_response": result}

def run_growth_system(company_description: str, target_audience: str) -> Dict[str, Any]:
    """
    Main function to run the complete Growth Agentic System.
    Simple orchestration of the entire workflow.
    """
    print("🚀 Starting Growth Agentic System...")
    print(f"📊 Company: {company_description[:50]}...")
    print(f"🎯 Audience: {target_audience[:50]}...")
    
    # Step 1: Select platforms
    print("\n📱 Selecting optimal social media platforms...")
    platform_selection = select_platforms(company_description, target_audience)
    
    if "error" in platform_selection:
        return platform_selection
    
    # Step 2: Generate content for each platform
    print("\n🤖 Creating content strategies...")
    content_strategies = {}
    
    for platform_info in platform_selection['selected_platforms']:
        platform = platform_info['platform']
        priority = platform_info['priority']
        
        print(f"🎬 Creating content for {platform} (Priority {priority})...")
        
        content_strategy = create_platform_content(
            platform=platform,
            company_description=company_description,
            target_audience=target_audience
        )
        
        content_strategies[platform] = {
            'priority': priority,
            'content_strategy': content_strategy
        }
    
    return {
        'selected_platforms': platform_selection['selected_platforms'],
        'content_strategies': content_strategies
    } 