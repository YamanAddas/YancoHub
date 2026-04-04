"""
YancoHub CatByte AI — OpenClaw integration for the CatByte gaming companion.
"""

import json
import logging
import requests
from pathlib import Path

logger = logging.getLogger('yancohub.catbyte')

OPENCLAW_PORT = 18789
OPENCLAW_URL = f"http://127.0.0.1:{OPENCLAW_PORT}"


class CatByte:
    def __init__(self):
        self._auth_token = None
        self._offline_until = 0
        self._load_auth_token()

    def _load_auth_token(self):
        """Load OpenClaw auth token from config."""
        config_paths = [
            Path.home() / ".openclaw" / "openclaw.json",
            Path(r"C:\Users") / Path.home().name / ".openclaw" / "openclaw.json",
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    self._auth_token = config.get('token', '')
                    logger.info(f"Loaded OpenClaw token from {config_path}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load OpenClaw config: {e}")

        logger.info("No OpenClaw config found — CatByte will be offline")

    def check_status(self):
        """Check if OpenClaw gateway is reachable."""
        import time
        if time.time() < self._offline_until:
            return {'status': 'offline', 'message': 'CatByte is resting (cooldown)'}

        try:
            headers = {}
            if self._auth_token:
                headers['Authorization'] = f'Bearer {self._auth_token}'

            resp = requests.get(f"{OPENCLAW_URL}/health", headers=headers, timeout=3)
            if resp.status_code == 200:
                return {'status': 'online', 'message': 'CatByte is ready!'}
            return {'status': 'offline', 'message': f'Gateway returned {resp.status_code}'}
        except requests.ConnectionError:
            return {'status': 'offline', 'message': 'OpenClaw gateway not running'}
        except Exception as e:
            return {'status': 'offline', 'message': str(e)}

    def chat(self, message, game_context=None, history=None):
        """Send a chat message to CatByte via OpenClaw."""
        import time
        if time.time() < self._offline_until:
            return {
                'response': "😺 CatByte is taking a catnap... try again in a moment!",
                'status': 'offline'
            }

        try:
            headers = {'Content-Type': 'application/json'}
            if self._auth_token:
                headers['Authorization'] = f'Bearer {self._auth_token}'

            # Build system message with game context
            system_parts = []
            if game_context:
                system_parts.append(f"The user is currently in: {game_context}")

            payload = {
                'message': message,
                'history': history or [],
            }
            if system_parts:
                payload['system'] = ' '.join(system_parts)

            resp = requests.post(
                f"{OPENCLAW_URL}/v1/chat",
                headers=headers,
                json=payload,
                timeout=30
            )

            if resp.status_code == 200:
                data = resp.json()
                return {
                    'response': data.get('response', data.get('message', '')),
                    'status': 'online'
                }
            else:
                logger.warning(f"CatByte chat error: {resp.status_code}")
                self._offline_until = time.time() + 30
                return {
                    'response': "😿 CatByte got distracted by a laser pointer... try again!",
                    'status': 'error'
                }

        except requests.ConnectionError:
            import time as t
            self._offline_until = t.time() + 30
            return {
                'response': "😺 CatByte is offline. Make sure OpenClaw is running!",
                'status': 'offline'
            }
        except Exception as e:
            logger.error(f"CatByte chat error: {e}")
            return {
                'response': "😿 Something went wrong with CatByte...",
                'status': 'error'
            }

    def chat_vision(self, message, image_base64, game_context=None, history=None):
        """Send a chat message with a screenshot to CatByte."""
        import time
        if time.time() < self._offline_until:
            return {
                'response': "😺 CatByte is taking a catnap...",
                'status': 'offline'
            }

        try:
            headers = {'Content-Type': 'application/json'}
            if self._auth_token:
                headers['Authorization'] = f'Bearer {self._auth_token}'

            payload = {
                'message': message,
                'image': image_base64,
                'history': history or [],
            }
            if game_context:
                payload['system'] = f"The user is currently in: {game_context}"

            resp = requests.post(
                f"{OPENCLAW_URL}/v1/chat-vision",
                headers=headers,
                json=payload,
                timeout=45
            )

            if resp.status_code == 200:
                data = resp.json()
                return {
                    'response': data.get('response', data.get('message', '')),
                    'status': 'online'
                }
            else:
                self._offline_until = time.time() + 30
                return {
                    'response': "😿 CatByte couldn't analyze the screenshot...",
                    'status': 'error'
                }
        except Exception as e:
            logger.error(f"CatByte vision error: {e}")
            self._offline_until = time.time() + 30
            return {
                'response': "😿 Vision failed...",
                'status': 'error'
            }
