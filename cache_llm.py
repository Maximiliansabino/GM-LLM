"""
cache_llm.py
─────────────────────────────────────────────────────────────
Cache de avaliações de criatividade para reduzir chamadas LLM.

Estratégia:
  1. Normaliza a ação (lowercase, sem pontuação extra)
  2. Calcula similaridade por bigramas de caracteres (rápido, sem deps)
  3. Se encontrar entrada com similaridade >= LIMIAR_SIMILARIDADE,
     retorna o score cacheado com leve variação aleatória (±JITTER)
     para evitar respostas idênticas repetidas
  4. Persiste o cache em disco (jornada/cache_criatividade.json)
     para reaproveitar entre sessões

Resultado: evita chamada LLM para ações muito parecidas com
ações já avaliadas anteriormente (ex: "ataco", "atacar",
"dou um golpe", variações do mesmo padrão básico).
─────────────────────────────────────────────────────────────
"""

import json
import os
import re
import random
from typing import Optional, Tuple

CACHE_FILE       = "jornada/cache_criatividade.json"
LIMIAR_SIMILAR   = 0.65   # similaridade mínima para cache hit (0–1)
JITTER           = 0.05   # variação aleatória aplicada ao score cacheado
MAX_ENTRADAS     = 200    # limite de entradas para não crescer indefinidamente


# ── Normalização ──────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    """Remove pontuação, espaços extras e coloca em lowercase."""
    texto = texto.lower().strip()
    texto = re.sub(r"[^\w\s]", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto


# ── Similaridade por bigramas ─────────────────────────────────

def _bigramas(texto: str) -> frozenset:
    return frozenset(texto[i:i+2] for i in range(len(texto) - 1))


def _similaridade(a: str, b: str,
                  ba: frozenset = None, bb: frozenset = None) -> float:
    """
    Coeficiente de Dice entre bigramas — aceita bigramas pré-computados
    para evitar recomputação quando um dos lados já é conhecido.
    """
    if not a or not b:
        return 0.0
    if ba is None: ba = _bigramas(a)
    if bb is None: bb = _bigramas(b)
    inter = len(ba & bb)
    total = len(ba) + len(bb)
    return (2 * inter / total) if total else 0.0


# ── Persistência ──────────────────────────────────────────────

def _carregar() -> list:
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _salvar(entradas: list) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    entradas = entradas[-MAX_ENTRADAS:]
    # Strip _bgs (frozenset) before JSON serialization
    clean = [{k: v for k, v in e.items() if k != "_bgs"} for e in entradas]
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


# ── API pública ───────────────────────────────────────────────

_cache_mem: list = []   # cache em memória carregado uma vez por sessão
_cache_carregado = False


def _garantir_carregado() -> None:
    global _cache_mem, _cache_carregado
    if not _cache_carregado:
        raw = _carregar()
        # Pre-compute bigramas on load
        for item in raw:
            if "_bgs" not in item:
                item["_bgs"] = _bigramas(item["acao_norm"])
        _cache_mem = raw
        _cache_carregado = True


def buscar(acao: str) -> Optional[Tuple[float, str]]:
    """
    Procura no cache uma ação similar usando bigramas pré-computados.
    Bigramas são calculados uma vez ao registrar e armazenados junto
    à entrada — evita recomputação durante a busca.
    Retorna (score, justificativa) com jitter, ou None se não encontrar.
    """
    _garantir_carregado()
    if not _cache_mem:
        return None

    norm = _normalizar(acao)
    bgs_query = _bigramas(norm)
    if not bgs_query:
        return None

    melhor_sim  = 0.0
    melhor_item = None

    for item in _cache_mem:
        # Use bigramas pré-computados quando disponíveis
        bgs_item = item.get("_bgs")
        if bgs_item is None:
            bgs_item = _bigramas(item["acao_norm"])
        sim = _similaridade(norm, item["acao_norm"], bgs_query, bgs_item)
        if sim > melhor_sim:
            melhor_sim  = sim
            melhor_item = item

    if melhor_sim >= LIMIAR_SIMILAR and melhor_item:
        score_base = melhor_item["score"]
        jitter     = random.uniform(-JITTER, JITTER)
        score      = round(max(0.5, min(1.0, score_base + jitter)), 3)
        just       = melhor_item["justificativa"]
        return score, just

    return None


def registrar(acao: str, score: float, justificativa: str) -> None:
    """Adiciona uma nova avaliação ao cache com bigramas pré-computados."""
    _garantir_carregado()
    norm = _normalizar(acao)
    entrada = {
        "acao_norm"    : norm,
        "score"        : round(score, 3),
        "justificativa": justificativa[:120],
        "_bgs"         : _bigramas(norm),   # pre-computed, not persisted
    }
    _cache_mem.append(entrada)
    _salvar(_cache_mem)


def stats() -> dict:
    """Retorna estatísticas do cache para debug."""
    _garantir_carregado()
    return {
        "entradas"  : len(_cache_mem),
        "arquivo"   : CACHE_FILE,
        "limiar"    : LIMIAR_SIMILAR,
        "max"       : MAX_ENTRADAS,
    }


def limpar() -> None:
    """Apaga o cache em disco e memória."""
    global _cache_mem
    _cache_mem = []
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    print("  [Cache] Limpo.")