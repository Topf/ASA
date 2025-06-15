from dotenv import load_dotenv
import os
import tweepy
from smolagents import CodeAgent, Tool, LiteLLMModel
import json
import requests
from typing import Dict, Any, Optional
from config import TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET, TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_BEARER_TOKEN

load_dotenv()

def load_twitter_credentials():
    credentials = {
        "api_key": TWITTER_API_KEY,
        "api_secret": TWITTER_API_SECRET,
        "access_token": TWITTER_ACCESS_TOKEN,
        "access_token_secret": TWITTER_ACCESS_TOKEN_SECRET
    }
    return credentials

class TwitterTool(Tool):
    
    name = "twitter_post"
    inputs = {
    "text": {
        "type": "string",
        "description": "The text content to tweet (max 280 characters)",
        }
    }
    output_type = "object"

    description = """
    Posts a tweet to Twitter/X. 
    Args:
        text (str): The text content to tweet (max 280 characters)
    Returns:
        dict: The response from the Twitter API, including tweet ID and status.
        
    """
    def __init__(self, api_key: str, api_secret: str, access_token: str, access_token_secret: str):
        super().__init__()
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        
        self._setup_twitter_client()
    
    def _setup_twitter_client(self):
        self.client = tweepy.Client(
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
            wait_on_rate_limit=True
        )
    
    def forward(self, text):
        text = text[:280] if len(text) > 280 else text
        response = self.client.create_tweet(text=text)
        return {
            "success": True,
            "tweet_id": response.data['id'],
            "text": text,
            "url": f"https://twitter.com/user/status/{response.data['id']}"
        }
        

class TwitterAgent:
    def __init__(self, 
                 twitter_credentials: Dict[str, str],
                 model_config: Dict[str, Any] = None):
        
        self.model = LiteLLMModel(**model_config)
        self.twitter_tool = TwitterTool(**twitter_credentials)
        self.name = "TwitterAgent"
        self.description = "An agent that helps manage and post content on Twitter"
        
        self.agent = CodeAgent(
            tools=[self.twitter_tool],
            model=self.model,
            max_steps=10
        )
        
    def post_tweet(self, content):
        return self.twitter_tool.forward(content)
    
twitter_creds = load_twitter_credentials()
model_config = {
                "model_id": os.getenv("ANTHROPIC_MODEL_ID") ,
                "temperature": os.getenv("ANTHROPIC_MODEL_TEMPERATURE"),
                "api_key": os.getenv("ANTHROPIC_API_KEY") 
            }
twitter_agent = TwitterAgent(twitter_creds, model_config)

#def main():
    #twitter_creds = load_twitter_credentials()
    #model_config = {
                #"model_id": os.getenv("ANTHROPIC_MODEL_ID") ,
                #"temperature": os.getenv("ANTHROPIC_MODEL_TEMPERATURE"),
                #"api_key": os.getenv("ANTHROPIC_API_KEY") 
            #}
    #agent = TwitterAgent(twitter_creds, model_config)
    
    #tweet_content = "al al al"    
    #response = agent.post_tweet(tweet_content)
    #print("Tweet Response:")
    #print(json.dumps(response, indent=2))
  
    
#if __name__ == "__main__":
    #main()
