class ToolError(Exception):
    """Raised when a tool encounters an error."""

    def __init__(self, message):
        self.message = message


class LLMEngineError(Exception):
    """Base exception for all LLM Engine errors"""


class TokenLimitExceeded(LLMEngineError):
    """Exception raised when the token limit is exceeded"""