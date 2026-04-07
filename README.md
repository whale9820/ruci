# Ruci

An LLM API gateway that exposes a single **OpenAI-compatible API endpoint** while letting you manage multiple backend LLM providers through a password-protected web dashboard.

## Features

- **Full OpenAI API compatibility** — chat completions, completions, embeddings, images, audio, fine-tuning, files, moderations, and all other `/v1/*` endpoints pass through transparently
- **Tool calls & streaming** — forwarded faithfully; Ruci doesn't inspect or modify them
- **Multi-provider routing** — use `provider_name/model_name` for explicit routing or just `model_name` to auto-match
- **Web dashboard** — add, edit, enable/disable providers; change password; set proxy API key
- **Zero-config storage** — every setting lives in `.env`. No database. Fresh `.env` = fresh install. Swap in a configured `.env` = instant restore.

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

Open **http://localhost:8000** to complete setup (set a dashboard password), then add your providers.

## Configuration (`.env`)

| Key | Description |
|-----|-------------|
| `HOST` | Bind address (default `0.0.0.0`) |
| `PORT` | Port (default `8000`) |
| `SESSION_SECRET` | Auto-generated on first run |
| `DASHBOARD_PASSWORD_HASH` | bcrypt hash, set via dashboard |
| `PROXY_API_KEY` | Optional key clients must send to use the API |
| `PROVIDERS` | JSON array of providers, managed via dashboard |

Copy `.env.example` to `.env` to pre-seed settings before first run.

## API Usage

Point any OpenAI-compatible app to `http://localhost:8000` (set base URL to `http://localhost:8000/v1`).

### Model Routing

| Request model | Behaviour |
|--------------|-----------|
| `gpt-4o` | Routes to first provider that lists `gpt-4o` in its models |
| `OpenAI/gpt-4o` | Routes explicitly to the provider named `OpenAI`, sends `gpt-4o` upstream |
| *(any model)* | Falls back to first enabled provider if no match found |

### Supported Endpoints

All `/v1/*` paths are proxied. Highlighted endpoints:

- `POST /v1/chat/completions` — streaming, tool calls, vision
- `POST /v1/completions`
- `GET  /v1/models` — aggregated across all enabled providers
- `POST /v1/embeddings`
- `POST /v1/images/generations`
- `POST /v1/audio/transcriptions` (multipart)
- `POST /v1/audio/translations` (multipart)
- `POST /v1/audio/speech`
- `POST /v1/moderations`
- `POST /v1/fine_tuning/jobs`
- `GET/DELETE /v1/files/*`
- Any other endpoint your provider supports

### Models endpoint

`GET /v1/models` returns all models from all enabled providers, prefixed as `provider_name/model_name`. If a provider has no static model list configured, Ruci fetches its `/v1/models` live.

### Proxy API Key

If `PROXY_API_KEY` is set in `.env` (configurable from the dashboard), clients must include:
```
Authorization: Bearer <your-proxy-api-key>
```
Leave blank for open (local) access.

## Portability

The entire state of Ruci — providers, credentials, password, settings — lives in `.env`. To migrate or restore:

1. Copy your `.env` to the new host
2. `pip install -r requirements.txt && python main.py`

Done.
