# Standard library imports
import requests
from typing import Optional

# Third-party imports
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
from bs4 import BeautifulSoup
from smolagents import tool, CodeAgent, LiteLLMModel

# Local imports
from config import ANTHROPIC_API_KEY

# Initialize Anthropic client
client = Anthropic(api_key=ANTHROPIC_API_KEY)

def scrape_website(url: str) -> str:
    """Scrape text content from the given website URL."""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        # Remove scripts and styles
        for tag in soup(["script", "style"]): tag.decompose()
        return ' '.join(soup.stripped_strings)[:8000]  # truncate for Claude
    except Exception as e:
        return f"Error scraping site: {e}"

def generate_description(text):
    """Use Anthropic Claude to generate a company description from text."""
    prompt = (
        f"{HUMAN_PROMPT} Here is some website content:\n\n{text}\n\n"
        "Please summarize this as a professional company description."
        f"{AI_PROMPT}"
    )
    
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=300,
        temperature=0.5,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.content[0].text
    
@tool
def describe_company_from_url(url: str) -> str:
    """
    Summarize the company description from the given website URL using Claude.

    Args:
        url: The URL of the company website to summarize.
    """
    website_text = scrape_website(url)
    if website_text.startswith("Error"):
        return website_text
    return generate_description(website_text)

@tool
def profiler(company_description: str) -> str:
    """
    Based on the company description, profile the people that could be interested in the product, give me an ideal customer profile.

    Args:
        company_description: The description of the company to analyze.
    """
    prompt = (
        f"{HUMAN_PROMPT} Here is a company description:\n\n{company_description}\n\n"
        "Based on this description, please provide a detailed ideal customer profile including:\n"
        "1. Demographics (age, role, industry)\n"
        "2. Pain points and challenges they face\n"
        "3. Goals and objectives they want to achieve\n"
        "4. Decision-making factors\n"
        "5. Technical sophistication level\n"
        "Please format this as a clear, professional customer profile."
        f"{AI_PROMPT}"
    )
    
    
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=300,
        temperature=0.5,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.content[0].text

web_agent = CodeAgent(tools=[describe_company_from_url, profiler], 
                      model=LiteLLMModel(
                          model_id="anthropic/claude-3-5-sonnet-latest",
                          api_key=ANTHROPIC_API_KEY,
                      ),
                      name="URLDescriptionAgent",
                      description="An agent that gives you the ideal customer profile from website URLs"
                      )

if __name__ == "__main__":
    web_agent = CodeAgent(tools=[describe_company_from_url, profiler], 
                      model=LiteLLMModel(
                          model_id="anthropic/claude-3-5-sonnet-latest",
                          api_key=ANTHROPIC_API_KEY,
                      ),
                      name="URLDescriptionAgent",
                      description="An agent that gives you the ideal customer profile from website URLs"
                      )
    url = "https://corolair.com/"

    web_agent.run(url)