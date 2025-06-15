import praw
import json
from typing import Dict, List, Optional
from smolagents import CodeAgent, DuckDuckGoSearchTool, LiteLLMModel
from smolagents.tools import Tool
import re
import time

class RedditPublisherTool(Tool):
    """Outil pour publier sur Reddit"""
    
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
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=username,
            password=password
        )
    
    def forward(self, title: str, content: str, subreddit: str, 
                post_type: Optional[str] = None, url: Optional[str] = None) -> str:
        try:
            sub = self.reddit.subreddit(subreddit)
            
            # Valeur par défaut si post_type n'est pas fourni
            if post_type is None:
                post_type = "text"
            
            if post_type == "text":
                submission = sub.submit(title=title, selftext=content)
            elif post_type == "link":
                if not url:
                    return "Erreur: URL requise pour un post de type link"
                submission = sub.submit(title=title, url=url)
            else:
                return "Erreur: Type de post invalide (text ou link)"
            
            return f"Post publié avec succès! URL: https://reddit.com{submission.permalink}"
            
        except Exception as e:
            return f"Erreur lors de la publication: {str(e)}"

class RedditAnalyzerTool(Tool):
    """Outil pour analyser les règles et tendances d'un subreddit"""
    
    name = "reddit_analyzer"
    description = "Analyse les règles et tendances d'un subreddit pour optimiser le post"
    inputs = {
        "subreddit": {"type": "string", "description": "Nom du subreddit à analyser"}
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
    
    def forward(self, subreddit: str) -> str:
        try:
            sub = self.reddit.subreddit(subreddit)
            
            # Récupérer les règles
            rules = []
            try:
                for rule in sub.rules:
                    rules.append(f"- {rule.short_name}: {rule.description}")
            except:
                rules = ["Règles non accessibles"]
            
            # Analyser les posts populaires récents
            hot_posts = []
            for post in sub.hot(limit=10):
                hot_posts.append({
                    "title": post.title,
                    "score": post.score,
                    "num_comments": post.num_comments,
                    "is_self": post.is_self
                })
            
            analysis = f"""
            Analyse du subreddit r/{subreddit}:
            
            Règles principales:
            {chr(10).join(rules)}
            
            Tendances des posts populaires:
            - Score moyen: {sum(p['score'] for p in hot_posts) / len(hot_posts):.0f}
            - Commentaires moyens: {sum(p['num_comments'] for p in hot_posts) / len(hot_posts):.0f}
            - Posts texte: {sum(1 for p in hot_posts if p['is_self'])} / {len(hot_posts)}
            
            Exemples de titres populaires:
            {chr(10).join([f"- {p['title'][:80]}..." for p in hot_posts[:3]])}
            """
            
            return analysis
            
        except Exception as e:
            return f"Erreur lors de l'analyse: {str(e)}"

class RedditAgent:
    """Agent principal pour créer et publier des posts Reddit"""
    
    def __init__(self, reddit_credentials: Dict[str, str], claude_api_key: str):
        # Initialiser le modèle Claude
        self.model = LiteLLMModel(
            model_id="claude-3-5-sonnet-20241022",
            api_key=claude_api_key
        )
        
        # Initialiser les outils
        self.reddit_publisher = RedditPublisherTool(**reddit_credentials)
        self.reddit_analyzer = RedditAnalyzerTool(**reddit_credentials)
        self.search_tool = DuckDuckGoSearchTool()
        
        # Initialiser l'agent
        self.agent = CodeAgent(
            tools=[self.reddit_publisher, self.reddit_analyzer, self.search_tool],
            model=self.model,
            max_steps=10
        )
    
    def create_and_publish_post(self, suggestion: str, target_subreddit: str) -> str:
        """
        Crée et publie un post Reddit basé sur une suggestion
        """
        
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
        
        try:
            result = self.agent.run(prompt)
            return result
        except Exception as e:
            return f"Erreur lors de l'exécution de l'agent: {str(e)}"

# Configuration et utilisation
def main():
    # Configuration Reddit (à remplir avec vos credentials)
    reddit_config = {
        "client_id": ...,
        "client_secret": ..., 
        "user_agent": "RedditAgent/1.0",
        "username": ...,
        "password": ...
    }
    
    # Clé API Claude
    claude_api_key = ...
    
    # Initialiser l'agent
    agent = RedditAgent(reddit_config, claude_api_key)
    
    # Exemple d'utilisation
    suggestion = "les agents IA dans l'industrie du jeu vidéo"
    subreddit = "hackathon_HF"
    
    print("Création et publication du post...")
    result = agent.create_and_publish_post(suggestion, subreddit)
    print(f"Résultat: {result}")

if __name__ == "__main__":
    main()
