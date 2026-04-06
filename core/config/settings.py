# core/config/settings.py
"""
Configuration centralisée pour la plateforme GlueTrade
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Charger les variables d'environnement
load_dotenv()

# Chemins du projet
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
SOURCES_DIR = DATA_DIR / "sources"

# Créer les répertoires s'ils n'existent pas
for directory in [DATA_DIR, LOGS_DIR, SOURCES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

class Config:
    """Configuration de base"""
    
    # Bot Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TOKEN')
    TELEGRAM_CHANNEL_ID = os.getenv('CHAT_ID')
    
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # APIs externes
    COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY', '')
    ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', '')
    
    # Base de données
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/gluetrade.db')
    
    # Configuration des services
    CRYPTO_UPDATE_INTERVAL = int(os.getenv('CRYPTO_UPDATE_INTERVAL', '300'))  # 5 minutes
    OPPORTUNITIES_UPDATE_INTERVAL = int(os.getenv('OPPORTUNITIES_UPDATE_INTERVAL', '3600'))  # 1 heure
    MARKET_ANALYSIS_INTERVAL = int(os.getenv('MARKET_ANALYSIS_INTERVAL', '1800'))  # 30 minutes
    
    # Seuils et paramètres
    MIN_CONFIDENCE_LEVEL = float(os.getenv('MIN_CONFIDENCE_LEVEL', '80.0'))
    MAX_OPPORTUNITIES = int(os.getenv('MAX_OPPORTUNITIES', '5'))
    
    # Notification
    ENABLE_CHANNEL_POSTS = os.getenv('ENABLE_CHANNEL_POSTS', 'true').lower() == 'true'
    ENABLE_ALERTS = os.getenv('ENABLE_ALERTS', 'true').lower() == 'true'
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = LOGS_DIR / "gluetrade.log"
    
    # Cache
    CACHE_DURATION = int(os.getenv('CACHE_DURATION', '3600'))  # 1 heure
    
    # Sécurité
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
    
    @classmethod
    def validate(cls):
        """Valide la configuration"""
        required_vars = [
            'TELEGRAM_TOKEN',
            'TELEGRAM_CHANNEL_ID',
            'OPENAI_API_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing_vars)}")
        
        return True

class DevelopmentConfig(Config):
    """Configuration développement"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """Configuration production"""
    DEBUG = False
    LOG_LEVEL = 'WARNING'

class TestingConfig(Config):
    """Configuration tests"""
    TESTING = True
    DATABASE_URL = 'sqlite:///:memory:'

# Configuration par défaut
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """Retourne la configuration appropriée"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    return config.get(config_name, config['default'])

# Instance globale de configuration
settings = get_config()

# Alias pour compatibilité
Config = settings 