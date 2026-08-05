"""
memoria_rag.py
─────────────────────────────────────────────────────────────
Sistema de Memória de Longo Prazo com RAG para o RPG GM LLM.

Componentes:
  1. Sumarização automática — a cada N eventos, gera resumo via LLM
     e comprime o log para evitar overflow de contexto.
  2. Busca semântica — recupera eventos relevantes por similaridade
     TF-IDF (sem dependência de GPU ou embeddings pesados).
  3. Integração com jornada.py — injeta contexto relevante nos prompts.

Uso:
  from memoria_rag import obter_contexto_rag, registrar_e_comprimir

Estratégia de compressão:
  - Eventos recentes (< JANELA_RECENTE turnos): mantidos integralmente
  - Eventos antigos (>= JANELA_RECENTE turnos): sumarizados em blocos
  - Fatos permanentes (NPCs, segredos, inimigos derrotados): sempre incluídos

Referência DSR:
  LIU et al. (2024) — Retrieval-Augmented Generation for Consistent
  Role-Playing Game Narratives. IEEE Transactions on Games, v.16, n.2.
"""

from __future__ import annotations
import json
import math
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Optional

import jornada as jrn

# ── Configurações ─────────────────────────────────────────────
JANELA_RECENTE    = 8    # últimos N turnos mantidos integralmente
BLOCO_SUMARIZACAO = 12   # sumarizar quando houver >= N eventos antigos
MAX_TOKENS_CTX    = 800  # limite aproximado de tokens no contexto RAG
ARQUIVO_RESUMOS   = "jornada/resumos_sessao.json"

# ── Estruturas de dados ───────────────────────────────────────

@dataclass
class ResumoBloco:
    """Resumo comprimido de um bloco de eventos antigos."""
    turno_inicio: int
    turno_fim:    int
    texto:        str
    temas:        List[str] = field(default_factory=list)


@dataclass
class EntradaMemoria:
    """Evento indexado para busca semântica."""
    turno:      int
    tipo:       str
    descricao:  str
    tokens:     List[str] = field(default_factory=list)   # para TF-IDF


# ── Cache em memória ──────────────────────────────────────────
_resumos:  List[ResumoBloco]  = []
_indice:   List[EntradaMemoria] = []
_idf_cache: Dict[str, float]  = {}
_carregado: bool = False


# ══════════════════════════════════════════════════════════════
#  1. CARREGAMENTO E PERSISTÊNCIA
# ══════════════════════════════════════════════════════════════

def _carregar() -> None:
    global _resumos, _indice, _carregado
    os.makedirs("jornada", exist_ok=True)
    if os.path.exists(ARQUIVO_RESUMOS):
        with open(ARQUIVO_RESUMOS, encoding="utf-8") as f:
            dados = json.load(f)
        _resumos = [ResumoBloco(**r) for r in dados.get("resumos", [])]
    # Reconstrói índice a partir do log atual
    _reindexar()
    _carregado = True


def _salvar() -> None:
    os.makedirs("jornada", exist_ok=True)
    with open(ARQUIVO_RESUMOS, "w", encoding="utf-8") as f:
        json.dump({
            "resumos": [
                {"turno_inicio": r.turno_inicio, "turno_fim": r.turno_fim,
                 "texto": r.texto, "temas": r.temas}
                for r in _resumos
            ]
        }, f, ensure_ascii=False, indent=2)


def _reindexar() -> None:
    """Reconstrói o índice TF-IDF a partir do log completo."""
    global _indice, _idf_cache
    eventos = jrn.obter_log_completo()
    _indice = []
    for ev in eventos:
        tokens = _tokenizar(ev.get("descricao", ""))
        _indice.append(EntradaMemoria(
            turno=ev.get("turno", 0),
            tipo=ev.get("tipo", ""),
            descricao=ev.get("descricao", ""),
            tokens=tokens,
        ))
    _idf_cache = _calcular_idf(_indice)


# ══════════════════════════════════════════════════════════════
#  2. TF-IDF LEVE (sem dependências externas)
# ══════════════════════════════════════════════════════════════

_STOPWORDS = {
    "o","a","os","as","um","uma","uns","umas","de","do","da","dos","das",
    "em","no","na","nos","nas","por","para","com","sem","sob","sobre",
    "e","ou","que","se","não","foi","era","está","ser","ter","isso","este",
    "este","essa","esse","aquele","aquela","como","mais","mas","também",
    "the","a","an","in","on","at","to","for","with","and","or","is","was",
}

def _tokenizar(texto: str) -> List[str]:
    tokens = re.findall(r"[a-záàãâéêíóôõúç]{3,}", texto.lower())
    return [t for t in tokens if t not in _STOPWORDS]


def _calcular_idf(entradas: List[EntradaMemoria]) -> Dict[str, float]:
    N = len(entradas) + 1
    df: Dict[str, int] = defaultdict(int)
    for e in entradas:
        for t in set(e.tokens):
            df[t] += 1
    return {t: math.log(N / (freq + 1)) for t, freq in df.items()}


def _score_tfidf(query_tokens: List[str], entrada: EntradaMemoria) -> float:
    if not entrada.tokens or not query_tokens:
        return 0.0
    tf: Dict[str, float] = defaultdict(float)
    for t in entrada.tokens:
        tf[t] += 1.0 / len(entrada.tokens)
    score = 0.0
    for qt in query_tokens:
        score += tf.get(qt, 0.0) * _idf_cache.get(qt, 0.0)
    return score


def buscar_eventos_relevantes(query: str, k: int = 4,
                               turno_atual: Optional[int] = None) -> List[EntradaMemoria]:
    """
    Retorna os k eventos mais relevantes para a query.
    Eventos recentes recebem boost automático.
    """
    if not _carregado:
        _carregar()
    if not _indice:
        return []

    q_tokens = _tokenizar(query)
    turno_max = turno_atual or (max(e.turno for e in _indice) if _indice else 0)

    scored = []
    for entrada in _indice:
        base = _score_tfidf(q_tokens, entrada)
        # Boost para eventos recentes (últimos JANELA_RECENTE turnos)
        recencia = 1 + (0.5 if turno_max - entrada.turno <= JANELA_RECENTE else 0)
        scored.append((base * recencia, entrada))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:k] if scored[0][0] > 0]


# ══════════════════════════════════════════════════════════════
#  3. SUMARIZAÇÃO AUTOMÁTICA VIA LLM
# ══════════════════════════════════════════════════════════════

def _sumarizar_bloco(eventos: List[dict]) -> str:
    """
    Gera um resumo conciso de um bloco de eventos via LLM.
    Fallback: concatena as descrições mais importantes.
    """
    try:
        from historias import _chamar_llm_narrativa
        textos = "\n".join(
            f"T{ev['turno']:02d}[{ev['tipo']}]: {ev['descricao'][:120]}"
            for ev in eventos
        )
        prompt = (
            f"Resuma em 2-3 frases concisas os seguintes eventos de uma sessão de RPG, "
            f"mantendo os fatos mais importantes (nomes, lugares, resultados de combate, "
            f"itens obtidos, NPCs encontrados):\n\n{textos}\n\nResumo:"
        )
        resumo = _chamar_llm_narrativa(prompt, contexto_jornada="",
                                        num_predict=120, stream=False)
        if resumo and len(resumo) > 20:
            return resumo.strip()
    except Exception:
        pass

    # Fallback: seleciona eventos mais importantes por tipo
    PRIORIDADE = {"combate": 3, "vitoria": 3, "item": 2, "npc": 2,
                  "narrativa": 1, "movimento": 0}
    selecionados = sorted(
        eventos,
        key=lambda e: PRIORIDADE.get(e.get("tipo", ""), 0),
        reverse=True
    )[:4]
    return " | ".join(e["descricao"][:80] for e in selecionados)


def comprimir_se_necessario() -> bool:
    """
    Verifica se há eventos antigos suficientes para sumarizar.
    Retorna True se comprimiu algo.
    """
    if not _carregado:
        _carregar()

    eventos = jrn.obter_log_completo()
    turno_atual = jrn.obter_estado().get("turno", 0)
    corte = turno_atual - JANELA_RECENTE

    # Eventos que já passaram da janela recente
    antigos = [ev for ev in eventos if ev.get("turno", 0) < corte]

    # Verifica se já foram resumidos
    turno_ja_resumido = max((r.turno_fim for r in _resumos), default=-1)
    nao_resumidos = [ev for ev in antigos if ev.get("turno", 0) > turno_ja_resumido]

    if len(nao_resumidos) < BLOCO_SUMARIZACAO:
        return False

    # Agrupa em blocos de BLOCO_SUMARIZACAO
    for i in range(0, len(nao_resumidos), BLOCO_SUMARIZACAO):
        bloco = nao_resumidos[i:i + BLOCO_SUMARIZACAO]
        if len(bloco) < BLOCO_SUMARIZACAO // 2:
            break  # bloco muito pequeno — aguarda mais eventos

        texto_resumo = _sumarizar_bloco(bloco)
        temas = list(set(ev.get("tipo", "") for ev in bloco))

        _resumos.append(ResumoBloco(
            turno_inicio=bloco[0]["turno"],
            turno_fim=bloco[-1]["turno"],
            texto=texto_resumo,
            temas=temas,
        ))

    _salvar()
    _reindexar()
    return True


# ══════════════════════════════════════════════════════════════
#  4. CONTEXTO RAG PARA INJEÇÃO NOS PROMPTS
# ══════════════════════════════════════════════════════════════

def obter_contexto_rag(query: str = "", max_tokens: int = MAX_TOKENS_CTX) -> str:
    """
    Retorna bloco de contexto otimizado para injeção nos prompts LLM.

    Estrutura:
      [Fatos Permanentes] — NPCs, segredos, itens importantes
      [Resumos de Sessão] — blocos antigos comprimidos
      [Eventos Relevantes] — eventos recentes + semanticamente similares
      [Estado Atual] — localização, PV, Psiquê

    max_tokens: limite aproximado (1 token ≈ 4 chars).
    """
    if not _carregado:
        _carregar()

    estado  = jrn.obter_estado()
    turno   = estado.get("turno", 0)
    budget  = max_tokens * 4  # em chars

    blocos: List[str] = []

    # ── Fatos permanentes ─────────────────────────────────────
    fatos: List[str] = []

    npcs = estado.get("npcs_conhecidos", {})
    for nome, info in list(npcs.items())[:6]:
        fatos.append(f"NPC {nome} ({info.get('atitude','?')}): {info.get('descricao','')[:60]}")

    inimigos_derrotados = estado.get("inimigos_derrotados", [])
    if inimigos_derrotados:
        nomes = [i.get("nome","?") for i in inimigos_derrotados[-5:]]
        fatos.append(f"Inimigos derrotados: {', '.join(nomes)}")

    segredos = estado.get("segredos_descobertos", [])
    for seg in segredos[-3:]:
        fatos.append(f"Fato estabelecido: {seg.get('descricao','')[:80]}")

    itens = estado.get("itens_obtidos", [])
    if itens:
        nomes_itens = [i.get("nome","?") for i in itens[-4:]]
        fatos.append(f"Itens obtidos: {', '.join(nomes_itens)}")

    if fatos:
        bloco_fatos = "[ Fatos da Sessão ]\n" + "\n".join(f"  • {f}" for f in fatos)
        blocos.append(bloco_fatos)

    # ── Resumos de blocos antigos ─────────────────────────────
    if _resumos:
        linhas_resumos = []
        for r in _resumos[-4:]:  # últimos 4 resumos
            linhas_resumos.append(
                f"  T{r.turno_inicio:02d}-T{r.turno_fim:02d}: {r.texto}"
            )
        blocos.append("[ Resumo de Eventos Anteriores ]\n" + "\n".join(linhas_resumos))

    # ── Eventos recentes (janela deslizante) ──────────────────
    todos_eventos = jrn.obter_log_completo()
    recentes = [ev for ev in todos_eventos if ev.get("turno", 0) >= turno - JANELA_RECENTE]

    # ── Busca semântica por eventos relevantes ─────────────────
    if query and _indice:
        relevantes = buscar_eventos_relevantes(query, k=3, turno_atual=turno)
        # Adiciona eventos relevantes que não estão nos recentes
        turnos_recentes = {ev.get("turno", 0) for ev in recentes}
        extras = [e for e in relevantes if e.turno not in turnos_recentes]
        if extras:
            linhas_extra = [
                f"  T{e.turno:02d}[{e.tipo}] {e.descricao[:80]}"
                for e in extras
            ]
            blocos.append("[ Eventos Relacionados (semântica) ]\n" + "\n".join(linhas_extra))

    if recentes:
        linhas_rec = [
            f"  T{ev.get('turno',0):02d}[{ev.get('tipo','?'):10}] {ev.get('descricao','')[:90]}"
            for ev in recentes[-JANELA_RECENTE:]
        ]
        blocos.append(f"[ Últimos {len(linhas_rec)} Eventos ]\n" + "\n".join(linhas_rec))

    # ── Estado atual ──────────────────────────────────────────
    pj = estado.get("personagem", {})
    loc = estado.get("localizacao_atual", "?")

    def _fmt(val, spec):
        try: return format(float(val), spec)
        except: return "?"

    estado_linha = (
        f"[ Estado Atual | T{turno} | {loc} ]\n"
        f"  {pj.get('nome','?')} — "
        f"PV {_fmt(pj.get('pv_atual'),'.0f')}/{_fmt(pj.get('pv_max'),'.0f')} | "
        f"Ψ {_fmt(pj.get('psique_atual'),'.1f')}/{_fmt(pj.get('psique_max'),'.1f')}"
    )
    blocos.append(estado_linha)

    # ── Montar e truncar se necessário ────────────────────────
    ctx_completo = "\n\n".join(blocos)
    if len(ctx_completo) > budget:
        ctx_completo = ctx_completo[:budget] + "\n[... contexto truncado ...]"

    return ctx_completo


# ══════════════════════════════════════════════════════════════
#  5. INTERFACE PRINCIPAL
# ══════════════════════════════════════════════════════════════

def registrar_e_comprimir(tipo: str, descricao: str) -> None:
    """
    Registra evento na jornada e dispara compressão se necessário.
    Substitui chamadas diretas a jrn.registrar_evento() quando
    a memória de longo prazo está ativa.
    """
    jrn.registrar_evento(tipo, descricao)
    _reindexar()  # atualiza índice imediatamente
    comprimir_se_necessario()


def inicializar_memoria(personagem_dict: dict, cenario: str) -> None:
    """Inicializa jornada e memória RAG para uma nova sessão."""
    global _resumos, _indice, _idf_cache, _carregado
    _resumos = []
    _indice  = []
    _idf_cache = {}
    _carregado = True
    os.makedirs("jornada", exist_ok=True)
    # Remove resumos de sessão anterior
    if os.path.exists(ARQUIVO_RESUMOS):
        os.remove(ARQUIVO_RESUMOS)
    jrn.inicializar_jornada(personagem_dict, cenario)


def stats_memoria() -> dict:
    """Retorna estatísticas da memória para o debugger."""
    if not _carregado:
        _carregar()
    return {
        "eventos_indexados": len(_indice),
        "blocos_resumidos":  len(_resumos),
        "tokens_vocab":      len(_idf_cache),
        "turno_resumido_ate": max((r.turno_fim for r in _resumos), default=0),
    }


# ══════════════════════════════════════════════════════════════
#  PONTO DE TESTE RÁPIDO
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os, json
    os.makedirs("jornada", exist_ok=True)
    # Setup mínimo
    with open("jornada/estado.json", "w") as f:
        json.dump({
            "turno": 15, "personagem": {"nome": "Max", "caminho": "Luta",
            "pv_atual": 120, "pv_max": 155, "psique_atual": 10, "psique_max": 14.6},
            "localizacao_atual": "Floresta das Sombras",
            "npcs_conhecidos": {"Breno": {"atitude": "amigavel", "descricao": "ferreiro local"}},
            "inimigos_derrotados": [{"nome": "Lobo da Floresta", "nivel": 1}],
            "itens_obtidos": [{"nome": "Espada Longa"}],
            "segredos_descobertos": [{"descricao": "O Curupira protege a floresta norte"}],
            "quests_ativas": [], "quests_concluidas": [], "reputacao": {},
            "npcs_conhecidos": {}, "habilidades_adquiridas": [],
        }, f)
    with open("jornada/log.json", "w") as f:
        json.dump({"eventos": [
            {"turno": i, "tipo": t, "descricao": d}
            for i, t, d in [
                (1, "narrativa", "A aventura começa na Vila de Pedra Branca."),
                (2, "combate", "Enfrentou um Lobo da Floresta e venceu."),
                (3, "item", "Encontrou uma Espada Longa no covil do lobo."),
                (4, "npc", "Conversou com Breno, o ferreiro. Ele mencionou o Curupira."),
                (5, "combate", "Derrotou uma Cutia com golpe de corte."),
                (6, "narrativa", "Entrou na Floresta das Sombras."),
                (7, "combate", "Confronto com Capivara — usou bola de fogo."),
                (8, "npc", "Encontrou Mira, a arqueira. Amizade: 45."),
                (9, "combate", "Derrotou Goblin Batedeiro com raio elétrico."),
                (10, "movimento", "Moveu-se para as Ruínas do Templo."),
                (11, "combate", "Enfrentou Jacaré do Pantanal. Quase morreu."),
                (12, "item", "Obteve Faca Enferrujada do Goblin."),
                (13, "narrativa", "Descobriu altar antigo com inscrições."),
                (14, "combate", "Venceu Cobra Venenosa com veneno dela mesma."),
                (15, "narrativa", "Chegou à beira do Pântano."),
            ]
        ]}, f)

    print("=== BUSCA SEMÂNTICA ===")
    resultados = buscar_eventos_relevantes("combate com fogo e magia", k=3)
    for r in resultados:
        print(f"  T{r.turno:02d}[{r.tipo}] {r.descricao}")

    print()
    print("=== CONTEXTO RAG ===")
    ctx = obter_contexto_rag(query="bola de fogo contra Capivara")
    print(ctx)

    print()
    print("=== STATS ===")
    print(stats_memoria())
