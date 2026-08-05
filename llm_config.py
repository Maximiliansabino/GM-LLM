"""
llm_config.py
─────────────────────────────────────────────────────────────
Configuração do backend de LLM utilizado pelo jogo.

INSTRUÇÕES:
  1. Escolha um BACKEND abaixo (descomente a linha desejada)
  2. Escolha o MODELO correspondente
  3. Salve e execute o jogo normalmente

Para Groq: defina sua API Key na variável GROQ_API_KEY
  - Obtenha gratuitamente em: https://console.groq.com
─────────────────────────────────────────────────────────────
"""


# ══════════════════════════════════════════════════════════════
#  BACKEND
#  Descomente APENAS UMA das linhas abaixo.
# ══════════════════════════════════════════════════════════════

BACKEND = "ollama"     # LLM local via Ollama  (padrão)
# BACKEND = "groq"     # Groq API — cloud gratuito, latência baixa
# BACKEND = "lmstudio" # LM Studio — servidor local OpenAI-compatible


# ══════════════════════════════════════════════════════════════
#  MODELO — OLLAMA LOCAL
#  Usado quando BACKEND = "ollama"
#  Execute antes:  ollama pull <modelo>
#                  ollama serve
# ══════════════════════════════════════════════════════════════

# ── Hardware potente (GPU com 8GB+ VRAM) ─────────────────────
#OLLAMA_MODEL = "qwen2.5:7b-instruct" 
#OLLAMA_MODEL = "llama3.1:8b"          # Melhor qualidade — padrão do projeto
# OLLAMA_MODEL = "llama3.2:3b"         # Mais leve, ainda boa qualidade

# ── Notebook / CPU (sem GPU dedicada) ─────────────────────────
# OLLAMA_MODEL = "qwen2.5:0.5b"        # ~400MB RAM — CPU pura, muito rápido
# OLLAMA_MODEL = "qwen2.5:1.5b"        # ~1.0GB RAM — CPU pura, equilibrado
# OLLAMA_MODEL = "tinyllama:1.1b"      # ~600MB RAM — CPU pura, leve
OLLAMA_MODEL = "gemma4:e2b"           # ~1.6GB RAM — CPU/iGPU, boa coerência
# OLLAMA_MODEL = "phi3.5:mini"         # ~2.2GB RAM — CPU/iGPU, qualidade superior

# ── Endereço do servidor Ollama (não altere salvo customização) ─
OLLAMA_BASE_URL = "http://localhost:11434"


# ══════════════════════════════════════════════════════════════
#  MODELO — LM STUDIO (servidor local)
#  Usado quando BACKEND = "lmstudio"
#
#  Como configurar:
#  1. Abra o LM Studio → aba "Local Server" (ícone <->)
#  2. Carregue qualquer modelo GGUF
#  3. Clique em "Start Server" (porta padrão: 1234)
#  4. O nome do modelo abaixo é ignorado pelo LM Studio —
#     ele usa sempre o modelo carregado no app.
#     Coloque qualquer string descritiva para o log da tese.
# ══════════════════════════════════════════════════════════════

LMSTUDIO_MODEL = "local-model"   # Deixe "local-model" para detecção automática
                                 # Ou coloque o nome exato: "qwen3.5-27b"

# Endereço do servidor LM Studio
LMSTUDIO_BASE_URL = "http://localhost:1234"
# LMSTUDIO_BASE_URL = "http://26.12.169.161:1234"  # servidor remoto na rede

# API Key do LM Studio 0.4.11+
# Como gerar:  LM Studio → aba "Developer" → "API Keys" → "+ New Key"
# Cole a key gerada abaixo (começa com "lms-...")
LMSTUDIO_API_KEY = "sk-lm-3BmdHS1J:XkxtMziszhNEHEFi8iv3"   # ← cole aqui sua key: "lms-..."

# Exemplos de modelos populares no LM Studio:
# LMSTUDIO_MODEL = "llama3.1-8b-instruct"
# LMSTUDIO_MODEL = "gemma-2-9b-it"
# LMSTUDIO_MODEL = "mistral-7b-instruct"
# LMSTUDIO_MODEL = "qwen3.5-27b"


# ══════════════════════════════════════════════════════════════
#  MODELO — GROQ API (cloud gratuito)
#  Usado quando BACKEND = "groq"
#  Limites gratuitos: ~14.400 req/dia | ~500K tokens/min
# ══════════════════════════════════════════════════════════════

# Obtenha em https://console.groq.com → API Keys → Create API Key
# Alternativa: defina a variável de ambiente  GROQ_API_KEY=gsk_...
GROQ_API_KEY = ""

GROQ_MODEL = "llama-3.1-8b-instant"     # Rápido, boa qualidade geral
# GROQ_MODEL = "gemma2-9b-it"            # Excelente em português brasileiro
# GROQ_MODEL = "mixtral-8x7b-32768"      # Maior contexto (32k tokens)
# GROQ_MODEL = "llama-3.3-70b-versatile" # Qualidade máxima disponível