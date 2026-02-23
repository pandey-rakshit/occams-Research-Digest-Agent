import os 
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _validate_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {var_name}")
    return value

@dataclass(frozen=True)
class AppSettings:
    pass


settings = AppSettings()