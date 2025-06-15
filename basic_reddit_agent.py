import praw
import json
from typing import Dict, List, Optional, Any
from smolagents import CodeAgent, DuckDuckGoSearchTool, LiteLLMModel
from smolagents.tools import Tool
import re
import time
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import logging
from functools import wraps
import backoff

# Configuration du logging
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

class RedditPublisherTool(Tool):
    """Outil pour publier sur Reddit avec gestion des erreurs et rate limiting"""
    
    name = "reddit_publisher"
    description = "Publie un post sur Reddit dans un subreddit spécifique"
    inputs = {
        "title": {"type": "string", "description": "Titre du post Reddit"},
        "content": {"type": "string", "description": "Contenu du post"},
        "subreddit": {"type": "string", "description": "Nom du subreddit (sans r/)"},
        "post_type": {"type": "string", "description": "Type de post: 'text' ou 'link'", "nullable": True},
        "url": {"type": "string", "description": "URL si c'est un post de type link", "nullable": True}
    }
    output_type = "string"
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str, 
                 username: str, password: str):
        super().__init__()
        self._validate_credentials(client_id, client_secret, user_agent, username, password)
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password
        )
    
    def _validate_credentials(self, client_id: str, client_secret: str, user_agent: str, 
                            username: str, password: str) -> None:
        """Validate Reddit credentials"""
        if not all([client_id, client_secret, user_agent, username, password]):
            raise ValueError("Tous les credentials Reddit sont requis")
    
    @backoff.on_exception(backoff.expo, praw.exceptions.RedditAPIException, max_tries=3)
    @rate_limit(calls=30, period=60)  # 30 appels par minute
    def forward(self, title: str, content: str, subreddit: str, 
                post_type: Optional[str] = None, url: Optional[str] = None) -> str:
        """Publie un post sur Reddit avec gestion des erreurs et retries"""
        try:
            self._validate_inputs(title, content, subreddit, post_type, url)
            sub = self.reddit.subreddit(subreddit)
            
            if post_type is None:
                post_type = "text"
            
            if post_type == "text":
                submission = sub.submit(title=title, selftext=content)
            elif post_type == "link":
                if not url:
                    raise ValueError("URL requise pour un post de type link")
                submission = sub.submit(title=title, url=url)
            else:
                raise ValueError("Type de post invalide (text ou link)")
            
            logger.info(f"Post publié avec succès dans r/{subreddit}")
            return f"Post publié avec succès! URL: https://reddit.com{submission.permalink}"
            
        except Exception as e:
            logger.error(f"Erreur lors de la publication: {str(e)}")
            raise
    
    def _validate_inputs(self, title: str, content: str, subreddit: str, 
                        post_type: Optional[str], url: Optional[str]) -> None:
        """Validate input parameters"""
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

class RedditAnalyzerTool(Tool):
    """Outil pour analyser les règles et tendances d'un subreddit avec rate limiting"""
    
    name = "reddit_analyzer"
    description = "Analyse les règles et tendances d'un subreddit pour optimiser le post"
    inputs = {
        "subreddit": {"type": "string", "description": "Nom du subreddit à analyser"}
    }
    output_type = "string"
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str, 
                 username: str, password: str):
        super().__init__()
        self._validate_credentials(client_id, client_secret, user_agent, username, password)
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password
        )
    
    def _validate_credentials(self, client_id: str, client_secret: str, user_agent: str, 
                            username: str, password: str) -> None:
        """Validate Reddit credentials"""
        if not all([client_id, client_secret, user_agent, username, password]):
            raise ValueError("Tous les credentials Reddit sont requis")
    
    @backoff.on_exception(backoff.expo, praw.exceptions.RedditAPIException, max_tries=3)
    @rate_limit(calls=30, period=60)
    def forward(self, subreddit: str) -> str:
        """Analyse un subreddit avec gestion des erreurs et retries"""
        try:
            if not subreddit:
                raise ValueError("Le nom du subreddit est requis")
                
            sub = self.reddit.subreddit(subreddit)
            
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

class RedditCommenterTool(Tool):
    """Outil pour commenter des posts Reddit"""
    
    name = "reddit_commenter"
    description = "Ajoute un commentaire à un post Reddit existant"
    inputs = {
        "post_url": {"type": "string", "description": "URL complète du post Reddit à commenter"},
        "comment_text": {"type": "string", "description": "Texte du commentaire à publier"},
        "parent_comment_id": {"type": "string", "description": "ID du commentaire parent si c'est une réponse", "nullable": True}
    }
    output_type = "string"
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str, 
                 username: str, password: str):
        super().__init__()
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password
        )
    def _validate_credentials(self, client_id: str, client_secret: str, user_agent: str, 
                            username: str, password: str) -> None:
        """Validate Reddit credentials"""
        if not all([client_id, client_secret, user_agent, username, password]):
            raise ValueError("Tous les credentials Reddit sont requis")
    
    @backoff.on_exception(backoff.expo, praw.exceptions.RedditAPIException, max_tries=3)
    @rate_limit(calls=30, period=60)  # 30 appels par minute

    def forward(self, post_url: str, comment_text: str, 
                parent_comment_id: Optional[str] = None) -> str:
        try:
            # Extraire l'ID du post depuis l'URL
            submission_id = self._extract_submission_id(post_url)
            if not submission_id:
                return "Erreur: Impossible d'extraire l'ID du post depuis l'URL"
            
            # Récupérer le post
            submission = self.reddit.submission(id=submission_id)
            
            # Si c'est une réponse à un commentaire
            if parent_comment_id:
                try:
                    parent_comment = self.reddit.comment(id=parent_comment_id)
                    comment = parent_comment.reply(comment_text)
                    return f"Réponse publiée avec succès! URL: https://reddit.com{comment.permalink}"
                except Exception as e:
                    return f"Erreur lors de la réponse au commentaire: {str(e)}"
            
            # Sinon, commenter directement le post
            else:
                comment = submission.reply(comment_text)
                return f"Commentaire publié avec succès! URL: https://reddit.com{comment.permalink}"
            
        except Exception as e:
            return f"Erreur lors de la publication du commentaire: {str(e)}"
    
    def _extract_submission_id(self, url: str) -> Optional[str]:
        """Extrait l'ID du post depuis une URL Reddit"""
        # Patterns pour différents formats d'URL Reddit
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

class RedditPostReaderTool(Tool):
    """Outil pour lire et analyser un post Reddit existant"""
    
    name = "reddit_post_reader"
    description = "Lit un post Reddit et ses commentaires pour analyse"
    inputs = {
        "post_url": {"type": "string", "description": "URL complète du post Reddit à analyser"},
        "max_comments": {"type": "integer", "description": "Nombre maximum de commentaires à récupérer", "nullable": True}
    }
    output_type = "string"
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str, 
                 username: str, password: str):
        super().__init__()
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password
        )
    def _validate_credentials(self, client_id: str, client_secret: str, user_agent: str, 
                            username: str, password: str) -> None:
        """Validate Reddit credentials"""
        if not all([client_id, client_secret, user_agent, username, password]):
            raise ValueError("Tous les credentials Reddit sont requis")
    
    @backoff.on_exception(backoff.expo, praw.exceptions.RedditAPIException, max_tries=3)
    @rate_limit(calls=30, period=60)  # 30 appels par minute
    
    def forward(self, post_url: str, max_comments: Optional[int] = 10) -> str:
        try:
            # Extraire l'ID du post
            submission_id = self._extract_submission_id(post_url)
            if not submission_id:
                return "Erreur: Impossible d'extraire l'ID du post depuis l'URL"
            
            # Récupérer le post
            submission = self.reddit.submission(id=submission_id)
            
            # Informations du post
            post_info = f"""
            Post: {submission.title}
            Auteur: u/{submission.author.name if submission.author else '[deleted]'}
            Subreddit: r/{submission.subreddit.display_name}
            Score: {submission.score}
            Nombre de commentaires: {submission.num_comments}
            Créé: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(submission.created_utc))}
            
            Contenu:
            {submission.selftext if submission.is_self else f'Lien: {submission.url}'}
            
            Commentaires populaires:
            """
            
            # Récupérer les commentaires
            submission.comments.replace_more(limit=0)  # Charger tous les commentaires
            comments_info = []
            
            for i, comment in enumerate(submission.comments[:max_comments]):
                if hasattr(comment, 'body'):  # Vérifier que c'est bien un commentaire
                    comment_text = comment.body[:200] + "..." if len(comment.body) > 200 else comment.body
                    comments_info.append(f"""
                    {i+1}. u/{comment.author.name if comment.author else '[deleted]'} (Score: {comment.score})
                       ID: {comment.id}
                       {comment_text}
                    """)
            
            return post_info + "\n".join(comments_info)
            
        except Exception as e:
            return f"Erreur lors de la lecture du post: {str(e)}"
    
    def _extract_submission_id(self, url: str) -> Optional[str]:
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

class RedditAgent:
    """Agent principal pour créer, publier et commenter des posts Reddit"""
    
    def __init__(self, reddit_credentials: Dict[str, str], claude_api_key: str):
        self._validate_credentials(reddit_credentials, claude_api_key)
        
        # Initialiser le modèle Claude
        self.model = LiteLLMModel(
            model_id="claude-3-5-sonnet-20241022",
            api_key=claude_api_key
        )
        
        # Initialiser les outils
        self.reddit_publisher = RedditPublisherTool(**reddit_credentials)
        self.reddit_analyzer = RedditAnalyzerTool(**reddit_credentials)
        self.reddit_commenter = RedditCommenterTool(**reddit_credentials)
        self.reddit_post_reader = RedditPostReaderTool(**reddit_credentials)
        self.search_tool = DuckDuckGoSearchTool()
        
        # Initialiser l'agent avec tous les outils
        self.agent = CodeAgent(
            tools=[
                self.reddit_publisher, 
                self.reddit_analyzer, 
                self.reddit_commenter,
                self.reddit_post_reader,
                self.search_tool
            ],
            model=self.model,
            max_steps=10
        )
    
    def _validate_credentials(self, reddit_credentials: Dict[str, str], claude_api_key: str) -> None:
        """Validate all required credentials"""
        required_reddit_fields = ["client_id", "client_secret", "user_agent", "username", "password"]
        for field in required_reddit_fields:
            if field not in reddit_credentials or not reddit_credentials[field]:
                raise ValueError(f"Credential Reddit manquant: {field}")
        
        if not claude_api_key:
            raise ValueError("Clé API Claude requise")
    
    def create_and_publish_post(self, suggestion: str, target_subreddit: str) -> str:
        """Crée et publie un post Reddit basé sur une suggestion"""
        try:
            if not suggestion or not target_subreddit:
                raise ValueError("La suggestion et le subreddit sont requis")
            
            prompt = f"""
            Tu es un expert en création de contenu Reddit. Tu dois :
            
            1. Analyser le subreddit r/{target_subreddit} pour comprendre ses règles et tendances
            2. Transformer cette suggestion en un post Reddit optimisé : "{suggestion}"
            3. Publier le post sur Reddit
            
            Étapes à suivre :
            - Utilise reddit_analyzer pour analyser r/{target_subreddit}
            - Si nécessaire, utilise duckduckgo_search pour enrichir le contenu
            - Crée un titre accrocheur et un contenu adapté au subreddit
            - Vérifie que le post respecte les règles du subreddit
            - Publie le post avec reddit_publisher
            
            Assure-toi que :
            - Le titre est engageant et suit les conventions du subreddit
            - Le contenu est informatif et respecte les règles
            - Le format est adapté (text ou link selon le cas)
            """
            
            result = self.agent.run(prompt)
            logger.info(f"Post créé et publié dans r/{target_subreddit}")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la création/publication du post: {str(e)}")
            raise

def main():
    # Charger les variables d'environnement
    load_dotenv()
    
    # Configuration Reddit depuis les variables d'environnement
    reddit_config = {
        "client_id": os.getenv("REDDIT_CLIENT_ID"),
        "client_secret": os.getenv("REDDIT_CLIENT_SECRET"),
        "user_agent": os.getenv("REDDIT_USER_AGENT"),
        "username": os.getenv("REDDIT_USERNAME"),
        "password": os.getenv("REDDIT_PASSWORD")
    }
    
    # Clé API Claude depuis les variables d'environnement
    claude_api_key = os.getenv("CLAUDE_API_KEY")
    
    try:
        # Initialiser l'agent
        agent = RedditAgent(reddit_config, claude_api_key)
        
        # Exemple d'utilisation
        suggestion = "les agents IA dans l'immobilier"
        subreddit = "hackathon_HF"
        
        logger.info("Création et publication du post...")
        result = agent.create_and_publish_post(suggestion, subreddit)
        logger.info(f"Résultat: {result}")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
