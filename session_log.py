"""
session_log.py
─────────────────────────────────────────────────────────────
Log de Sessão — RPG GM LLM

Registra em CSV cada chamada LLM com:
  - timestamp, turno, tipo (avaliacao/narracao/npc/...)
  - entrada do jogador
  - resposta da LLM
  - tokens_prompt, tokens_resposta, tokens_total
  - tempo_resposta_s
  - custo_usd (estimado)
  - modelo usado
  - criatividade, eficiencia (quando aplicável)

Cada sessão cria um arquivo CSV único:
  logs/sessao_YYYY-MM-DD_HH-MM-SS.csv

Uso mínimo:
  from session_log import log_llm, iniciar_sessao
  iniciar_sessao(personagem_nome, modelo)
  log_llm("narracao_jogador", entrada, resposta, tokens_p, tokens_r, tempo)
"""

from __future__ import annotations
import csv
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Preços por 1M tokens (USD) — atualizar conforme provider ──
PRECOS_POR_MILHAO: dict = {
    # Groq (llama-3.1-8b-instant)
    "llama-3.1-8b-instant":       {"prompt": 0.05, "completion": 0.08},
    # Ollama local = custo zero
    "llama3.1:8b":                 {"prompt": 0.00, "completion": 0.00},
    "llama3.1:8b-instruct-q4_0":  {"prompt": 0.00, "completion": 0.00},
    # Fallback genérico
    "default":                     {"prompt": 0.05, "completion": 0.08},
}

# ── Estado da sessão ───────────────────────────────────────────
_csv_path:   Optional[Path] = None
_modelo:     str = "desconhecido"
_personagem: str = "?"
_turno:      int = 0
_session_start: float = 0.0

# Acumuladores da sessão
_total_tokens_prompt:    int   = 0
_total_tokens_resposta:  int   = 0
_total_custo_usd:        float = 0.0
_total_chamadas:         int   = 0
_total_tempo_s:          float = 0.0


# ══════════════════════════════════════════════════════════════
#  INICIALIZAÇÃO
# ══════════════════════════════════════════════════════════════

def iniciar_sessao(personagem_nome: str = "?", modelo: str = "desconhecido") -> Path:
    """
    Cria o arquivo CSV da sessão e reseta contadores.
    Deve ser chamado uma vez no início de cada jogo.
    Retorna o caminho do arquivo criado.
    """
    global _csv_path, _modelo, _personagem, _turno, _session_start
    global _total_tokens_prompt, _total_tokens_resposta
    global _total_custo_usd, _total_chamadas, _total_tempo_s

    _modelo     = modelo
    _personagem = personagem_nome
    _turno      = 0
    _session_start = time.time()
    _total_tokens_prompt   = 0
    _total_tokens_resposta = 0
    _total_custo_usd       = 0.0
    _total_chamadas        = 0
    _total_tempo_s         = 0.0

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _csv_path = logs_dir / f"sessao_{ts}.csv"

    with open(_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "turno", "tipo",
            "personagem", "modelo",
            "entrada_preview",        # primeiros 120 chars da entrada
            "resposta_preview",       # primeiros 200 chars da resposta
            "tokens_prompt", "tokens_resposta", "tokens_total",
            "tempo_s", "custo_usd",
            "criatividade", "eficiencia",
            "finish_reason",
        ])

    print(f"  \033[90m[LOG] Sessão iniciada → {_csv_path}\033[0m")
    return _csv_path


def set_turno(t: int) -> None:
    """Atualiza o turno atual (chamado a cada turno do loop de combate)."""
    global _turno
    _turno = t


# ══════════════════════════════════════════════════════════════
#  REGISTRO DE CHAMADA LLM
# ══════════════════════════════════════════════════════════════

def log_llm(
    tipo:           str,          # "avaliacao" | "narracao_jogador" | "narracao_inimigo" | "npc" | ...
    entrada:        str,          # prompt enviado à LLM
    resposta:       str,          # texto retornado
    tokens_prompt:  int = 0,
    tokens_resposta: int = 0,
    tempo_s:        float = 0.0,
    criatividade:   Optional[float] = None,
    eficiencia:     Optional[float] = None,
    finish_reason:  str = "",
) -> None:
    """
    Registra uma chamada LLM no CSV e atualiza os acumuladores.
    Thread-safe para chamadas sequenciais.
    """
    global _total_tokens_prompt, _total_tokens_resposta
    global _total_custo_usd, _total_chamadas, _total_tempo_s

    if _csv_path is None:
        return  # log não inicializado — não trava o jogo

    tokens_total = tokens_prompt + tokens_resposta
    custo = _calcular_custo(tokens_prompt, tokens_resposta)

    # Atualiza acumuladores
    _total_tokens_prompt    += tokens_prompt
    _total_tokens_resposta  += tokens_resposta
    _total_custo_usd        += custo
    _total_chamadas         += 1
    _total_tempo_s          += tempo_s

    row = [
        datetime.now().isoformat(timespec="seconds"),
        _turno,
        tipo,
        _personagem,
        _modelo,
        _truncar(entrada,  2000),
        _truncar(resposta, 2000),
        tokens_prompt,
        tokens_resposta,
        tokens_total,
        round(tempo_s, 3),
        round(custo, 6),
        round(criatividade, 3) if criatividade is not None else "",
        round(eficiencia,   3) if eficiencia   is not None else "",
        finish_reason,
    ]

    try:
        with open(_csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except Exception:
        pass  # nunca crashar por falha de log


def _calcular_custo(tokens_p: int, tokens_r: int) -> float:
    precos = PRECOS_POR_MILHAO.get(_modelo, PRECOS_POR_MILHAO["default"])
    return (tokens_p * precos["prompt"] + tokens_r * precos["completion"]) / 1_000_000


def _truncar(texto: str, n: int) -> str:
    texto = texto.replace("\n", " ").replace("\r", "")
    return texto[:n] + "…" if len(texto) > n else texto


# ══════════════════════════════════════════════════════════════
#  ESTATÍSTICAS DA SESSÃO
# ══════════════════════════════════════════════════════════════

def stats_sessao() -> dict:
    """Retorna resumo acumulado da sessão."""
    duracao = round(time.time() - _session_start, 1) if _session_start else 0
    return {
        "chamadas":         _total_chamadas,
        "tokens_prompt":    _total_tokens_prompt,
        "tokens_resposta":  _total_tokens_resposta,
        "tokens_total":     _total_tokens_prompt + _total_tokens_resposta,
        "custo_usd":        round(_total_custo_usd, 6),
        "tempo_total_s":    round(_total_tempo_s, 2),
        "tempo_medio_s":    round(_total_tempo_s / max(1, _total_chamadas), 2),
        "duracao_sessao_s": duracao,
        "modelo":           _modelo,
        "csv":              str(_csv_path) if _csv_path else "—",
    }


# ══════════════════════════════════════════════════════════════
#  LOG DO QUESTIONÁRIO INICIAL
# ══════════════════════════════════════════════════════════════

def log_questionario(
    pergunta_id:     int,
    dominio:         str,
    pergunta_texto:  str,
    resposta:        str,
    criatividade:    float,
    comentario:      str,
    bonus_psique:    float,
    bonus_atributo:  float,
    tokens_prompt:   int = 0,
    tokens_resposta: int = 0,
    tempo_s:         float = 0.0,
) -> None:
    """
    Registra uma pergunta do questionário inicial no CSV unificado da sessão.
    Usa tipo='questionario' para diferenciar das chamadas LLM de combate.
    """
    # Monta entrada como texto para os campos de entrada/resposta
    entrada_txt  = f"[P{pergunta_id}/{dominio}] {_truncar(pergunta_texto, 2000)}"
    resposta_txt = f"R: {_truncar(resposta, 2000)} | {_truncar(comentario, 500)}"

    row = [
        datetime.now().isoformat(timespec="seconds"),
        _turno,
        f"questionario_p{pergunta_id}",
        _personagem,
        _modelo,
        entrada_txt,
        resposta_txt,
        tokens_prompt,
        tokens_resposta,
        tokens_prompt + tokens_resposta,
        round(tempo_s, 3),
        0.0,           # custo_usd (não aplicável)
        round(criatividade, 3),
        round(bonus_atributo, 3),
        "",            # finish_reason
    ]

    global _total_chamadas, _total_tempo_s
    _total_chamadas += 1
    _total_tempo_s  = round(_total_tempo_s + tempo_s, 3)

    try:
        if _csv_path is None:
            iniciar_sessao(_personagem)
        with open(_csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except Exception:
        pass


def exibir_resumo_questionario(ganhos: list, personagem_nome: str) -> None:
    """Imprime resumo do questionário e loga summary no CSV unificado."""
    media_cri = sum(g[0] for g in ganhos) / max(len(ganhos), 1)
    total_psi = sum(g[1] for g in ganhos)
    total_att = sum(g[2] for g in ganhos)

    print(f"  \033[90m{'─' * 50}")
    print(f"  📋 Questionário registrado no log da sessão")
    if _csv_path:
        print(f"     {_csv_path}")
    print(f"  {'─' * 50}\033[0m")

    # Linha de resumo no CSV
    log_llm("questionario_resumo",
            f"{len(ganhos)} perguntas | cri_media={media_cri:.2f}",
            f"psi=+{total_psi:.1f} attr=+{total_att:.1f}")


def exibir_stats_sessao() -> None:
    """Imprime um resumo da sessão ao final do jogo."""
    s = stats_sessao()
    print(f"\n  \033[90m{'─' * 50}")
    print(f"  📊 Resumo da sessão LLM")
    print(f"  {'─' * 50}")
    print(f"  Chamadas LLM:    {s['chamadas']}")
    print(f"  Tokens usados:   {s['tokens_total']:,}  "
          f"(prompt: {s['tokens_prompt']:,}  resp: {s['tokens_resposta']:,})")
    print(f"  Custo estimado:  ${s['custo_usd']:.6f} USD")
    print(f"  Tempo médio:     {s['tempo_medio_s']:.2f}s / chamada")
    print(f"  Tempo total LLM: {s['tempo_total_s']:.1f}s")
    print(f"  Log salvo em:    {s['csv']}")
    print(f"  {'─' * 50}\033[0m")