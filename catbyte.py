"""
YancoHub CatByte AI — Multi-backend gaming companion.
Supports OpenClaw, Ollama, LM Studio, OpenAI, and custom
OpenAI-compatible endpoints. All backends use /v1/chat/completions.
"""

import json
import logging
import time
import requests
from pathlib import Path
from constants import OPENCLAW_PORT

logger = logging.getLogger('yancohub.catbyte')

# ── Backend Presets ────────────────────────────────────────────────────────────
# Each preset defines defaults that the user can override in settings.
# All use OpenAI-compatible /v1/chat/completions — the universal LLM lingua franca.

BACKEND_PRESETS = {
    'openclaw': {
        'name': 'OpenClaw',
        'description': 'Uses your ChatGPT subscription via OpenClaw gateway',
        'base_url': f'http://127.0.0.1:{OPENCLAW_PORT}',
        'default_model': 'openclaw',  # OpenClaw's default routing alias
        'api_key_required': False,
        'local': True,
        'setup_hint': 'Install OpenClaw: npm install -g @openclaw/cli\n'
                      'Then run: openclaw onboard --auth-choice openai-codex',
    },
    'ollama': {
        'name': 'Ollama',
        'description': 'Free, private, runs on your GPU — no API key needed',
        'base_url': 'http://127.0.0.1:11434',
        'default_model': 'llama3.2',
        'api_key_required': False,
        'local': True,
        'setup_hint': 'Install from ollama.com, then: ollama pull llama3.2',
    },
    'lmstudio': {
        'name': 'LM Studio',
        'description': 'Local models with a visual interface',
        'base_url': 'http://127.0.0.1:1234',
        'default_model': 'default',
        'api_key_required': False,
        'local': True,
        'setup_hint': 'Install from lmstudio.ai, load a model, and start the server',
    },
    'openai': {
        'name': 'OpenAI',
        'description': 'GPT-4o and other OpenAI models — requires API key',
        'base_url': 'https://api.openai.com',
        'default_model': 'gpt-4o-mini',
        'api_key_required': True,
        'local': False,
        'setup_hint': 'Get an API key from platform.openai.com/api-keys',
    },
    'custom': {
        'name': 'Custom Endpoint',
        'description': 'Any OpenAI-compatible API endpoint',
        'base_url': '',
        'default_model': '',
        'api_key_required': False,
        'local': False,
        'setup_hint': 'Enter the base URL of your OpenAI-compatible API server',
    },
}

CATBYTE_SYSTEM_PROMPT = (
    "You are CatByte, the sharp, witty gaming AI companion inside YancoHub — "
    "a unified PC game launcher that aggregates Steam, Epic, GOG, Xbox, EA, "
    "Ubisoft, Battle.net, local games, and retro ROMs. "
    "Cat-themed personality (puns when natural, never forced). "
    "Punchy 2-3 sentence responses. Be genuinely helpful — clear guidance "
    "beats jokes when a gamer is stuck. PC gaming expert: hardware, performance, "
    "walkthroughs, retro emulation, mods, settings optimization. "
    "If you don't know, say so — don't make up game info."
)


class CatByte:
    """Multi-backend AI companion. All backends use OpenAI-compatible chat format."""

    def __init__(self):
        self._offline_until = 0
        self._auto_model = ''  # Auto-detected first model from backend
        self._settings = {
            'backend': 'ollama',
            'base_url': '',       # empty = use preset default
            'api_key': '',
            'model': '',          # empty = use preset default
            'cat_puns': True,
            'game_awareness': True,
        }

    def configure(self, settings: dict):
        """Update CatByte configuration from userdata settings."""
        self._settings.update(settings)
        self._offline_until = 0  # Reset cooldown on config change

        # Sanitize: clear model if it's invalid for the current backend
        backend = self._settings.get('backend', 'openclaw')
        model = self._settings.get('model', '').strip()
        if backend == 'openclaw' and model and not model.startswith('openclaw'):
            logger.info(f"Clearing invalid OpenClaw model '{model}' from settings")
            self._settings['model'] = ''

        logger.info(f"CatByte configured: backend={backend}, "
                    f"model={self.get_model()}")

    def get_config(self) -> dict:
        """Return current config (safe — no secrets in response)."""
        return {
            'backend': self._settings.get('backend', 'openclaw'),
            'base_url': self._get_base_url(),
            'model': self.get_model(),
            'cat_puns': self._settings.get('cat_puns', True),
            'game_awareness': self._settings.get('game_awareness', True),
            'has_api_key': bool(self._settings.get('api_key', '')),
        }

    def get_presets(self) -> dict:
        """Return available backend presets for the settings UI."""
        return BACKEND_PRESETS

    def _get_base_url(self) -> str:
        """Resolve the effective base URL from settings or preset."""
        custom_url = self._settings.get('base_url', '').strip()
        if custom_url:
            return custom_url.rstrip('/')
        backend = self._settings.get('backend', 'openclaw')
        preset = BACKEND_PRESETS.get(backend, BACKEND_PRESETS['openclaw'])
        return preset['base_url'].rstrip('/')

    def get_model(self) -> str:
        """Resolve the effective model name from settings or preset.
        For OpenClaw: only its aliases (openclaw, openclaw/*) are valid —
        any other saved value is ignored to prevent 400 errors."""
        custom_model = self._settings.get('model', '').strip()
        backend = self._settings.get('backend', 'openclaw')

        if custom_model:
            # OpenClaw only accepts 'openclaw' or 'openclaw/<agentId>' as model
            if backend == 'openclaw' and not custom_model.startswith('openclaw'):
                logger.info(f"Ignoring invalid OpenClaw model '{custom_model}', using default")
            else:
                return custom_model

        preset = BACKEND_PRESETS.get(backend, BACKEND_PRESETS['openclaw'])
        default = preset.get('default_model', '')
        if default:
            return default
        if self._auto_model:
            return self._auto_model
        return ''

    def _headers(self) -> dict:
        """Build request headers — works for all OpenAI-compatible backends."""
        headers = {'Content-Type': 'application/json'}
        api_key = self._settings.get('api_key', '').strip()
        backend = self._settings.get('backend', 'openclaw')

        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        elif backend == 'openclaw':
            # Try loading OpenClaw auth token from its config
            token = self._load_openclaw_token()
            if token:
                headers['Authorization'] = f'Bearer {token}'
        elif backend == 'ollama':
            # Ollama accepts any key but requires the header
            headers['Authorization'] = 'Bearer ollama'
        elif backend == 'lmstudio':
            headers['Authorization'] = 'Bearer lm-studio'

        return headers

    def _load_openclaw_config(self) -> dict:
        """Load the full OpenClaw config from its JSON file."""
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load OpenClaw config: {e}")
        return {}

    def _load_openclaw_token(self) -> str:
        """Load OpenClaw auth token from its config file."""
        config = self._load_openclaw_config()
        return config.get('gateway', {}).get('auth', {}).get('token', '')

    def _load_openclaw_models(self) -> list:
        """Build an enriched model list for OpenClaw.
        OpenClaw only accepts aliases (openclaw, openclaw/default, openclaw/main)
        in API calls, but we enrich them with the primary model name from its config
        so the user knows what's actually being used."""
        # Get the API aliases (the only values OpenClaw accepts)
        base_url = self._get_base_url()
        aliases = []
        if base_url:
            try:
                resp = requests.get(f"{base_url}/v1/models",
                                    headers=self._headers(), timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    aliases = [m['id'] for m in data.get('data', [])]
            except Exception:
                pass
        if not aliases:
            aliases = ['openclaw']

        return aliases

    def get_openclaw_info(self) -> dict:
        """Get OpenClaw routing info: primary model and available models from config."""
        config = self._load_openclaw_config()
        primary = (config.get('agents', {}).get('defaults', {})
                   .get('model', {}).get('primary', ''))
        models_dict = config.get('agents', {}).get('defaults', {}).get('models', {})
        available = []
        for model_id, info in models_dict.items():
            available.append({
                'id': model_id,
                'alias': info.get('alias', model_id),
            })
        return {'primary': primary, 'available': available}

    def _build_system_prompt(self, game_context: str = None) -> str:
        """Build the system prompt with optional personality and context tweaks."""
        prompt = CATBYTE_SYSTEM_PROMPT

        if not self._settings.get('cat_puns', True):
            prompt = prompt.replace(
                "Cat-themed personality (puns when natural, never forced). ",
                "Professional tone, no cat puns. "
            )

        if game_context and self._settings.get('game_awareness', True):
            prompt += f"\n\nThe user is currently playing: {game_context}"

        return prompt

    # ── Status Check ─────────────────────────────────────────────────────────

    def check_status(self) -> dict:
        """Check if the configured backend is reachable."""
        if time.time() < self._offline_until:
            return {'status': 'offline', 'message': 'CatByte is resting (cooldown)'}

        backend = self._settings.get('backend', 'openclaw')
        base_url = self._get_base_url()
        backend_name = BACKEND_PRESETS.get(backend, {}).get('name', backend)

        if not base_url:
            return {'status': 'offline', 'message': 'No backend configured'}

        try:
            if backend == 'ollama':
                resp = requests.get(f"{base_url}/api/tags", timeout=3)
            else:
                resp = requests.get(f"{base_url}/v1/models",
                                    headers=self._headers(), timeout=5)

            if resp.status_code == 200:
                model = self.get_model()
                return {
                    'status': 'online',
                    'backend': backend,
                    'backend_name': backend_name,
                    'model': model,
                    'message': 'CatByte is ready!',
                }
            return {'status': 'offline',
                    'message': f'{backend_name} returned {resp.status_code}'}
        except requests.ConnectionError:
            return {'status': 'offline',
                    'message': f'{backend_name} not running'}
        except Exception as e:
            return {'status': 'offline', 'message': str(e)}

    def list_models(self) -> list:
        """List available models from the configured backend.
        Always fetches live so added/removed models are reflected."""
        backend = self._settings.get('backend', 'openclaw')

        models = []
        if backend == 'openclaw':
            models = self._load_openclaw_models()
        else:
            base_url = self._get_base_url()
            if not base_url:
                return []
            try:
                if backend == 'ollama':
                    resp = requests.get(f"{base_url}/api/tags", timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        models = [m['name'] for m in data.get('models', [])]
                else:
                    resp = requests.get(f"{base_url}/v1/models",
                                        headers=self._headers(), timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        models = [m['id'] for m in data.get('data', [])]
            except Exception as e:
                logger.warning(f"Failed to list models: {e}")

        # Cache first model for auto-detection when no model is configured
        self._auto_model = models[0] if models else ''
        return models

    def chat(self, message: str, game_context: str = None,
             history: list = None) -> dict:
        """Send a chat message via OpenAI-compatible /v1/chat/completions."""
        if time.time() < self._offline_until:
            return {
                'response': "\U0001f63a CatByte is taking a catnap... try again in a moment!",
                'status': 'offline',
            }

        backend = self._settings.get('backend', 'openclaw')
        backend_name = BACKEND_PRESETS.get(backend, {}).get('name', backend)
        base_url = self._get_base_url()
        if not base_url:
            return {
                'response': "\U0001f63a No AI backend configured. Open Settings \u2192 CatByte to set one up!",
                'status': 'offline',
            }

        try:
            messages = [{'role': 'system',
                         'content': self._build_system_prompt(game_context)}]

            for h in (history or []):
                role = h.get('role', 'user')
                content = h.get('content', '')
                if role in ('user', 'assistant') and content:
                    messages.append({'role': role, 'content': content})

            messages.append({'role': 'user', 'content': message})

            payload = {
                'model': self.get_model(),
                'messages': messages,
                'stream': False,
            }

            resp = requests.post(
                f"{base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=120,
            )

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get('choices', [])
                if choices:
                    content = choices[0].get('message', {}).get('content', '')
                    if content:
                        return {'response': content, 'status': 'online'}
                # Fallback response shapes
                content = data.get('response', data.get('message', ''))
                return {'response': content or 'No response from CatByte.',
                        'status': 'online'}
            else:
                logger.warning(f"CatByte chat error ({backend_name}): "
                               f"{resp.status_code} \u2014 {resp.text[:200]}")
                self._offline_until = time.time() + 5
                return {
                    'response': f"\U0001f63f {backend_name} returned an error ({resp.status_code}). Try again!",
                    'status': 'error',
                }

        except requests.ConnectionError:
            self._offline_until = time.time() + 5
            return {
                'response': f"\U0001f63a CatByte can't reach {backend_name}. Make sure it's running!",
                'status': 'offline',
            }
        except Exception as e:
            logger.error(f"CatByte chat error ({backend_name}): {e}")
            self._offline_until = time.time() + 5
            return {
                'response': f"\U0001f63f Something went wrong with {backend_name}.",
                'status': 'error',
            }

    def chat_vision(self, message: str, image_base64: str,
                    game_context: str = None, history: list = None) -> dict:
        """Send a screenshot + question. Uses /v1/chat/completions with image content."""
        if time.time() < self._offline_until:
            return {
                'response': "\U0001f63a CatByte is taking a catnap...",
                'status': 'offline',
            }

        backend = self._settings.get('backend', 'openclaw')
        backend_name = BACKEND_PRESETS.get(backend, {}).get('name', backend)
        base_url = self._get_base_url()
        if not base_url:
            return {
                'response': "\U0001f63a No AI backend configured.",
                'status': 'offline',
            }

        try:
            messages = [{'role': 'system',
                         'content': self._build_system_prompt(game_context)}]

            for h in (history or []):
                role = h.get('role', 'user')
                content = h.get('content', '')
                if role in ('user', 'assistant') and content:
                    messages.append({'role': role, 'content': content})

            # OpenAI vision format — works with OpenAI, Ollama (vision models),
            # and any compliant backend
            messages.append({
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': message},
                    {
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:image/jpeg;base64,{image_base64}',
                        },
                    },
                ],
            })

            payload = {
                'model': self.get_model(),
                'messages': messages,
                'stream': False,
            }

            resp = requests.post(
                f"{base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=120,
            )

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get('choices', [])
                if choices:
                    content = choices[0].get('message', {}).get('content', '')
                    if content:
                        return {'response': content, 'status': 'online'}
                return {'response': data.get('response', 'No response.'),
                        'status': 'online'}
            else:
                logger.warning(f"CatByte vision error ({backend_name}): "
                               f"{resp.status_code} \u2014 {resp.text[:200]}")
                self._offline_until = time.time() + 5
                return {
                    'response': f"\U0001f63f {backend_name} couldn't analyze the screenshot ({resp.status_code}).",
                    'status': 'error',
                }
        except requests.ConnectionError:
            self._offline_until = time.time() + 5
            return {
                'response': f"\U0001f63a Can't reach {backend_name}. Make sure it's running!",
                'status': 'offline',
            }
        except Exception as e:
            logger.error(f"CatByte vision error ({backend_name}): {e}")
            self._offline_until = time.time() + 5
            return {
                'response': f"\U0001f63f Vision failed with {backend_name}.",
                'status': 'error',
            }

    def generate_title(self, messages: list) -> dict:
        """Generate a short title for a conversation from its first messages."""
        base_url = self._get_base_url()
        if not base_url:
            return {'title': ''}

        try:
            prompt_messages = [
                {'role': 'system',
                 'content': 'Generate a 3-5 word title for this conversation. '
                            'Reply with ONLY the title, nothing else. No quotes.'},
            ]
            for m in messages[:4]:
                role = m.get('role', 'user')
                content = m.get('content', '')
                if role in ('user', 'assistant') and content:
                    prompt_messages.append({'role': role, 'content': content[:200]})

            resp = requests.post(
                f"{base_url}/v1/chat/completions",
                headers=self._headers(),
                json={'model': self.get_model(), 'messages': prompt_messages, 'stream': False},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get('choices', [])
                if choices:
                    title = choices[0].get('message', {}).get('content', '').strip()
                    return {'title': title}
        except Exception as e:
            logger.warning(f"Title generation failed: {e}")
        return {'title': ''}

    def test_connection(self) -> dict:
        """Send a quick test message to verify the backend works end-to-end."""
        backend = self._settings.get('backend', 'openclaw')
        backend_name = BACKEND_PRESETS.get(backend, {}).get('name', backend)
        base_url = self._get_base_url()
        if not base_url:
            return {'success': False, 'message': 'No backend URL configured'}

        try:
            payload = {
                'model': self.get_model(),
                'messages': [
                    {'role': 'user', 'content': 'Say "CatByte online!" in exactly 3 words.'}
                ],
                'stream': False,
            }
            resp = requests.post(
                f"{base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get('choices', [])
                reply = ''
                if choices:
                    reply = choices[0].get('message', {}).get('content', '')
                return {
                    'success': True,
                    'message': f'Connected! Response: "{reply[:100]}"',
                    'model': self.get_model(),
                }
            return {
                'success': False,
                'message': f'{backend_name} returned {resp.status_code}: {resp.text[:150]}',
            }
        except requests.ConnectionError:
            return {'success': False,
                    'message': f'Connection refused — is {backend_name} running?'}
        except Exception as e:
            return {'success': False, 'message': str(e)}
