import praw
# The smolagents library provides the CodeAgent class and model handlers.
from smolagents import CodeAgent, LiteLLMModel
# The @tool decorator is needed to convert a function into a tool the agent can use.
from smolagents.tools import tool
import os

# --- Reddit Tool Definition ---
# IMPORTANT: Fill in your Reddit API credentials here.
# You can get these by creating a new application on Reddit's developer portal:
# https://www.reddit.com/prefs/apps
REDDIT_CLIENT_ID = "IrF4ZTs4tPsXebGXQVLUcA"
REDDIT_CLIENT_SECRET = "BBdBMoYmeXLpPabtmBbr6tnxszTr2g"
REDDIT_USER_AGENT = "smolagent-reddit-scraper/1.0"
os.environ["ANTHROPIC_API_KEY"] = "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"

@tool
def search_reddit(subreddit_name: str, query: str, limit: int = 5) -> list:
    """
    Searches a given subreddit for a query and returns the top posts.

    Args:
        subreddit_name: The name of the subreddit to search (e.g., 'startups').
        query: The search query.
        limit: The maximum number of posts to return.

    Returns:
        A list of dictionaries, where each dictionary represents a post
        and contains the title, url, score, and number of comments.
    """
    # Ensure credentials are provided
    if "YOUR_CLIENT_ID" in REDDIT_CLIENT_ID or "YOUR_CLIENT_SECRET" in REDDIT_CLIENT_SECRET:
        return "Error: Reddit API credentials are not set. Please edit the script to add them."
        
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        # Set to read-only mode
        reddit.read_only = True
        subreddit = reddit.subreddit(subreddit_name)
        search_results = subreddit.search(query, limit=limit)
        
        posts = []
        for post in search_results:
            posts.append({
                "title": post.title,
                "url": post.url,
                "score": post.score,
                "num_comments": post.num_comments
            })
        return posts
    except Exception as e:
        return f"An error occurred with the Reddit API: {e}"


# --- Smolagent Integration ---
def run_reddit_agent(subreddit: str, search_query: str):
    """
    Initializes and runs the smolagent to search Reddit.
    """

    # 1. Define the tools the agent can use.
    # Because we used the @tool decorator, search_reddit is now a valid Tool object.
    tools = [search_reddit]
    
    # 2. Define a system prompt to guide the agent.
    # This prompt tells the agent how to behave and what tools it has.
    system_prompt = (
        "You are a helpful AI assistant that can use Python tools to answer questions. "
        "To use a tool, you must write a Python code block that calls the function. "
        "For example, to search Reddit, you would write:\n"
        "```python\n"
        "print(search_reddit(subreddit_name='startups', query='AI'))\n"
        "```"
    )

    # 3. Initialize the agent with the system prompt, tools, and a model.
    try:
        # 3a. First, initialize the model you want the agent to use.
        # The system prompt is passed to the model, not the agent.
        model = LiteLLMModel(
            model_id="anthropic/claude-3-5-sonnet-latest",
            system=system_prompt

        )

        # 3b. Now, initialize the agent and pass the model object to it.
        agent = CodeAgent(
            tools=tools,
            model=model # Pass the initialized model object here
        )
    except ImportError:
        print("Error: LiteLLM is not installed. Please run 'pip install smolagents[litellm]' to use models like Claude.")
        return
    except Exception as e:
        print(f"Error initializing agent. Have you set your model's API key (e.g., ANTHROPIC_API_KEY)? Error: {e}")
        return

    # 4. Define the user's prompt (the task for the agent).
    user_prompt = f"Search the '{subreddit}' subreddit for '{search_query}' and get the top {5} posts."

    # 5. Run the agent. The agent will generate and execute code to call the tool.
    # The 'result' will be the direct output from the 'search_reddit' function.
    print("Agent is thinking...")
    top_posts = agent.run(user_prompt)
    print("Agent has finished.")

    # 6. Process and display the results.
    print("\n--- Top 5 Reddit Threads ---")
    if isinstance(top_posts, list):
        if not top_posts:
            print("No posts found for your query.")
        for i, post in enumerate(top_posts):
            print(f"{i+1}. URL: {post['url']}")
            print(f"   Title: {post['title']}")
            print(f"   Score: {post['score']}")
            print(f"   Comments: {post['num_comments']}\n")
    else:
        # If the agent returned an error message or something unexpected.
        print(f"Agent did not return a list of posts. Response:\n{top_posts}")


# --- Example Usage ---
if __name__ == "__main__":
    # Example: Search the 'startups' subreddit for posts about 'AI agents'
    # You can change these values to search for anything else.
    run_reddit_agent("startups", "AI agents")
