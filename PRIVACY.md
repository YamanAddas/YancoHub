# Privacy

YancoHub is a local Windows application. It does not collect, transmit, or
sell any personal data on its own.

## What it stores, and where

All user data stays on the machine YancoHub is installed on:

- **Settings, library state, collections, favourites, playtimes, per-game
  notes**, and Save Guardian snapshots live under
  `%LOCALAPPDATA%\YancoHub\` (installed mode) or in the app folder itself
  (portable mode). Nothing is uploaded.
- **Cached game artwork and metadata** is stored under
  `%LOCALAPPDATA%\YancoHub\cache\` so the carousel renders without
  re-fetching.

## Network connections — all opt-in

YancoHub makes a network request only when a user explicitly enables a
feature that needs one:

- **Steam Web API** — only if the user enters their Steam ID and a personal
  API key in Settings → Accounts. Used to read the user's owned-games list.
- **GOG Galaxy local database** — read-only access to the user's existing
  Galaxy install. Nothing is sent to GOG.
- **Epic Games Launcher local catalog cache** — read-only access to the
  user's local Epic cache. Nothing is sent to Epic.
- **CatByte AI assistant** — disabled by default. If enabled, messages are
  sent only to the backend the user configures (a local Ollama / LM Studio
  endpoint, or an OpenAI-compatible URL the user pastes in). YancoHub never
  ships a default cloud endpoint or relays through any of its own servers.
- **Artwork providers** — public CDN endpoints (Steam grid CDN, LibRetro
  thumbnails, optionally SteamGridDB) are queried only to fetch cover art
  for games already in the user's library.
- **GitHub Releases API** — queried at startup to check for new YancoHub
  versions. No user information is sent — only YancoHub's own version
  number and the standard HTTP user agent.

## API keys and credentials

API keys the user enters (Steam, optionally OpenAI / SteamGridDB) are
stored in plaintext inside `userdata.json` for local use. That file is
git-ignored in this repository and is never transmitted.

## Telemetry

There is none. YancoHub does not phone home, count installs, report crashes,
or measure usage in any way.

## Contact

For privacy questions, please open an issue at
<https://github.com/YamanAddas/YancoHub/issues>.
