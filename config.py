"""
config.py
─────────────────────────────────────────────────────────────
Configurações globais do sistema RPG com LLM local (Ollama).
Modelo: llama3.1:8b
─────────────────────────────────────────────────────────────
"""

# ── Conexão com Ollama ────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_API_URL  = f"{OLLAMA_BASE_URL}/api/chat"
LLM_MODEL       = "llama3.1:8b"
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS       = 1024  # fallback
LLM_TOKENS_AVALIACAO = 220   # combat eval — needs room for full JSON with componentes
LLM_TOKENS_NARRATIVA = 400   # scene descriptions
LLM_TOKENS_NPC       = 200   # NPC dialogue (max 4 lines)

# ── Parâmetros de Combate ─────────────────────────────────────
CRIATIVIDADE_MIN = 0.5
CRIATIVIDADE_MAX = 1.0
EFICIENCIA_MIN   = 0.5
EFICIENCIA_MAX   = 1.5

# Escala de dano — divide dano_personagem para calibrar combates
# Bioma 1: goblin morre em 3-6 turnos; boss bioma 11: 15-30 turnos
ESCALA_DANO      = 1.2

# ── Conhecimento como limite de caracteres ────────────────────
# Limite = Conhecimento * CHARS_POR_CONHECIMENTO
# Exemplo: Conhecimento 5.0 * 2 = 10 caracteres permitidos
CHARS_POR_CONHECIMENTO = 2

# ── Divisor de dano ───────────────────────────────────────────
# Dano final dividido por este valor para balancear os combates

# ── Frequência de treino e descanso ──────────────────────────
# O jogador pode treinar/dormir somente nas batalhas múltiplas
# deste número (exceto batalha 5 e 10 que têm eventos fixos).
# Ex: FREQUENCIA_DESCANSO = 3 → ocorre nas batalhas 3, 6, 9
FREQUENCIA_DESCANSO = 3

# ── Limites de Habilidades por Personagem ─────────────────────
MAX_HABILIDADES_ATIVAR   = 0
MAX_HABILIDADES_PASSIVAS = 7

# ── Psiquê como Mana ──────────────────────────────────────────
PSIQUE_REGEN_POR_BATALHA = 0.10
PSIQUE_REGEN_DORMIR      = 1.00

# ── Inventário ────────────────────────────────────────────────
SLOTS_INVENTARIO_BASE = 3
SLOTS_INVENTARIO_MAX  = 5

# ── Bioma ─────────────────────────────────────────────────────
COMBATES_POR_BIOMA   = 10
BATALHA_NPC_EVENTO   = 5
BATALHA_BOSS         = 10
ITENS_ESCOLHA_BOSS   = 3

# ── Arquivos de Persistência ──────────────────────────────────
JORNADA_DIR         = "jornada"
JORNADA_LOG_FILE    = "jornada/log.json"
JORNADA_ESTADO_FILE = "jornada/estado.json"

# ── Configurações de Narrativa ────────────────────────────────
# Controlado pelo idioma escolhido no menu — não edite manualmente
LINGUA_NARRATIVA = "pt-BR"   # "pt-BR" | "en-US"
ESTILO_NARRATIVA_PT = (
    "narrativa em segunda pessoa, tom épico mas acessível, "
    "descrições sensoriais ricas, pausas dramáticas com reticências"
)
ESTILO_NARRATIVA_EN = (
    "second-person narrative, epic yet accessible tone, "
    "rich sensory descriptions, dramatic pauses with ellipses"
)

def get_estilo_narrativa() -> str:
    from i18n import LANG
    return ESTILO_NARRATIVA_EN if LANG == "en" else ESTILO_NARRATIVA_PT

def get_lingua_narrativa() -> str:
    from i18n import LANG
    return "en-US" if LANG == "en" else "pt-BR"

# ── Seed ─────────────────────────────────────────────────────
# Seed baseada no tempo → inimigos e sorteios diferentes a cada sessão.
# Para reproduzir uma sessão específica, defina SEED manualmente e descomente random.seed(SEED).
import random
SEED = None   # None = seed aleatória por sessão
random.seed(SEED)

# ── System Prompt ─────────────────────────────────────────────
SYSTEM_PROMPT = """
Você é um Mestre de RPG autônomo, narrando uma aventura em português brasileiro.
Regras de comportamento:
1. Nunca invente fatos sobre o estado do mundo — consulte sempre o contexto fornecido.
2. Nunca contradiga informações já estabelecidas na jornada.
3. Avalie ações do jogador com base em criatividade (0.5–1.0) e eficiência (0.5–1.5).
4. Retorne SEMPRE JSON válido quando solicitado — sem texto adicional fora do JSON.
5. Mantenha consistência com os atributos e habilidades do personagem fornecidos.
6. NPCs têm personalidade consistente — nunca contradiga falas anteriores.
7. Na justificativa, use EXATAMENTE o nome do inimigo fornecido no campo "Inimigo:".
   NUNCA substitua o nome por outro inimigo, mesmo que pareça similar.
8. Base a justificativa APENAS nas fraquezas e resistências listadas. Não invente outras.
"""
# System prompt leve para narração — sem regras de JSON para evitar vazamento
SYSTEM_PROMPT_NARRACAO = (
    "Você é um Mestre de RPG narrando uma aventura em português brasileiro. "
    "Narre apenas o que for pedido, em segunda pessoa, de forma vívida e direta. "
    "Nunca repita instruções ou regras na resposta."
)

# ── Prompt único: avalia criatividade + eficiência em uma chamada ──
# Reduz latência pela metade ao eliminar uma round-trip ao LLM.
# ── Custo de Psiquê por componentes de ação ─────────────────
# Cada componente detectado na ação adiciona custo:
#   acao      = 0.5  (intenção de ataque direcionado, não "ataco" genérico)
#   intensidade = 0.5 (força concentrada, precisão, foco)
#   forma     = 0.5  (manipulação de posição/corpo: salto, giro, esquiva ativa)
#   elemento  = 1.0  (fogo, gelo, trovão, luz, trevas, arcano, veneno...)
#   tecnica   = 0.5  (nome de técnica, combo, estilo marcial)
#   magia     = 1.0  (conjuração explícita, invocação, ritual)
# Ação simples "ataco" → nenhum componente → 0 Ψ

CUSTOS_PSIQUE = {
    "acao"       : 0.5,
    "intensidade": 0.5,
    "forma"      : 0.5,
    "elemento"   : 1.0,
    "tecnica"    : 0.5,
    "magia"      : 1.0,
}

# ── Tipos de dano semântico detectados pela LLM ───────────────
# Físicos: multiplicadores definidos por item (semantica dict)
# Mágicos: elemento e forma já existem nos componentes de Psiquê
TIPOS_DANO_FISICO = ["corte", "perfurar", "impacto", "esmagamento", "choque"]
TIPOS_DANO_MAGICO = ["elemento", "forma", "magia"]

AVALIACAO_PROMPT = """
Avalie esta ação de combate em TRÊS aspectos. Responda com JSON exato.

=== CRIATIVIDADE (0.5–1.0) ===
Âncoras obrigatórias:
  0.5 = genérico: "ataco", "golpeio", "avanço"
  0.6 = direcionado: "golpeio no braço", "ataco pela esquerda"
  0.7 = usa contexto: "empurro contra a parede e golpeio"
  0.8 = tática: "finjo recuar e contra-ataco quando ele avança"
  0.9 = ambiente/item: "jogo areia nos olhos e golpeio por baixo"
  1.0 = brilhante: engano + ambiente + timing em combinação única
Regra: sem uso de ambiente/engano → máximo 0.7

=== EFICIÊNCIA (0.5–1.5) ===
  0.5 = ataque ineficaz contra esta defesa
  1.0 = ataque neutro/padrão
  1.5 = explora fraqueza direta do alvo

=== COMPONENTES DE PSIQUÊ ===
Detecte quais componentes estão presentes na ação (lista vazia se nenhum):
  "acao"        — intenção de ataque direcionado (NÃO inclua para "ataco" genérico)
  "intensidade" — força concentrada, precisão elevada, foco especial
  "forma"       — manipulação ativa de posição/corpo (salto, giro, esquiva ativa)
  "elemento"    — uso de elemento: fogo, gelo, trovão, luz, arcano, veneno, etc.
  "tecnica"     — nome de técnica, combo ou estilo marcial específico
  "magia"       — conjuração explícita, invocação, ritual, feitiço

=== TIPO DE DANO FÍSICO ===
Se a ação envolve ataque físico, identifique o tipo predominante (ou null se mágico/nenhum):
  "corte"       — lâmina deslizando (golpe de espada, faca)
  "perfurar"    — ponta penetrando (estocada, flecha, lança)
  "impacto"     — colisão sem corte (soco, pancada, cabo)
  "esmagamento" — pressão destruindo (esmagar, pisar, amassar)
  "choque"      — colisão de alta energia (investida, choque corpo a corpo)

Exemplos:
  "ataco"                    → componentes: [],           tipo_dano_fisico: null
  "golpeio com força"        → ["acao", "intensidade"],   tipo_dano_fisico: "impacto"
  "bola de fogo"             → ["forma", "elemento"],     tipo_dano_fisico: null
  "dou um corte"             → ["acao"],                  tipo_dano_fisico: "corte"
  "estoco com a espada"      → ["acao", "intensidade"],   tipo_dano_fisico: "perfurar"
  "invoco raio"              → ["elemento", "magia"],     tipo_dano_fisico: null

Responda SOMENTE com este JSON (sem texto fora dele):
{{"criatividade": <float>, "eficiencia": <float>, "justificativa": "<1 frase>", "componentes": [<lista de strings>], "tipo_dano_fisico": <string ou null>}}

REGRAS DA JUSTIFICATIVA:
- Escreva como NARRADOR em segunda pessoa, 1-2 frases vívidas de cena de batalha.
- ESTRUTURA: [descrição sensorial da ação] + [efeito no inimigo ou no ambiente].
- Se explorar fraqueza listada: mencione o efeito específico na criatura.
- Se não houver fraqueza: descreva o impacto físico real — chamas, impacto, som, reação do inimigo.
- NUNCA invente fraquezas ou características não listadas.
- Exemplos de tom:
    "Suas chamas varrem o Curupira — o espírito da floresta recua, consumido pelo próprio fogo que teme."
    "O golpe ecoa pela caverna, fazendo o Troll perder o equilíbrio por um instante."
    "A rajada de gelo congela o ar em volta do Jacaré, travando seus movimentos por um momento."

Ação: {acao}
Inimigo: {nome_inimigo}
Tipo de defesa: {tipo_defesa}
Fraquezas reais: {fraquezas}
Resistências: {resistencias}
Contexto: {contexto}
""".strip()

# Mantidos para compatibilidade retroativa (não usados no combate principal)
CRIATIVIDADE_PROMPT = AVALIACAO_PROMPT
EFICIENCIA_PROMPT   = AVALIACAO_PROMPT
