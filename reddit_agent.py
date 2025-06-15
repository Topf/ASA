# Standard library imports
import praw
import json
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import wraps
import logging
import os
from dotenv import load_dotenv
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, REDDIT_USERNAME, REDDIT_PASSWORD, CLAUDE_API_KEY

# Third-party imports
import backoff
from smolagents import CodeAgent, DuckDuckGoSearchTool, LiteLLMModel, tool

# Configuration
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting decorator
def rate_limit(calls: int, period: int):
    """Decorator to implement rate limiting"""
    def decorator(func):
        last_reset = datetime.now()
        calls_made = 0
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal last_reset, calls_made
            now = datetime.now()
            
            if now - last_reset > timedelta(seconds=period):
                last_reset = now
                calls_made = 0
                
            if calls_made >= calls:
                sleep_time = period - (now - last_reset).total_seconds()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                last_reset = datetime.now()
                calls_made = 0
                
            calls_made += 1
            return func(*args, **kwargs)
        return wrapper
    return decorator

@tool
@backoff.on_exception(backoff.expo, praw.exceptions.RedditAPIException, max_tries=3)
@rate_limit(calls=30, period=60)
def publish_post(title: str, content: str, subreddit: str, 
                post_type: Optional[str] = None, url: Optional[str] = None) -> str:
    """
    Publie un post sur Reddit dans un subreddit spécifique.

    Args:
        title: Titre du post Reddit
        content: Contenu du post
        subreddit: Nom du subreddit (sans r/)
        post_type: Type de post ('text' ou 'link')
        url: URL si c'est un post de type link
    """
    try:
        # Validation des entrées
        if not title or len(title) > 300:
            raise ValueError("Le titre doit faire entre 1 et 300 caractères")
        if not content or len(content) > 40000:
            raise ValueError("Le contenu doit faire entre 1 et 40000 caractères")
        if not subreddit:
            raise ValueError("Le nom du subreddit est requis")
        if post_type and post_type not in ["text", "link"]:
            raise ValueError("Type de post invalide (text ou link)")
        if post_type == "link" and not url:
            raise ValueError("URL requise pour un post de type link")

        # Initialisation de l'API Reddit
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD
        )

        sub = reddit.subreddit(subreddit)
        
        if post_type is None:
            post_type = "text"
        
        if post_type == "text":
            submission = sub.submit(title=title, selftext=content)
        else:  # post_type == "link"
            submission = sub.submit(title=title, url=url)
        
        logger.info(f"Post publié avec succès dans r/{subreddit}")
        return f"Post publié avec succès! URL: https://reddit.com{submission.permalink}"
        
    except Exception as e:
        logger.error(f"Erreur lors de la publication: {str(e)}")
        raise

@tool
@backoff.on_exception(backoff.expo, praw.exceptions.RedditAPIException, max_tries=3)
@rate_limit(calls=30, period=60)
def analyze_subreddit(subreddit: str) -> str:
    """
    Analyse les règles et tendances d'un subreddit.

    Args:
        subreddit: Nom du subreddit à analyser
    """
    try:
        if not subreddit:
            raise ValueError("Le nom du subreddit est requis")

        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD
        )
            
        sub = reddit.subreddit(subreddit)
        
        # Récupérer les règles
        rules = []
        try:
            for rule in sub.rules:
                rules.append(f"- {rule.short_name}: {rule.description}")
        except Exception as e:
            logger.warning(f"Impossible de récupérer les règles: {str(e)}")
            rules = ["Règles non accessibles"]
        
        # Analyser les posts populaires récents
        hot_posts = []
        try:
            for post in sub.hot(limit=10):
                hot_posts.append({
                    "title": post.title,
                    "score": post.score,
                    "num_comments": post.num_comments,
                    "is_self": post.is_self
                })
        except Exception as e:
            logger.warning(f"Impossible de récupérer les posts chauds: {str(e)}")
        
        analysis = f"""
        Analyse du subreddit r/{subreddit}:
        
        Règles principales:
        {chr(10).join(rules)}
        
        Tendances des posts populaires:
        - Score moyen: {sum(p['score'] for p in hot_posts) / len(hot_posts) if hot_posts else 0:.0f}
        - Commentaires moyens: {sum(p['num_comments'] for p in hot_posts) / len(hot_posts) if hot_posts else 0:.0f}
        - Posts texte: {sum(1 for p in hot_posts if p['is_self'])} / {len(hot_posts)}
        
        Exemples de titres populaires:
        {chr(10).join([f"- {p['title'][:80]}..." for p in hot_posts[:3]]) if hot_posts else "Aucun post disponible"}
        """
        
        logger.info(f"Analyse terminée pour r/{subreddit}")
        return analysis
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse: {str(e)}")
        raise

@tool
@backoff.on_exception(backoff.expo, praw.exceptions.RedditAPIException, max_tries=3)
@rate_limit(calls=30, period=60)
def comment_on_post(post_url: str, comment_text: str, 
                   parent_comment_id: Optional[str] = None) -> str:
    """
    Ajoute un commentaire à un post Reddit existant.

    Args:
        post_url: URL complète du post Reddit à commenter
        comment_text: Texte du commentaire à publier
        parent_comment_id: ID du commentaire parent si c'est une réponse
    """
    try:
        # Extraire l'ID du post depuis l'URL
        submission_id = _extract_submission_id(post_url)
        if not submission_id:
            raise ValueError("Impossible d'extraire l'ID du post depuis l'URL")
        
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD
        )
        
        # Récupérer le post
        submission = reddit.submission(id=submission_id)
        
        # Si c'est une réponse à un commentaire
        if parent_comment_id:
            parent_comment = reddit.comment(id=parent_comment_id)
            comment = parent_comment.reply(comment_text)
        else:
            comment = submission.reply(comment_text)
        
        logger.info(f"Commentaire publié avec succès sur {post_url}")
        return f"Commentaire publié avec succès! URL: https://reddit.com{comment.permalink}"
        
    except Exception as e:
        logger.error(f"Erreur lors de la publication du commentaire: {str(e)}")
        raise

def _extract_submission_id(url: str) -> Optional[str]:
    """Extrait l'ID du post depuis une URL Reddit"""
    patterns = [
        r'reddit\.com/r/\w+/comments/([a-zA-Z0-9]+)',
        r'redd\.it/([a-zA-Z0-9]+)',
        r'/comments/([a-zA-Z0-9]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

if __name__ == "__main__":
    # Initialiser l'agent avec les outils
    agent = CodeAgent(
        tools=[publish_post, analyze_subreddit, comment_on_post, DuckDuckGoSearchTool()],
        model=LiteLLMModel(
            model_id="claude-3-5-sonnet-20241022",
            api_key=CLAUDE_API_KEY
        ),
        name="RedditContentAgent",
        description="Un agent qui crée et publie du contenu optimisé sur Reddit"
    )

    # Exemple d'utilisation
    try:
        # Analyse d'un subreddit
        subreddit = "hackathon_HF"
        logger.info(f"Analyse du subreddit r/{subreddit}...")
        analysis = agent.run(f"Analyse le subreddit r/{subreddit} et ses tendances")
        logger.info(f"Analyse: {analysis}")

        # Création et publication d'un post
        suggestion = "les agents IA dans l'immobilier"
        logger.info("Création et publication du post...")
        result = agent.run(f"Crée et publie un post sur r/{subreddit} à propos de : {suggestion}")
        logger.info(f"Résultat: {result}")

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution: {str(e)}")
        raise
