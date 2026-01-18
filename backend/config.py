import json
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

class GameConfig:
    """游戏配置"""
    def __init__(self):
        config_path = Path(__file__).parent.parent / "data" / "config" / "game_config.json"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.EXP_MULTIPLIER = config.get("exp_multiplier", 1.0)
                self.DROP_RATE_MULTIPLIER = config.get("drop_rate_multiplier", 1.0)
                self.GOLD_MULTIPLIER = config.get("gold_multiplier", 1.0)
        except Exception as e:
            print(f"加载游戏配置失败，使用默认值: {e}")
            self.EXP_MULTIPLIER = 1.0
            self.DROP_RATE_MULTIPLIER = 1.0
            self.GOLD_MULTIPLIER = 1.0

settings = Settings()
game_config = GameConfig()