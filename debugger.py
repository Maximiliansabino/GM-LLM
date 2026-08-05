"""
debugger.py
─────────────────────────────────────────────────────────────
Ferramenta de auditoria e debug do sistema RPG LLM.

Instrumenta as funções-chave do pipeline de combate via decoradores,
registrando inputs/outputs com timestamps e exibindo um painel
visual em tempo real no terminal.

ATIVAÇÃO:
  No menu principal ou via variável de ambiente:
    DEBUG_RPG=1 python main.py

  Ou programaticamente:
    from debugger import ativar, desativar, painel
    ativar()

NÍVEIS:
  0 = OFF      — sem output de debug
  1 = RESUMIDO — só resultados finais por turno
  2 = NORMAL   — inputs/outputs de cada função
  3 = VERBOSE  — inclui prompts completos ao LLM

ARQUIVO DE LOG:
  debug_log.jsonl — uma linha JSON por evento, append-only
  Pode ser importado e analisado depois:
    python debugger.py analyze debug_log.jsonl
─────────────────────────────────────────────────────────────
"""

import os
import sys
import json
import time
import functools
import threading
from datetime import datetime
from typing import Any, Callable, Optional
from collections import deque

# ── Estado global ─────────────────────────────────────────────
_NIVEL: int  = 0
_LOG_FILE     = "jornada/debug_log.jsonl"
_eventos: deque = deque(maxlen=200)   # ring buffer em memória
_lock = threading.Lock()
_turno_atual = 0
_sessao_id   = datetime.now().strftime("%Y%m%d_%H%M%S")

# ── Cores ANSI ────────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    # foreground
    RED    = "\033[31m";  LRED   = "\033[91m"
    GREEN  = "\033[32m";  LGREEN = "\033[92m"
    YELLOW = "\033[33m";  LYELLOW= "\033[93m"
    BLUE   = "\033[34m";  LBLUE  = "\033[94m"
    MAGENTA= "\033[35m";  LMAG   = "\033[95m"
    CYAN   = "\033[36m";  LCYAN  = "\033[96m"
    WHITE  = "\033[37m";  LGRAY  = "\033[90m"
    # backgrounds
    BGRED  = "\033[41m";  BGGRN  = "\033[42m"
    BGBLU  = "\033[44m";  BGCYAN = "\033[46m"
    BGMAG  = "\033[45m";  BGGRAY = "\033[100m"


# ── Categorias de evento com cores ────────────────────────────
CATS = {
    "LLM_CALL"   : (C.MAGENTA,  "◈ LLM"),
    "LLM_RESP"   : (C.LMAG,     "◉ LLM"),
    "CACHE_HIT"  : (C.CYAN,     "⚡ CACHE"),
    "CACHE_MISS" : (C.LGRAY,    "○ CACHE"),
    "CACHE_STORE": (C.BLUE,     "● CACHE"),
    "CRIATIVIDADE": (C.YELLOW,  "★ CRIA"),
    "EFICIENCIA" : (C.GREEN,    "⊕ EFI"),
    "PSIQUE"     : (C.LMAG,     "Ψ PSI"),
    "DANO"       : (C.RED,      "⚔ DANO"),
    "INIMIGO_ATK": (C.LRED,     "⚡ INI"),
    "TURNO"      : (C.LCYAN,    "► TURN"),
    "MAESTRIA"   : (C.LYELLOW,  "✦ MAES"),
    "JORNADA"    : (C.LGRAY,    "💾 JRN"),
    "ERROR"      : (C.LRED,     "✖ ERRO"),
    "INFO"       : (C.LBLUE,    "ℹ INFO"),
}

# ── API pública ───────────────────────────────────────────────

def ativar(nivel: int = 2) -> None:
    global _NIVEL
    _NIVEL = max(0, min(3, nivel))
    os.makedirs("jornada", exist_ok=True)
    _log_evento("INFO", "Debugger ativado", {"nivel": _NIVEL, "sessao": _sessao_id})
    _print_header()

def desativar() -> None:
    global _NIVEL, _INSTALADO
    _NIVEL = 0
    _INSTALADO = False

def nivel_atual() -> int:
    return _NIVEL

def set_turno(t: int) -> None:
    global _turno_atual
    _turno_atual = t


# ── Registro de evento ────────────────────────────────────────

def _log_evento(categoria: str, descricao: str, dados: dict = None,
                turno: int = None) -> None:
    """Registra um evento no buffer em memória e no arquivo JSONL."""
    if _NIVEL == 0:
        return
    ts = time.perf_counter()
    evento = {
        "ts"       : datetime.now().isoformat(timespec="milliseconds"),
        "sessao"   : _sessao_id,
        "turno"    : turno if turno is not None else _turno_atual,
        "categoria": categoria,
        "descricao": descricao,
        "dados"    : dados or {},
    }
    with _lock:
        _eventos.append(evento)
        try:
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(evento, ensure_ascii=False) + "\n")
        except Exception:
            pass


# ── Impressão formatada ───────────────────────────────────────

def _ts() -> str:
    return f"{C.LGRAY}{datetime.now().strftime('%H:%M:%S.%f')[:-3]}{C.RESET}"

def _prefix(categoria: str) -> str:
    col, label = CATS.get(categoria, (C.WHITE, categoria[:6]))
    return f"{_ts()} {col}{C.BOLD}{label:10}{C.RESET}"

def _print(categoria: str, linha: str, nivel_min: int = 1) -> None:
    if _NIVEL < nivel_min:
        return
    print(f"  {_prefix(categoria)} {linha}")

def _print_sep(char="─", col=C.LGRAY, n=60) -> None:
    if _NIVEL < 1:
        return
    print(f"  {col}{char * n}{C.RESET}")

def _print_header() -> None:
    print(f"\n  {C.BGCYAN}{C.BOLD}  DEBUG RPG LLM — Nível {_NIVEL}  {C.RESET}  "
          f"{C.LGRAY}sessão {_sessao_id}{C.RESET}")
    print(f"  {C.LGRAY}Log: {_LOG_FILE}  |  nível 1=resumido 2=normal 3=verbose{C.RESET}\n")


# ── Decoradores ───────────────────────────────────────────────

def trace_llm(func: Callable) -> Callable:
    """Instrumenta chamadas ao LLM — mostra prompt (nível 3) e resposta."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if _NIVEL == 0:
            return func(*args, **kwargs)

        prompt     = args[0] if args else kwargs.get("prompt", "")
        num_pred   = kwargs.get("num_predict") or (args[3] if len(args) > 3 else 80)
        label      = kwargs.get("label", "LLM")
        t0 = time.perf_counter()

        # Nível 3: mostra prompt completo
        if _NIVEL >= 3:
            _print_sep("┌")
            _print("LLM_CALL", f"{C.BOLD}PROMPT ({len(prompt)} chars, max_tokens={num_pred}){C.RESET}", 3)
            for ln in prompt.split("\n")[:20]:
                print(f"  {C.LGRAY}│ {ln}{C.RESET}")
            if prompt.count("\n") > 20:
                print(f"  {C.LGRAY}│ ... ({prompt.count(chr(10))-20} linhas omitidas){C.RESET}")
            _print_sep("└")
        else:
            _print("LLM_CALL", f"prompt {len(prompt)}ch → max_tokens={num_pred}", 2)

        _log_evento("LLM_CALL", f"{func.__name__}", {"prompt_len": len(prompt), "num_predict": num_pred})

        result = func(*args, **kwargs)

        dt = (time.perf_counter() - t0) * 1000
        resp_preview = str(result)[:120].replace("\n", " ")

        if _NIVEL >= 2:
            _print("LLM_RESP", f"{C.GREEN}{dt:.0f}ms{C.RESET}  {C.LGRAY}{resp_preview}{C.RESET}", 2)
        else:
            _print("LLM_RESP", f"{C.GREEN}{dt:.0f}ms{C.RESET}", 1)

        _log_evento("LLM_RESP", "resposta recebida", {"ms": round(dt), "resp_preview": resp_preview})
        return result
    return wrapper


def trace_cache(func_buscar: Callable) -> Callable:
    """Instrumenta cache_llm.buscar — mostra hit/miss e similaridade."""
    @functools.wraps(func_buscar)
    def wrapper(acao: str):
        if _NIVEL == 0:
            return func_buscar(acao)

        result = func_buscar(acao)

        if result is not None:
            score, just = result
            _print("CACHE_HIT",
                   f"'{C.CYAN}{acao[:30]}{C.RESET}' → "
                   f"{C.BOLD}{score:.3f}{C.RESET}  {C.LGRAY}{just[:50]}{C.RESET}", 2)
            _log_evento("CACHE_HIT", acao[:60], {"score": score})
        else:
            _print("CACHE_MISS", f"'{C.LGRAY}{acao[:30]}{C.RESET}' → sem match (LLM necessário)", 2)
            _log_evento("CACHE_MISS", acao[:60])
        return result
    return wrapper


def trace_avaliar(func: Callable) -> Callable:
    """Instrumenta avaliar_acao — mostra criatividade, eficiência e componentes."""
    @functools.wraps(func)
    def wrapper(acao, inimigo, contexto):
        if _NIVEL == 0:
            return func(acao, inimigo, contexto)

        _print_sep()
        _print("TURNO", f"avaliando ação: {C.BOLD}'{acao}'{C.RESET}", 1)

        result = func(acao, inimigo, contexto)
        cri, efi, just, componentes, tipo_dano_fisico = result

        cri_col = C.LGREEN if cri >= 0.8 else (C.YELLOW if cri >= 0.65 else C.LRED)
        efi_col = C.LGREEN if efi >= 1.2 else (C.YELLOW if efi >= 0.9 else C.LRED)

        _print("CRIATIVIDADE",
               f"{cri_col}{C.BOLD}{cri:.3f}{C.RESET}  "
               f"{C.LGRAY}(fator {cri**2:.3f}×){C.RESET}  {just[:60]}", 1)
        tipo_str = f"  tipo: {tipo_dano_fisico}" if tipo_dano_fisico else ""
        _print("EFICIENCIA",
               f"{efi_col}{C.BOLD}{efi:.3f}{C.RESET}  "
               f"{C.LGRAY}vs {inimigo.nome} [{inimigo.tipo_defesa}]{tipo_str}{C.RESET}", 1)

        if componentes:
            from config import CUSTOS_PSIQUE
            custo_total = sum(CUSTOS_PSIQUE.get(c, 0) for c in componentes)
            comp_str = " + ".join(f"{c}({CUSTOS_PSIQUE.get(c,0)}Ψ)" for c in componentes)
            _print("PSIQUE",
                   f"componentes: {C.LMAG}{comp_str}{C.RESET}  "
                   f"= {C.BOLD}{custo_total:.1f} Ψ{C.RESET}", 1)
        else:
            _print("PSIQUE", f"{C.LGRAY}sem componentes → 0.0 Ψ{C.RESET}", 2)

        _log_evento("CRIATIVIDADE", acao[:60],
                    {"cri": cri, "efi": efi, "componentes": componentes, "just": just})
        return result
    return wrapper


def trace_dano(func: Callable) -> Callable:
    """Instrumenta calcular_dano_final — mostra breakdown completo."""
    @functools.wraps(func)
    def wrapper(personagem, inimigo, criatividade, eficiencia, habilidade_ativa=None):
        if _NIVEL == 0:
            return func(personagem, inimigo, criatividade, eficiencia, habilidade_ativa)

        result = func(personagem, inimigo, criatividade, eficiencia, habilidade_ativa)
        dano_final, bd = result

        if _NIVEL >= 2:
            _print("DANO",
                   f"{C.LGRAY}D_pessoal={bd['dano_personagem']:.1f}  "
                   f"× efi={bd['eficiencia']:.2f}  "
                   f"× c²={bd['criatividade²']:.3f}  "
                   f"= bruto {bd['dano_bruto']:.1f}  "
                   f"- def {bd['defesa_inimigo']:.0f}{C.RESET}", 2)

        dano_col = C.LRED if dano_final > 30 else (C.YELLOW if dano_final > 10 else C.LGRAY)
        _print("DANO",
               f"{dano_col}{C.BOLD}DANO FINAL: {dano_final:.1f}{C.RESET}  "
               f"{C.LGRAY}→ {inimigo.nome} "
               f"PV {inimigo.pv_atual:.0f}/{inimigo.pv_max:.0f}{C.RESET}", 1)

        _log_evento("DANO", f"{personagem.nome} → {inimigo.nome}",
                    {"dano": dano_final, "breakdown": bd})
        return result
    return wrapper


def trace_inimigo(func: Callable) -> Callable:
    """Instrumenta processar_turno_inimigo — mostra ataque escolhido."""
    @functools.wraps(func)
    def wrapper(inimigo, personagem):
        if _NIVEL == 0:
            return func(inimigo, personagem)

        result = func(inimigo, personagem)

        atk_nome = result.get("ataque", "Ataque")
        dano     = result.get("dano", 0)
        especial = result.get("especial", False)

        atk_col = C.LRED if especial else C.LGRAY
        especial_str = f"{C.LRED}[ESPECIAL]{C.RESET} " if especial else ""
        _print("INIMIGO_ATK",
               f"{C.BOLD}{inimigo.nome}{C.RESET} usa "
               f"{atk_col}{especial_str}{atk_nome}{C.RESET}  "
               f"dano={C.RED}{dano:.1f}{C.RESET}  "
               f"→ {personagem.nome} PV {personagem.pv_atual:.0f}/{personagem.pv_max:.0f}", 1)

        _log_evento("INIMIGO_ATK", f"{inimigo.nome} usa {atk_nome}",
                    {"dano": dano, "especial": especial, "pv_restante": personagem.pv_atual})
        return result
    return wrapper


def trace_turno(func: Callable) -> Callable:
    """Instrumenta processar_turno_jogador — mostra resumo do turno."""
    @functools.wraps(func)
    def wrapper(acao, personagem, inimigo, turno):
        if _NIVEL == 0:
            return func(acao, personagem, inimigo, turno)

        global _turno_atual
        _turno_atual = turno

        t0 = time.perf_counter()
        result = func(acao, personagem, inimigo, turno)
        dt = (time.perf_counter() - t0) * 1000

        _print("TURNO",
               f"T{turno}  {C.LGRAY}ação: '{acao[:25]}'  "
               f"total {dt:.0f}ms{C.RESET}", 2)

        _log_evento("TURNO", f"turno {turno} concluído",
                    {"acao": acao, "ms": round(dt),
                     "cri": result.get("criatividade"),
                     "dano": result.get("dano_causado"),
                     "inimigo_vivo": result.get("inimigo_vivo")}, turno=turno)
        return result
    return wrapper


def trace_jornada(func: Callable, nome: str = "") -> Callable:
    """Instrumenta funções de jornada (escrita/leitura) no nível 3."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if _NIVEL < 3:
            return func(*args, **kwargs)

        result = func(*args, **kwargs)
        desc = args[0] if args else ""
        _print("JORNADA", f"{nome or func.__name__}({str(desc)[:40]})", 3)
        return result
    return wrapper


# ══════════════════════════════════════════════════════════════
#  APLICAÇÃO DOS DECORADORES
# ══════════════════════════════════════════════════════════════

_INSTALADO: bool = False

def instalar() -> None:
    """
    Aplica os decoradores de debug nas funções-chave.
    Idempotente — ignora chamadas repetidas para não empilhar wrappers.
    Usa monkey-patching — não altera o código fonte.
    """
    global _INSTALADO
    if _INSTALADO:
        return
    _INSTALADO = True

    import combate
    import cache_llm
    import llm_backend
    import jornada

    # LLM backend
    llm_backend._chamar_ollama = trace_llm(llm_backend._chamar_ollama)
    llm_backend._chamar_groq   = trace_llm(llm_backend._chamar_groq)

    # Cache
    cache_llm.buscar    = trace_cache(cache_llm.buscar)

    # Combat pipeline
    combate.avaliar_acao           = trace_avaliar(combate.avaliar_acao)
    combate.calcular_dano_final    = trace_dano(combate.calcular_dano_final)
    combate.processar_turno_jogador = trace_turno(combate.processar_turno_jogador)
    combate.processar_turno_inimigo = trace_inimigo(combate.processar_turno_inimigo)

    # Jornada I/O (nível 3 only)
    jornada.registrar_evento    = trace_jornada(jornada.registrar_evento, "reg_evento")
    jornada.atualizar_personagem = trace_jornada(jornada.atualizar_personagem, "upd_pers")
    jornada.avancar_turno       = trace_jornada(jornada.avancar_turno, "avancar_turno")

    _print("INFO", f"{C.GREEN}Decoradores instalados — {len(_NIVEL_DESCS[_NIVEL])} categorias ativas{C.RESET}", 1)


_NIVEL_DESCS = {
    0: [],
    1: ["TURNO", "CRIATIVIDADE", "EFICIENCIA", "PSIQUE", "DANO", "INIMIGO_ATK"],
    2: ["+ LLM_CALL", "LLM_RESP", "CACHE_HIT", "CACHE_MISS"],
    3: ["+ JORNADA I/O", "prompts completos"],
}


# ══════════════════════════════════════════════════════════════
#  PAINEL DE ESTATÍSTICAS
# ══════════════════════════════════════════════════════════════

def painel_sessao() -> None:
    """Exibe painel estatístico da sessão atual (lido do buffer em memória)."""
    if not _eventos:
        print(f"\n  {C.LGRAY}Nenhum evento registrado nesta sessão.{C.RESET}")
        return

    cats = {}
    llm_tempos = []
    turnos = []
    danos  = []
    criatividades = []
    cache_hits = cache_misses = 0

    for ev in _eventos:
        cat = ev["categoria"]
        cats[cat] = cats.get(cat, 0) + 1
        if cat == "LLM_RESP":
            llm_tempos.append(ev["dados"].get("ms", 0))
        if cat == "TURNO":
            turnos.append(ev["dados"])
        if cat == "DANO":
            danos.append(ev["dados"].get("dano", 0))
        if cat == "CRIATIVIDADE":
            criatividades.append(ev["dados"].get("cri", 0))
        if cat == "CACHE_HIT":
            cache_hits += 1
        if cat == "CACHE_MISS":
            cache_misses += 1

    W = 60
    print(f"\n  {C.BGCYAN}{C.BOLD}  PAINEL DA SESSÃO  {C.RESET}")
    print(f"  {C.LGRAY}{'─'*W}{C.RESET}")

    # LLM stats
    if llm_tempos:
        avg = sum(llm_tempos) / len(llm_tempos)
        total = sum(llm_tempos) / 1000
        print(f"  {C.MAGENTA}◈ LLM{C.RESET}  {len(llm_tempos)} chamadas  "
              f"avg {avg:.0f}ms  total {total:.1f}s")

    # Cache stats
    total_cache = cache_hits + cache_misses
    if total_cache:
        hit_rate = cache_hits / total_cache * 100
        bar = int(hit_rate / 5)
        print(f"  {C.CYAN}⚡ CACHE{C.RESET} {cache_hits}/{total_cache} hits  "
              f"[{'█'*bar}{'░'*(20-bar)}] {hit_rate:.0f}%")

    # Criatividade
    if criatividades:
        avg_cri = sum(criatividades) / len(criatividades)
        cri_col = C.LGREEN if avg_cri >= 0.75 else (C.YELLOW if avg_cri >= 0.65 else C.LRED)
        dist = {f"{v:.1f}": sum(1 for c in criatividades if abs(c - v) < 0.05)
                for v in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]}
        print(f"  {C.YELLOW}★ CRIA{C.RESET} avg {cri_col}{avg_cri:.3f}{C.RESET}  "
              f"dist: {' '.join(f'{k}×{v}' for k,v in dist.items() if v)}")

    # Danos
    if danos:
        print(f"  {C.RED}⚔ DANO{C.RESET} "
              f"min={min(danos):.1f}  max={max(danos):.1f}  "
              f"avg={sum(danos)/len(danos):.1f}  total={sum(danos):.1f}")

    # Turnos
    if turnos:
        t_ms = [t["ms"] for t in turnos if "ms" in t]
        if t_ms:
            print(f"  {C.LCYAN}► TURN{C.RESET} {len(turnos)} turnos  "
                  f"avg {sum(t_ms)/len(t_ms):.0f}ms/turno  "
                  f"total {sum(t_ms)/1000:.1f}s")

    print(f"  {C.LGRAY}{'─'*W}")
    print(f"  Log: {_LOG_FILE}  ({len(_eventos)} eventos){C.RESET}\n")


# ══════════════════════════════════════════════════════════════
#  ANALISADOR DE LOG (modo standalone)
# ══════════════════════════════════════════════════════════════

def analisar_log(caminho: str) -> None:
    """
    Lê um arquivo debug_log.jsonl e exibe estatísticas detalhadas.
    Uso: python debugger.py analyze debug_log.jsonl
    """
    if not os.path.exists(caminho):
        print(f"Arquivo não encontrado: {caminho}")
        return

    eventos = []
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            try:
                eventos.append(json.loads(linha.strip()))
            except Exception:
                continue

    print(f"\n{C.BOLD}=== ANÁLISE: {caminho} ==={C.RESET}")
    print(f"Total de eventos: {len(eventos)}")

    # Sessões únicas
    sessoes = set(e.get("sessao") for e in eventos)
    print(f"Sessões: {len(sessoes)}")

    # Por categoria
    cats = {}
    for e in eventos:
        cats[e["categoria"]] = cats.get(e["categoria"], 0) + 1
    print(f"\n{C.BOLD}Por categoria:{C.RESET}")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        col, label = CATS.get(cat, (C.WHITE, cat))
        print(f"  {col}{label:12}{C.RESET} {n:5}×")

    # LLM timing distribution
    llm = [e["dados"]["ms"] for e in eventos if e["categoria"] == "LLM_RESP" and "ms" in e.get("dados",{})]
    if llm:
        print(f"\n{C.BOLD}Distribuição de latência LLM ({len(llm)} chamadas):{C.RESET}")
        buckets = [(0,1000,"<1s"), (1000,3000,"1-3s"), (3000,6000,"3-6s"),
                   (6000,10000,"6-10s"), (10000,99999,">10s")]
        for lo, hi, label in buckets:
            n = sum(1 for t in llm if lo <= t < hi)
            bar = "█" * (n * 30 // max(len(llm), 1))
            print(f"  {label:6} {bar} {n}")
        print(f"  avg={sum(llm)/len(llm):.0f}ms  p50={sorted(llm)[len(llm)//2]:.0f}ms  "
              f"p95={sorted(llm)[int(len(llm)*0.95)]:.0f}ms  max={max(llm):.0f}ms")

    # Criatividade distribution
    cris = [e["dados"]["cri"] for e in eventos if e["categoria"] == "CRIATIVIDADE" and "cri" in e.get("dados",{})]
    if cris:
        print(f"\n{C.BOLD}Distribuição de criatividade ({len(cris)} avaliações):{C.RESET}")
        for lo, hi in [(0.5,0.6),(0.6,0.7),(0.7,0.8),(0.8,0.9),(0.9,1.01)]:
            n = sum(1 for c in cris if lo <= c < hi)
            bar = "█" * (n * 30 // max(len(cris), 1))
            print(f"  [{lo:.1f}-{hi:.1f}) {bar} {n}")
        print(f"  avg={sum(cris)/len(cris):.3f}")

    # Cache hit rate
    hits   = cats.get("CACHE_HIT",  0)
    misses = cats.get("CACHE_MISS", 0)
    total  = hits + misses
    if total:
        print(f"\n{C.BOLD}Cache hit rate:{C.RESET} {hits}/{total} = {hits/total*100:.1f}%")

    print()


# ══════════════════════════════════════════════════════════════
#  MENU DE DEBUG (chamado pelo main.py)
# ══════════════════════════════════════════════════════════════

def menu_debug() -> None:
    """Menu interativo para controlar o debugger durante o jogo."""
    while True:
        print(f"\n  {C.BGCYAN}{C.BOLD}  DEBUG MENU  {C.RESET}")
        print(f"  Nível atual: {C.BOLD}{_NIVEL}{C.RESET} "
              f"({'OFF' if _NIVEL==0 else ['','RESUMIDO','NORMAL','VERBOSE'][_NIVEL]})")
        print()
        print("  [0] Desativar debug")
        print("  [1] Nível 1 — Resumido (turnos e danos)")
        print("  [2] Nível 2 — Normal   (+ LLM e cache)")
        print("  [3] Nível 3 — Verbose  (+ prompts e jornada)")
        print("  [p] Painel da sessão")
        print("  [a] Analisar log completo")
        print("  [v] Ver últimos 10 eventos")
        print("  [q] Voltar ao jogo")
        print()
        op = input("  > ").strip().lower()

        if op in ("0","1","2","3"):
            n = int(op)
            ativar(n) if n > 0 else desativar()
            instalar()
            print(f"  Debug {'ativado nível ' + str(n) if n > 0 else 'desativado'}.")
        elif op == "p":
            painel_sessao()
        elif op == "a":
            analisar_log(_LOG_FILE)
        elif op == "v":
            _mostrar_ultimos(10)
        elif op in ("q", ""):
            return


def _mostrar_ultimos(n: int = 10) -> None:
    """Imprime os últimos N eventos do buffer."""
    ultimos = list(_eventos)[-n:]
    if not ultimos:
        print(f"  {C.LGRAY}Nenhum evento ainda.{C.RESET}")
        return
    print(f"\n  {C.BOLD}Últimos {len(ultimos)} eventos:{C.RESET}")
    for ev in ultimos:
        col, label = CATS.get(ev["categoria"], (C.WHITE, ev["categoria"]))
        ts = ev["ts"].split("T")[1][:12]
        dados_str = ""
        d = ev.get("dados", {})
        if "dano" in d:   dados_str += f" dano={d['dano']:.1f}"
        if "cri" in d:    dados_str += f" cri={d['cri']:.3f}"
        if "ms" in d:     dados_str += f" {d['ms']}ms"
        if "score" in d:  dados_str += f" score={d['score']:.3f}"
        print(f"  {C.LGRAY}{ts}{C.RESET} {col}{label:10}{C.RESET} "
              f"{ev['descricao'][:40]}{C.LGRAY}{dados_str}{C.RESET}")


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT (análise de log standalone)
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "analyze":
        analisar_log(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "analyze":
        analisar_log(_LOG_FILE)
    else:
        print("Uso:")
        print("  python debugger.py analyze                    # analisa log atual")
        print("  python debugger.py analyze <arquivo.jsonl>   # analisa arquivo específico")
