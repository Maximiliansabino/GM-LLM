"""
memoria_npc.py
─────────────────────────────────────────────────────────────
Memória Persistente de NPCs — RPG GM LLM

Armazenamento:
  SQLite  → conversas recentes (últimas 20 por NPC)
  JSON    → lore estabelecido (fatos canônicos por NPC)
  CSV     → log de interações (para análise/tese)

Limites de ganho de atributo:
  Por conversa:   máx. 1.0 Conhecimento Explícito total
  Por NPC/sessão: máx. 0.5 por NPC por sessão de jogo
  Por dia-jogo:   máx. 2.0 em todos os NPCs combinados
  Segredos:       +0.5 Conhecimento Tácito (uma vez por segredo)

Referência DSR:
  LIU et al. (2024) — RAG for Consistent RPG Narratives.
"""

from __future__ import annotations
import sqlite3
import json
import csv
import os
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# ── Caminhos ─────────────────────────────────────────────────
DIR_JORNADA     = Path("jornada")
DB_PATH         = DIR_JORNADA / "npc_conversas.db"
LORE_PATH       = DIR_JORNADA / "npc_lore.json"
LOG_CSV_PATH    = DIR_JORNADA / "npc_interacoes.csv"

# ── Limites de ganho de atributo ─────────────────────────────
LIMITE_CONVERSA_SESSAO   = 0.5   # máx. por NPC por sessão
LIMITE_TOTAL_SESSAO      = 2.0   # máx. combinado todos NPCs na sessão
LIMITE_SEGREDO           = 0.5   # ganho fixo por segredo revelado (uma vez)
MAX_FALAS_BONUS          = 6     # máx. de falas que geram bônus por conversa

# ── Ganho base por palavra ────────────────────────────────────
BONUS_BASE        = 0.1   # bônus mínimo por fala ≥4 palavras
BONUS_POR_PALAVRA = 0.01  # bônus adicional por palavra extra (máx. 0.3)

# ── Controle de sessão (em memória) ──────────────────────────
_ganho_sessao: Dict[str, float] = {}   # {npc_nome: total_ganho_sessao}
_ganho_total_sessao: float = 0.0
_falas_bonus: Dict[str, int] = {}      # {npc_nome: n_falas_com_bonus}


# ══════════════════════════════════════════════════════════════
#  1. INICIALIZAÇÃO DO BANCO
# ══════════════════════════════════════════════════════════════

def inicializar() -> None:
    """Cria tabelas SQLite e arquivos JSON/CSV se não existirem."""
    DIR_JORNADA.mkdir(exist_ok=True)

    # SQLite — conversas
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS conversas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_nome    TEXT    NOT NULL,
                turno       INTEGER NOT NULL,
                de          TEXT    NOT NULL,   -- 'jogador' ou nome do NPC
                texto       TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL
            )
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_npc_turno
            ON conversas(npc_nome, turno DESC)
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS ganhos_atributo (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_nome    TEXT    NOT NULL,
                atributo    TEXT    NOT NULL,
                valor       REAL    NOT NULL,
                motivo      TEXT,
                turno       INTEGER,
                timestamp   TEXT    NOT NULL
            )
        """)

    # JSON — lore canônico
    if not LORE_PATH.exists():
        LORE_PATH.write_text(json.dumps({}, ensure_ascii=False, indent=2), encoding="utf-8")

    # CSV — log de interações
    if not LOG_CSV_PATH.exists():
        with open(LOG_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "timestamp", "npc_nome", "turno", "de",
                "texto_preview", "ganho_atributo", "amizade_delta"
            ])


def _conn() -> sqlite3.Connection:
    """Retorna conexão SQLite com context manager."""
    return sqlite3.connect(str(DB_PATH))


# ══════════════════════════════════════════════════════════════
#  2. CONVERSAS — SQLite
# ══════════════════════════════════════════════════════════════

def salvar_fala(npc_nome: str, de: str, texto: str, turno: int = 0) -> None:
    """Salva uma fala no histórico persistente."""
    ts = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        con.execute(
            "INSERT INTO conversas (npc_nome, turno, de, texto, timestamp) VALUES (?,?,?,?,?)",
            (npc_nome, turno, de, texto[:500], ts)
        )


def obter_historico(npc_nome: str, n: int = 10) -> List[Dict]:
    """
    Retorna as últimas n falas da conversa com este NPC.
    Formato: [{"de": "Jogador", "texto": "..."}, ...]
    """
    with _conn() as con:
        rows = con.execute(
            """SELECT de, texto FROM conversas
               WHERE npc_nome = ?
               ORDER BY id DESC LIMIT ?""",
            (npc_nome, n)
        ).fetchall()
    # Inverter para ordem cronológica
    return [{"de": r[0], "texto": r[1]} for r in reversed(rows)]


def obter_resumo_conversa(npc_nome: str) -> str:
    """
    Retorna bloco de texto formatado com o histórico recente.
    Para injetar no prompt do LLM.
    """
    historico = obter_historico(npc_nome, n=8)
    if not historico:
        return ""
    linhas = [f"Histórico com {npc_nome} (últimas {len(historico)} falas):"]
    for h in historico:
        linhas.append(f"  {h['de']}: {h['texto'][:120]}")
    return "\n".join(linhas)


def n_interacoes_totais(npc_nome: str) -> int:
    """Total de falas trocadas com este NPC (histórico completo)."""
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM conversas WHERE npc_nome = ?",
            (npc_nome,)
        ).fetchone()
    return row[0] if row else 0


# ══════════════════════════════════════════════════════════════
#  3. LORE CANÔNICO — JSON
# ══════════════════════════════════════════════════════════════

def registrar_lore(npc_nome: str, fato: str, categoria: str = "geral") -> None:
    """
    Registra um fato canônico sobre ou revelado por um NPC.
    Evita duplicatas por similaridade.
    """
    dados = _carregar_lore()
    entrada = dados.setdefault(npc_nome, {"fatos": [], "ultima_atualizacao": ""})
    fatos = entrada["fatos"]

    # Evita duplicata exata
    fato_lower = fato.lower().strip()
    if any(f["texto"].lower() == fato_lower for f in fatos):
        return

    fatos.append({
        "categoria": categoria,
        "texto":     fato[:300],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    })
    entrada["ultima_atualizacao"] = datetime.now().isoformat(timespec="seconds")
    _salvar_lore(dados)


def obter_lore(npc_nome: str, categoria: Optional[str] = None) -> List[str]:
    """Retorna fatos canônicos de um NPC, opcionalmente filtrados por categoria."""
    dados = _carregar_lore()
    fatos = dados.get(npc_nome, {}).get("fatos", [])
    if categoria:
        fatos = [f for f in fatos if f.get("categoria") == categoria]
    return [f["texto"] for f in fatos]


def obter_lore_formatado(npc_nome: str) -> str:
    """Retorna bloco de lore para injetar no prompt do LLM."""
    fatos = obter_lore(npc_nome)
    if not fatos:
        return ""
    linhas = [f"Fatos estabelecidos sobre {npc_nome}:"]
    for f in fatos[-5:]:  # últimos 5 fatos
        linhas.append(f"  - {f}")
    return "\n".join(linhas)


def _carregar_lore() -> dict:
    try:
        return json.loads(LORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _salvar_lore(dados: dict) -> None:
    LORE_PATH.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ══════════════════════════════════════════════════════════════
#  4. LOG DE INTERAÇÕES — CSV
# ══════════════════════════════════════════════════════════════

def log_interacao(npc_nome: str, turno: int, de: str, texto: str,
                  ganho_attr: float = 0.0, amizade_delta: float = 0.0) -> None:
    """Appenda uma linha ao CSV de interações (para análise da tese)."""
    try:
        with open(LOG_CSV_PATH, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                datetime.now().isoformat(timespec="seconds"),
                npc_nome, turno, de,
                texto[:80], round(ganho_attr, 3), round(amizade_delta, 1)
            ])
    except Exception:
        pass  # nunca crashar por log


# ══════════════════════════════════════════════════════════════
#  5. CONTROLE DE GANHO DE ATRIBUTO
# ══════════════════════════════════════════════════════════════

def calcular_bonus_conversa(npc_nome: str, fala: str) -> float:
    """
    Calcula o bônus de Conhecimento Explícito para uma fala.
    Retorna 0.0 se o limite foi atingido.

    Limites aplicados:
      - Fala precisa ter ≥ 4 palavras
      - Máx. MAX_FALAS_BONUS falas com bônus por conversa por NPC
      - Máx. LIMITE_CONVERSA_SESSAO por NPC por sessão
      - Máx. LIMITE_TOTAL_SESSAO combinado na sessão
    """
    global _ganho_total_sessao

    palavras = len(fala.split())
    if palavras < 4:
        return 0.0

    # Limite de falas com bônus por NPC nesta sessão
    falas_npc = _falas_bonus.get(npc_nome, 0)
    if falas_npc >= MAX_FALAS_BONUS:
        return 0.0

    # Limite de ganho por NPC na sessão
    ganho_npc = _ganho_sessao.get(npc_nome, 0.0)
    if ganho_npc >= LIMITE_CONVERSA_SESSAO:
        return 0.0

    # Limite total na sessão
    if _ganho_total_sessao >= LIMITE_TOTAL_SESSAO:
        return 0.0

    # Calcula bônus proporcional às palavras
    bonus = round(BONUS_BASE + min(0.3, (palavras - 4) * BONUS_POR_PALAVRA), 2)

    # Aplica limite residual por NPC
    espaco_npc   = LIMITE_CONVERSA_SESSAO - ganho_npc
    espaco_total = LIMITE_TOTAL_SESSAO    - _ganho_total_sessao
    bonus = round(min(bonus, espaco_npc, espaco_total), 2)

    return max(0.0, bonus)


def registrar_ganho(npc_nome: str, atributo: str, valor: float,
                     motivo: str = "", turno: int = 0) -> None:
    """Registra ganho de atributo no SQLite e atualiza contadores de sessão."""
    global _ganho_total_sessao

    if valor <= 0:
        return

    # Atualiza contadores de sessão
    _ganho_sessao[npc_nome] = round(_ganho_sessao.get(npc_nome, 0.0) + valor, 3)
    if atributo == "conhecimento_explicito":
        _falas_bonus[npc_nome] = _falas_bonus.get(npc_nome, 0) + 1
        _ganho_total_sessao = round(_ganho_total_sessao + valor, 3)

    # Persiste no SQLite
    ts = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        con.execute(
            "INSERT INTO ganhos_atributo (npc_nome, atributo, valor, motivo, turno, timestamp) "
            "VALUES (?,?,?,?,?,?)",
            (npc_nome, atributo, valor, motivo, turno, ts)
        )


def pode_ganhar_segredo(npc_nome: str) -> bool:
    """
    Verifica se o bônus de segredo deste NPC já foi concedido.
    Cada segredo só pode ser revelado uma vez.
    """
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM ganhos_atributo "
            "WHERE npc_nome=? AND motivo LIKE 'segredo%'",
            (npc_nome,)
        ).fetchone()
    return (row[0] if row else 0) == 0


def stats_ganhos_sessao() -> dict:
    """Retorna estatísticas de ganhos desta sessão."""
    return {
        "ganho_por_npc":     dict(_ganho_sessao),
        "ganho_total":       _ganho_total_sessao,
        "falas_bonus":       dict(_falas_bonus),
        "limite_sessao":     LIMITE_TOTAL_SESSAO,
        "restante":          round(LIMITE_TOTAL_SESSAO - _ganho_total_sessao, 3),
    }


def resetar_sessao() -> None:
    """Reseta contadores de sessão (chamar no início de cada jogo)."""
    global _ganho_total_sessao
    _ganho_sessao.clear()
    _falas_bonus.clear()
    _ganho_total_sessao = 0.0


# ══════════════════════════════════════════════════════════════
#  6. INTERFACE RÁPIDA PARA biomas.py
# ══════════════════════════════════════════════════════════════

def processar_fala(npc_nome: str, de: str, texto: str, turno: int,
                   amizade_delta: float = 0.0) -> float:
    """
    Registra fala no SQLite e CSV, calcula bônus de atributo.
    Retorna o bônus de Conhecimento Explícito a ser aplicado (0.0 se limite).
    """
    inicializar()
    salvar_fala(npc_nome, de, texto, turno)

    bonus = 0.0
    if de not in (npc_nome, "sistema"):
        bonus = calcular_bonus_conversa(npc_nome, texto)
        if bonus > 0:
            registrar_ganho(npc_nome, "conhecimento_explicito", bonus,
                            f"conversa com {npc_nome}", turno)

    log_interacao(npc_nome, turno, de, texto, bonus, amizade_delta)
    return bonus


def contexto_para_llm(npc_nome: str) -> str:
    """
    Retorna bloco de contexto completo para injetar no prompt do NPC.
    Combina histórico de conversa + lore canônico.
    """
    inicializar()
    partes = []
    historico = obter_resumo_conversa(npc_nome)
    if historico:
        partes.append(historico)
    lore = obter_lore_formatado(npc_nome)
    if lore:
        partes.append(lore)
    return "\n\n".join(partes)


# ══════════════════════════════════════════════════════════════
#  PONTO DE TESTE RÁPIDO
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import shutil
    # Limpa estado anterior para teste limpo
    if DB_PATH.exists():   DB_PATH.unlink()
    if LORE_PATH.exists(): LORE_PATH.unlink()

    inicializar()
    print("=== TESTE MEMÓRIA NPC ===\n")

    # Simula uma conversa com Breno
    turnos_test = [
        ("jogador", "Breno, o que você sabe sobre as estradas perigosas ao sul?"),
        ("Breno",   "As estradas ao sul estão cheias de bandidos desde a queda do forte."),
        ("jogador", "Onde exatamente fica o forte que foi tomado?"),
        ("Breno",   "Três léguas ao sul, onde a estrada bifurca. Não vá por lá."),
        ("jogador", "Qual o nome do líder dos bandidos?"),
        ("Breno",   "Chamam ele de Mão de Ferro. Ninguém o viu de perto e sobreviveu."),
        ("jogador", "ok"),  # fala curta — sem bônus
    ]

    print("── Simulando conversa com Breno ──")
    for de, texto in turnos_test:
        bonus = processar_fala("Breno", de, texto, turno=1)
        marca = f"  [+{bonus:.2f} Conh.Exp]" if bonus > 0 else ""
        print(f"  {de:10}: {texto[:60]}{marca}")

    # Registra lore revelado
    registrar_lore("Breno", "Mão de Ferro lidera os bandidos ao sul", "antagonista")
    registrar_lore("Breno", "Forte caiu há 3 meses — fonte dos problemas", "localizacao")

    print()
    print("── Histórico recuperado do SQLite ──")
    for h in obter_historico("Breno", n=5):
        print(f"  {h['de']:10}: {h['texto'][:60]}")

    print()
    print("── Lore JSON ──")
    for f in obter_lore("Breno"):
        print(f"  - {f}")

    print()
    print("── Stats de ganho ──")
    stats = stats_ganhos_sessao()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print()
    print("── Contexto para LLM ──")
    print(contexto_para_llm("Breno"))

    print()
    print(f"── Interações totais com Breno: {n_interacoes_totais('Breno')} ──")
    print(f"── CSV criado em: {LOG_CSV_PATH} ──")
    print(f"── SQLite criado em: {DB_PATH} ──")
    print(f"── Lore JSON criado em: {LORE_PATH} ──")
