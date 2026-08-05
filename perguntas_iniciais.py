"""
perguntas_iniciais.py
─────────────────────────────────────────────────────────────
5 perguntas narrativas logo após o jogador escolher o nome.
A LLM avalia a criatividade de cada resposta e o jogador
recebe bônus calibrados:

  Criatividade    Ψ ganho   Atributo ganho
  ──────────────────────────────────────────
  < 0.55          0.0 Ψ     0.0
  0.55 – 0.64     0.5 Ψ     0.0
  0.65 – 0.74     1.0 Ψ     0.0
  0.75 – 0.84     1.5 Ψ     0.3 (domínio da pergunta)
  0.85 – 0.94     2.0 Ψ     0.6
  ≥ 0.95          2.0 Ψ     1.0

Cada pergunta tem um "domínio": fisico ou mental.
  - fisico  → bônus vai para Força ou Vigor (corpo_fisico)
  - mental  → bônus vai para Conhecimento Explícito
─────────────────────────────────────────────────────────────
"""

import json
import re
import requests
import time
from typing import Tuple

from config import SYSTEM_PROMPT
from loading import spinner
try:
    import session_log as _slog
    _SLOG_OK = True
except ImportError:
    _SLOG_OK = False


# ── Perguntas ─────────────────────────────────────────────────

PERGUNTAS = [
    {
        "id": 1,
        "dominio": "mental",
        "texto_pt": (
            "Você acaba de encontrar um mapa rasgado dentro de um livro abandonado. "
            "O mapa parece indicar algo importante, mas metade está destruída. "
            "O que você faz?"
        ),
        "texto_en": (
            "You just found a torn map inside an abandoned book. "
            "The map seems to point to something important, but half is destroyed. "
            "What do you do?"
        ),
    },
    {
        "id": 2,
        "dominio": "fisico",
        "texto_pt": (
            "Uma criança está presa no galho mais alto de uma árvore enorme "
            "e não consegue descer. Não há escada por perto. O que você faz?"
        ),
        "texto_en": (
            "A child is stuck on the highest branch of a huge tree "
            "and cannot come down. There is no ladder nearby. What do you do?"
        ),
    },
    {
        "id": 3,
        "dominio": "mental",
        "texto_pt": (
            "Você precisa atravessar uma ponte guardada por um velho sábio que "
            "só deixa passar quem responder sua pergunta: "
            "\"O que é mais valioso: ouro, conhecimento ou coragem?\" "
            "O que você responde?"
        ),
        "texto_en": (
            "You need to cross a bridge guarded by a wise old man who "
            "only lets you pass if you answer his question: "
            "\"What is more valuable: gold, knowledge or courage?\" "
            "What do you answer?"
        ),
    },
    {
        "id": 4,
        "dominio": "fisico",
        "texto_pt": (
            "Você está acampado e percebe que um grupo de bandidos está se "
            "aproximando enquanto seus companheiros dormem. "
            "Você está sozinho de guarda. O que você faz?"
        ),
        "texto_en": (
            "You are camping and notice a group of bandits approaching "
            "while your companions sleep. You are alone on guard. What do you do?"
        ),
    },
    {
        "id": 5,
        "dominio": "mental",
        "texto_pt": (
            "Após uma batalha longa, você encontra um inimigo gravemente ferido "
            "que, momentos atrás, tentou te matar. Ele te pede ajuda. "
            "O que você faz?"
        ),
        "texto_en": (
            "After a long battle, you find a gravely wounded enemy "
            "who, moments ago, tried to kill you. He asks for your help. "
            "What do you do?"
        ),
    },
]


# ── Prompt de avaliação ───────────────────────────────────────

PROMPT_CRIATIVIDADE_PERGUNTA = """
Você avalia a qualidade narrativa de respostas em RPG. Responda APENAS com JSON.

ÂNCORAS — use estes exemplos para calibrar:
  0.5 = vaga ou sem relação ("não sei", "sim", "sair", resposta aleatória)
  0.6 = ação básica sem detalhes ("ataco", "fujo", "peço ajuda")
  0.7 = ação clara com intenção específica ("me escondo atrás das pedras e espero")
  0.8 = plano com lógica e propósito ("faço uma emboscada para eliminar o perigo antes que acordem")
  0.9 = combina contexto + criatividade + consequência ("finjo ser aliado para descobrir seu líder")
  1.0 = brilhante, original, revela personalidade única do personagem

REGRA PRINCIPAL — avalie a INTENÇÃO e ELABORAÇÃO, não a extensão:
  Uma resposta curta mas inteligente vale mais que uma longa e genérica.
  Uma ação com OBJETIVO CLARO e LÓGICA PRÓPRIA é 0.8 ou mais.
  Reserve 0.5 apenas para respostas incompreensíveis ou sem conexão com a situação.

FILTRO DE NONSENSE (aplique primeiro):
  Palavras inventadas sem sentido ("trolilora"), letras aleatórias → 0.5

EXEMPLOS de respostas para a situação de bandidos se aproximando:
  "fujo"                                              → 0.5
  "acordo todos"                                      → 0.6
  "me posiciono em silêncio e preparo um ataque"      → 0.7
  "faço uma emboscada e mato todos antes que acordem" → 0.8
  "apago a fogueira, acordo um amigo silenciosamente e armamos uma tocaia" → 0.9

RETORNE APENAS ESTE JSON:
{{"criatividade": 0.0, "comentario": "<1 frase narrativa sobre o que o jogador fez>"}}

Situação: {situacao}
Resposta do jogador: {resposta}
""".strip()


# ── LLM call (sem cache — respostas únicas) ───────────────────

# Palavras comuns em português — usadas para detectar nonsense
_PALAVRAS_PT = {
    "a","o","e","é","de","da","do","com","em","um","uma","que","se",
    "na","no","os","as","eu","me","meu","minha","ele","ela","nós","eles",
    "para","por","mas","não","sim","ser","ter","ir","vir","ver","dar","há",
    "ao","às","dos","das","sua","seu","este","esta","isso","aqui","lá",
    "como","mais","muito","todo","bem","já","ainda","só","até","então",
    "quando","onde","quem","qual","porque","assim","depois","antes","também",
    "pego","subo","luto","ataco","corro","fujo","ajudo","cuido","olho",
    "chamo","grito","escuto","vou","venho","fico","saio","entro","abro",
    "fecho","uso","tenho","posso","devo","quero","preciso","tento","faço",
    "mapa","livro","ponte","árvore","criança","bandido","inimigo","sábio",
    "ouro","conhecimento","coragem","galho","escada","caminho","floresta",
    "meus","minha","seus","sua","poderes","mentais","magicos","força",
    "espada","cajado","arma","magia","feitiço","poder","habilidade",
}

def _validar_resposta(resposta: str) -> tuple:
    """
    Valida se a resposta é legível antes de enviar ao LLM.
    Retorna (valida, cri_penalidade, comentario_penalidade).
    """
    import unicodedata
    stripped = resposta.strip().lower()

    # Mínimo absoluto
    if len(stripped) < 4:
        return False, 0.5, "Resposta muito curta — descreva uma ação."

    # Normaliza acentos para comparação
    def norm(s):
        return unicodedata.normalize("NFD", s).encode("ascii","ignore").decode()

    palavras = stripped.split()

    # Precisa de pelo menos 2 palavras
    if len(palavras) < 2:
        # Exceção: palavra única longa e reconhecível
        if len(stripped) >= 8 and any(c in "aeiou" for c in stripped):
            pass  # continue validation
        else:
            return False, 0.5, "Resposta muito curta — descreva uma ação."

    # Conta palavras reconhecíveis (em PT ou com padrão sílaba válido)
    def parece_palavra(p):
        # Está no vocabulário base
        if norm(p) in {norm(w) for w in _PALAVRAS_PT}:
            return True
        # Tem pelo menos 3 chars e padrão consoante-vogal válido
        if len(p) < 3:
            return False
        vogais = "aeiouáéíóúãõâêô"
        consoantes = "bcdfghjklmnpqrstvwxyz"
        # Deve ter pelo menos 1 vogal e não pode ser só consoantes
        tem_vogal = any(c in vogais for c in p)
        so_consoantes = all(c in consoantes for c in p if c.isalpha())
        if not tem_vogal or so_consoantes:
            return False
        # Verifica padrão CV: precisa de ao menos uma sequência consoante+vogal
        for i in range(len(p) - 1):
            if p[i] in consoantes and p[i+1] in vogais:
                return True
        # Ou começa com vogal (válido em PT)
        return p[0] in vogais

    reconhecidas = [p for p in palavras if parece_palavra(p)]
    proporcao = len(reconhecidas) / max(len(palavras), 1)

    # Menos de 40% das palavras são reconhecíveis → nonsense
    if proporcao < 0.40:
        return False, 0.5, "Resposta não compreendida — tente palavras em português."

    return True, None, None


def _avaliar_manualmente(resposta: str) -> float:
    """
    Avaliação heurística local quando o LLM está indisponível.
    Baseia-se em comprimento, vocabulário e estrutura da resposta.
    """
    r = resposta.strip().lower()
    palavras = r.split()
    n = len(palavras)

    # Base por comprimento (respostas longas tendem a ser mais elaboradas)
    if n <= 2:   cri = 0.50
    elif n <= 5: cri = 0.60
    elif n <= 10: cri = 0.68
    elif n <= 20: cri = 0.73
    else:         cri = 0.78

    # Bônus por palavras criativas
    criativos = {"porém","enquanto","além","primeiro","depois","entretanto",
                 "cuidadosamente","secretamente","habilmente","astutamente",
                 "combinando","aproveitando","usando","escondendo","marcando"}
    bonus = sum(0.03 for w in palavras if w in criativos)
    cri = min(0.90, cri + bonus)

    return round(cri, 2)


def _comentario_manual(cri: float) -> str:
    """Comentário local baseado no score heurístico."""
    if cri >= 0.80: return "Resposta elaborada e criativa."
    if cri >= 0.70: return "Boa resposta com detalhes relevantes."
    if cri >= 0.60: return "Resposta razoável."
    return "Resposta simples — tente elaborar mais."


def _avaliar_resposta(situacao: str, resposta: str) -> Tuple[float, str]:
    """Chama a LLM e retorna (criatividade, comentario)."""
    global _last_elapsed  # declarado UMA vez no topo da função
    _last_elapsed = 0.0   # valor padrão — substituído se LLM responder

    # Validate before sending to LLM
    valida, pen_cri, pen_com = _validar_resposta(resposta)
    if not valida:
        return pen_cri, pen_com

    prompt = PROMPT_CRIATIVIDADE_PERGUNTA.format(
        situacao=situacao, resposta=resposta
    )
    try:
        import llm_backend as lb
        import time as _time
        result = [None]
        _t0 = [0.0]
        def _call():
            _t0[0] = _time.time()
            # 120 tokens: enough for {"criatividade": 0.85, "comentario": "..."}
            result[0] = lb.chamar(prompt, SYSTEM_PROMPT, num_predict=120)
        with spinner("Avaliando sua resposta..."):
            _call()
        raw = result[0] or ""
        _last_elapsed = round(_time.time() - _t0[0], 3)

        # Robust JSON extraction: try full parse, then regex for {...}
        dados = {}
        try:
            dados = json.loads(raw)
        except Exception:
            # Find JSON object anywhere in the response (model may add preamble)
            m = re.search(r'\{[^{}]*"criatividade"[^{}]*\}', raw, re.DOTALL)
            if m:
                try:
                    dados = json.loads(m.group())
                except Exception:
                    pass

        # Extract criatividade — look for float in raw text as last resort
        if "criatividade" not in dados:
            m_float = re.search(r'"criatividade"\s*:\s*([0-9.]+)', raw)
            if m_float:
                dados["criatividade"] = float(m_float.group(1))

        cri = float(dados.get("criatividade", 0.75))
        cri = max(0.5, min(1.0, cri))

        # Extract comentario — fallback to cleaned raw text if not in JSON
        com = dados.get("comentario", "")
        if not com:
            # Strip JSON artifacts from raw text to use as comment
            com = re.sub(r'\{.*\}', '', raw, flags=re.DOTALL).strip()
            com = re.sub(r'[\n\r]+', ' ', com).strip()
            com = com[:120] if com else "Resposta avaliada."

        return cri, com
    except Exception as e:
        # Captura qualquer erro de conexão (HTTPError, OSError, ConnectionError, etc.)
        try:
            import llm_backend as _lb
            import importlib as _il; _il.reload(_lb)
            _dica = _lb.dica_conexao()
        except Exception:
            _dica = "Verifique a conexão com o servidor LLM"
        print(f"\n  \033[33m⚠  LLM indisponível — avaliação manual.\033[0m")
        cri = _avaliar_manualmente(resposta)
        return cri, _comentario_manual(cri)


# ── Tabela de bônus ───────────────────────────────────────────

def _calcular_bonus(criatividade: float) -> Tuple[float, float]:
    """Retorna (bonus_psique, bonus_atributo)."""
    if criatividade < 0.55:
        return 0.0, 0.0
    elif criatividade < 0.65:
        return 0.5, 0.0
    elif criatividade < 0.75:
        return 1.0, 0.0
    elif criatividade < 0.85:
        return 1.5, 0.3
    elif criatividade < 0.95:
        return 2.0, 0.6
    else:
        return 2.0, 1.0


# ── Interface principal ───────────────────────────────────────

def aplicar_bonus(personagem, bonus_psique: float, bonus_atributo: float, dominio: str) -> None:
    """Aplica os bônus diretamente no personagem."""
    if bonus_psique > 0:
        personagem.psique_base = round(personagem.psique_base + bonus_psique, 2)
        # Re-sync psique_atual
        personagem.psique_atual = personagem.psique_max

    if bonus_atributo > 0:
        if dominio == "fisico":
            # Distribui meio a meio entre força e vigor
            personagem.forca = round(personagem.forca + bonus_atributo / 2, 2)
            personagem.vigor = round(personagem.vigor + bonus_atributo / 2, 2)
        else:
            personagem.conhecimento_explicito = round(
                personagem.conhecimento_explicito + bonus_atributo, 2
            )
        # Re-sync pv_atual (corpo_fisico pode ter mudado)
        personagem.pv_atual = personagem.pv_max
        personagem.psique_atual = personagem.psique_max


def executar_perguntas_iniciais(personagem) -> None:
    """
    Exibe as 5 perguntas ao jogador após escolher o personagem.
    Aplica bônus de Psiquê e atributos baseados na criatividade das respostas.
    """
    global _last_elapsed, _last_tokens_p, _last_tokens_r
    _last_elapsed = 0.0
    _last_tokens_p = 0
    _last_tokens_r = 0
    from i18n import LANG

    print()
    print(f"  \033[1m{'═'*52}\033[0m")
    print(f"  \033[36m  AVALIAÇÃO INICIAL — Quem é você, aventureiro?\033[0m")
    print(f"  \033[90m  Responda com suas próprias palavras. Criatividade importa.\033[0m")
    print(f"  \033[1m{'═'*52}\033[0m")

    total_psi  = 0.0
    total_attr = 0.0
    ganhos = []

    for i, pergunta in enumerate(PERGUNTAS):
        texto = pergunta["texto_en"] if LANG == "en" else pergunta["texto_pt"]
        dominio = pergunta["dominio"]

        print()
        print(f"  \033[33m[{i+1}/5]\033[0m {texto}")
        print()

        while True:
            resposta = input("  Sua resposta > ").strip()
            if resposta:
                break
            print("  (Digite sua resposta para continuar)")

        criatividade, comentario = _avaliar_resposta(texto, resposta)
        bonus_psi, bonus_attr = _calcular_bonus(criatividade)

        # Feedback visual baseado na criatividade
        if criatividade >= 0.85:
            estrelas = "\033[33m★★★\033[0m"
            cor_com  = "\033[93m"   # amarelo brilhante
        elif criatividade >= 0.75:
            estrelas = "\033[33m★★\033[0m\033[90m☆\033[0m"
            cor_com  = "\033[32m"   # verde
        elif criatividade >= 0.65:
            estrelas = "\033[33m★\033[0m\033[90m☆☆\033[0m"
            cor_com  = "\033[36m"   # ciano
        else:
            estrelas = "\033[90m☆☆☆\033[0m"
            cor_com  = "\033[90m"   # cinza

        print(f"\n  {estrelas}  {cor_com}{comentario}\033[0m")

        # Mostrar bônus ganhos
        linha_bonus = []
        if bonus_psi > 0:
            linha_bonus.append(f"\033[35m+{bonus_psi:.1f} Ψ\033[0m")
        if bonus_attr > 0:
            if dominio == "fisico":
                linha_bonus.append(f"\033[32m+{bonus_attr:.1f} Corpo Físico\033[0m")
            else:
                linha_bonus.append(f"\033[36m+{bonus_attr:.1f} Conhecimento\033[0m")
        if linha_bonus:
            print(f"  Bônus: {' | '.join(linha_bonus)}")

        # Aplica imediatamente
        aplicar_bonus(personagem, bonus_psi, bonus_attr, dominio)
        total_psi  += bonus_psi
        total_attr += bonus_attr
        ganhos.append((criatividade, bonus_psi, bonus_attr, dominio))

        # Log no CSV
        if _SLOG_OK:
            _slog.log_questionario(
                pergunta_id    = pergunta["id"],
                dominio        = dominio,
                pergunta_texto = texto,
                resposta       = resposta,
                criatividade   = criatividade,
                comentario     = comentario,
                bonus_psique   = bonus_psi,
                bonus_atributo = bonus_attr,
                tempo_s        = _last_elapsed,
            )

    # ── Resumo final ────────────────────────────────────────
    print()
    print(f"  \033[1m{'─'*52}\033[0m")
    print(f"  \033[1m  Avaliação concluída!\033[0m")

    cf_final  = personagem.corpo_fisico
    cn_final  = personagem.conhecimento
    psi_final = personagem.psique_max

    print(f"  Psiquê total ganho   : \033[35m+{total_psi:.1f} Ψ\033[0m")
    print(f"  Atributo total ganho : \033[32m+{total_attr:.1f}\033[0m")
    print()
    print(f"  \033[90mCF: {cf_final:.1f}  |  Conhecimento: {cn_final:.2f}  |  "
          f"Ψ máx: {psi_final:.1f}\033[0m")
    print(f"  \033[1m{'─'*52}\033[0m")
    print()

    if _SLOG_OK:
        _slog.exibir_resumo_questionario(ganhos, personagem.nome)