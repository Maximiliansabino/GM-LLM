# RPG_LLM_COMBATE_VERSION = "2026-03-29"
"""
combate.py
─────────────────────────────────────────────────────────────
Motor de combate.

Regras principais:
  • Limite de chars por ação = Conhecimento × CHARS_POR_CONHECIMENTO (2)
    → Exceder: "Você não tem conhecimento o bastante..."
  • Psiquê como mana: habilidades de ativar custam Psiquê
  • Dano = (comp_fisico + comp_arcano) × eficiência × criatividade²

Fórmulas:
  Limite chars    = int(Conhecimento × 2)
  Dano Personagem = (dano_arma/10) × (corpo_fisico/4) × (conhecimento×4)
  Dano Final      = (dano_personagem × eficiência × criatividade²) − defesa_alvo
─────────────────────────────────────────────────────────────
"""

import json, re
from typing import Tuple, Optional
import cache_llm
from loading import spinner
from i18n import t, name as iname
try:
    from referee import arbitrar, exibir_resultado
    _REFEREE_ATIVO = True
except ImportError:
    _REFEREE_ATIVO = False

try:
    import session_log as _slog
    _SLOG_OK = True
except ImportError:
    _SLOG_OK = False

try:
    from diplomacia_combate import (
        detectar_diplomacia, resolver_diplomacia, exibir_resultado_diplomacia
    )
    _DIPLO_ATIVO = True
except ImportError:
    _DIPLO_ATIVO = False

from status_effects import (
    detectar_efeito_acao, aplicar_efeito_inimigo, aplicar_efeito_personagem,
    processar_status_personagem, processar_status_inimigo,
    exibir_status_personagem, exibir_status_inimigo,
)
from i18n import LANG
from config import (
    OLLAMA_API_URL, LLM_MODEL, LLM_TEMPERATURE,
    LLM_TOKENS_AVALIACAO,
    SYSTEM_PROMPT, AVALIACAO_PROMPT, CUSTOS_PSIQUE,
    CRIATIVIDADE_MIN, CRIATIVIDADE_MAX, EFICIENCIA_MIN, EFICIENCIA_MAX,
    CHARS_POR_CONHECIMENTO,
)
from personagens import Personagem
from inimigos import Inimigo
import jornada as jrn
try:
    import memoria_rag as _rag
    _RAG_DISPONIVEL = True
except ImportError:
    _RAG_DISPONIVEL = False


# ── LLM ──────────────────────────────────────────────────────

def _chamar_llm(prompt: str, system: str = SYSTEM_PROMPT,
                label: str = "Avaliando...",
                num_predict: int = None) -> str:
    import llm_backend as lb
    if num_predict is None:
        num_predict = LLM_TOKENS_AVALIACAO
    fallback = '{"criatividade": 0.7, "eficiencia": 1.0, "justificativa": "fallback"}'
    try:
        result = [None]
        def _call():
            result[0] = lb.chamar(prompt, system, num_predict=num_predict)
        with spinner(label):
            _call()
        return result[0] or fallback
    except OSError as e:
        print(f"\n  \033[31m✖  Ollama indisponível — usando fallback de avaliação.\033[0m")
        print(f"  \033[90m   {__import__('llm_backend').dica_conexao()}\033[0m")
        return fallback
    except Exception as e:
        print(f"  \033[31m[ERRO LLM]\033[0m {type(e).__name__}: {str(e)[:80]}")
        return fallback


def _extrair_json(texto: str) -> dict:
    try:
        return json.loads(texto)
    except Exception:
        m = re.search(r'\{.*?\}', texto, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {}


# ── Limite de caracteres por Conhecimento ────────────────────

def limite_chars(personagem: Personagem) -> int:
    """Limite de chars = Conhecimento × 2 (mínimo 4)."""
    return max(4, int(personagem.conhecimento * CHARS_POR_CONHECIMENTO))


def _e_nonsense(acao: str) -> bool:
    """
    Detecta se a ação é nonsense — texto sem significado em português.
    Critérios:
      - Menos de 3 letras no total
      - Proporção de vogais < 20% (consoantes demais = nonsense)
      - Sem nenhuma palavra portuguesa reconhecível de 2+ letras
      - Apenas caracteres repetidos ou sequência de teclado
    """
    import re
    a = acao.lower().strip()
    letras = re.sub(r'[^a-záàãâéêíóôõúç]', '', a)

    # Palavras muito curtas sem vogal → nonsense
    # (2+ chars com vogal como "ok", "ei" são válidos)
    vogais = sum(1 for c in letras if c in "aáàãâeéêiíoóôõuúç")
    if len(letras) < 3 and vogais == 0:
        return True
    if len(letras) < 2:
        return True

    # Sequências de teclado óbvias
    _KBD = {"qwe","wer","ert","rty","tyu","yui","uio","iop",
             "asd","sdf","dfg","fgh","ghj","hjk","jkl",
             "zxc","xcv","cvb","vbn","bnm","qwerty","asdf","zxcv",
             "aaaa","bbbb","cccc","dddd","eeee","ffff","xxxx"}
    if a.replace(" ","") in _KBD or any(k in a for k in _KBD):
        return True

    # Proporção de vogais muito baixa (< 15% das letras)
    if len(letras) >= 3 and vogais / len(letras) < 0.15:
        return True

    # Sem nenhuma palavra com 1+ letras reais
    palavras = [p for p in re.split(r'\s+', a) if len(p) >= 1]
    if not palavras:
        return True

    return False


def validar_acao(acao: str, personagem: Personagem) -> bool:
    """
    Retorna True se a ação está dentro do limite e não é nonsense.
    Retorna False e exibe mensagem de bloqueio caso contrário.
    """
    # Filtro de nonsense — antes de qualquer outra validação
    if _e_nonsense(acao):
        print(f"  \033[33m⚠  '{acao}' não é uma ação reconhecível. "
              f"Descreva o que você faz (ex: 'ataco', 'bola de fogo', 'corto com a espada').\033[0m")
        return False

    limite = limite_chars(personagem)
    if len(acao) > limite:
        print(f"\n  ╔{'═'*51}╗")
        print(f"  ║  {t('combat.no_knowledge')[:49]:<49}║")
        print(f"  ╚{'═'*51}╝")
        print(f"  Limite: {limite} chars  |  Sua ação: {len(acao)} chars")
        print(f"  (Conhecimento {personagem.conhecimento:.1f} × 2 = {limite})")
        print(f"  {t('combat.rewrite')} {limite} {t('combat.chars')}.")
        return False
    return True


# ── Avaliações ────────────────────────────────────────────────

def calcular_custo_psique(componentes: list) -> float:
    """
    Soma os custos dos componentes detectados pela LLM.
    Retorna 0 para ação sem componentes (ex: "ataco" genérico).
    Robusto contra listas aninhadas e valores não-string da LLM.
    """
    flat = _normalizar_componentes(componentes)
    return round(sum(CUSTOS_PSIQUE.get(c, 0) for c in flat), 1)


def _normalizar_componentes(componentes) -> list:
    """
    Garante que componentes é sempre uma lista plana de strings.
    Trata: lista aninhada [[...]], valores None, não-string, etc.
    """
    if not isinstance(componentes, list):
        return []
    flat = []
    for c in componentes:
        if isinstance(c, list):
            # Aninhamento: [["acao", "tecnica"]] → ["acao", "tecnica"]
            for sub in c:
                if isinstance(sub, str) and sub:
                    flat.append(sub)
        elif isinstance(c, str) and c:
            flat.append(c)
        # None, int, dict etc. são silenciosamente ignorados
    return flat


# In-memory componentes cache (session only) — survives similarity-cache hits
_componentes_cache: dict = {}

# ── Keyword fallback detector ─────────────────────────────────
# Used when the LLM omits the componentes field (truncation at low token budgets)
_KW_ELEMENTO   = {"fogo","gelo","trovão","trovao","raio","relâmpago","relampago",
                   "luz","trevas","arcano","veneno","água","agua","terra","vento",
                   "ácido","acido","sangue","sombra","cristal","chamas",
                   # inglês
                   "fire","flame","burn","blaze","inferno",
                   "ice","frost","snow","freeze","frozen","cold","chill",
                   "thunder","lightning","electric","shock","volt","zap",
                   "poison","acid","venom","toxic","plague",
                   "shadow","dark","void","soul","death","necrotic",
                   "light","holy","arcane","chaos","curse","hex",
                   "water","wind","earth","nature","blood","crystal","magic"}
_KW_MAGIA      = {"invoco","conjuro","lanço","lanco","evoco","ritual","feitiço",
                   "feitico","magia","mágica","magica","encantamento","invocação",
                   # inglês
                   "cast","invoke","conjure","summon","spell","evoke","channel","incant"}
# Formas mágicas — dar forma ao feitiço
_KW_FORMA_MAGICA = {"bola","cone","rajada","onda","explosão","explosao","feixe",
                    "círculo","circulo","espiral","corrente","nuvem","pilar",
                    # inglês
                    "ball","bolt","beam","blast","wave","burst","orb","nova","strike","arrow"}

# Movimentos corporais — deslocamento do corpo do personagem
_KW_MOVIMENTO  = {"correr","corro","correndo","corra",
                   "pular","pulo","pulando","salto","saltar","saltando",
                   "rolar","rolo","rolando","rolamento",
                   "avançar","avançando","avanço e",
                   "recuar","recuando",
                   "girar","girando","giro e",
                   "mergulhar","mergulhando",
                   "esquivar","esquivando","esquiva e",
                   "deslizar","deslizando"}
# Nota: "salto","giro","avanço","esquiva","investida" são também substantivos de ação física
# — não entram em _KW_MOVIMENTO para não triggerar penalidade de movimento erroneamente

_KW_FORMA      = _KW_FORMA_MAGICA | _KW_MOVIMENTO  # mantido para compatibilidade com _detectar_componentes_fallback
_KW_TECNICA    = {"duplo","triplo","giratório","giratorio","perfurante","devastador",
                   "fulminante","cortante","preciso","certeiro","veloz","combo",
                   "corte duplo","golpe duplo","sequência","sequencia","finalizador"}
_KW_INTENSIDADE= {"máxima","maxima","total","plena","intensa","poderosa","brutal",
                   "extrema","concentrada","forte","violenta","com tudo","com toda",
                   "gigante","enorme","imensa","massiva","colossal","potente","avassaladora",
                   "força máxima","com força","força total","toda força","plena força",
                   # comparativos e superlativos de tamanho/poder
                   "maior","grande","mais forte","mais poderosa","mais intensa",
                   "mais potente","mais devastadora","amplificada","reforçada","carregada",
                   "concentrada","dobrada","triplicada","maximizada","turbinada",
                   # inglês
                   "bigger","larger","greater","massive","huge","giant","powerful",
                   "max","maximum","full power","stronger","boosted","enhanced","super"}
_KW_ACAO       = {"ataco com","firo","miro","foco em","concentro","direciono",
                   "lanço contra","miro em","golpeio com","ataque focado",
                   "miro no","aponto para","dirijo meu","direciono meu"}

# ── Ações defensivas ─────────────────────────────────────────
_KW_DEFESA = {
    # Português
    "defesa","defender","defendo","defende","defendi",
    "esquiva","esquivar","esquivo","esquivei","me esquivo",
    "bloqueio","bloquear","bloqueia","bloqueei","escudo",
    "paro","parar","aparar","aparei","aparo",
    "recuo","recuar","recuo e","me afasto","afasto",
    "rolo","rolar","rolamento","me jogo","me desvio","desvio",
    "proteção","proteger","me protejo","proteção","cubro",
    "guarda","postura de guarda","posição defensiva","firmo","me firmo",
    "agacho","agachar","me abaixo","abaixo","abaixar",
    # Inglês
    "defend","defense","block","blocking","dodge","dodging",
    "parry","parrying","evade","evading","shield","guard",
    "deflect","deflecting","roll","rolling",
}

def detectar_acao_defensiva(acao: str) -> bool:
    """
    Retorna True APENAS se a ação é PURAMENTE defensiva.
    Se contém palavras ofensivas junto (corte, golpe, ataque...),
    trata como ataque normal — o jogador quer defender E atacar.
    """
    a = acao.lower().strip()
    if not any(kw in a for kw in _KW_DEFESA):
        return False
    # Palavras que indicam intenção ofensiva junto com defesa
    _KW_OFENSIVA = {
        "corto","corte","golpe","golpeio","ataco","ataque","espada",
        "faca","lança","lanço","firo","miro","executo","execução",
        "apunhalo","perfuro","esmago","cut","slash","strike","hit",
        "attack","stab","blade","sword","contra atacar","contra-atacar",
        "e ataco","e golpeio","e corto","e executo","para atacar",
        "fatal","blow","flame","fire","trovão","trovejante",
    }
    if any(kw in a for kw in _KW_OFENSIVA):
        return False  # misto = ataque normal com componente defensivo
    return True


def calcular_reducao_defesa(acao: str, personagem) -> tuple:
    """
    Calcula a redução de dano e custo de Psiquê para ação defensiva.

    Retorna (reducao_pct, custo_psi, descricao)
      reducao_pct: 0.0 a 0.50 — percentual de dano reduzido
      custo_psi:   0.1 fixo por enquanto
      descricao:   texto exibido ao jogador
    """
    custo_psi = 0.1

    a = acao.lower()

    # Tipo de defesa influencia a redução
    if any(kw in a for kw in {"escudo","bloquear","bloqueio","block","shield","paro","aparar","parry"}):
        reducao_pct = 0.40   # bloqueio físico — mais eficiente
        desc = "bloqueio"
    elif any(kw in a for kw in {"esquiva","esquivar","dodge","evade","rolo","roll","desvio"}):
        reducao_pct = 0.35   # esquiva — eficiente mas gasta mais precisão
        desc = "esquiva"
    elif any(kw in a for kw in {"recuo","recuar","afasto","afastar"}):
        reducao_pct = 0.20   # recuo — menos eficiente mas sempre funciona
        desc = "recuo"
    else:
        reducao_pct = 0.25   # defesa genérica
        desc = "defesa"

    # Vigor aumenta levemente a eficiência
    vigor = getattr(personagem, "vigor", 10)
    bonus_vigor = min(0.10, (vigor - 10) * 0.01)
    reducao_pct = round(min(0.50, reducao_pct + bonus_vigor), 3)

    # Não pode defender se Psiquê insuficiente
    if personagem.psique_atual < custo_psi:
        return 0.0, 0.0, "Psiquê insuficiente para defender"

    return reducao_pct, custo_psi, desc


# ── Tipo de dano físico ───────────────────────────────────────
# Usa palavras isoladas (word-boundary check) para evitar falsos positivos.
# "corto" e "corte" cobrem "dou um corte", "corto o braço", etc.
_KW_TIPO_DANO = {
    "corte"      : {"corte","corto","corta","cortando","cortei","lâmina","lamina",
                    "fio da","slash","rasgo","rasgando","rasgou",
                    "cut","slice","cleave","hack","swing"},
    "perfurar"   : {"estoco","estocar","estocada","perfuro","perfura","perfurei",
                    "perfurante","furo","furar","ponta","flecha","espeto","espetar",
                    "trespassar","trespassa","traspassar","lanceio",
                    "stab","pierce","thrust","jab","impale","puncture"},
    "impacto"    : {"pancada","cabo","punho","soco","arremesso","baque","batida",
                    "chuto","martelada","martelar","bato com","bato no",
                    "golpe pesado","golpe brutal","golpe violento","golpe de escudo",
                    "golpe com o","golpeio com o","soco pesado","murro",
                    "golpeio com","ataco com a espada","ataco com minha"},
    "esmagamento": {"esmago","esmagar","esmagamento","amasso","amassar","piso",
                    "pisar","pressiono","comprimo","comprime","destruo","quebrando",
                    "trituro","triturar","aplano"},
    "choque"     : {"invisto","investida","investir","colido","colisão","choque",
                    "arremeto","arremetida","arremeter","carrego","carga"},
}

def _palavras(texto: str) -> set:
    """Retorna palavras individuais do texto normalizado."""
    import re
    return set(re.sub(r"[^\w\s]", "", texto.lower()).split())

def _detectar_tipo_dano_fisico(acao: str) -> str:
    """
    Detecta o tipo de dano físico por palavras-chave.
    Usa combinação de substring + word-match para cobrir variações.
    Retorna None para ações mágicas ou completamente neutras.
    """
    a = acao.lower()
    # Ações puramente mágicas → sem tipo físico
    if any(kw in a for kw in _KW_MAGIA | _KW_ELEMENTO):
        return None
    words = _palavras(a)
    for tipo, kws in _KW_TIPO_DANO.items():
        # Tenta substring primeiro (pega plurais, conjugações)
        if any(kw in a for kw in kws):
            return tipo
        # Depois word-exact (pega palavras curtas sem risco de substring errado)
        if any(kw in words for kw in kws):
            return tipo
    # Ação com intenção de ataque mas sem tipo específico → None (não força impacto)
    return None


def _detectar_penalidade_movimento(acao: str) -> bool:
    """
    Retorna True se a ação combina MOVIMENTO corporal + MAGIA/ELEMENTO.
    Exemplos que disparam: "vou correr e lançar bola de fogo"
                           "pulo e conjuro trovão"
                           "rolo e lanço rajada de água"
    Exemplos que NÃO disparam: "bola de fogo" (só magia)
                                "salto e golpeio" (movimento + físico)
                                "invoco raio" (só magia)
    """
    a = acao.lower()
    tem_movimento = any(kw in a for kw in _KW_MOVIMENTO)
    tem_magia     = any(kw in a for kw in _KW_MAGIA | _KW_ELEMENTO | _KW_FORMA_MAGICA)
    return tem_movimento and tem_magia


def _detectar_componentes_fallback(acao: str) -> list:
    """
    Detecção por palavras-chave como fallback quando o LLM não retorna componentes.
    Regras:
      elemento   — fogo, gelo, trovão, raio, veneno, arcano...
      magia      — invoco, conjuro, lanço, feitiço, ritual...
      forma      — formas mágicas (bola, cone, rajada) OU movimento corporal (salto, giro)
      tecnica    — duplo, triplo, cortante, veloz, combo, finalizador...
      intensidade— máxima, brutal, gigante, forte, poderosa...
      acao       — ataque direcionado explícito (ataco com, miro em, golpeio com...)
    Nota: "ataco" e "golpeio" genéricos NÃO geram 'acao' — só custam Psiquê quando
    combinados com modificadores (com força, miro em, etc.)
    """
    a = acao.lower()
    words = _palavras(a)
    comp = []
    if any(kw in a for kw in _KW_ELEMENTO):            comp.append("elemento")
    if any(kw in a for kw in _KW_MAGIA):                comp.append("magia")
    if any(kw in a for kw in _KW_FORMA_MAGICA):         comp.append("forma")
    if any(kw in a for kw in _KW_MOVIMENTO):            comp.append("forma")
    if any(kw in a for kw in _KW_TECNICA):              comp.append("tecnica")
    if any(kw in a for kw in _KW_INTENSIDADE):          comp.append("intensidade")
    if any(kw in a for kw in _KW_ACAO):                 comp.append("acao")
    return list(dict.fromkeys(comp))  # dedup, preserve order


def avaliar_acao(acao: str, inimigo, contexto: str) -> Tuple[float, float, str, list, str]:
    """
    Single LLM call returning (criatividade, eficiencia, justificativa, componentes).
    Componentes cached in-memory so psique costs survive score-cache hits.
    """
    import re as _re
    acao_norm = _re.sub(r"[^\w\s]", "", acao.lower().strip())

    cache_key_cri = acao
    # Inclui fraquezas na chave — evita compartilhar eficiência entre inimigos
    # com mesmo tipo_defesa mas fraquezas diferentes (lobo vs jacaré, ambos "natural")
    fraq_key = ",".join(sorted(inimigo.fraquezas)) if inimigo.fraquezas else ""
    cache_key_efi = f"{acao[:40]}|{inimigo.tipo_defesa}|{fraq_key}"

    hit_cri = cache_llm.buscar(cache_key_cri)
    hit_efi = cache_llm.buscar(cache_key_efi)

    if hit_cri and hit_efi:
        cri, just = hit_cri
        efi, _    = hit_efi
        efi = max(EFICIENCIA_MIN, min(EFICIENCIA_MAX, efi))
        # Restore componentes from memory cache.
        # If not in memory (e.g. first turn of session, cache loaded from disk),
        # always run keyword fallback so Psiquê is never silently skipped.
        componentes = _normalizar_componentes(_componentes_cache.get(acao_norm) or _detectar_componentes_fallback(acao))
        tipo_dano_fisico = _detectar_tipo_dano_fisico(acao)
        return cri, efi, just, componentes, tipo_dano_fisico

    # Build prompt with all needed context
    fraquezas_str   = ", ".join(inimigo.fraquezas)   if inimigo.fraquezas   else "nenhuma conhecida"
    resistencias_str = ", ".join(inimigo.resistencias) if inimigo.resistencias else "nenhuma"
    prompt = AVALIACAO_PROMPT.format(
        acao=acao,
        nome_inimigo=inimigo.nome,
        tipo_defesa=inimigo.tipo_defesa,
        fraquezas=fraquezas_str,
        resistencias=resistencias_str,
        contexto=contexto,
    )
    dados = _extrair_json(
        _chamar_llm(prompt, label=t("combat.creativity") + " + " + t("combat.efficiency"))
    )

    cri  = max(CRIATIVIDADE_MIN, min(CRIATIVIDADE_MAX, float(dados.get("criatividade", 0.7))))
    efi  = max(EFICIENCIA_MIN,   min(EFICIENCIA_MAX,   float(dados.get("eficiencia",   1.0))))
    just = dados.get("justificativa", "—")
    componentes      = _normalizar_componentes(dados.get("componentes", []))
    tipo_dano_fisico = dados.get("tipo_dano_fisico")  # "corte"|"perfurar"|"impacto"|"esmagamento"|"choque"|None

    # Fallback: if LLM omitted componentes, detect via keywords
    if not componentes:
        componentes = _detectar_componentes_fallback(acao)

    # Fallback: detect tipo_dano_fisico from keywords if LLM omitted it
    if not tipo_dano_fisico:
        tipo_dano_fisico = _detectar_tipo_dano_fisico(acao)

    # Cache scores
    if not hit_cri:
        cache_llm.registrar(cache_key_cri, cri, just)
    if not hit_efi:
        cache_llm.registrar(cache_key_efi, efi, just)

    # Store in memory cache
    _componentes_cache[acao_norm] = componentes

    return cri, efi, just, componentes, tipo_dano_fisico


# Keep old names as thin wrappers for any external callers
def avaliar_criatividade(acao: str, contexto: str) -> Tuple[float, str]:
    hit = cache_llm.buscar(acao)
    if hit:
        return hit
    return 0.7, "—"

def avaliar_eficiencia(tipo_ataque: str, defesa_alvo: str, fraquezas: list) -> Tuple[float, str]:
    hit = cache_llm.buscar(f"{tipo_ataque[:40]}|{defesa_alvo}")
    if hit:
        score, just = hit
        return max(EFICIENCIA_MIN, min(EFICIENCIA_MAX, score)), just
    return 1.0, "—"


# Passive skills always active — no menu in combat.


# ── Fórmula de dano ──────────────────────────────────────────

def calcular_dano_final(
    personagem: Personagem,
    inimigo: Inimigo,
    criatividade: float,
    eficiencia: float,
    habilidade_ativa=None,
    tipo_dano_fisico: str = None,
    penalidade_mov: bool = False,
    tem_intensidade: bool = False,
) -> Tuple[float, dict]:
    """
    Tabela de multiplicadores por arma × tipo de ação:

      Ação                  Espada (físico)        Cajado (mágico)
      ─────────────────────────────────────────────────────────────
      corte / perfurar    D_fis × 1.1             D_fis × 0.1 (ineficaz)
      impacto / choque    D_fis × 0.4             D_fis sem penalidade extra
      esmagamento         D_fis × 0.1             — (D_fis × 0.1)
      bola de fogo        D_fis × 0.1 (ineficaz)  D_mag × 1.0 (ideal)
      cajado + movimento  —                        D_mag × 0.6 (penalidade)
    """
    d_fis_base = personagem.dano_fisico_base()
    d_mag_base = personagem.dano_magico_base()
    item       = personagem.item_equipado
    tipo_arma  = item.tipo_dano if item else "fisico"
    restricoes = personagem.restricoes_arma
    sem        = personagem.semantica_arma
    fator_cri  = criatividade ** 1.5  # ^1.5 penaliza menos que ^2 — ações razoáveis não são destruídas

    # Detecta se é ação mágica:
    # - tem_intensidade vem de fora mas não temos a ação aqui
    # - usamos componentes_info passados via parâmetro quando disponível
    # Regra para espada (tipo_arma="fisico"):
    #   tipo=None + D_mag_base > D_fis_base → ação mágica (penaliza D_fis × 0.1)
    #   tipo=None + D_mag_base <= D_fis_base → ação neutra/física (mult=1.0)
    # Regra para cajado (tipo_arma="magico"):
    #   tipo=None → ação mágica ideal (mult_mag=1.0, mult_fis=0.0)
    #   tipo!=None → tentativa física com cajado (penalizada)
    d_fis_base = personagem.dano_fisico_base()
    d_mag_base = personagem.dano_magico_base()

    # ── Dano Físico ──────────────────────────────────────────
    # Regras por tipo de arma:
    # ESPADA (fisico):
    #   tipo=corte/perfurar → aplica semântica (1.1×)
    #   tipo=impacto/choque → semântica (0.4×)
    #   tipo=None           → ação neutra ou mágica
    #     • tem_intensidade=False → "ataco" genérico → neutro (1.0×)
    #     • tem_intensidade não importa — a LLM já avaliou efi baixa para espada+magia
    # CAJADO (magico):
    #   tipo=None → ação mágica ideal → sem D_fis (0.0)
    #   tipo!=None → ação física com cajado → semântica penalizada
    if tipo_arma == "fisico":
        if tipo_dano_fisico and sem:
            mult_fis = sem.get(tipo_dano_fisico, 1.0)
        else:
            mult_fis = 1.0   # "ataco", "golpeio" genérico → neutro
    else:
        # Cajado
        if tipo_dano_fisico and sem:
            mult_fis = sem.get(tipo_dano_fisico, 0.1)
        else:
            mult_fis = 0.0   # ação mágica pura com cajado: sem componente físico

    d_fis = d_fis_base * mult_fis * eficiencia * fator_cri

    # ── Bônus de Intensidade ─────────────────────────────────
    # +20% ao dano físico e mágico quando a ação tem intensidade detectada
    # ("bola de fogo gigante", "grande rajada de gelo", "golpe com força máxima")
    # Custo em Psiquê já cobrado separadamente em processar_turno_jogador.
    mult_intensidade = 1.20 if tem_intensidade else 1.0
    d_fis *= mult_intensidade

    # ── Dano Mágico ──────────────────────────────────────────
    if tipo_arma == "magico":
        # Penalidade: cajado + movimento corporal + magia na mesma ação
        # Detectado via cache de acao ou re-detectado aqui via keywords
        # _penalidade_mov é calculada em processar_turno_jogador e passada via param
        if "penalidade_movimento" in restricoes and penalidade_mov:
            mult_mag = 0.6   # -40%: "corro e lanço bola de fogo"
        else:
            mult_mag = 1.0   # ação mágica pura com cajado: ideal
    else:
        # Espada: mágico entra normalmente (base já pequeno para Kael)
        mult_mag = 1.0

    d_mag = d_mag_base * mult_mag * eficiencia * fator_cri * mult_intensidade

    dano_bruto = d_fis + d_mag
    dano_final = max(0, dano_bruto - inimigo.defesa)

    bd = {
        "criatividade"     : round(criatividade, 3),
        "criatividade²"    : round(fator_cri, 3),
        "eficiencia"       : round(eficiencia, 3),
        "tipo_dano_fisico" : tipo_dano_fisico or "—",
        "mult_semantico"   : round(mult_fis, 2),
        "intensidade"      : tem_intensidade,
        "penalidade_mov"   : penalidade_mov,
        "dano_fisico_base" : round(d_fis_base, 2),
        "dano_magico_base" : round(d_mag_base, 2),
        "dano_fisico"      : round(d_fis, 2),
        "dano_magico"      : round(d_mag, 2),
        "dano_bruto"       : round(dano_bruto, 2),
        "defesa_inimigo"   : inimigo.defesa,
        "dano_final"       : round(dano_final, 2),
        "dano_personagem"  : round(d_fis_base + d_mag_base, 2),  # legacy compat
    }

    if habilidade_ativa:
        ctx = {"dano_personagem": dano_personagem, "inimigo": inimigo.to_dict()}
        efeito = habilidade_ativa.aplicar_efeito(ctx)
        bd["habilidade_ativa"] = habilidade_ativa.nome
        bd["efeito"] = efeito

        if "multiplicador_golpes" in efeito:
            dano_final = (dano_final
                          * efeito["fator_dano"]
                          * efeito["multiplicador_golpes"])
        if "dano_bonus" in efeito:
            dano_final += efeito["dano_bonus"]
        if "eficiencia_bonus" in efeito:
            dano_final += efeito["eficiencia_bonus"] * dano_personagem * 0.3
        if "cura" in efeito:
            personagem.pv_atual = min(personagem.pv_max,
                                      personagem.pv_atual + efeito["cura"])
            print(f"  [Cura] +{efeito['cura']:.0f} PV → {personagem.pv_atual:.0f}")
        if "defesa_bonus_turno" in efeito:
            personagem.defesa_bonus_turno += efeito["defesa_bonus_turno"]
            print(f"  [Barreira] +{efeito['defesa_bonus_turno']:.0f} defesa neste turno")

        bd["dano_final_com_habilidade"] = round(dano_final, 2)

    return round(dano_final, 2), bd


def _narrar_ataque_jogador(
    acao: str, personagem, inimigo, dano_real: float, bd: dict,
    criatividade: float, eficiencia: float, just_aval: str,
    tipo_dano_fisico, penalidade_mov: bool, psi_insuficiente: bool
) -> None:
    """
    Exibe a narração do ataque do jogador.
    A LLM narra a cena em segunda pessoa — os dados técnicos ficam em segundo plano.

    Layout:
      [narração LLM — 1-2 frases vívidas]
      [stats em cinza: dano, PV inimigo, cri, efi — discretos]
    """
    from historias import _chamar_llm_narrativa
    import jornada as jrn

    nome_ini  = iname(inimigo)
    pj        = personagem.nome
    pv_ini_pct = int((inimigo.pv_atual / max(inimigo.pv_max, 1)) * 100)
    pv_pj_pct  = int((personagem.pv_atual / max(personagem.pv_max, 1)) * 100)
    arma      = personagem.item_equipado
    arma_nome = arma.nome if arma else "mãos nuas"
    fraquezas = ", ".join(inimigo.fraquezas) if inimigo.fraquezas else "nenhuma"

    # Qualidade do dano como guia narrativo
    dano_pct = dano_real / max(inimigo.pv_max, 1) * 100
    if dano_pct >= 30:
        impacto = "golpe devastador — o inimigo sofreu dano enorme"
    elif dano_pct >= 15:
        impacto = "golpe sólido e efetivo"
    elif dano_pct >= 5:
        impacto = "acerto moderado"
    else:
        impacto = "ataque fraco — pouco dano causado"

    mod_lista = []
    if penalidade_mov:     mod_lista.append("penalizado pelo movimento")
    if psi_insuficiente:   mod_lista.append("Psiquê insuficiente — ação enfraquecida")
    if bd.get("intensidade", False):
        mod_lista.append("concentrou força extra")
    modificadores = ", ".join(mod_lista) if mod_lista else "nenhum modificador"

    # Justificativa da LLM — usada como contexto adicional, não exibida diretamente
    contexto_just = ""
    if just_aval and just_aval not in ("—", "fallback", "Resposta avaliada."):
        contexto_just = f"  Avaliação interna: {just_aval[:80]}\n"

    # Monta lista de modificadores apenas com os que se aplicam
    _mods = []
    if eficiencia >= 1.3: _mods.append(f"explorou fraqueza: {fraquezas}")
    if penalidade_mov:     _mods.append("movimento atrapalhou a precisão")
    if psi_insuficiente:   _mods.append("ação enfraquecida por Psiquê insuficiente")
    if pv_ini_pct < 20:    _mods.append("inimigo quase derrotado")
    _mods_str = (", ".join(_mods) + ".") if _mods else ""

    prompt = (
        f"Narre em português, segunda pessoa (você), o seguinte ataque de RPG:\n"
        f"\n"
        f"Atacante: {pj}\n"
        f"Ação executada: \"{acao}\"\n"
        f"Alvo: {nome_ini}\n"
        f"Resultado: {impacto}\n"
        f"{('Detalhe: ' + _mods_str) if _mods_str else ''}\n"
        f"\n"
        f"Regras de consistência:\n"
        f"- Descreva APENAS a ação \"{acao}\" — não invente outro ataque\n"
        f"- Use SEMPRE o nome \"{nome_ini}\" para o inimigo\n"
        f"- Escreva em segunda pessoa: você, seu, sua (nunca eu/meu/minha)\n"
        f"- Descreva o efeito físico e visual da ação\n"
        f"- Sem números, sem PV, sem termos técnicos de jogo\n"
        f"- Sem pensamentos ou intenções do inimigo\n"
        f"- NUNCA invente personagens, eventos ou contexto não mencionados\n"
    )

    # Narração — stream para aparecer imediatamente
    # (stream já imprime os tokens; apenas define cor antes e reseta depois)
    print("  \033[97m", end="", flush=True)
    narracao = _chamar_llm_narrativa(
        prompt, "",
        num_predict=300, stream=True
    )
    print("\033[0m", flush=True)
    if _SLOG_OK and narracao:
        _slog.log_llm("narracao_jogador", acao[:120], narracao)

    # Fallback se Ollama indisponível — exibe a justificativa da avaliação
    if not narracao or "indisponível" in narracao or "ERRO" in narracao:
        if just_aval and just_aval not in ("—", "fallback"):
            print(f"  \033[90m{just_aval}\033[0m")

    # Stats discretos em cinza — informação de suporte, não protagonista
    psi_str = f"Ψ {personagem.psique_atual:.1f}  " if True else ""
    tipo_str = f"[{tipo_dano_fisico}]  " if tipo_dano_fisico else ""
    print(
        f"  \033[90m{tipo_str}"
        f"cri={criatividade:.2f}  efi={eficiencia:.2f}  "
        f"dano={dano_real:.1f}  "
        f"{nome_ini} {inimigo.pv_atual:.0f}/{inimigo.pv_max:.0f} PV\033[0m"
    )


# ── Turno do jogador ─────────────────────────────────────────

def processar_turno_jogador(acao: str, personagem: Personagem,
                             inimigo: Inimigo, turno: int) -> dict:
    print(f"\n  ── Turno {turno} ──")

    # ── Status effects do personagem (início do turno) ────────
    exibir_status_personagem(personagem)
    perde_turno = processar_status_personagem(personagem)

    # Ajuste de dano por congelar
    _mult_congelar = 0.70 if "congelar" in personagem.status_effects else 1.0
    # Ajuste de criatividade por confusão
    _pen_confusao  = -0.20 if "confundir" in personagem.status_effects else 0.0

    if perde_turno:
        print(f"  {personagem.nome} não consegue agir este turno!")
        return {"turno": turno, "acao": acao, "criatividade": 0.0,
                "eficiencia": 0.0, "breakdown": {}, "dano_causado": 0.0,
                "inimigo_vivo": inimigo.esta_vivo()}

    # ── Comandos de inventário (não consomem turno de combate) ─
    _acao_lower = acao.strip().lower()
    _CMDS_BOLSA   = {"usar", "bolsa", "poção", "pocao", "consumivel", "consumível"}
    _CMDS_EQUIPAR = {"equipar", "inv", "inventario", "inventário", "trocar"}

    if _acao_lower in _CMDS_BOLSA:
        try:
            from _item_ui import menu_usar_consumivel_combate
            ok, msg = menu_usar_consumivel_combate(personagem)
            print(f"  {msg}")
        except Exception as _e:
            print(f"  Erro: {_e}")
        return {"turno": turno, "acao": acao, "item_usado": True,
                "criatividade": 0.0, "eficiencia": 0.0, "breakdown": {},
                "dano_causado": 0.0, "inimigo_vivo": inimigo.esta_vivo()}

    if _acao_lower in _CMDS_EQUIPAR:
        try:
            from _item_ui import menu_equipar_inventario
            menu_equipar_inventario(personagem)
        except Exception as _e:
            print(f"  Erro: {_e}")
        return {"turno": turno, "acao": acao, "equipou": True,
                "criatividade": 0.0, "eficiencia": 0.0, "breakdown": {},
                "dano_causado": 0.0, "inimigo_vivo": inimigo.esta_vivo()}

    # ── Detectar ação defensiva (antes do LLM) ───────────
    _acao_eh_defesa = detectar_acao_defensiva(acao)
    _reducao_defesa = 0.0
    _custo_psi_def  = 0.0
    if _acao_eh_defesa:
        _reducao_defesa, _custo_psi_def, _desc_def = calcular_reducao_defesa(acao, personagem)
        if _custo_psi_def > 0:
            personagem.psique_atual = max(0, round(personagem.psique_atual - _custo_psi_def, 2))
            print(f"  \033[36m🛡 {_desc_def.capitalize()} preparada! "
                  f"Ψ -{_custo_psi_def:.1f} | "
                  f"Redução de dano: {int(_reducao_defesa*100)}%\033[0m")

    # Verificação de limite de conhecimento — só faz sentido dentro do loop
    # (esta função é chamada por turno, não tem loop próprio)

    # ── Referee — validação de regras ──────────────────────
    if _REFEREE_ATIVO:
        import jornada as _jrn2
        _estado_loc = _jrn2.obter_estado()
        _loc = _estado_loc.get('localizacao_atual', '?')
        # Usa _bioma_tipo do inimigo se disponível; senão tenta inferir da localização
        bioma_tipo = getattr(inimigo, '_bioma_tipo', None)
        if not bioma_tipo:
            _loc_lower = _loc.lower()
            if any(w in _loc_lower for w in ['deserto','areia','ossos','seco']):
                bioma_tipo = 'deserto'
            elif any(w in _loc_lower for w in ['pantano','pântano','lodoso','podridão']):
                bioma_tipo = 'pantano'
            elif any(w in _loc_lower for w in ['neve','gelo','pico','nevado','gelido','gelado']):
                bioma_tipo = 'gelido'
            elif any(w in _loc_lower for w in ['ruínas','ruinas','arcana','magia','mágico']):
                bioma_tipo = 'sombrio'
            elif any(w in _loc_lower for w in ['vulcão','vulcao','lava','chamas','vulcânico']):
                bioma_tipo = 'vulcanico'
            elif any(w in _loc_lower for w in ['agua','aqua','lago','rio','mar','oceano']):
                bioma_tipo = 'aquatico'
            else:
                bioma_tipo = 'floresta'  # padrão
        _ref = arbitrar(acao, personagem, inimigo,
                        bioma_tipo=bioma_tipo, localizacao=_loc, usar_llm=False)
        exibir_resultado(_ref)
        if _ref.bloqueado:
            return {"turno":turno,"acao":acao,"bloqueado":True,
                    "criatividade":0.0,"eficiencia":0.0,"breakdown":{},
                    "dano_causado":0.0,"inimigo_vivo":inimigo.esta_vivo()}
        _pen_referee = _ref.penalidade_cri
        _mod_efi_ref = _ref.mod_efi
    else:
        _pen_referee = 0.0
        _mod_efi_ref = 1.0

    contexto = (
        f"Personagem: {personagem.nome} "
        f"(CF={personagem.corpo_fisico:.1f}, "
        f"Conh={personagem.conhecimento:.2f}, "
        f"Psique={personagem.psique_atual:.1f}/{personagem.psique_max:.1f})."
    )

    t0_aval = __import__('time').time()
    # Ações puramente defensivas: avaliação simplificada sem custo de componentes
    if _acao_eh_defesa:
        criatividade  = 0.70   # defesa competente mas não criativa
        eficiencia    = 1.00
        just_aval     = f"Ação defensiva: {acao}."
        componentes   = []     # sem custo de Psiquê adicional
        tipo_dano_fisico = None
    else:
        criatividade, eficiencia, just_aval, componentes, tipo_dano_fisico = avaliar_acao(acao, inimigo, contexto)
    if _SLOG_OK:
        _slog.set_turno(turno)
        _slog.log_llm("avaliacao", acao, just_aval or "",
                      criatividade=criatividade, eficiencia=eficiencia,
                      tempo_s=round(__import__('time').time() - t0_aval, 3))

    # Aplicar penalidade do Referee + modificador ambiental
    criatividade  = max(0.5, criatividade - _pen_referee)
    eficiencia    = round(eficiencia * _mod_efi_ref, 3)

    # Penalidade de confusão e redução de dano por congelamento
    criatividade = max(0.50, criatividade + _pen_confusao)

    # ── Custo de Psiquê ───────────────────────────────────────
    custo_psi = calcular_custo_psique(componentes)
    psi_insuficiente = False
    if custo_psi > 0:
        if personagem.psique_atual >= custo_psi:
            personagem.psique_atual = round(max(0, personagem.psique_atual - custo_psi), 2)
            comp_str = " + ".join(componentes) if componentes else "—"
            psi_bar  = int((personagem.psique_atual / max(personagem.psique_max, 1)) * 16)
            psi_fill = "█" * psi_bar + "░" * (16 - psi_bar)
            print(f"  \033[35mΨ -{custo_psi:.1f}  [{psi_fill}] "
                  f"{personagem.psique_atual:.1f}/{personagem.psique_max:.1f}  "
                  f"({comp_str})\033[0m")
        else:
            psi_insuficiente = True
            criatividade = max(0.5, criatividade - 0.2)
            psi_bar  = int((personagem.psique_atual / max(personagem.psique_max, 1)) * 16)
            psi_fill = "█" * psi_bar + "░" * (16 - psi_bar)
            print(f"  \033[33mΨ insuficiente  [{psi_fill}] "
                  f"{personagem.psique_atual:.1f}/{personagem.psique_max:.1f}  "
                  f"— cri -{0.2:.1f}\033[0m")

    penalidade_mov  = _detectar_penalidade_movimento(acao)
    tem_intensidade = "intensidade" in componentes

    # Bônus de Psiquê na criatividade
    custo_psi_total = calcular_custo_psique(componentes)
    if custo_psi_total > 0:
        bonus_cri = min(0.20, custo_psi_total * 0.08)
        criatividade = round(min(1.0, criatividade + bonus_cri), 3)

    dano_final, bd = calcular_dano_final(
        personagem, inimigo, criatividade, eficiencia,
        tipo_dano_fisico=tipo_dano_fisico,
        penalidade_mov=penalidade_mov,
        tem_intensidade=tem_intensidade)
    dano_real = inimigo.receber_dano(dano_final)

    # ── Efeito de status ao inimigo ───────────────────────────
    efeito_status = detectar_efeito_acao(acao, componentes, tipo_dano_fisico, criatividade)
    if efeito_status:
        aplicar_efeito_inimigo(inimigo, efeito_status)

    # ── Narração do ataque do jogador via LLM ─────────────────
    _narrar_ataque_jogador(
        acao, personagem, inimigo, dano_real, bd,
        criatividade, eficiencia, just_aval,
        tipo_dano_fisico, penalidade_mov, psi_insuficiente
    )

    # Maestria
    if personagem.item_equipado:
        desbloqueou = personagem.item_equipado.ganhar_maestria(
            2.0 + criatividade * 3, "combate")
        if desbloqueou:
            aplicar_maestria(personagem)

    personagem.ganhar_conhecimento_tacito(0.1, "")

    return {
        "turno": turno, "acao": acao,
        "criatividade": criatividade, "eficiencia": eficiencia,
        "breakdown": bd, "dano_causado": dano_real,
        "inimigo_vivo": inimigo.esta_vivo(),
    }


# ── Narrativas de ataque do inimigo por tipo ─────────────────
_NARRATIVAS_INIMIGO = {
    # besta — ataques físicos animalescos
    "besta": [
        "{nome} avança com velocidade e lança uma mordida feroz em {pj}.",
        "{nome} ergue as garras e rasga com brutalidade o flanco de {pj}.",
        "{nome} investiu em {pj} com seu corpo inteiro.",
        "{nome} salta sobre {pj} com dentes expostos e olhos selvagens.",
        "{nome} usa seus reflexos e golpeia {pj} antes que ele(a) reaja.",
    ],
    # humanoide — ataques com armas ou técnica
    "humanoide": [
        "{nome} mira uma abertura e golpeia {pj} com precisão.",
        "{nome} desfere um ataque rápido que pega {pj} desprevenido(a).",
        "{nome} avança com sua arma e atinge {pj} no torso.",
        "{nome} executa um golpe lateral que {pj} não consegue desviar.",
        "{nome} aproveita um momento de distração e bate em {pj}.",
    ],
    # arcano — ataques mágicos ou sobrenaturais
    "arcano": [
        "{nome} libera uma descarga de energia que acerta {pj} em cheio.",
        "{nome} distorce o espaço ao redor de {pj} e causa dano arcano.",
        "{nome} conjura uma força invisível que empurra {pj} para trás.",
        "{nome} sussurra palavras antigas — uma onda de magia atinge {pj}.",
        "{nome} canaliza poder das sombras e golpeia {pj}.",
    ],
    # morto-vivo — ataques frios e perturbadores
    "morto-vivo": [
        "{nome} estende garras ressequidas e rasga {pj} com força sobrenatural.",
        "{nome} avança silenciosamente e atinge {pj} com golpe glacial.",
        "{nome} emite um grito gélido que paralisa {pj} por um instante.",
        "Os ossos de {nome} rangem enquanto ele desfere um golpe em {pj}.",
        "{nome} se move de forma estranha e atinge {pj} de um ângulo inesperado.",
    ],
    # elemental — ataques da natureza
    "elemental": [
        "{nome} projeta sua essência contra {pj} com força brutal.",
        "{nome} se expande e golpeia {pj} com toda a potência de sua forma.",
        "{nome} lança um fragmento de si mesmo contra {pj}.",
        "Uma extensão de {nome} atinge {pj} como uma onda imparável.",
        "{nome} desfere um golpe que ecoa com o poder dos elementos.",
    ],
}
_NARRATIVAS_EFEITO = {
    "queimar":      "O calor das chamas deixa uma marca dolorosa em {pj}.",
    "drenar_psique": "Uma névoa escura drena a concentração de {pj}.",
    "paralisar":    "{pj} sente os membros travarem por um instante.",
    "confundir":    "A mente de {pj} gira — os sentidos se embaralham.",
    "sangrar":      "Um corte profundo faz {pj} sangrar além do esperado.",
}


def _narrar_ataque_inimigo(inimigo, personagem, atk: dict, dano: float) -> None:
    """
    Narra o ataque do inimigo via LLM com streaming.
    A LLM recebe todos os dados reais e narra livremente.
    Templates como fallback se Ollama indisponível.
    """
    from historias import _chamar_llm_narrativa
    import jornada as jrn

    nome      = iname(inimigo)
    pj        = personagem.nome
    tipo      = getattr(inimigo, "tipo", "besta")
    especial  = atk.get("especial", False)
    efeito    = atk.get("efeito", "")
    descricao = atk.get("descricao", "")
    pv_pct    = int((personagem.pv_atual / max(personagem.pv_max, 1)) * 100)

    efeito_info = {
        "queimar":       "aplica queimadura",
        "drenar_psique": "drena energia mental do alvo",
        "paralisar":     "causa paralisia temporaria",
        "confundir":     "confunde os sentidos do alvo",
        "sangrar":       "causa sangramento adicional",
    }.get(efeito, "")

    tipo_info = {
        "besta":      "animal selvagem — ataca com dentes, garras ou peso corporal",
        "humanoide":  "combatente humanoide — usa armas, tecnicas ou astucia",
        "arcano":     "ser magico ou espiritual — usa poderes sobrenaturais",
        "morto-vivo": "ser nao-morto — golpe frio e sobrenatural",
        "elemental":  "forca da natureza — canaliza seu elemento como arma",
    }.get(tipo, "criatura desconhecida")

    ataque_desc = (atk["nome"] + " — " + descricao) if especial else f"ataque básico"
    efeito_str  = f" causando {efeito_info}" if efeito_info else ""
    critico_str = f" {pj} está em perigo crítico!" if pv_pct < 30 else ""

    prompt = (
        f"Narre em português, segunda pessoa (você), o seguinte ataque de RPG:\n"
        f"\n"
        f"Atacante: {nome} — {tipo_info}\n"
        f"Descrição da criatura: {inimigo.descricao[:100]}\n"
        f"Ataque: {ataque_desc}{efeito_str}\n"
        f"Alvo: {pj}\n"
        f"{critico_str}\n"
        f"\n"
        f"Regras de consistência:\n"
        f"- Use SEMPRE o nome \"{nome}\" para o atacante\n"
        f"- Descreva como ESTA criatura específica atacaria — baseado na descrição acima\n"
        f"- Escreva em segunda pessoa: você, seu, sua (nunca eu/meu/minha/não posso)\n"
        f"- Descreva o efeito físico e visual do ataque em {pj}\n"
        f"- Sem números, sem PV, sem termos técnicos de jogo\n"
        f"- Sem pensamentos, recusa, motivações ou diálogo do inimigo\n"
        f"- NUNCA invente personagens, eventos ou contexto que não foram mencionados\n"
    )

    print("  \033[31m", end="", flush=True)
    narracao = _chamar_llm_narrativa(
        prompt, "",
        num_predict=280, stream=True
    )
    print("\033[0m", flush=True)
    if _SLOG_OK and narracao:
        _slog.log_llm("narracao_inimigo", inimigo.nome, narracao)

    # Fallback se LLM indisponivel
    if not narracao or "indisponivel" in narracao or "ERRO" in narracao:
        import random as _rnd
        pool = _NARRATIVAS_INIMIGO.get(tipo, _NARRATIVAS_INIMIGO["besta"])
        frase = _rnd.choice(pool).format(nome=nome, pj=pj)
        efeito_n = _NARRATIVAS_EFEITO.get(efeito, "")
        if efeito_n:
            frase += " " + efeito_n.format(pj=pj)
        print(f"  \033[31m{frase}\033[0m")


def processar_turno_inimigo(inimigo: Inimigo,
                              personagem: Personagem,
                              reducao_defesa: float = 0.0) -> dict:
    # ── Status effects do inimigo (início do turno) ───────────
    exibir_status_inimigo(inimigo)
    dano_status, perde_turno_ini = processar_status_inimigo(inimigo)

    # Verifica morte por status antes de atacar
    if not inimigo.esta_vivo():
        print(f"  [32m{iname(inimigo)} sucumbiu aos efeitos de status![0m")
        return {"dano": 0.0, "ataque": "status", "especial": False,
                "personagem_vivo": personagem.esta_vivo()}

    if perde_turno_ini:
        return {"dano": 0.0, "ataque": "status_skip", "especial": False,
                "personagem_vivo": personagem.esta_vivo()}

    atk  = inimigo.escolher_ataque()
    dano = atk["dano"]
    # Congelado reduz dano do inimigo também
    if any(e["nome"] == "congelar" for e in getattr(inimigo, "status_effects", [])):
        dano *= 0.70

    efeito_str = ""

    if atk["especial"]:
        efeito = atk.get("efeito")
        if efeito:
            # Aplica o efeito como status persistente no personagem
            aplicar_efeito_personagem(personagem, efeito)
            defn = __import__("status_effects").EFEITOS.get(efeito, {})
            efeito_str = f" | {defn.get('cor','')}{defn.get('icone','')}{efeito}[0m"
            # Efeito imediato legado (compatibilidade)
            if efeito == "drenar_psique":
                drain = round(dano * 0.15, 1)
                personagem.psique_atual = max(0, personagem.psique_atual - drain)
                efeito_str += f" [35m-{drain:.1f}Ψ[0m"
            elif efeito == "paralisar":
                dano *= 0.8  # ataque de paralisia faz menos dano inicial

    # Aplica redução por defesa/esquiva do turno anterior
    dano_final = dano
    msg_defesa = ""
    if reducao_defesa > 0:
        dano_reduzido = round(dano * reducao_defesa, 1)
        dano_final    = round(max(1.0, dano - dano_reduzido), 1)
        msg_defesa    = (f"  \033[36m🛡 Defesa absorveu {dano_reduzido:.1f} de dano "
                         f"({int(reducao_defesa*100)}% reduzido)\033[0m")
        dano = dano_final

    personagem.receber_dano(dano)
    if msg_defesa:
        print(msg_defesa)

    # Narração do ataque via LLM (streaming — tokens aparecem enquanto chegam)
    _narrar_ataque_inimigo(inimigo, personagem, atk, dano)
    print(f"  Dano: {dano:.1f}{efeito_str} | "
          f"PV: {personagem.pv_atual:.1f}/{personagem.pv_max:.1f} | "
          f"Ψ: {personagem.psique_atual:.1f}/{personagem.psique_max:.1f}")

    return {"dano": round(dano, 2), "ataque": atk["nome"],
            "especial": atk["especial"],
            "personagem_vivo": personagem.esta_vivo()}


# ── Maestria → habilidade ─────────────────────────────────────

def aplicar_maestria(personagem: Personagem) -> None:
    from habilidades import obter_habilidade, CATALOGO_HABILIDADES
    item = personagem.item_equipado
    if not item:
        return
    for chave_hab in item.habilidades_item:
        hab_ref = CATALOGO_HABILIDADES.get(chave_hab)
        if not hab_ref:
            continue
        ja_tem = any(h.nome == hab_ref.nome
                     for h in (personagem.habilidades_ativar
                                + personagem.habilidades_passivas))
        if ja_tem:
            continue
        hab = obter_habilidade(chave_hab)
        if personagem.adicionar_habilidade(hab):
            print(f"\n  ✦ HABILIDADE DESBLOQUEADA: {hab.nome} (via {item.nome})")
            custo = f" — custo: {hab.custo_psique} Psique" if hab.custo_psique else ""
            print(f"    {hab.descricao}{custo}")
            jrn.registrar_habilidade_adquirida(
                hab.nome, hab.tipo, f"maestria:{item.nome}")



# ══════════════════════════════════════════════════════════════
#  HUD DE COMBATE
# ══════════════════════════════════════════════════════════════

def _barra(atual: float, maximo: float, largura: int = 20) -> str:
    pct    = max(0.0, min(1.0, atual / max(maximo, 1)))
    filled = round(pct * largura)
    empty  = largura - filled
    if pct > 0.5:    cor = "\033[32m"
    elif pct > 0.25: cor = "\033[33m"
    else:             cor = "\033[31m"
    bloco = "\u2588" * filled
    vazio = "\u2591" * empty
    return f"{cor}{bloco}\033[90m{vazio}\033[0m"


def exibir_hud_combate(personagem, inimigo) -> None:
    """HUD de combate — exibido a cada turno. Sem fraquezas e sem atributos."""
    L = 54
    _IC = {"queimar":"🔥","congelar":"❄️","paralisar":"⚡",
           "envenenar":"☠️","sangrar":"🩸",
           "drenar_psique":"💜","confundir":"💫"}

    print(f"\n  [36m{'=' * L}[0m")
    print(f"  [1m{personagem.nome}[0m  [90mvs[0m  [33m{inimigo.nome}[0m")
    print(f"  [90m{'-' * L}[0m")

    # Arte ASCII do inimigo
    try:
        from arte_inimigos import obter_arte
        lines = obter_arte(getattr(inimigo, '_chave', ''), inimigo.tipo).strip("\n").split("\n")
    except Exception:
        _artes = {
            "besta":       [" /V-V ",  "( ^.^ )", " > o < ", "  | |  "],
            "besta_lobo":  ["  /^^. ", " ( o.o)", "/|WwW| ", "  d b  "],
            "besta_corvo": [" ,~~.  ", "(o)(o) ", "  /NN  ", " ~~^^~~"],
            "besta_reptil":["__/^__ ", "(~___~)", " |___| ", " /---  "],
            "humanoide":   ["   o   ", "  -|-  ", "  | |  ", " /  .  "],
            "arcano":      ["  *.*  ", " (*V*) ", "  )|(  ", " ( ~ ) "],
            "morto-vivo":  ["  ___  ", " (x x) ", "  )--( ", " /|||  "],
            "elemental":   ["  ~*~  ", " *( )* ", "  ~*~  ", "  ~~~  "],
        }
        lines = _artes.get(tipo_arte, _artes.get(inimigo.tipo, ["  ???  "]))
    for line in lines[:5]:
        print(f"  [36m{line}[0m")

    # HP do inimigo
    print(f"  [90m{'-' * L}[0m")
    print(f"  [33m{inimigo.nome:<28}[90mN{inimigo.nivel} | {inimigo.tipo.upper()}[0m")
    print(f"  PV  [{_barra(inimigo.pv_atual, inimigo.pv_max, 24)}] "
          f"[97m{inimigo.pv_atual:.0f}[90m/{inimigo.pv_max:.0f}[0m")

    # Status effects do inimigo
    se_ini = getattr(inimigo, 'status_effects', [])
    if se_ini:
        se_str = "  ".join(
            f"{_IC.get(e.get('nome',''),'*')}[90m({e.get('duracao',0)}t)[0m"
            for e in se_ini
        )
        print(f"  {se_str}")

    # Separador + jogador
    print(f"  [36m{'-' * L}[0m")
    print(f"  [97m{personagem.nome}[0m  [90m{personagem.caminho}[0m")
    print(f"  [90m{'-' * L}[0m")

    # PV e Psiquê do jogador
    print(f"  ❤  PV  [{_barra(personagem.pv_atual, personagem.pv_max, 18)}] "
          f"[97m{personagem.pv_atual:.0f}/{personagem.pv_max:.0f}[0m")
    print(f"  💜 Psi [{_barra(personagem.psique_atual, personagem.psique_max, 18)}] "
          f"[97m{personagem.psique_atual:.1f}/{personagem.psique_max:.1f}[0m")

    # Status effects do jogador
    se_pj = getattr(personagem, 'status_effects', {})
    if se_pj:
        se_pj_str = "  ".join(
            f"{_IC.get(ef,'*')}[90m{ef}[0m" for ef in se_pj
        )
        print(f"  [31m⚠ {se_pj_str}[0m")

    print(f"  [36m{'=' * L}[0m")


def exibir_hud_pos_batalha(personagem) -> None:
    """Exibe atributos completos + arma + bolsa — apenas no final da batalha."""
    L = 54
    forca  = getattr(personagem, 'forca', 0)
    vigor  = getattr(personagem, 'vigor', 0)
    conh_t = getattr(personagem, 'conhecimento_tacito', 0)
    conh_e = getattr(personagem, 'conhecimento_explicito', 0)

    print(f"  [90m{'-' * L}[0m")
    print(f"  ⚔ Forca  [{_barra(forca, 20, 12)}] [97m{forca:.1f}[0m   "
          f"🛡 Vigor [{_barra(vigor, 20, 12)}] [97m{vigor:.1f}[0m")
    print(f"  📚 C.Tac [{_barra(conh_t, 10, 12)}] [97m{conh_t:.2f}[0m   "
          f"📖 C.Exp [{_barra(conh_e, 10, 12)}] [97m{conh_e:.2f}[0m")
    arma_nome = personagem.item_equipado.nome if personagem.item_equipado else "Desarmado"
    lim = limite_chars(personagem)
    print(f"  [90m{'-' * L}[0m")
    print(f"  🗡 {arma_nome:<22} 🎒 {len(personagem.bolsa)}/{personagem.BOLSA_MAX}  📝 {lim}ch")
    print(f"  [36m{'=' * L}[0m")

# ── Loop de combate ───────────────────────────────────────────

def iniciar_combate(personagem: Personagem, inimigo: Inimigo, bioma_key: str = "") -> str:
    """Retorna: 'vitoria' | 'derrota' | 'fuga'"""
    turno = 1
    dano_causado_total  = 0.0
    dano_recebido_total = 0.0
    acoes_destaque      = []

    # Propaga bioma_key para o inimigo se não já definido
    if bioma_key and not getattr(inimigo, "_bioma_tipo", None):
        inimigo._bioma_tipo = bioma_key
    _reducao_defesa = 0.0  # reset a cada turno
    while personagem.esta_vivo() and inimigo.esta_vivo():
        jrn.avancar_turno()
        _reducao_defesa = 0.0  # garante reset no início de cada turno

        exibir_hud_combate(personagem, inimigo)

        # Jogador descreve a ação
        acao = input(f"  {t('combat.your_action')} > ").strip()
        if not acao:
            continue

        flee_cmds = tuple(t("combat.flee_cmd").split(","))
        if acao.lower() in flee_cmds:
            print(f"  {t('combat.flee')}")
            jrn.registrar_combate(inimigo.nome, "fuga", turno,
                                   dano_causado_total, dano_recebido_total,
                                   acoes_destaque)
            return "fuga"

        # ── Diplomacia / atos de carinho ──────────────────────
        if _DIPLO_ATIVO and detectar_diplomacia(acao):
            res_diplo = resolver_diplomacia(acao, personagem, inimigo)
            exibir_resultado_diplomacia(res_diplo)

            if res_diplo.desfecho == "amizade":
                # Inimigo aceita amizade — combate termina
                if res_diplo.item_doado:
                    from _item_ui import receber_item
                    receber_item(personagem, res_diplo.item_doado)
                jrn.registrar_combate(inimigo.nome, "amizade", turno,
                                       dano_causado_total, dano_recebido_total,
                                       acoes_destaque)
                jrn.registrar_evento("diplomacia",
                    f"{personagem.nome} fez amizade com {inimigo.nome}",
                    {"acao": acao, "item": res_diplo.item_doado.nome if res_diplo.item_doado else None})
                return "amizade"

            elif res_diplo.desfecho == "fuga":
                # Inimigo foge — combate termina (vitória parcial)
                if res_diplo.item_roubado:
                    jrn.registrar_evento("diplomacia",
                        f"{inimigo.nome} fugiu levando {res_diplo.item_roubado.nome}",
                        {"item_roubado": res_diplo.item_roubado.nome})
                else:
                    jrn.registrar_evento("diplomacia",
                        f"{inimigo.nome} fugiu após gesto de carinho", {})
                return "fuga_inimigo"

            else:
                # Rejeição — narra tentativa do jogador + inimigo ataca
                print(f"  \033[90m{personagem.nome} tentou '{acao}' mas {inimigo.nome} rejeitou!\033[0m")
                rel_ini = processar_turno_inimigo(inimigo, personagem)
                dano_recebido_total += rel_ini.get("dano", 0)
                turno += 1
                continue


        rel = processar_turno_jogador(acao, personagem, inimigo, turno)
        dano_causado_total += rel["dano_causado"]
        if rel["criatividade"] >= 0.9:
            acoes_destaque.append(acao[:60])

        if inimigo.esta_vivo():
            rel_ini = processar_turno_inimigo(inimigo, personagem,
                                              reducao_defesa=_reducao_defesa)
            dano_recebido_total += rel_ini["dano"]
            _reducao_defesa = 0.0  # reset após usar

        turno += 1

    resultado = "vitoria" if not inimigo.esta_vivo() else "derrota"
    exibir_hud_pos_batalha(personagem)
    print(f"\n  {'🏆 ' + t('combat.victory') if resultado == 'vitoria' else '💀 ' + t('combat.defeat')}")

    if resultado == "vitoria":
        loot = inimigo.gerar_loot()
        for item_chave in loot:
            try:
                from itens import obter_item
                from _item_ui import receber_item
                item_drop = obter_item(item_chave)
                print(f"\n  🎁 {t('combat.loot')}: {iname(item_drop)}")
                receber_item(personagem, item_drop)
                jrn.registrar_item_obtido(item_chave, f"loot:{inimigo.nome}")
            except KeyError:
                print(f"  Loot desconhecido: {item_chave}")
        jrn.registrar_inimigo_derrotado(inimigo.nome, inimigo.nivel, loot)
        personagem.ganhar_conhecimento_tacito(
            0.5 * inimigo.nivel, "")

    jrn.registrar_combate(inimigo.nome, resultado, turno,
                          dano_causado_total, dano_recebido_total,
                          acoes_destaque)
    jrn.atualizar_personagem(personagem.to_dict())
    if _SLOG_OK:
        _slog.exibir_stats_sessao()
    return resultado


if __name__ == "__main__":
    from personagens import criar_kael
    from inimigos import obter_inimigo
    kael = criar_kael()
    goblin = obter_inimigo("goblin_batedeiro")
    dano, bd = calcular_dano_final(kael, goblin, 0.85, 1.2)
    print(f"Dano final: {dano}")
    print(json.dumps(bd, indent=2, ensure_ascii=False))
    print(f"\nLimite de chars — Kael: {limite_chars(kael)}")