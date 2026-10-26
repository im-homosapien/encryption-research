"""Talk to Ollama. Python encrypts. The model only answers.

A cloud model uses https://ollama.com when OLLAMA_API_KEY is set in the
environment or in a gitignored .env file. The key is never printed.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from research.paths import ROOT

OLLAMA_URL = "http://127.0.0.1:11434"
CLOUD_URL = "https://ollama.com"
# The CLI name gemma4:cloud is gemma4:31b on the cloud API.
CLOUD_MODEL_NAMES = {"gemma4:cloud": "gemma4:31b"}


class OllamaError(RuntimeError):
    """Ollama is not running, the model is missing, or the call failed."""


def installed_models() -> list[str]:
    """Return model names Ollama already has, such as ``mistral:latest``."""
    request = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise OllamaError(
            "Ollama is not running. Start it, then pull a model. "
            f"Tried {OLLAMA_URL}/api/tags ({exc})."
        ) from exc
    return [str(item["name"]) for item in body.get("models", [])]


def model_ready(model: str, installed: list[str] | None = None) -> bool:
    """True when a local model is installed, or the name is an Ollama cloud model."""
    if model.endswith(":cloud"):
        return True
    names = installed_models() if installed is None else installed
    wanted = model if ":" in model else f"{model}:latest"
    return model in names or wanted in names


def api_key() -> str:
    """Read the cloud key from the environment or a local .env file."""
    key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if key:
        return key
    env_path = ROOT / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "OLLAMA_API_KEY":
            return value.strip().strip('"').strip("'")
    return ""


def call_ollama(
    model: str,
    prompt: str,
    temperature: float = 0.0,
    timeout: int = 1800,
    cloud: bool = False,
) -> str:
    """Ask one model. Temperature 0 keeps the reply steady from run to run."""
    key = api_key()
    headers = {"Content-Type": "application/json"}
    use_cloud = cloud or model.endswith(":cloud")
    if use_cloud:
        if not key:
            raise OllamaError(
                "Cloud model needs OLLAMA_API_KEY in the environment or in .env. "
                "Do not paste the key into chat."
            )
        if model.endswith(":cloud"):
            request_model = CLOUD_MODEL_NAMES.get(model, model[: -len(":cloud")])
        else:
            request_model = model
        url = f"{CLOUD_URL}/api/generate"
        headers["Authorization"] = f"Bearer {key}"
    else:
        request_model = model
        url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": request_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 1024,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code in (429, 503) and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise OllamaError(f"Ollama refused {model}: HTTP {exc.code} {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise OllamaError(f"Could not reach Ollama for {model}: {exc}") from exc
    else:
        raise OllamaError(f"Ollama refused {model} after retries")
    if body.get("error"):
        raise OllamaError(str(body["error"]))
    return str(body.get("response", "")).strip()
