"""Retry utilities for handling transient failures."""

import functools
import random
import time
from collections.abc import Callable
from typing import TypeVar

from premiere.utils.logger import get_logger

T = TypeVar("T")


class RetryError(Exception):
    """Error raised when all retry attempts fail."""

    def __init__(self, message: str, last_exception: Exception | None = None):
        super().__init__(message)
        self.last_exception = last_exception


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying functions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including initial).
        initial_delay: Initial delay in seconds between retries.
        max_delay: Maximum delay in seconds between retries.
        exponential_base: Base for exponential backoff calculation.
        jitter: Whether to add random jitter to delays.
        retryable_exceptions: Tuple of exception types that should trigger retry.
        on_retry: Optional callback called on each retry with (exception, attempt).

    Returns:
        Decorated function with retry logic.

    Example:
        @retry(max_attempts=3, initial_delay=1.0)
        def fetch_data():
            return api.get("/data")
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            logger = get_logger()
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise RetryError(
                            f"Failed after {max_attempts} attempts: {e}",
                            last_exception=e,
                        ) from e

                    # Calculate delay with exponential backoff
                    delay = min(
                        initial_delay * (exponential_base ** (attempt - 1)),
                        max_delay,
                    )

                    # Add jitter if enabled
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    time.sleep(delay)

            # This should never be reached, but just in case
            raise RetryError(
                f"Failed after {max_attempts} attempts",
                last_exception=last_exception,
            )

        return wrapper

    return decorator


def retry_on_network_error(
    max_attempts: int = 4,
    initial_delay: float = 2.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying functions on network errors.

    Uses exponential backoff: 2s, 4s, 8s, 16s.

    Args:
        max_attempts: Maximum number of attempts.
        initial_delay: Initial delay in seconds.

    Returns:
        Decorated function with retry logic for network errors.
    """
    import socket
    import urllib.error

    # Common network-related exceptions
    network_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        socket.timeout,
        urllib.error.URLError,
        OSError,
    )

    # Try to add httpx/requests exceptions if available
    try:
        import httpx

        network_exceptions = (*network_exceptions, httpx.NetworkError, httpx.TimeoutException)
    except ImportError:
        pass

    try:
        import requests

        network_exceptions = (
            *network_exceptions,
            requests.ConnectionError,
            requests.Timeout,
        )
    except ImportError:
        pass

    return retry(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        exponential_base=2.0,
        retryable_exceptions=network_exceptions,
    )


def retry_on_ffmpeg_error(
    max_attempts: int = 2,
    initial_delay: float = 1.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying FFmpeg operations.

    Some FFmpeg operations can fail due to temporary file access issues
    or resource contention.

    Args:
        max_attempts: Maximum number of attempts.
        initial_delay: Initial delay in seconds.

    Returns:
        Decorated function with retry logic for FFmpeg errors.
    """
    from premiere.utils.ffmpeg import FFmpegError

    return retry(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        exponential_base=2.0,
        retryable_exceptions=(FFmpegError, OSError, PermissionError),
    )


class RetryContext:
    """Context manager for retry logic with manual control.

    Example:
        with RetryContext(max_attempts=3) as ctx:
            for attempt in ctx:
                try:
                    result = risky_operation()
                    break
                except SomeError as e:
                    ctx.record_failure(e)
    """

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.attempt = 0
        self.last_exception: Exception | None = None
        self._failed = False

    def __enter__(self) -> "RetryContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __iter__(self):
        return self

    def __next__(self) -> int:
        if self.attempt >= self.max_attempts:
            if self._failed:
                raise RetryError(
                    f"Failed after {self.max_attempts} attempts",
                    last_exception=self.last_exception,
                )
            raise StopIteration

        if self.attempt > 0 and self._failed:
            delay = min(
                self.initial_delay * (self.exponential_base ** (self.attempt - 1)),
                self.max_delay,
            )
            delay = delay * (0.5 + random.random())  # Add jitter
            time.sleep(delay)

        self.attempt += 1
        self._failed = False
        return self.attempt

    def record_failure(self, exception: Exception) -> None:
        """Record a failure for the current attempt."""
        self.last_exception = exception
        self._failed = True
        get_logger().warning(
            f"Attempt {self.attempt}/{self.max_attempts} failed: {exception}"
        )
