"""
verificar.py — Diagnóstico completo do ambiente RPG GM LLM
Verifica conectividade, modelos disponíveis e faz um teste de resposta.

Uso:
    python verificar.py
"""
import json, os, sys, time
from pathlib import Path

SEP  = "═" * 58
SEP2 = "─" * 58

def ok(msg):  print(f"  \033[32m✓\033[0m  {msg}")
def err(msg): print(f"  \033[31m✗\033[0m  {msg}")
def aviso(msg): print(f"  \033[33m⚠\033[0m  {msg}")
def info(msg):  print(f"  \033[90m→\033[0m  {msg}")

def testar_resposta(url, headers, payload, campo_resposta):
    """Faz POST e extrai texto da resposta. Retorna (texto, tempo_s) ou (None, 0)."""
    try:
        import requests
        t0 = time.time()
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        elapsed = round(time.time() - t0, 2)
        data = r.json()
        if "error" in data:
            return None, elapsed, str(data["error"])
        texto = campo_resposta(data)
        return texto, elapsed, None
    except Exception as e:
        return None, 0, str(e)


print(f"\n{SEP}")
print(f"  RPG GM LLM — VERIFICADOR DE AMBIENTE")
print(f"{SEP}\n")

# ── Carrega llm_config.py ─────────────────────────────────────
print("1. Configuração (llm_config.py)")
try:
    import llm_config as cfg
    backend = getattr(cfg, "BACKEND", "ollama")
    ok(f"llm_config.py carregado — BACKEND = {backend!r}")
except ImportError:
    err("llm_config.py não encontrado — usando padrões")
    cfg = None
    backend = "ollama"

print()

# ══════════════════════════════════════════════════════════════
# 2. OLLAMA
# ══════════════════════════════════════════════════════════════
print("2. Ollama")
try:
    import requests
    base = getattr(cfg, "OLLAMA_BASE_URL", "http://localhost:11434") if cfg else "http://localhost:11434"
    modelo_cfg = getattr(cfg, "OLLAMA_MODEL", "llama3.1:8b") if cfg else "llama3.1:8b"

    # Ping
    try:
        r = requests.get(base, timeout=3)
        ok(f"Servidor rodando em {base}")
    except Exception:
        err(f"Servidor não encontrado em {base}")
        print(f"  \033[90m  Inicie com: ollama serve\033[0m")
        print()
        goto_groq = True
    else:
        goto_groq = False

    if not goto_groq:
        # Lista modelos
        try:
            r = requests.get(f"{base}/api/tags", timeout=5)
            modelos = r.json().get("models", [])
            if modelos:
                ok(f"{len(modelos)} modelo(s) instalado(s):")
                for m in modelos:
                    nome = m.get("name", "?")
                    tam  = m.get("size", 0)
                    tam_gb = f"{tam/1e9:.1f}GB" if tam else ""
                    ativo = " ← configurado" if nome == modelo_cfg else ""
                    print(f"       \033[97m{nome}\033[0m  {tam_gb}{ativo}")
            else:
                err("Nenhum modelo instalado")
                info(f"Baixe com: ollama pull llama3.1:8b")
        except Exception as e:
            err(f"Não foi possível listar modelos: {e}")
            modelos = []

        # Verifica modelo configurado
        nomes = [m.get("name","") for m in modelos]
        if modelo_cfg in nomes:
            ok(f"Modelo configurado '{modelo_cfg}' disponível")
        else:
            err(f"Modelo configurado '{modelo_cfg}' NÃO está instalado")
            # Sugestão de nome mais próximo
            sugestoes = [n for n in nomes if modelo_cfg.split(":")[0] in n]
            if sugestoes:
                aviso(f"Modelos similares encontrados: {', '.join(sugestoes)}")
                info(f"No llm_config.py, mude para: OLLAMA_MODEL = \"{sugestoes[0]}\"")
            elif nomes:
                info(f"Modelos disponíveis: {', '.join(nomes)}")
                info(f"Ou baixe com: ollama pull {modelo_cfg}")

        # Teste de resposta
        if modelos:
            print(f"\n  Testando resposta do Ollama ({modelo_cfg if modelo_cfg in nomes else nomes[0]})...")
            modelo_teste = modelo_cfg if modelo_cfg in nomes else nomes[0]
            payload = {
                "model": modelo_teste, "stream": False,
                "options": {"temperature": 0.1, "num_predict": 15},
                "messages": [{"role": "user", "content": "Diga apenas: funcionou"}],
            }
            texto, t, erro = testar_resposta(
                f"{base}/api/chat", {}, payload,
                lambda d: d.get("message", {}).get("content", "")
            )
            if texto:
                ok(f"Resposta em {t}s: {texto.strip()[:60]!r}")
            else:
                err(f"Sem resposta: {erro}")

except ImportError:
    err("requests não instalado — pip install requests")

print()

# ══════════════════════════════════════════════════════════════
# 3. GROQ
# ══════════════════════════════════════════════════════════════
print("3. Groq API")
try:
    import requests
    groq_key   = getattr(cfg, "GROQ_API_KEY", "") if cfg else ""
    groq_model = getattr(cfg, "GROQ_MODEL", "llama-3.1-8b-instant") if cfg else "llama-3.1-8b-instant"

    if not groq_key:
        aviso("GROQ_API_KEY não configurada em llm_config.py")
        info("Obtenha em: https://console.groq.com → API Keys")
    else:
        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
        # Lista modelos
        try:
            r = requests.get("https://api.groq.com/openai/v1/models",
                             headers=headers, timeout=8)
            if r.ok:
                modelos_groq = [m["id"] for m in r.json().get("data", [])
                                if "whisper" not in m["id"]]
                ok(f"API key válida — {len(modelos_groq)} modelos disponíveis")
                for m in modelos_groq[:6]:
                    ativo = " ← configurado" if m == groq_model else ""
                    print(f"       \033[97m{m}\033[0m{ativo}")
                if len(modelos_groq) > 6:
                    print(f"       ... e mais {len(modelos_groq)-6}")
                if groq_model not in modelos_groq:
                    err(f"Modelo '{groq_model}' não encontrado na Groq")
                    info(f"Mude GROQ_MODEL para um dos listados acima")
            else:
                err(f"API key inválida ou sem acesso (status {r.status_code})")
        except Exception as e:
            err(f"Sem acesso à Groq: {e}")

        # Teste de resposta
        print(f"\n  Testando resposta da Groq ({groq_model})...")
        payload = {
            "model": groq_model, "max_tokens": 15, "temperature": 0.1, "stream": False,
            "messages": [{"role": "user", "content": "Diga apenas: funcionou"}],
        }
        texto, t, erro = testar_resposta(
            "https://api.groq.com/openai/v1/chat/completions",
            headers, payload,
            lambda d: d["choices"][0]["message"]["content"]
        )
        if texto:
            ok(f"Resposta em {t}s: {texto.strip()[:60]!r}")
        else:
            err(f"Sem resposta: {erro}")

except ImportError:
    pass

print()

# ══════════════════════════════════════════════════════════════
# 4. LM STUDIO
# ══════════════════════════════════════════════════════════════
print("4. LM Studio")
try:
    import requests
    lm_base  = getattr(cfg, "LMSTUDIO_BASE_URL", "http://localhost:1234") if cfg else "http://localhost:1234"
    lm_model = getattr(cfg, "LMSTUDIO_MODEL", "local-model") if cfg else "local-model"
    lm_key   = getattr(cfg, "LMSTUDIO_API_KEY", "") if cfg else ""

    lm_headers = {
        "Authorization": f"Bearer {lm_key.strip()}" if lm_key else "Bearer lm-studio",
        "Content-Type": "application/json",
    }

    # Ping
    try:
        r = requests.get(lm_base, timeout=3)
        ok(f"Servidor rodando em {lm_base}")
    except Exception:
        err(f"Servidor não encontrado em {lm_base}")
        info("Abra o LM Studio → Local Server → Start Server")
        print()
    else:
        # Key check
        if not lm_key:
            aviso("LMSTUDIO_API_KEY não configurada — pode falhar no 0.4.11+")
            info("Gere em: LM Studio → Developer → API Keys → + New Key")
        else:
            ok(f"API key configurada: {lm_key[:12]}...")

        # Lista modelos
        try:
            r = requests.get(f"{lm_base}/api/v1/models",
                             headers=lm_headers, timeout=5)
            if r.ok:
                data = r.json()
                modelos_lm = data.get("models", data.get("data", []))
                if modelos_lm:
                    ok(f"{len(modelos_lm)} modelo(s) carregado(s):")
                    for m in modelos_lm:
                        key_m = m.get("key", m.get("id", "?"))
                        state = m.get("state", "")
                        ativo = " ← configurado" if key_m == lm_model else ""
                        print(f"       \033[97m{key_m}\033[0m  {state}{ativo}")

                    # Verifica modelo configurado
                    chaves = [m.get("key", m.get("id","")) for m in modelos_lm]
                    if lm_model == "local-model":
                        aviso(f"LMSTUDIO_MODEL = 'local-model' — usando primeiro disponível: '{chaves[0]}'")
                        info(f"Recomendado: LMSTUDIO_MODEL = \"{chaves[0]}\"")
                        lm_model = chaves[0]
                    elif lm_model not in chaves:
                        err(f"Modelo '{lm_model}' não encontrado no LM Studio")
                        info(f"Modelos disponíveis: {', '.join(chaves)}")
                        info(f"Mude LMSTUDIO_MODEL para um dos listados")
                        lm_model = chaves[0] if chaves else lm_model
                    else:
                        ok(f"Modelo configurado '{lm_model}' disponível")
                else:
                    err("Nenhum modelo carregado no LM Studio")
                    info("Carregue um modelo no app antes de iniciar o servidor")
            else:
                err(f"Não foi possível listar modelos (status {r.status_code})")
                if r.status_code == 401:
                    err("API key inválida ou expirada")
        except Exception as e:
            err(f"Erro ao listar modelos: {e}")
            modelos_lm = []

        # Teste de resposta
        if modelos_lm:
            print(f"\n  Testando resposta do LM Studio ({lm_model})...")
            payload = {
                "model": lm_model,
                "input": "Diga apenas: funcionou",
                "system_prompt": "Responda de forma muito breve.",
                "max_output_tokens": 20,
                "temperature": 0.1,
                "stream": False,
            }
            texto, t, erro = testar_resposta(
                f"{lm_base}/api/v1/chat", lm_headers, payload,
                lambda d: next(
                    (i.get("content","") for i in d.get("output",[])
                     if i.get("type") == "message"), ""
                )
            )
            if texto:
                ok(f"Resposta em {t}s: {texto.strip()[:60]!r}")
            else:
                err(f"Sem resposta: {erro}")

except ImportError:
    pass

print()

# ══════════════════════════════════════════════════════════════
# 5. RESUMO
# ══════════════════════════════════════════════════════════════
print(f"{SEP}")
print(f"  RESUMO — backend ativo: \033[1m{backend.upper()}\033[0m")
print(f"{SEP}")

if cfg:
    if backend == "ollama":
        m = getattr(cfg, "OLLAMA_MODEL", "?")
        print(f"  OLLAMA_MODEL    = {m!r}")
        print(f"  OLLAMA_BASE_URL = {getattr(cfg,'OLLAMA_BASE_URL','http://localhost:11434')!r}")
    elif backend == "groq":
        m = getattr(cfg, "GROQ_MODEL", "?")
        k = getattr(cfg, "GROQ_API_KEY", "")
        print(f"  GROQ_MODEL   = {m!r}")
        print(f"  GROQ_API_KEY = {'configurada' if k else 'NÃO configurada'}")
    elif backend == "lmstudio":
        m = getattr(cfg, "LMSTUDIO_MODEL", "?")
        b = getattr(cfg, "LMSTUDIO_BASE_URL", "?")
        k = getattr(cfg, "LMSTUDIO_API_KEY", "")
        print(f"  LMSTUDIO_MODEL    = {m!r}")
        print(f"  LMSTUDIO_BASE_URL = {b!r}")
        print(f"  LMSTUDIO_API_KEY  = {'configurada' if k else 'NÃO configurada'}")

print(f"{SEP}\n")