"""
rpg_judge.py
─────────────────────────────────────────────────────────────
RPG-Judge — Avaliação Automática de Sessões via LLM-as-a-Judge

Baseado em YU et al. (2025) RPGBench e CHEN et al. (2024).

Métricas avaliadas por sessão CSV:
  GS1 — Qualidade Narrativa       (narrações do GM)
  GS2 — Consistência Factual      (NPC/inimigo/nome corretos)
  GS3 — Coerência de Ação         (ação do jogador refletida)
  GS4 — Criatividade do Jogador   (média das avaliações internas)
  GS5 — Eficiência Mecânica       (média das eficiências)
  GS6 — Consistência de Estado    (sem contradições entre turnos)
  QC1 — Qualidade do Questionário (avaliação das respostas iniciais)

Uso:
  python rpg_judge.py sessao_2026-04-17.csv
  python rpg_judge.py logs/           # avalia todos os CSVs da pasta
  python rpg_judge.py --relatorio     # gera relatório agregado

Referências:
  YU et al. (2025). RPGBench: Evaluating Large Language Models as
      Role-Playing Game Engines. arXiv:2502.00595
  CHEN et al. (2024). Evaluating LLMs as Autonomous Game Masters:
      A Multi-Dimensional Framework. ACM SIGIR.
"""

from __future__ import annotations
import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Configuração ──────────────────────────────────────────────
OUTPUT_DIR  = Path("judge_results")
JUDGE_MODEL = "meta-llama-3.1-8b-instruct"  # modelo para julgar
MAX_RETRIES = 3

# Escalas de avaliação (alinhadas com RPGBench)
ESCALA_LIKERT = "1 (péssimo) a 5 (excelente)"
PASS_THRESHOLD = 3.0  # pontuação mínima aceitável

# ── Prompts de avaliação ──────────────────────────────────────
PROMPT_NARRATIVA = """Você é um avaliador de qualidade narrativa em RPG.
Avalie a seguinte narração do GM (Mestre do Jogo) em TRÊS critérios.
Responda APENAS com JSON válido, sem texto adicional.

Narração avaliada:
"{narracao}"

Contexto (ação do jogador que gerou esta narração):
"{acao_jogador}"

Critérios de avaliação ({escala}):
1. qualidade_narrativa: Riqueza do texto, vocabulário, imersão
2. consistencia: A narração descreve a ação "{acao_curta}" corretamente?
3. segunda_pessoa: Usa corretamente "você/seu/sua" (não "eu/meu")?

JSON esperado:
{{"qualidade_narrativa": N, "consistencia": N, "segunda_pessoa": N, "justificativa": "..."}}"""

PROMPT_CONSISTENCIA_ESTADO = """Você é um árbitro de consistência em RPG.
Analise estes dois turnos consecutivos e verifique se há contradições.

Turno {t1} — Narração:
"{narr1}"

Turno {t2} — Narração:
"{narr2}"

Há contradições factuais entre os turnos? (personagem morto mas ainda age, 
inimigo derrotado mas ainda aparece, localização impossível, etc.)

Responda APENAS com JSON:
{{"consistente": true/false, "problemas": ["lista de contradições encontradas"], "score": N}}
onde score: {escala}"""

PROMPT_COERENCIA_ACAO = """Avalie se a narração do GM reflete corretamente a ação do jogador.

Ação do jogador: "{acao}"
Narração gerada: "{narracao}"

A narração descreve exatamente a ação "{acao_curta}"?
Ou inventou uma ação diferente?

Responda APENAS com JSON:
{{"reflete_acao": true/false, "score": N, "observacao": "..."}}
onde score: {escala}"""

PROMPT_QUESTIONARIO = """Você é um avaliador de sistemas de RPG com IA.
Avalie a QUALIDADE DA AVALIAÇÃO feita pelo GM LLM (não a resposta do jogador em si).

Situação proposta: "{situacao}"
Resposta do jogador: "{resposta}"
Comentário do GM LLM: "{comentario_llm}"
Score de criatividade dado pelo GM: {score_interno}/1.0

Avalie se o GM LLM avaliou bem ({escala}):
- precisao_avaliacao: o score de criatividade dado é adequado para esta resposta?
- qualidade_feedback: o comentário é útil, específico e coerente com a resposta?
- consistencia_criterio: o GM aplicou critérios razoáveis de criatividade narrativa?

Responda APENAS com JSON:
{{"precisao_avaliacao": N, "qualidade_feedback": N, "consistencia_criterio": N, "justificativa": "..."}}"""


# ══════════════════════════════════════════════════════════════
#  CHAMADA AO JUDGE LLM
# ══════════════════════════════════════════════════════════════

# ── Diagnóstico do judge (resetado por sessão) ────────────────
_JUDGE_STATS: dict = {
    "modelo_judge"          : "?",
    "backend_judge"         : "?",
    "chamadas_totais"       : 0,
    "chamadas_com_parse_ok" : 0,
    "chamadas_falha_parse"  : 0,
    "exemplos_falha"        : [],   # primeiros 3 erros
}


def _reset_judge_stats() -> None:
    _JUDGE_STATS["modelo_judge"]          = "?"
    _JUDGE_STATS["backend_judge"]         = "?"
    _JUDGE_STATS["chamadas_totais"]       = 0
    _JUDGE_STATS["chamadas_com_parse_ok"] = 0
    _JUDGE_STATS["chamadas_falha_parse"]  = 0
    _JUDGE_STATS["exemplos_falha"]        = []


def _extrair_json(raw: str) -> Optional[dict]:
    """Tenta extrair JSON de uma string. Robusto a reasoning models
    (Gemma 4, DeepSeek-R1, Qwen3) e a fences markdown.

    Estratégia em camadas:
      1. Remove blocos <think>...</think> ou <thought>...</thought>
      2. Remove cercas markdown ```json ... ``` em qualquer posição
      3. Tenta parse direto
      4. Busca por TODOS os {...} balanceados (até 2 níveis) e tenta
         o ÚLTIMO primeiro (modelos reasoning costumam emitir JSON ao final)
    """
    if not raw:
        return None
    s = raw

    # 1) Strip <think>/<thought> blocks (reasoning models)
    s = re.sub(r'<think>.*?</think>', '', s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r'<thought>.*?</thought>', '', s, flags=re.DOTALL | re.IGNORECASE)
    # Tags abertas sem fechamento (token cortado pelo num_predict)
    # — para no primeiro '{' para preservar o JSON que vem depois
    s = re.sub(r'<think>[^{]*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'<thought>[^{]*', '', s, flags=re.IGNORECASE)

    # 2) Strip cercas markdown em qualquer posição
    s = re.sub(r'```(?:json|JSON)?\s*\n?', '', s)
    s = re.sub(r'\n?\s*```', '', s)
    s = s.strip()

    if not s:
        return None

    # 3) Parse direto se a string toda é JSON
    try:
        v = json.loads(s)
        if isinstance(v, dict):
            return v
    except json.JSONDecodeError:
        pass

    # 4) Captura todos os {...} com até 2 níveis de aninhamento.
    #    Preferimos o ÚLTIMO (reasoning models emitem JSON após thinking).
    pattern = r'\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}'
    matches = list(re.finditer(pattern, s, flags=re.DOTALL))
    for m in reversed(matches):
        try:
            v = json.loads(m.group())
            if isinstance(v, dict):
                return v
        except json.JSONDecodeError:
            continue
    return None


def _chamar_ollama_json(prompt: str, system: str) -> str:
    """Chama Ollama com format=json para forçar saída JSON válida.

    Ajustes específicos por família de modelo:
      - Gemma 4 / DeepSeek-R1 / Qwen3 (reasoning): num_predict elevado
        para acomodar bloco <think>; NÃO passamos think=false porque
        isso quebra o format=json (Ollama issue #15260).
      - Demais (qwen2.5, llama3.x): num_predict padrão.
    """
    import requests
    try:
        import llm_config as cfg
        url   = f"{getattr(cfg, 'OLLAMA_BASE_URL', 'http://localhost:11434')}/api/chat"
        model = getattr(cfg, "OLLAMA_MODEL", "qwen2.5:7b-instruct")
    except Exception:
        url, model = "http://localhost:11434/api/chat", "qwen2.5:7b-instruct"

    # Modelos reasoning precisam de mais tokens para o bloco <think> + JSON
    is_reasoning = any(tag in model.lower() for tag in
                       ("gemma4", "gemma-4", "deepseek-r1", "qwen3"))
    num_predict  = 1200 if is_reasoning else 400

    payload = {
        "model"  : model,
        "stream" : False,
        "format" : "json",
        "options": {"temperature": 0.3, "num_predict": num_predict},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
    }
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "").strip()


def _chamar_judge(prompt: str) -> Optional[dict]:
    """Chama o judge LLM e retorna dict parseado, ou None se falhou.
    Atualiza _JUDGE_STATS para diagnóstico no JSON de saída."""
    _JUDGE_STATS["chamadas_totais"] += 1
    try:
        import llm_backend as lb
        import llm_config as cfg
        backend = getattr(cfg, "BACKEND", "ollama")
        model   = getattr(cfg, "OLLAMA_MODEL", "?") if backend == "ollama" else "?"
        if _JUDGE_STATS["modelo_judge"] == "?":
            _JUDGE_STATS["modelo_judge"]  = model
            _JUDGE_STATS["backend_judge"] = backend
        system = (
            "Você é um avaliador especialista em qualidade narrativa de RPG. "
            "Responda EXCLUSIVAMENTE com um objeto JSON válido. "
            "Não inclua texto antes ou depois, nem cercas markdown."
        )
        last_raw = ""
        last_err = ""
        for tentativa in range(MAX_RETRIES):
            try:
                if backend == "ollama":
                    last_raw = _chamar_ollama_json(prompt, system)
                else:
                    last_raw = lb.chamar(prompt, system, num_predict=400)
                parsed = _extrair_json(last_raw)
                if parsed is not None:
                    _JUDGE_STATS["chamadas_com_parse_ok"] += 1
                    return parsed
            except Exception as e:
                last_err = str(e)[:200]
            if tentativa < MAX_RETRIES - 1:
                time.sleep(1)
        # Esgotou as tentativas — registra exemplo de falha
        _JUDGE_STATS["chamadas_falha_parse"] += 1
        if len(_JUDGE_STATS["exemplos_falha"]) < 3:
            _JUDGE_STATS["exemplos_falha"].append({
                "raw_preview": (last_raw or "")[:300],
                "erro"       : last_err,
            })
        return None
    except ImportError:
        print("  ⚠  llm_backend não encontrado — instale o jogo no mesmo diretório")
        return None


def _nota(valor, chave: str = "score") -> Optional[float]:
    """Extrai nota numérica de dict. Retorna None se ausente/inválido —
    NÃO promove ausência de dado para 1.0."""
    if not isinstance(valor, dict) or chave not in valor:
        return None
    try:
        n = float(valor[chave])
    except (TypeError, ValueError):
        return None
    return max(1.0, min(5.0, n))


def _media_validas(valores) -> Optional[float]:
    """Média ignorando None. Retorna None se nenhum valor válido."""
    v = [x for x in valores if x is not None]
    return round(sum(v) / len(v), 2) if v else None


def _fmt(v) -> str:
    """Formata métrica para print, mostrando '—' quando None."""
    return f"{v:.2f}" if isinstance(v, (int, float)) else "  — "


# ══════════════════════════════════════════════════════════════
#  CARREGAMENTO DO CSV
# ══════════════════════════════════════════════════════════════

def carregar_sessao(caminho: Path) -> Dict[str, List[dict]]:
    """Lê o CSV e organiza por tipo de entrada."""
    dados: Dict[str, List[dict]] = {}
    with open(caminho, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = row.get("tipo", "")
            dados.setdefault(t, []).append(row)
    return dados


# ══════════════════════════════════════════════════════════════
#  MÉTRICAS
# ══════════════════════════════════════════════════════════════

def avaliar_narrativas(rows: List[dict]) -> Tuple[float, List[dict]]:
    """GS1+GS3: Qualidade narrativa e coerência de ação."""
    if not rows:
        return 0.0, []
    resultados = []
    scores = []
    print(f"  Avaliando {len(rows)} narrações...", end="", flush=True)
    for i, r in enumerate(rows):
        narracao = r.get("resposta_preview", "")
        acao     = r.get("entrada_preview", "")
        acao_curta = acao[:40]
        if len(narracao) < 10:
            continue
        prompt = PROMPT_NARRATIVA.format(
            narracao=narracao[:300],
            acao_jogador=acao[:150],
            acao_curta=acao_curta,
            escala=ESCALA_LIKERT,
        )
        res = _chamar_judge(prompt)
        qn  = _nota(res, "qualidade_narrativa")
        cs  = _nota(res, "consistencia")
        sp  = _nota(res, "segunda_pessoa")
        media = _media_validas([qn, cs, sp])
        if media is not None: scores.append(media)
        resultados.append({
            "turno": r.get("turno"), "tipo": r.get("tipo"),
            "acao": acao[:60], "narracao": narracao[:100],
            "qualidade_narrativa": qn, "consistencia": cs,
            "segunda_pessoa": sp, "media": media,
            "justificativa": res.get("justificativa", ""),
        })
        print(".", end="", flush=True)
    print()
    media_geral = _media_validas(scores)
    return media_geral, resultados


def avaliar_consistencia_estado(narrações_ordenadas: List[dict]) -> Tuple[float, List[dict]]:
    """GS6: Verifica contradições entre turnos consecutivos."""
    if len(narrações_ordenadas) < 2:
        return None, []   # sem dado: não inflar com 5.0
    resultados = []
    scores = []
    print(f"  Verificando consistência entre {len(narrações_ordenadas)-1} pares de turnos...", end="", flush=True)
    for i in range(len(narrações_ordenadas) - 1):
        r1 = narrações_ordenadas[i]
        r2 = narrações_ordenadas[i + 1]
        n1 = r1.get("resposta_preview", "")
        n2 = r2.get("resposta_preview", "")
        if len(n1) < 10 or len(n2) < 10:
            continue
        prompt = PROMPT_CONSISTENCIA_ESTADO.format(
            t1=r1.get("turno", i),
            t2=r2.get("turno", i+1),
            narr1=n1[:200],
            narr2=n2[:200],
            escala=ESCALA_LIKERT,
        )
        res = _chamar_judge(prompt)
        score = _nota(res, "score")
        if score is not None: scores.append(score)
        resultados.append({
            "turno_par": f"{r1.get('turno')}-{r2.get('turno')}",
            "consistente": res.get("consistente", True),
            "problemas": res.get("problemas", []),
            "score": score,
        })
        print(".", end="", flush=True)
    print()
    media = _media_validas(scores)
    return media, resultados


def avaliar_questionario(rows: List[dict]) -> Tuple[float, List[dict]]:
    """QC1: Avalia qualidade das respostas do jogador no questionário."""
    if not rows:
        return 0.0, []
    resultados = []
    scores = []
    print(f"  Avaliando {len(rows)} respostas do questionário...", end="", flush=True)
    for r in rows:
        entrada  = r.get("entrada_preview", "")
        resposta = r.get("resposta_preview", "")
        # Formato: "R: resposta_jogador | comentario_gm_llm"
        partes    = resposta.split(" | ")
        resp_txt  = partes[0].replace("R: ", "").strip() if partes else resposta
        coment_llm = partes[1].strip() if len(partes) > 1 else ""
        sit_txt   = entrada.split("] ", 1)[-1] if "] " in entrada else entrada
        score_int = float(r.get("criatividade", 0.5) or 0.5)

        prompt = PROMPT_QUESTIONARIO.format(
            situacao=sit_txt[:200],
            resposta=resp_txt[:200],
            comentario_llm=coment_llm[:200],
            score_interno=round(score_int, 2),
            escala=ESCALA_LIKERT,
        )
        res = _chamar_judge(prompt)
        prec = _nota(res, "precisao_avaliacao")
        qual = _nota(res, "qualidade_feedback")
        cons = _nota(res, "consistencia_criterio")
        media = _media_validas([prec, qual, cons])
        if media is not None: scores.append(media)
        resultados.append({
            "pergunta_id"          : r.get("tipo","").replace("questionario_",""),
            "resposta_jogador"     : resp_txt[:80],
            "comentario_gm"        : coment_llm[:80],
            "score_gm"             : score_int,
            "precisao_avaliacao"   : prec,
            "qualidade_feedback"   : qual,
            "consistencia_criterio": cons,
            "media_judge"          : media,
            "justificativa"        : res.get("justificativa",""),
        })
        print(".", end="", flush=True)
    print()
    media_geral = _media_validas(scores)
    return media_geral, resultados


def metricas_internas(dados: Dict[str, List[dict]]) -> dict:
    """GS4+GS5: Extrai médias das métricas já calculadas pelo sistema."""
    avals = dados.get("avaliacao", [])
    cris = [float(r["criatividade"]) for r in avals if r.get("criatividade")]
    efis = [float(r["eficiencia"])   for r in avals if r.get("eficiencia")]
    tempos = [float(r["tempo_s"]) for r in
              [row for rows in dados.values() for row in rows]
              if r.get("tempo_s") and r["tempo_s"] != "0"]
    tokens = [int(r["tokens_total"]) for r in
              [row for rows in dados.values() for row in rows]
              if r.get("tokens_total") and r["tokens_total"] != "0"]
    return {
        "criatividade_media"  : round(sum(cris)/len(cris), 3) if cris else 0,
        "criatividade_min"    : round(min(cris), 3) if cris else 0,
        "criatividade_max"    : round(max(cris), 3) if cris else 0,
        "eficiencia_media"    : round(sum(efis)/len(efis), 3) if efis else 0,
        "acoes_avaliadas"     : len(avals),
        "tempo_medio_llm_s"   : round(sum(tempos)/len(tempos), 2) if tempos else 0,
        "tokens_medio"        : round(sum(tokens)/len(tokens)) if tokens else 0,
        "tokens_total_sessao" : sum(tokens),
    }


# ══════════════════════════════════════════════════════════════
#  AVALIAÇÃO DE UMA SESSÃO
# ══════════════════════════════════════════════════════════════

def avaliar_sessao(caminho: Path) -> dict:
    """Avalia um CSV de sessão completo. Retorna relatório dict."""
    _reset_judge_stats()
    print(f"\n{'='*60}")
    print(f"  RPG-Judge: {caminho.name}")
    print(f"{'='*60}")

    dados = carregar_sessao(caminho)
    modelo = next(
        (r.get("modelo","?") for rows in dados.values() for r in rows),
        "?"
    )
    personagem = next(
        (r.get("personagem","?") for rows in dados.values() for r in rows),
        "?"
    )
    print(f"  Personagem: {personagem} | Modelo: {modelo}")

    # ── GS1+GS3: Narrativas ───────────────────────────────────
    print("\n[GS1+GS3] Qualidade Narrativa + Coerência de Ação")
    narrações_j = dados.get("narracao_jogador", [])
    narrações_i = dados.get("narracao_inimigo", [])
    todas_narrações = narrações_j + narrações_i
    gs1_score, gs1_detalhe = avaliar_narrativas(todas_narrações)

    # ── GS3 separado: coerência ação→narração ─────────────────
    gs3_scores = [d["consistencia"] for d in gs1_detalhe if d.get("consistencia") is not None]
    gs3_score  = _media_validas(gs3_scores)

    # ── GS6: Consistência de estado ───────────────────────────
    print("\n[GS6] Consistência de Estado entre Turnos")
    todas_sorted = sorted(todas_narrações, key=lambda r: int(r.get("turno",0) or 0))
    gs6_score, gs6_detalhe = avaliar_consistencia_estado(todas_sorted)

    # ── QC1: Questionário ─────────────────────────────────────
    print("\n[QC1] Qualidade das Respostas do Questionário")
    perguntas = [r for t, rows in dados.items()
                 for r in rows if t.startswith("questionario_p")]
    qc1_score, qc1_detalhe = avaliar_questionario(perguntas)

    # ── GS4+GS5: Métricas internas ────────────────────────────
    internas = metricas_internas(dados)

    # ── Mundo Aberto (se houver) ──────────────────────────────
    mundo_tipos = [t for t in dados if t.startswith("mundo_")]
    mundo_acoes = sum(len(dados[t]) for t in mundo_tipos)

    # ── Mundo Aberto (se mundo_log.csv existir junto ao CSV) ─────
    mundo_score = 0.0
    mundo_detalhes = {}
    mundo_log_path = caminho.parent.parent / "jornada" / "mundo_log.csv"
    if not mundo_log_path.exists():
        # Tenta na mesma pasta
        mundo_log_path = caminho.parent / "mundo_log.csv"
    if mundo_log_path.exists():
        print("\n[MW1+MW2] Mundo Aberto — Narrações e Consistência")
        # session_id = nome do CSV sem extensão (ex: "sessao_2026-04-17_21-06-53")
        sid = caminho.stem
        mundo_score, mundo_detalhes = avaliar_mundo_log(mundo_log_path, session_id=sid)

    # ── Score global (média ponderada — baseado em RPGBench) ──
    # GS4/GS5 só fazem sentido quando há ações avaliadas
    if internas["acoes_avaliadas"] > 0:
        gs4_norm = min(5.0, internas["criatividade_media"] * 5)
        gs5_norm = min(5.0, internas["eficiencia_media"]  * 2.5)
    else:
        gs4_norm = None
        gs5_norm = None

    if mundo_score is not None and mundo_score > 0:
        pesos = {"gs1":0.25,"gs3":0.14,"gs6":0.25,"gs4":0.04,"gs5":0.02,"qc1":0.03,"mw":0.27}
    else:
        pesos = {"gs1":0.36,"gs3":0.25,"gs6":0.30,"gs4":0.04,"gs5":0.02,"qc1":0.03}

    metric_pairs = [
        (gs1_score,    pesos.get("gs1", 0)),
        (gs3_score,    pesos.get("gs3", 0)),
        (gs6_score,    pesos.get("gs6", 0)),
        (gs4_norm,     pesos.get("gs4", 0)),
        (gs5_norm,     pesos.get("gs5", 0)),
        (qc1_score,    pesos.get("qc1", 0)),
        (mundo_score,  pesos.get("mw",  0)),
    ]
    valid = [(v, w) for v, w in metric_pairs if v is not None and w > 0]
    if valid:
        total_w = sum(w for _, w in valid)
        score_global = round(sum(v * w for v, w in valid) / total_w, 2)
    else:
        score_global = None

    resultado = {
        "arquivo"       : caminho.name,
        "personagem"    : personagem,
        "modelo"        : modelo,
        "data_sessao"   : caminho.stem.replace("sessao_",""),
        "metricas": {
            "GS1_qualidade_narrativa"  : gs1_score,
            "GS3_coerencia_acao"       : gs3_score,
            "GS6_consistencia_estado"  : gs6_score,
            "QC1_criatividade_jogador_pregame": qc1_score,
            "GS4_criatividade_jogador" : (round(gs4_norm, 2) if gs4_norm is not None else None),
            "GS5_eficiencia_mecanica"  : (round(gs5_norm, 2) if gs5_norm is not None else None),
            "MW1_narracao_mundo"       : mundo_detalhes.get("MW1_qualidade_narracao_mundo", 0),
            "MW2_consistencia_mundo"   : mundo_detalhes.get("MW2_consistencia_modificacoes", 0),
            "score_mundo"              : mundo_score,
            "score_global"             : score_global,
        },
        "internas"      : internas,
        "mundo_aberto"  : {"tipos": mundo_tipos, "total_acoes": mundo_acoes},
        "diagnostico"   : {
            "modelo_judge"          : _JUDGE_STATS["modelo_judge"],
            "backend_judge"         : _JUDGE_STATS["backend_judge"],
            "chamadas_totais"       : _JUDGE_STATS["chamadas_totais"],
            "chamadas_com_parse_ok" : _JUDGE_STATS["chamadas_com_parse_ok"],
            "chamadas_falha_parse"  : _JUDGE_STATS["chamadas_falha_parse"],
            "taxa_sucesso_parse"    : (
                round(_JUDGE_STATS["chamadas_com_parse_ok"] /
                      _JUDGE_STATS["chamadas_totais"], 3)
                if _JUDGE_STATS["chamadas_totais"] else None
            ),
            "exemplos_falha"        : list(_JUDGE_STATS["exemplos_falha"]),
        },
        "detalhes": {
            "narrativas" : gs1_detalhe,
            "consistencia": gs6_detalhe,
            "questionario": qc1_detalhe,
        },
    }

    _exibir_resultado(resultado)
    return resultado


def _exibir_resultado(r: dict) -> None:
    m = r["metricas"]
    i = r["internas"]
    print(f"\n{'─'*60}")
    print(f"  RESULTADO — {r['arquivo']}")
    print(f"{'─'*60}")
    print(f"  GS1 Qualidade Narrativa   : {_fmt(m['GS1_qualidade_narrativa'])}/5.0")
    print(f"  GS3 Coerência Ação→Narr   : {_fmt(m['GS3_coerencia_acao'])}/5.0")
    print(f"  GS6 Consistência Estado   : {_fmt(m['GS6_consistencia_estado'])}/5.0")
    print(f"  QC1 Qualidade Questionário: {_fmt(m.get('QC1_criatividade_jogador_pregame'))}/5.0")
    print(f"  GS4 Criatividade Jogador  : {_fmt(m['GS4_criatividade_jogador'])}/5.0")
    print(f"  GS5 Eficiência Mecânica   : {_fmt(m['GS5_eficiencia_mecanica'])}/5.0")
    if m.get("score_mundo") is not None and m.get("score_mundo", 0) > 0:
        print(f"  MW1 Narração Mundo Aberto : {_fmt(m.get('MW1_narracao_mundo'))}/5.0")
        print(f"  MW2 Consistência Mundo    : {_fmt(m.get('MW2_consistencia_mundo'))}/5.0")
    print(f"{'─'*60}")
    sg = m.get('score_global')
    status = ('—' if sg is None else
              ('APROVADO' if sg >= PASS_THRESHOLD else 'ABAIXO DO LIMIAR'))
    print(f"  ★  SCORE GLOBAL           : {_fmt(sg)}/5.0  ({status})")
    # Diagnóstico do judge
    diag = r.get("diagnostico", {})
    if diag:
        taxa = diag.get("taxa_sucesso_parse")
        taxa_str = f"{taxa*100:.1f}%" if taxa is not None else "—"
        print(f"  Judge: {diag.get('modelo_judge','?')} ({diag.get('backend_judge','?')})  "
              f"| chamadas={diag.get('chamadas_totais',0)}  "
              f"| parse OK={diag.get('chamadas_com_parse_ok',0)} ({taxa_str})")
    print(f"{'─'*60}")
    print(f"  Ações avaliadas: {i['acoes_avaliadas']}  "
          f"| Criatividade média: {i['criatividade_media']:.3f}  "
          f"| Eficiência: {i['eficiencia_media']:.3f}")
    print(f"  Tempo médio LLM: {i['tempo_medio_llm_s']:.1f}s  "
          f"| Tokens/sessão: {i['tokens_total_sessao']:,}")
    if r["mundo_aberto"]["total_acoes"]:
        print(f"  Mundo Aberto: {r['mundo_aberto']['total_acoes']} eventos "
              f"({', '.join(r['mundo_aberto']['tipos'][:4])})")


# ══════════════════════════════════════════════════════════════
#  RELATÓRIO AGREGADO (múltiplas sessões)
# ══════════════════════════════════════════════════════════════

def gerar_relatorio_agregado(resultados: List[dict], saida: Path) -> None:
    """Gera CSV + JSON com métricas agregadas de todas as sessões."""
    if not resultados:
        return

    # ── CSV por sessão ────────────────────────────────────────
    csv_path = saida / "rpg_judge_resultados.csv"
    campos = ["arquivo", "data_sessao", "personagem", "modelo",
              "GS1_qualidade_narrativa", "GS3_coerencia_acao",
              "GS6_consistencia_estado", "QC1_criatividade_jogador_pregame",
              "GS4_criatividade_jogador", "GS5_eficiencia_mecanica",
              "score_global", "acoes_avaliadas", "criatividade_media",
              "eficiencia_media", "tempo_medio_llm_s", "tokens_total_sessao"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for r in resultados:
            row = {**{k: v for k,v in r.items() if k in campos},
                   **r["metricas"], **r["internas"]}
            w.writerow({c: row.get(c, "") for c in campos})

    # ── Médias globais (ignora None / 0) ──────────────────────
    def media(campo):
        vals = [r["metricas"].get(campo) for r in resultados
                if r["metricas"].get(campo) is not None]
        return round(sum(vals)/len(vals), 3) if vals else None

    agregado = {
        "n_sessoes"       : len(resultados),
        "modelos"         : list(set(r["modelo"] for r in resultados)),
        "data_avaliacao"  : datetime.now().isoformat(timespec="seconds"),
        "medias": {
            "GS1_qualidade_narrativa"  : media("GS1_qualidade_narrativa"),
            "GS3_coerencia_acao"       : media("GS3_coerencia_acao"),
            "GS6_consistencia_estado"  : media("GS6_consistencia_estado"),
            "QC1_criatividade_jogador_pregame"         : media("QC1_criatividade_jogador_pregame"),
            "GS4_criatividade_jogador" : media("GS4_criatividade_jogador"),
            "GS5_eficiencia_mecanica"  : media("GS5_eficiencia_mecanica"),
            "score_global"             : media("score_global"),
        },
        "sessoes": resultados,
    }

    # ── JSON completo ─────────────────────────────────────────
    json_path = saida / "rpg_judge_agregado.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(agregado, f, ensure_ascii=False, indent=2)

    # ── Exibe resumo ──────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  RPG-JUDGE — RELATÓRIO AGREGADO ({len(resultados)} sessões)")
    print(f"{'='*60}")
    m = agregado["medias"]
    print(f"  GS1 Qualidade Narrativa   : {_fmt(m['GS1_qualidade_narrativa'])}/5.0")
    print(f"  GS3 Coerência Ação→Narr   : {_fmt(m['GS3_coerencia_acao'])}/5.0")
    print(f"  GS6 Consistência Estado   : {_fmt(m['GS6_consistencia_estado'])}/5.0")
    print(f"  QC1 Qualidade Questionário: {_fmt(m.get('QC1_criatividade_jogador_pregame'))}/5.0")
    print(f"  GS4 Criatividade Jogador  : {_fmt(m['GS4_criatividade_jogador'])}/5.0")
    print(f"  GS5 Eficiência Mecânica   : {_fmt(m['GS5_eficiencia_mecanica'])}/5.0")
    print(f"{'─'*60}")
    print(f"  ★  SCORE GLOBAL MÉDIO     : {_fmt(m['score_global'])}/5.0")
    print(f"{'─'*60}")
    print(f"\n  Resultados salvos:")
    print(f"    {csv_path}")
    print(f"    {json_path}")


# ══════════════════════════════════════════════════════════════
#  AVALIAÇÃO DO MUNDO ABERTO (mundo_log.csv)
# ══════════════════════════════════════════════════════════════

PROMPT_MUNDO_NARRACAO = """Você é um avaliador de qualidade narrativa em RPG de mundo aberto.
Avalie a narração gerada pelo GM para a ação do jogador neste local.

Bioma: {bioma} | Coordenadas: ({x},{y},{z})
Ação do jogador: "{acao}"
Narração gerada: "{narracao}"

Avalie ({escala}):
- qualidade: riqueza descritiva, vocabulário, coerência com o bioma
- relevancia: a narração reflete a ação "{acao_curta}" no contexto do bioma?
- imersao: evoca sensações, atmosfera, folclore brasileiro?

Responda APENAS com JSON:
{{"qualidade": N, "relevancia": N, "imersao": N, "justificativa": "..."}}"""

PROMPT_MUNDO_CONSISTENCIA = """Avalie se as modificações ambientais no mesmo local são consistentes.

Local: bioma={bioma} coord=({x},{y},{z})
Modificação 1 (T{t1}): {acao1} → {desc1}
Modificação 2 (T{t2}): {acao2} → {desc2}

As duas modificações são fisicamente compatíveis? 
(ex: lugar congelado não pode pegar fogo logo depois)

Responda APENAS com JSON:
{{"compativel": true/false, "score": N, "observacao": "..."}}
onde score: {escala}"""


def avaliar_mundo_log(caminho_mundo: Path, session_id: str = "") -> Tuple[float, dict]:
    """
    Avalia o mundo_log.csv — narrações de exploração, modificações, encontros.
    Filtra por session_id para avaliar apenas a sessão correspondente.
    Retorna (score_medio, detalhes).
    """
    if not caminho_mundo.exists():
        return 0.0, {"erro": "mundo_log.csv não encontrado"}

    with open(caminho_mundo, encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    if not all_rows:
        return 0.0, {"erro": "mundo_log.csv vazio"}

    # Filtra apenas os eventos da sessão atual (session_id)
    if session_id and "session_id" in (all_rows[0] if all_rows else {}):
        rows = [r for r in all_rows if r.get("session_id","") == session_id]
        if not rows:
            rows = all_rows  # fallback se session_id não bater
            print(f"  ⚠  session_id '{session_id}' não encontrado — avaliando tudo")
    else:
        rows = all_rows

    print(f"  Avaliando {len(rows)} eventos do mundo aberto...", end="", flush=True)

    # ── MW1: Qualidade das narrações de exploração ────────────
    narrações_mundo = [r for r in rows
                       if r.get("tipo_evento") in ("acao_livre", "chegada", "movimento")
                       and r.get("descricao_preview", "").strip()]

    mw1_scores = []
    mw1_detalhes = []
    for r in narrações_mundo[:20]:  # max 20 para não sobrecarregar
        narracao = r.get("descricao_preview", "")
        acao     = r.get("acao_jogador", "")
        if len(narracao) < 10:
            continue
        prompt = PROMPT_MUNDO_NARRACAO.format(
            bioma=r.get("bioma","?"),
            x=r.get("x","0"), y=r.get("y","0"), z=r.get("z","0"),
            acao=acao[:100], acao_curta=acao[:30],
            narracao=narracao[:250],
            escala=ESCALA_LIKERT,
        )
        res = _chamar_judge(prompt)
        q = _nota(res, "qualidade")
        rv = _nota(res, "relevancia")
        im = _nota(res, "imersao")
        media = _media_validas([q, rv, im])
        if media is not None: mw1_scores.append(media)
        mw1_detalhes.append({
            "turno": r.get("turno"), "coord": f"({r.get('x')},{r.get('y')},{r.get('z')})",
            "bioma": r.get("bioma"), "acao": acao[:50],
            "qualidade": q, "relevancia": rv, "imersao": im, "media": media,
            "justificativa": res.get("justificativa",""),
        })
        print(".", end="", flush=True)

    mw1 = _media_validas(mw1_scores)

    # ── MW2: Consistência das modificações por coord ──────────
    from collections import defaultdict
    mods_por_coord = defaultdict(list)
    for r in rows:
        if r.get("tipo_evento","").startswith("mod_"):
            coord_key = f"{r.get('x')},{r.get('y')},{r.get('z')}"
            mods_por_coord[coord_key].append(r)

    mw2_scores = []
    mw2_detalhes = []
    for coord, mods in mods_por_coord.items():
        if len(mods) < 2:
            continue
        r1, r2 = mods[0], mods[1]
        prompt = PROMPT_MUNDO_CONSISTENCIA.format(
            bioma=r1.get("bioma","?"),
            x=r1.get("x","0"), y=r1.get("y","0"), z=r1.get("z","0"),
            t1=r1.get("turno","?"), acao1=r1.get("acao_jogador","?")[:50],
            desc1=r1.get("descricao_preview","?")[:80],
            t2=r2.get("turno","?"), acao2=r2.get("acao_jogador","?")[:50],
            desc2=r2.get("descricao_preview","?")[:80],
            escala=ESCALA_LIKERT,
        )
        res = _chamar_judge(prompt)
        score = _nota(res, "score")
        if score is not None: mw2_scores.append(score)
        mw2_detalhes.append({
            "coord": coord, "score": score,
            "compativel": res.get("compativel", True),
            "observacao": res.get("observacao",""),
        })
        print(".", end="", flush=True)

    mw2 = _media_validas(mw2_scores)   # None se sem dado (não inflar com 5.0)

    # ── Estatísticas gerais ───────────────────────────────────
    tipos = {}
    for r in rows:
        t = r.get("tipo_evento","")
        tipos[t] = tipos.get(t, 0) + 1

    coords_unicas = len(set(
        f"{r.get('x')},{r.get('y')},{r.get('z')}" for r in rows
    ))
    encontros = [r for r in rows if r.get("tipo_evento") == "encontro"]
    vitorias  = sum(1 for r in encontros if r.get("resultado_encontro") == "vitoria")

    print()
    # score_mundo: média ponderada SOMENTE sobre métricas válidas
    parts, ws = [], []
    if mw1 is not None: parts.append(mw1); ws.append(0.7)
    if mw2 is not None: parts.append(mw2); ws.append(0.3)
    score_medio = round(sum(p*w for p,w in zip(parts,ws))/sum(ws), 2) if ws else None

    detalhes = {
        "MW1_qualidade_narracao_mundo": mw1,
        "MW2_consistencia_modificacoes": mw2,
        "score_mundo": score_medio,
        "stats": {
            "coords_visitadas": coords_unicas,
            "total_eventos": len(rows),
            "tipos_evento": tipos,
            "encontros": len(encontros),
            "vitorias": vitorias,
            "taxa_vitoria": round(vitorias/len(encontros), 2) if encontros else 0,
        },
        "detalhes_narracao": mw1_detalhes,
        "detalhes_consistencia": mw2_detalhes,
    }
    return score_medio, detalhes


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="RPG-Judge — Avaliação automática de sessões RPG via LLM-as-a-Judge"
    )
    parser.add_argument(
        "alvo", nargs="?", default="logs/",
        help="Arquivo CSV ou pasta com CSVs (default: logs/)"
    )
    parser.add_argument(
        "--saida", default="judge_results/",
        help="Pasta de saída dos relatórios (default: judge_results/)"
    )
    parser.add_argument(
        "--modelo", default=None,
        help="Modelo LLM para julgamento (sobrescreve llm_config.py)"
    )
    args = parser.parse_args()

    # Configura modelo do judge se especificado
    if args.modelo:
        try:
            import llm_config as cfg
            cfg.LMSTUDIO_MODEL = args.modelo
        except Exception:
            pass

    saida = Path(args.saida)
    saida.mkdir(exist_ok=True)

    # Coleta arquivos CSV
    alvo = Path(args.alvo)
    if alvo.is_file() and alvo.suffix == ".csv":
        csvs = [alvo]
    elif alvo.is_dir():
        csvs = sorted(alvo.glob("sessao_*.csv"))
        if not csvs:
            print(f"Nenhum CSV de sessão encontrado em {alvo}")
            sys.exit(1)
    else:
        print(f"Alvo inválido: {alvo}")
        sys.exit(1)

    print(f"\n  RPG-Judge v1.0 — {len(csvs)} sessão(ões) para avaliar")
    print(f"  Baseado em: YU et al. (2025) RPGBench | CHEN et al. (2024)")
    print(f"  Saída: {saida.resolve()}")

    resultados = []
    for csv_path in csvs:
        try:
            r = avaliar_sessao(csv_path)
            resultados.append(r)
            # Salva resultado individual
            json_ind = saida / f"judge_{csv_path.stem}.json"
            with open(json_ind, "w", encoding="utf-8") as f:
                # Remove detalhes volumosos para o JSON individual
                r_slim = {k: v for k, v in r.items() if k != "detalhes"}
                json.dump(r_slim, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ✗ Erro ao avaliar {csv_path.name}: {e}")

    if len(resultados) > 1:
        gerar_relatorio_agregado(resultados, saida)
    elif resultados:
        gerar_relatorio_agregado(resultados, saida)

    print("\n  Avaliação concluída.")


if __name__ == "__main__":
    main()