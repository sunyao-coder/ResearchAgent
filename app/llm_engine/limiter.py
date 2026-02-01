import asyncio
import random
from typing import Tuple


class ChatLimiter:
    """
    A class to limit the number of concurrent chat requests and introduce a delay between requests.
    This is useful for preventing overwhelming the server and avoiding being blocked.
    """

    def __init__(self, concurrency: int, delay_range: Tuple[float, float]) -> None:
        """
        Args:
            concurrency (int): The maximum number of concurrent chat requests.
            delay_range (Tuple[float, float]): The range of delay in seconds between requests.
        """
        self.semaphore = asyncio.Semaphore(concurrency)
        self.delay_range = delay_range
        self.lock = asyncio.Lock()

    async def wait(self):
        """
        Wait for the semaphore and introduce a random delay.
        This method should be called before making a chat request to ensure that the rate limit is respected.
        """
        async with self.lock:
            delay = random.uniform(*self.delay_range)
            await asyncio.sleep(delay)


_chat_limiter_instance: ChatLimiter = None


def get_chat_limiter() -> ChatLimiter:
    """
    Get the current instance of the ChatLimiter.
    If it has not been initialized, create a new instance.

    Returns:
        ChatLimiter: The current instance of the ChatLimiter.
    """
    global _chat_limiter_instance
    if _chat_limiter_instance is None:
        # Default values can be adjusted as needed
        _chat_limiter_instance = ChatLimiter(concurrency=10, delay_range=(0.5, 2.0))
    return _chat_limiter_instance
