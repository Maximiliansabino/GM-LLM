"""
jornada.py
─────────────────────────────────────────────────────────────
Módulo de persistência da jornada.

Responsável por:
  1. Gravar todos os eventos relevantes em log.json
  2. Manter o estado canônico do mundo em estado.json
  3. Fornecer contexto comprimido à LLM para evitar alucinações
  4. Registrar NPCs, decisões, combates e descobertas

A LLM NUNCA deve ser chamada sem receber o contexto desta camada.
─────────────────────────────────────────────────────────────
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import JORNADA_DIR, JORNADA_LOG_FILE, JORNADA_ESTADO_FILE


# ══════════════════════════════════════════════════════════════
#  CACHE EM MEMÓRIA — write-through com flush diferido
#  Reduz leituras de disco de ~4/turno para 0 após o primeiro load
# ══════════════════════════════════════════════════════════════
_estado_cache: dict = {}
_log_cache:    dict = {}
_cache_dirty   = False


def _get_estado() -> dict:
    global _estado_cache
    if not _estado_cache:
        _estado_cache = _carregar_json(JORNADA_ESTADO_FILE) or {}
    return _estado_cache


def _get_log() -> dict:
    global _log_cache
    if not _log_cache:
        _log_cache = _carregar_json(JORNADA_LOG_FILE) or {"eventos": []}
    return _log_cache


def _flush_estado() -> None:
    if _estado_cache:
        _salvar_json(JORNADA_ESTADO_FILE, _estado_cache)


def _flush_log() -> None:
    if _log_cache:
        _salvar_json(JORNADA_LOG_FILE, _log_cache)


# ══════════════════════════════════════════════════════════════
#  INICIALIZAÇÃO
# ══════════════════════════════════════════════════════════════

def inicializar_jornada(personagem_dict: dict, cenario_inicial: str) -> None:
    """Cria os arquivos de jornada se não existirem."""
    os.makedirs(JORNADA_DIR, exist_ok=True)

    # Carrega estado existente ou cria do zero
    if os.path.exists(JORNADA_ESTADO_FILE):
        estado_inicial = _get_estado()
    else:
        estado_inicial = {
            "turno": 0,
            "npcs_conhecidos": {},
            "inimigos_derrotados": [],
            "itens_obtidos": [],
            "habilidades_adquiridas": [],
            "segredos_descobertos": [],
            "quests_ativas": [],
            "quests_concluidas": [],
            "reputacao": {},
        }
    # Sempre atualiza personagem e localização ao inicializar
    global _estado_cache, _log_cache
    estado_inicial["personagem"] = personagem_dict
    estado_inicial["localizacao_atual"] = cenario_inicial
    _estado_cache = estado_inicial
    _flush_estado()

    if not os.path.exists(JORNADA_LOG_FILE):
        _log_cache = {"eventos": []}
        _flush_log()
    else:
        _log_cache = _carregar_json(JORNADA_LOG_FILE) or {"eventos": []}

    print(f"[Jornada] Inicializada em '{JORNADA_DIR}/'")


# ══════════════════════════════════════════════════════════════
#  REGISTRO DE EVENTOS
# ══════════════════════════════════════════════════════════════

def registrar_evento(
    tipo: str,
    descricao: str,
    dados: Optional[Dict[str, Any]] = None,
    turno: Optional[int] = None,
) -> None:
    """
    Tipos de evento: "narrativa" | "combate" | "dialogo" | "descoberta" |
                     "item_obtido" | "habilidade" | "morte" | "quest" | "erro"
    """
    log    = _get_log()
    estado = _get_estado()

    turno_atual = turno if turno is not None else estado.get("turno", 0)

    evento = {
        "id"        : len(log["eventos"]) + 1,
        "turno"     : turno_atual,
        "timestamp" : datetime.now().isoformat(),
        "tipo"      : tipo,
        "descricao" : descricao,
        "dados"     : dados or {},
    }

    log["eventos"].append(evento)
    _flush_log()


def avancar_turno() -> int:
    estado = _get_estado()
    estado["turno"] += 1
    _flush_estado()
    return estado["turno"]


# ══════════════════════════════════════════════════════════════
#  ATUALIZAÇÃO DE ESTADO
# ══════════════════════════════════════════════════════════════

def atualizar_personagem(personagem_dict: dict) -> None:
    estado = _get_estado()
    estado["personagem"] = personagem_dict
    _flush_estado()


def mover_para(nova_localizacao: str) -> None:
    estado = _get_estado()
    anterior = estado.get("localizacao_atual", "?")
    estado["localizacao_atual"] = nova_localizacao
    _flush_estado()
    registrar_evento(
        "narrativa",
        f"Personagem se deslocou de '{anterior}' para '{nova_localizacao}'.",
        {"de": anterior, "para": nova_localizacao},
    )


def salvar_amizade_npcs(amizades: dict) -> None:
    """Persiste o dicionário {chave_npc: amizade} no estado.json."""
    estado = _get_estado()
    estado["amizade_npcs"] = amizades
    _flush_estado()


def carregar_amizade_npcs() -> dict:
    """Retorna o dicionário de amizades salvo, ou {} se não existir."""
    return _get_estado().get("amizade_npcs", {})


def registrar_npc(nome: str, descricao: str, atitude: str = "neutro", dados_extras: dict = None) -> None:
    """
    Registra ou atualiza um NPC conhecido.
    atitude: "amigavel" | "neutro" | "hostil" | "aliado"
    """
    estado = _get_estado()
    estado["npcs_conhecidos"][nome] = {
        "descricao" : descricao,
        "atitude"   : atitude,
        "turno_met" : estado.get("turno", 0),
        **(dados_extras or {}),
    }
    _flush_estado()
    registrar_evento("dialogo", f"NPC '{nome}' registrado. Atitude: {atitude}.", {"npc": nome})


def registrar_inimigo_derrotado(nome_inimigo: str, nivel: int, loot: List[str]) -> None:
    estado = _get_estado()
    registro = {
        "nome"  : nome_inimigo,
        "nivel" : nivel,
        "turno" : estado.get("turno", 0),
        "loot"  : loot,
    }
    estado["inimigos_derrotados"].append(registro)
    _flush_estado()
    registrar_evento("combate", f"Inimigo '{nome_inimigo}' derrotado.", registro)


def registrar_item_obtido(nome_item: str, origem: str) -> None:
    estado = _get_estado()
    estado["itens_obtidos"].append({
        "item"  : nome_item,
        "origem": origem,
        "turno" : estado.get("turno", 0),
    })
    _flush_estado()
    registrar_evento("item_obtido", f"Item '{nome_item}' obtido via {origem}.")


def registrar_habilidade_adquirida(nome_habilidade: str, tipo: str, origem: str) -> None:
    estado = _get_estado()
    estado["habilidades_adquiridas"].append({
        "habilidade": nome_habilidade,
        "tipo"      : tipo,
        "origem"    : origem,
        "turno"     : estado.get("turno", 0),
    })
    _flush_estado()
    registrar_evento("habilidade", f"Habilidade '{nome_habilidade}' adquirida via {origem}.")


def registrar_segredo(descricao: str) -> None:
    estado = _get_estado()
    estado["segredos_descobertos"].append({
        "descricao": descricao,
        "turno"    : estado.get("turno", 0),
    })
    _flush_estado()
    registrar_evento("descoberta", f"Segredo descoberto: {descricao[:60]}...")


def registrar_combate(
    inimigo_nome: str,
    resultado: str,          # "vitoria" | "derrota" | "fuga"
    turnos: int,
    dano_causado: float,
    dano_recebido: float,
    acoes_destaque: List[str],
) -> None:
    dados = {
        "inimigo"       : inimigo_nome,
        "resultado"     : resultado,
        "turnos"        : turnos,
        "dano_causado"  : round(dano_causado, 2),
        "dano_recebido" : round(dano_recebido, 2),
        "acoes_destaque": acoes_destaque,
    }
    registrar_evento("combate", f"Combate com '{inimigo_nome}': {resultado}.", dados)


# ══════════════════════════════════════════════════════════════
#  CONTEXTO PARA A LLM  (anti-alucinação)
# ══════════════════════════════════════════════════════════════

def obter_contexto_llm(n_eventos_recentes: int = 10) -> str:
    """
    Retorna um bloco de texto comprimido com:
      - estado atual do personagem
      - localização
      - NPCs conhecidos
      - N eventos mais recentes
    Este texto é injetado em TODA chamada à LLM.
    """
    estado = _get_estado()
    log    = _get_log()

    personagem = estado.get("personagem", {})
    npcs = estado.get("npcs_conhecidos", {})
    eventos = log.get("eventos", [])[-n_eventos_recentes:]

    def _fmt(val, spec):
        """Formata apenas se val for numérico, senão retorna '?' sem crash."""
        try:
            return format(float(val), spec)
        except (TypeError, ValueError):
            return "?"

    pv_at  = _fmt(personagem.get("pv_atual"),    ".0f")
    pv_mx  = _fmt(personagem.get("pv_max"),      ".0f")
    cf     = _fmt(personagem.get("corpo_fisico"), ".1f")
    conh   = _fmt(personagem.get("conhecimento"), ".2f")
    psi_at = _fmt(personagem.get("psique_atual"), ".1f")
    psi_mx = _fmt(personagem.get("psique_max"),   ".1f")

    linhas = [
        "=== CONTEXTO CANÔNICO DA JORNADA ===",
        f"Turno: {estado.get('turno', 0)}",
        f"Localização: {estado.get('localizacao_atual', '?')}",
        "",
        "[ Personagem ]",
        f"  Nome: {personagem.get('nome', '?')} | Caminho: {personagem.get('caminho', '?')}",
        f"  PV: {pv_at}/{pv_mx}",
        f"  Corpo Físico: {cf}",
        f"  Conhecimento: {conh}",
        f"  Psiquê: {psi_at}/{psi_mx}",
        f"  Item Equipado: {personagem.get('item_equipado', 'Nenhum')}",
        f"  Habilidades: {personagem.get('habilidades_ativar', [])} | {personagem.get('habilidades_passivas', [])}",
    ]

    if npcs:
        linhas.append("")
        linhas.append("[ NPCs Conhecidos ]")
        for nome, info in npcs.items():
            linhas.append(f"  {nome} ({info.get('atitude', '?')}): {info.get('descricao', '')[:80]}")

    if estado.get("segredos_descobertos"):
        linhas.append("")
        linhas.append("[ Segredos / Fatos Estabelecidos ]")
        for seg in estado["segredos_descobertos"]:
            linhas.append(f"  - {seg['descricao']}")

    if eventos:
        linhas.append("")
        linhas.append(f"[ Últimos {len(eventos)} Eventos ]")
        for ev in eventos:
            linhas.append(f"  T{ev['turno']:03d} [{ev['tipo']:12}] {ev['descricao'][:100]}")

    linhas.append("=== FIM DO CONTEXTO ===")
    return "\n".join(linhas)


def obter_contexto_compacto() -> str:
    """
    Compressed context for narrative LLM calls.
    ~40% fewer tokens than obter_contexto_llm.
    Only the most essential facts: location, character vitals, recent events.
    """
    estado = _get_estado()
    log    = _get_log()
    p      = estado.get("personagem", {})

    def _fmt(val, spec):
        try: return format(float(val), spec)
        except: return "?"

    eventos_recentes = [
        f"T{e['turno']:02d}[{e['tipo']}] {e['descricao'][:60]}"
        for e in log.get("eventos", [])[-4:]
    ]

    linhas = [
        f"[Turno {estado.get('turno',0)} | {estado.get('localizacao_atual','?')}]",
        f"[{p.get('nome','?')} | PV {_fmt(p.get('pv_atual'),':.0f')}/{_fmt(p.get('pv_max'),':.0f')} | Psique {_fmt(p.get('psique_atual'),':.1f')}]",
    ]
    if eventos_recentes:
        linhas.append("Eventos: " + " | ".join(eventos_recentes))
    npcs = estado.get("npcs_conhecidos", {})
    if npcs:
        linhas.append("NPCs: " + ", ".join(f"{n}({i.get('atitude','?')})" for n, i in list(npcs.items())[:4]))
    return " ".join(linhas)


def obter_estado() -> dict:
    return _get_estado()


def obter_log_completo() -> list:
    return _get_log().get("eventos", [])


# ══════════════════════════════════════════════════════════════
#  UTILITÁRIOS INTERNOS
# ══════════════════════════════════════════════════════════════

def _salvar_json(caminho: str, dados: Any) -> None:
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def _carregar_json(caminho: str) -> Any:
    if not os.path.exists(caminho):
        return {}
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════
#  PONTO DE TESTE RÁPIDO
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from personagens import criar_kael
    kael = criar_kael()

    inicializar_jornada(kael.to_dict(), "Vila de Pedra Branca")
    registrar_evento("narrativa", "A aventura começa na taverna da vila.")
    registrar_npc("Taverneiro Breno", "Homem gordo e jovial. Conhece os rumores locais.", "amigavel")
    mover_para("Floresta das Sombras")
    avancar_turno()
    registrar_evento("combate", "Encontrou um lobo na floresta.")

    print(obter_contexto_llm())
