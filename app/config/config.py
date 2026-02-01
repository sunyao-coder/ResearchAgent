import os
import os.path as osp
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings


def get_project_root() -> Path:
    """
    Get the project root directory

    Returns:
        Path: Path object representing the project root
    """
    return Path(__file__).resolve().parent.parent.parent


PROJECT_ROOT = get_project_root()
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


class LLMSettings(BaseModel):
    model_name: str = Field(..., description="Name of the LLM model to use")
    max_tokens: int = Field(
        ..., description="Maximum number of tokens to generate in the response"
    )
    temperature: float = Field(..., description="Sampling temperature for the LLM")
    api_type: str = Field(
        "openai", description="Type of API to use for the LLM (e.g., openai, azure)"
    )
    api_key: str = Field(..., description="API key for accessing the LLM service")
    api_version: str = Field(
        ..., description="Version of the API to use for the LLM service"
    )
    base_url: str = Field(..., description="Base URL for the LLM API")


class GeneralConfig(BaseSettings):
    llm: Dict[str, LLMSettings] = Field(
        default_factory=lambda: {
            "default": LLMSettings(
                model_name="gpt-3.5-turbo",
                max_tokens=1500,
                temperature=0.7,
                api_key="your_api_key_here",
                api_version="2023-05-15",
                base_url="https://api.openai.com/v1",
            )
        },
        description="Settings for the LLM, can contain multiple configurations",
    )

    @classmethod
    def load_from_yaml(cls, file_path: str) -> "GeneralConfig":
        """
        Load configuration from a YAML file.

        Args:
            file_path (str): Path to the YAML configuration file.

        Returns:
            GeneralConfig: An instance of GeneralConfig with loaded settings.
        """

        with open(file_path, "r") as file:
            data = yaml.safe_load(file)
        return cls(**data)


_config_instance: Optional[GeneralConfig] = None


def get_config() -> GeneralConfig:
    """
    Get the current configuration instance.
    Raises:
        RuntimeError: If the configuration has not been initialized.
    Returns:
        GeneralConfig: The current configuration instance.
    """
    global _config_instance
    if _config_instance is None:
        raise RuntimeError(
            "Config has not been initialized. Call `init_config(path)` first."
        )
    return _config_instance


def init_config(path: str) -> None:
    """
    Initialize the configuration from a YAML file.
    Args:
        path (str): Path to the YAML configuration file.
    """
    global _config_instance
    _config_instance = GeneralConfig.load_from_yaml(path)
