"""
llm_backend.py
─────────────────────────────────────────────────────────────
Camada de abstração para backends de LLM.

Suporta três modos selecionáveis no menu inicial:

  1. OLLAMA LOCAL (padrão)
     - Qualquer modelo instalado via `ollama pull`
     - Recomendado para hardware potente
     - llama3.1:8b (qualidade alta, ~4GB VRAM)

  2. OLLAMA LOCAL — MODELO PEQUENO
     - Modelos leves para notebook/CPU
     - qwen2.5:0.5b  (~400MB RAM — CPU pura)
     - tinyllama:1.1b (~600MB RAM — CPU pura)
     - phi3.5:mini    (~2.2GB RAM — CPU ou iGPU)
     - Selecionável por submenu

  3. GROQ API (cloud, gratuito com limite)
     - Requer GROQ_API_KEY em variável de ambiente ou input
     - Modelos: llama-3.1-8b-instant, gemma2-9b-it, mixtral-8x7b-32768
     - Limites gratuitos: ~14.400 req/dia, ~500K tokens/min
     - Vantagem: latência muito baixa (~0.5–1s vs 10–30s local)
─────────────────────────────────────────────────────────────
"""

import os
import json
import time
from typing import Optional

try:
    import session_log as _slog
    _SLOG_OK = True
except ImportError:
    _SLOG_OK = False

# ── Session persistente (reutiliza conexão TCP) ───────────────
_session = None

def _get_session():
    """
    Retorna uma requests.Session() persistente.
    - Lazy import: requests só é carregado na primeira chamada LLM (~320ms economizados no startup)
    - Session reutiliza conexão TCP via HTTP Keep-Alive: economiza ~50-100ms por chamada
    - Thread-safe para uso com a barra de loading (daemon thread)
    """
    global _session
    if _session is None:
        import requests
        _session = requests.Session()
        _session.headers.update({"Content-Type": "application/json"})
    return _session

# ── Estado global — carregado de llm_config.py ───────────────
def _carregar_config():
    try:
        import llm_config as cfg
        import os
        backend  = getattr(cfg, "BACKEND", "ollama")
        base_url = getattr(cfg, "OLLAMA_BASE_URL", "http://localhost:11434")
        if backend == "groq":
            model = getattr(cfg, "GROQ_MODEL", "llama-3.1-8b-instant")
            key   = getattr(cfg, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        elif backend == "lmstudio":
            model    = getattr(cfg, "LMSTUDIO_MODEL", "local-model")
            base_url = getattr(cfg, "LMSTUDIO_BASE_URL", "http://localhost:1234")
            key      = getattr(cfg, "LMSTUDIO_API_KEY", "") or os.environ.get("LMSTUDIO_API_KEY", "")
        else:
            model = getattr(cfg, "OLLAMA_MODEL", "llama3.1:8b")
            key   = ""
        # Atualiza URLs do LM Studio se configurado
        if backend == "lmstudio":
            global LMSTUDIO_URL, LMSTUDIO_URL_V1, _LM_BASE, _LM_KEY
            lm_base = getattr(cfg, "LMSTUDIO_BASE_URL", "http://localhost:1234")
            _LM_BASE        = lm_base
            _LM_KEY         = getattr(cfg, "LMSTUDIO_API_KEY", "") or os.environ.get("LMSTUDIO_API_KEY", "")
            LMSTUDIO_URL    = lm_base + "/api/v1/chat"
            LMSTUDIO_URL_V1 = lm_base + "/v1/chat/completions"
        return backend, model, key, base_url
    except ImportError:
        return "ollama", "llama3.1:8b", "", "http://localhost:11434"

_BACKEND, _MODEL, _GROQ_KEY, _BASE_URL = _carregar_config()


def dica_conexao() -> str:
    """Retorna mensagem de dica adequada ao backend configurado."""
    if _BACKEND == "lmstudio":
        return f"Verifique: LM Studio Server rodando em {_LM_BASE}"
    if _BACKEND == "groq":
        return "Verifique sua GROQ_API_KEY em llm_config.py"
    return "Verifique: ollama serve   (em outro terminal)"


def obter_modelo_atual() -> str:
    """
    Retorna o nome real do modelo em uso — resolve para LM Studio, Groq e Ollama.
    Atualiza o global _MODEL para que session_log grave corretamente.
    Chamar no início de cada sessão antes de iniciar_sessao().
    """
    global _MODEL
    try:
        import llm_config as cfg
        if _BACKEND == "lmstudio":
            # Lê direto do config — se não for "local-model" usa esse valor
            modelo = getattr(cfg, "LMSTUDIO_MODEL", "local-model").strip()
            if modelo and modelo != "local-model":
                _MODEL = modelo
                return _MODEL
            # Senão consulta o servidor
            modelo = _lmstudio_model()
            if modelo:
                _MODEL = modelo
                return _MODEL
        elif _BACKEND == "groq":
            modelo = getattr(cfg, "GROQ_MODEL", "llama-3.1-8b-instant").strip()
            if modelo:
                _MODEL = modelo
                return _MODEL
        else:  # ollama
            modelo = getattr(cfg, "OLLAMA_MODEL", "llama3.1:8b").strip()
            if modelo:
                _MODEL = modelo
                return _MODEL
    except Exception:
        pass
    return _MODEL or "desconhecido"

# ── Modelos pequenos disponíveis para Ollama ──────────────────
MODELOS_PEQUENOS = [
    ("qwen2.5:0.5b",  "~400MB RAM  — CPU pura, muito rápido"),
    ("tinyllama:1.1b","~600MB RAM  — CPU pura, bom custo-benefício"),
    ("phi3.5:mini",   "~2.2GB RAM  — CPU/iGPU, qualidade superior"),
    ("gemma2:2b",     "~1.6GB RAM  — CPU/iGPU, boa coerência"),
    ("qwen2.5:1.5b",  "~1.0GB RAM  — CPU pura, equilibrado"),
]

# ── Modelos Groq disponíveis (gratuitos) ──────────────────────
MODELOS_GROQ = [
    ("llama-3.1-8b-instant", "Llama 3.1 8B  — rápido, boa qualidade"),
    ("gemma2-9b-it",         "Gemma 2 9B    — excelente em PT-BR"),
    ("mixtral-8x7b-32768",   "Mixtral 8x7B  — maior contexto (32k)"),
    ("llama-3.3-70b-versatile", "Llama 3.3 70B — qualidade máxima"),
]

GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
# LM Studio 0.4.11 usa /api/v1/chat (não /v1/chat/completions)
_LM_BASE        = "http://localhost:1234"   # sobrescrito em _carregar_config
_LM_KEY         = ""                          # API key — sobrescrita em _carregar_config
LMSTUDIO_URL    = _LM_BASE + "/api/v1/chat"
LMSTUDIO_URL_V1 = _LM_BASE + "/v1/chat/completions"  # fallback versões antigas

# ── Modelos LM Studio — depende do que você carregou no app ───
MODELOS_LMSTUDIO = [
    ("lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF", "Llama 3.1 8B — padrão"),
    ("lmstudio-community/gemma-2-9b-it-GGUF",              "Gemma 2 9B  — ótimo PT-BR"),
    ("lmstudio-community/Mistral-7B-Instruct-v0.3-GGUF",   "Mistral 7B  — leve e rápido"),
    ("lmstudio-community/Phi-3.5-mini-instruct-GGUF",      "Phi 3.5 Mini — muito leve"),
]


# ══════════════════════════════════════════════════════════════
#  CONFIGURAÇÃO
# ══════════════════════════════════════════════════════════════

def configurar(backend: str, model: str,
               groq_key: str = "", base_url: str = "") -> None:
    global _BACKEND, _MODEL, _GROQ_KEY, _BASE_URL
    _BACKEND  = backend
    _MODEL    = model
    _GROQ_KEY = groq_key
    _BASE_URL = base_url or "http://localhost:11434"


def get_info() -> dict:
    return {
        "backend": _BACKEND,
        "model"  : _MODEL,
        "groq_key_set": bool(_GROQ_KEY),
    }


# ══════════════════════════════════════════════════════════════
#  CHAMADA UNIFICADA
# ══════════════════════════════════════════════════════════════

def chamar(
    prompt: str,
    system: str,
    num_predict: int = 80,
    stream: bool = False,
    timeout: int = 90,
) -> str:
    """
    Chama o backend configurado e retorna o texto da resposta.
    Backends suportados: ollama | groq | lmstudio
    """
    if _BACKEND == "groq":
        return _chamar_groq(prompt, system, num_predict, stream, timeout)
    elif _BACKEND == "lmstudio":
        return _chamar_lmstudio(prompt, system, num_predict, stream, timeout)
    else:
        return _chamar_ollama(prompt, system, num_predict, stream, timeout)


def chamar_stream(prompt: str, system: str, num_predict: int = 350,
                  timeout: int = 90) -> str:
    """
    Streaming de tokens — imprime conforme chegam, retorna texto completo.
    Backends suportados: ollama | groq | lmstudio
    """
    if _BACKEND == "groq":
        return _stream_groq(prompt, system, num_predict, timeout)
    elif _BACKEND == "lmstudio":
        return _stream_lmstudio(prompt, system, num_predict, timeout)
    else:
        return _stream_ollama(prompt, system, num_predict, timeout)


# ══════════════════════════════════════════════════════════════
#  OLLAMA
# ══════════════════════════════════════════════════════════════


# ── Helper: ajuste adaptativo de num_predict para modelos reasoning ───
# Modelos como Gemma 4, DeepSeek-R1 e Qwen 3 emitem blocos <think>...</think>
# antes da resposta visível. Se num_predict for baixo, o pensamento consome
# todo o budget e a resposta efetiva fica vazia. Aplicamos um multiplicador
# automático nesses modelos.
_REASONING_TAGS = ("gemma4", "gemma-4", "deepseek-r1", "qwen3")
_REASONING_OVERHEAD_TOKENS = 800  # orçamento extra para o bloco <think>


def _ajustar_num_predict(num_predict: int) -> int:
    """Se o modelo configurado for reasoning, soma um overhead para
    acomodar o bloco <think> sem cortar a resposta visível."""
    try:
        modelo = (_MODEL or "").lower()
    except NameError:
        return num_predict
    if any(tag in modelo for tag in _REASONING_TAGS):
        return num_predict + _REASONING_OVERHEAD_TOKENS
    return num_predict


def _filtrar_think(texto: str) -> str:
    """Remove blocos <think>...</think> e <thought>...</thought> de saídas
    de reasoning models, incluindo tags abertas sem fechamento (token cortado)."""
    import re
    if not texto:
        return texto
    texto = re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL | re.IGNORECASE)
    texto = re.sub(r'<thought>.*?</thought>', '', texto, flags=re.DOTALL | re.IGNORECASE)
    # Tags abertas (modelo cortou no meio do pensamento) — descarta tudo após
    # a abertura, preservando texto antes da tag, se houver
    texto = re.sub(r'<think>.*$', '', texto, flags=re.DOTALL | re.IGNORECASE)
    texto = re.sub(r'<thought>.*$', '', texto, flags=re.DOTALL | re.IGNORECASE)
    return texto.strip()


def _chamar_ollama(prompt, system, num_predict, stream, timeout) -> str:
    url = f"{_BASE_URL}/api/chat"
    num_predict_eff = _ajustar_num_predict(num_predict)
    payload = {
        "model"  : _MODEL,
        "stream" : False,
        "options": {"temperature": 0.7, "num_predict": num_predict_eff},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
    }
    t0 = time.time()
    timeout_eff = max(timeout, 180) if num_predict_eff > num_predict else timeout
    r  = _get_session().post(url, json=payload, timeout=timeout_eff)
    r.raise_for_status()
    elapsed = round(time.time() - t0, 3)
    data    = r.json()
    texto   = data.get("message", {}).get("content", "").strip()

    if _SLOG_OK:
        uso = data.get("prompt_eval_count", 0), data.get("eval_count", 0)
        _slog.log_llm(
            tipo="llm_raw",
            entrada=prompt, resposta=texto,
            tokens_prompt=uso[0], tokens_resposta=uso[1],
            tempo_s=elapsed,
            finish_reason=data.get("done_reason", ""),
        )
    return texto


def _stream_ollama(prompt, system, num_predict, timeout) -> str:
    import sys
    url = f"{_BASE_URL}/api/chat"
    num_predict_eff = _ajustar_num_predict(num_predict)
    payload = {
        "model"  : _MODEL,
        "stream" : True,
        "options": {"temperature": 0.7, "num_predict": num_predict_eff},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
    }
    full = []
    with _get_session().post(url, json=payload, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except Exception:
                continue
            token = chunk.get("message", {}).get("content", "")
            if token:
                print(token, end="", flush=True)
                full.append(token)
            if chunk.get("done"):
                break
    # NÃO usar print() aqui — linha em branco seria consumida pelo input() seguinte
    sys.stdout.write("\n"); sys.stdout.flush()
    return "".join(full).strip()


# ══════════════════════════════════════════════════════════════
#  GROQ
# ══════════════════════════════════════════════════════════════

def _groq_headers() -> dict:
    return {
        "Authorization": f"Bearer {_GROQ_KEY}",
        "Content-Type" : "application/json",
    }


def _chamar_groq(prompt, system, num_predict, stream, timeout) -> str:
    payload = {
        "model"      : _MODEL,
        "messages"   : [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens" : num_predict,
        "temperature": 0.7,
        "stream"     : False,
    }
    t0 = time.time()
    r  = _get_session().post(GROQ_API_URL, headers=_groq_headers(),
                              json=payload, timeout=timeout)
    r.raise_for_status()
    elapsed = round(time.time() - t0, 3)
    data    = r.json()
    texto   = data["choices"][0]["message"]["content"].strip()
    uso     = data.get("usage", {})

    if _SLOG_OK:
        _slog.log_llm(
            tipo="llm_raw",
            entrada=prompt, resposta=texto,
            tokens_prompt=uso.get("prompt_tokens", 0),
            tokens_resposta=uso.get("completion_tokens", 0),
            tempo_s=elapsed,
            finish_reason=data["choices"][0].get("finish_reason", ""),
        )
    return texto


def _stream_groq(prompt, system, num_predict, timeout) -> str:
    import sys
    payload = {
        "model"      : _MODEL,
        "messages"   : [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens" : num_predict,
        "temperature": 0.7,
        "stream"     : True,
    }
    full = []
    with _get_session().post(GROQ_API_URL, headers=_groq_headers(),
                       json=payload, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8") if isinstance(line, bytes) else line
            if text.startswith("data: "):
                text = text[6:]
            if text.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(text)
                token = chunk["choices"][0]["delta"].get("content", "")
                if token:
                    print(token, end="", flush=True)
                    full.append(token)
            except Exception:
                continue
    # NÃO usar print() aqui — linha em branco seria consumida pelo input() seguinte
    sys.stdout.write("\n"); sys.stdout.flush()
    return "".join(full).strip()


# ══════════════════════════════════════════════════════════════
#  LM STUDIO  (OpenAI-compatible local server)
# ══════════════════════════════════════════════════════════════

def _lmstudio_headers() -> dict:
    """
    LM Studio 0.4.11+ — lê a API key do llm_config.py a cada chamada.
    Prioridade: llm_config.py → variável de ambiente → global _LM_KEY
    Imprime aviso claro se a key estiver ausente (sem crashar o jogo).
    """
    key = ""
    try:
        import llm_config as _cfg
        key = getattr(_cfg, "LMSTUDIO_API_KEY", "") or os.environ.get("LMSTUDIO_API_KEY", "")
    except ImportError:
        pass

    if not key:
        key = _LM_KEY

    # Remove espaços, aspas e caracteres invisíveis
    key = str(key).strip().strip('"').strip("'").strip()

    if not key or len(key) < 10:
        # Aviso visível mas sem crashar — o servidor vai rejeitar e o jogo
        # mostrará "LLM indisponível" com a dica correta
        print(
            "\n  \033[33m⚠  LMSTUDIO_API_KEY não configurada!\033[0m\n"
            "  Configure em llm_config.py:\n"
            "    LMSTUDIO_API_KEY = \"sk-lm-...\"\n"
            "  Gere em: LM Studio → Developer → API Keys\n"
        )

    return {
        "Content-Type" : "application/json",
        "Authorization": "Bearer " + key,
    }


def _lmstudio_model() -> str:
    """
    Retorna o identificador completo do modelo carregado no LM Studio.
    Lê LMSTUDIO_MODEL do llm_config.py a cada chamada.
    Se for "local-model", consulta /api/v1/models para auto-detectar.
    """
    # Lê do config em runtime (não usa global _MODEL que pode estar desatualizado)
    try:
        import llm_config as _cfg
        model = getattr(_cfg, "LMSTUDIO_MODEL", "local-model").strip()
        if model and model != "local-model":
            return model
    except ImportError:
        if _MODEL and _MODEL != "local-model":
            return _MODEL

    # Auto-detecção via /api/v1/models
    try:
        r = _get_session().get(
            _LM_BASE + "/api/v1/models",
            headers=_lmstudio_headers(), timeout=5
        )
        if r.ok:
            data = r.json()
            # LM Studio /api/v1/models retorna "models" (não "data")
            # cada modelo tem campo "key" como identificador
            models = data.get("models", data.get("data", []))
            if models:
                m = models[0]
                return m.get("key", m.get("id", m.get("path", "")))
    except Exception:
        pass
    return ""


def _chamar_lmstudio(prompt, system, num_predict, stream, timeout) -> str:
    """
    LM Studio 0.4.x — API nativa /api/v1/chat
    Docs: https://lmstudio.ai/docs/developer/rest/chat

    Formato oficial:
      input          : string  (prompt direto)
      system_prompt  : string  (instrução do sistema)
      max_output_tokens, temperature, stream
    Resposta: data["output"] = [{type:"message", content:"..."}]
    """
    modelo  = _lmstudio_model()
    headers = _lmstudio_headers()
    # Reasoning models precisam de tokens extras para pensar antes de responder
    # Garante mínimo de 200 tokens para não cortar no meio do raciocínio
    tokens = max(num_predict, 200)
    payload = {
        "model"            : modelo,
        "input"            : prompt,
        "system_prompt"    : system,
        "max_output_tokens": tokens,
        "temperature"      : 0.7,
        "stream"           : False,
    }
    t0 = time.time()
    r = _get_session().post(
        LMSTUDIO_URL, json=payload,
        headers=headers, timeout=timeout
    )
    elapsed = round(time.time() - t0, 3)
    data = r.json()

    if "error" in data:
        msg = data["error"].get("message", str(data["error"]))
        raise OSError(f"LM Studio error: {msg}")
    r.raise_for_status()

    # Resposta nativa: output = [{type:"message"|"reasoning", content:"..."}]
    # Para reasoning models: "reasoning" vem antes de "message"
    texto = ""
    reasoning = ""
    for item in data.get("output", []):
        if item.get("type") == "message":
            texto = item.get("content", "")
            break
        elif item.get("type") == "reasoning":
            reasoning = item.get("content", "")
    # Se não há message mas há reasoning, o modelo ficou sem tokens — usa reasoning
    if not texto and reasoning:
        texto = reasoning

    stats = data.get("stats", {})
    if _SLOG_OK:
        _slog.log_llm(
            tipo="llm_raw",
            entrada=prompt, resposta=texto,
            tokens_prompt=stats.get("input_tokens", 0),
            tokens_resposta=stats.get("total_output_tokens", 0),
            tempo_s=elapsed,
        )
    return texto.strip()


def _stream_lmstudio(prompt, system, num_predict, timeout) -> str:
    """
    Streaming via LM Studio 0.4.x API nativa.
    Docs: https://lmstudio.ai/docs/developer/rest/streaming-events
    Eventos SSE — type:contentBlockDelta carrega os tokens.
    """
    modelo  = _lmstudio_model()
    payload = {
        "model"            : modelo,
        "input"            : prompt,
        "system_prompt"    : system,
        "max_output_tokens": num_predict,
        "temperature"      : 0.7,
        "stream"           : True,
    }
    full = []
    with _get_session().post(LMSTUDIO_URL, json=payload,
                              headers=_lmstudio_headers(),
                              stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8") if isinstance(line, bytes) else line
            if text.startswith("data: "):
                text = text[6:]
            if text.strip() in ("[DONE]", ""):
                continue
            try:
                ev = json.loads(text)
                # LM Studio streaming: type = "contentBlockDelta"
                # delta.type = "text", delta.text = token
                ev_type = ev.get("type", "")
                if ev_type == "contentBlockDelta":
                    delta = ev.get("delta", {})
                    if delta.get("type") == "text":
                        token = delta.get("text", "")
                        if token:
                            print(token, end="", flush=True)
                            full.append(token)
                # Ignora "reasoning" tokens no stream — não exibe raciocínio interno
                elif ev_type == "content_block_delta":
                    delta = ev.get("delta", {})
                    token = delta.get("text", "")
                    if token:
                        print(token, end="", flush=True)
                        full.append(token)
                # Formato alternativo OpenAI-like
                elif "choices" in ev:
                    token = ev["choices"][0].get("delta", {}).get("content", "")
                    if token:
                        print(token, end="", flush=True)
                        full.append(token)
            except Exception:
                continue
    # NÃO usar print() aqui — linha em branco seria consumida pelo input() seguinte
    sys.stdout.write("\n"); sys.stdout.flush()
    return "".join(full).strip()


# ══════════════════════════════════════════════════════════════
#  TESTE DE CONECTIVIDADE
# ══════════════════════════════════════════════════════════════

def testar_conexao() -> tuple[bool, str]:
    """Testa se o backend está acessível. Retorna (ok, mensagem)."""
    try:
        if _BACKEND == "groq":
            if not _GROQ_KEY:
                return False, "GROQ_API_KEY não definida."
            r = _get_session().get("https://api.groq.com/openai/v1/models",
                             headers=_groq_headers(), timeout=8)
            if r.status_code == 200:
                return True, f"Groq OK — modelo: {_MODEL}"
            return False, f"Groq erro {r.status_code}: {r.text[:80]}"
        else:
            r = _get_session().get(f"{_BASE_URL}/api/tags", timeout=5)
            modelos = [m["name"] for m in r.json().get("models", [])]
            if _MODEL in modelos or any(_MODEL in m for m in modelos):
                return True, f"Ollama OK — modelo: {_MODEL}"
            return False, (
                f"Modelo '{_MODEL}' não encontrado.\n"
                f"  Execute: ollama pull {_MODEL}\n"
                f"  Modelos disponíveis: {', '.join(modelos[:5])}"
            )
    except OSError:
        if _BACKEND == "groq":
            return False, "Sem conexão com api.groq.com. Verifique a internet."
        return False, (
            f"Ollama não encontrado em {_BASE_URL}.\n"
            f"  Execute: ollama serve"
        )
    except Exception as e:
        return False, f"Erro: {e}"