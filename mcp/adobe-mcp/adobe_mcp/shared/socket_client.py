# MIT License
#
# Copyright (c) 2025 Mike Chambers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import socketio
import time
import threading
import json
from queue import Queue
from . import logger

# Global configuration variables
proxy_url = None
proxy_timeout = None
application = None

# Singleton persistent client
_client = None
_client_lock = threading.Lock()


class AppError(Exception):
    pass


class PersistentSocketClient:
    """Persistent Socket.IO client that connects once and reuses the connection."""

    def __init__(self, url, app):
        self._url = url
        self._app = app
        self._sio = socketio.Client(
            logger=False,
            reconnection=True,
            reconnection_attempts=0,  # unlimited
            reconnection_delay=0.5,
            reconnection_delay_max=5,
        )
        self._send_lock = threading.Lock()
        self._connected = threading.Event()
        self._response_queues = {}  # keyed by socket session id isn't needed; we serialize sends
        self._current_queue = None
        self._bg_thread = None

        self._setup_handlers()

    def _setup_handlers(self):
        @self._sio.event
        def connect():
            logger.log(f"[Persistent] Connected with session ID: {self._sio.sid}")
            self._connected.set()

        @self._sio.event
        def packet_response(data):
            logger.log(f"[Persistent] Received response: {data}")
            q = self._current_queue
            if q is not None:
                q.put(data)

        @self._sio.event
        def disconnect():
            logger.log("[Persistent] Disconnected from server")
            self._connected.clear()
            # Unblock any waiting sender
            q = self._current_queue
            if q is not None and q.empty():
                q.put(None)

        @self._sio.event
        def connect_error(error):
            logger.log(f"[Persistent] Connection error: {error}")
            self._connected.clear()

    def _ensure_connected(self, timeout=10):
        """Connect if not already connected. Returns True if connected."""
        if self._sio.connected:
            return True

        logger.log(f"[Persistent] Connecting to {self._url}...")

        def _run():
            try:
                self._sio.connect(self._url, transports=['websocket'])
                self._sio.wait()
            except Exception as e:
                logger.log(f"[Persistent] Background thread error: {e}")
                self._connected.clear()

        if self._bg_thread is None or not self._bg_thread.is_alive():
            self._bg_thread = threading.Thread(target=_run, daemon=True)
            self._bg_thread.start()

        if not self._connected.wait(timeout=timeout):
            raise RuntimeError(
                f"Error: Could not connect to {self._app} command proxy server. "
                f"Make sure that the proxy server is running listening on the correct url {self._url}."
            )
        return True

    def send(self, command, timeout=None):
        """Send a command and wait for a response. Thread-safe via _send_lock."""
        wait_timeout = timeout if timeout is not None else proxy_timeout or 120

        with self._send_lock:
            self._ensure_connected()

            q = Queue()
            self._current_queue = q

            try:
                logger.log(f"[Persistent] Sending to {self._app}: {command}")
                self._sio.emit('command_packet', {
                    'type': "command",
                    'application': self._app,
                    'command': command
                })

                response = q.get(timeout=wait_timeout)

                if response is None:
                    raise RuntimeError(
                        f"Error: No response from {self._app}. Connection may have dropped."
                    )

                try:
                    logger.log(json.dumps(response))
                except Exception:
                    logger.log(f"Response (not JSON-serializable): {response}")

                if response.get("status") == "FAILURE":
                    raise AppError(f"Error returned from {self._app}: {response['message']}")

                return response

            except AppError:
                raise
            except Exception as e:
                logger.log(f"[Persistent] Error waiting for response: {e}")
                # Force reconnect on next call
                try:
                    if self._sio.connected:
                        self._sio.disconnect()
                except Exception:
                    pass
                self._connected.clear()
                raise RuntimeError(
                    f"Error: Could not connect to {self._app}. Connection Timed Out. "
                    f"Make sure that {self._app} is running and that the MCP Plugin is connected. "
                    f"Original error: {e}"
                )
            finally:
                self._current_queue = None

    def disconnect(self):
        """Explicitly disconnect the persistent client."""
        try:
            if self._sio.connected:
                self._sio.disconnect()
        except Exception:
            pass
        self._connected.clear()


def _get_client():
    """Get or create the singleton persistent client."""
    global _client
    if _client is not None:
        return _client

    with _client_lock:
        if _client is not None:
            return _client

        if not application or not proxy_url:
            raise RuntimeError("Socket client not configured. Call configure() first.")

        _client = PersistentSocketClient(proxy_url, application)
        return _client


def send_message_blocking(command, timeout=None):
    """
    Blocking function that sends a message via the persistent connection,
    waits for a response, then returns it.

    Args:
        command: The command to send
        timeout (int): Maximum time to wait for response in seconds

    Returns:
        dict: The response received from the server, or None if no response
    """
    if not application or not proxy_url or not proxy_timeout:
        logger.log("Socket client not configured. Call configure() first.")
        return None

    client = _get_client()
    return client.send(command, timeout=timeout)


def configure(app=None, url=None, timeout=None):
    global application, proxy_url, proxy_timeout, _client

    if app:
        application = app
    if url:
        proxy_url = url
    if timeout:
        proxy_timeout = timeout

    # Reset singleton if config changes so next call reconnects with new settings
    if _client is not None:
        _client.disconnect()
        _client = None

    logger.log(f"Socket client configured: app={application}, url={proxy_url}, timeout={proxy_timeout}")
