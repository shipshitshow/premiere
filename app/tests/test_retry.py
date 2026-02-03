"""Tests for retry utilities."""

import time
from unittest.mock import MagicMock, patch

import pytest

from premiere.utils.retry import (
    RetryContext,
    RetryError,
    retry,
    retry_on_ffmpeg_error,
    retry_on_network_error,
)


class TestRetryDecorator:
    """Tests for the retry decorator."""

    def test_retry_succeeds_first_attempt(self):
        """Test that successful function doesn't retry."""
        call_count = 0

        @retry(max_attempts=3)
        def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = always_succeeds()
        assert result == "success"
        assert call_count == 1

    def test_retry_succeeds_after_failures(self):
        """Test that retry eventually succeeds."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = fails_twice()
        assert result == "success"
        assert call_count == 3

    def test_retry_raises_after_max_attempts(self):
        """Test that RetryError is raised after max attempts."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(RetryError) as exc_info:
            always_fails()

        assert call_count == 3
        assert "Failed after 3 attempts" in str(exc_info.value)
        assert isinstance(exc_info.value.last_exception, ValueError)

    def test_retry_only_catches_specified_exceptions(self):
        """Test that only specified exceptions trigger retry."""
        call_count = 0

        @retry(max_attempts=3, retryable_exceptions=(ValueError,), initial_delay=0.01)
        def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retryable")

        with pytest.raises(TypeError):
            raises_type_error()

        assert call_count == 1  # Should not retry

    def test_retry_calls_on_retry_callback(self):
        """Test that on_retry callback is called on each retry."""
        retries = []

        def on_retry_callback(exc, attempt):
            retries.append((str(exc), attempt))

        @retry(max_attempts=3, initial_delay=0.01, on_retry=on_retry_callback)
        def fails_twice():
            if len(retries) < 2:
                raise ValueError("Failure")
            return "success"

        result = fails_twice()
        assert result == "success"
        assert len(retries) == 2
        assert retries[0][1] == 1
        assert retries[1][1] == 2

    def test_retry_exponential_backoff(self):
        """Test that delay increases exponentially."""
        delays = []
        original_sleep = time.sleep

        def mock_sleep(duration):
            delays.append(duration)
            # Don't actually sleep in tests

        call_count = 0

        @retry(
            max_attempts=4,
            initial_delay=1.0,
            exponential_base=2.0,
            jitter=False,
        )
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Fail")

        with patch("time.sleep", mock_sleep):
            with pytest.raises(RetryError):
                always_fails()

        # Delays should be: 1, 2, 4 (no delay before first attempt or after last)
        assert len(delays) == 3
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0

    def test_retry_respects_max_delay(self):
        """Test that delay is capped at max_delay."""
        delays = []

        @retry(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=3.0,
            exponential_base=2.0,
            jitter=False,
        )
        def always_fails():
            raise ValueError("Fail")

        with patch("time.sleep", lambda d: delays.append(d)):
            with pytest.raises(RetryError):
                always_fails()

        # Delays should be capped at 3.0
        assert all(d <= 3.0 for d in delays)


class TestRetryOnNetworkError:
    """Tests for retry_on_network_error decorator."""

    def test_retries_on_connection_error(self):
        """Test that ConnectionError triggers retry."""
        call_count = 0

        @retry_on_network_error(max_attempts=2, initial_delay=0.01)
        def network_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Network down")
            return "success"

        result = network_call()
        assert result == "success"
        assert call_count == 2

    def test_retries_on_timeout(self):
        """Test that TimeoutError triggers retry."""
        call_count = 0

        @retry_on_network_error(max_attempts=2, initial_delay=0.01)
        def timeout_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Connection timed out")
            return "success"

        result = timeout_call()
        assert result == "success"


class TestRetryOnFfmpegError:
    """Tests for retry_on_ffmpeg_error decorator."""

    def test_retries_on_ffmpeg_error(self):
        """Test that FFmpegError triggers retry."""
        from premiere.utils.ffmpeg import FFmpegError

        call_count = 0

        @retry_on_ffmpeg_error(max_attempts=2, initial_delay=0.01)
        def ffmpeg_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise FFmpegError("FFmpeg failed")
            return "success"

        result = ffmpeg_call()
        assert result == "success"
        assert call_count == 2


class TestRetryContext:
    """Tests for RetryContext class."""

    def test_context_succeeds_first_attempt(self):
        """Test context manager succeeds on first attempt."""
        attempts = 0
        with RetryContext(max_attempts=3) as ctx:
            for attempt in ctx:
                attempts = attempt
                break  # Success on first attempt

        assert attempts == 1

    def test_context_retries_on_failure(self):
        """Test context manager retries after recorded failure."""
        attempts = []

        with RetryContext(max_attempts=3, initial_delay=0.01) as ctx:
            for attempt in ctx:
                attempts.append(attempt)
                if attempt < 3:
                    ctx.record_failure(ValueError("Fail"))
                else:
                    break

        assert attempts == [1, 2, 3]

    def test_context_raises_after_max_attempts(self):
        """Test context manager raises RetryError after max attempts."""
        with pytest.raises(RetryError):
            with RetryContext(max_attempts=2, initial_delay=0.01) as ctx:
                for attempt in ctx:
                    ctx.record_failure(ValueError("Always fails"))

    def test_context_preserves_last_exception(self):
        """Test that last exception is preserved."""
        try:
            with RetryContext(max_attempts=2, initial_delay=0.01) as ctx:
                for attempt in ctx:
                    ctx.record_failure(ValueError(f"Failure {attempt}"))
        except RetryError as e:
            assert "Failure 2" in str(e.last_exception)


class TestRetryError:
    """Tests for RetryError exception."""

    def test_error_message(self):
        """Test error message formatting."""
        error = RetryError("Custom message")
        assert str(error) == "Custom message"

    def test_error_with_last_exception(self):
        """Test error preserves last exception."""
        original = ValueError("Original error")
        error = RetryError("Wrapper", last_exception=original)
        assert error.last_exception is original
