"""
geracao_procedural.py
─────────────────────────────────────────────────────────────
Geração Procedural de Conteúdo — RPG GM LLM

Gera inimigos, itens e mini-cenários on-the-fly, balanceados
matematicamente pelo nível do personagem.

Componentes:
  1. GeracaoInimigo   — gera inimigo único equilibrado
  2. GeracaoItem      — gera item com stats proporcionais
  3. GeracaoCenario   — gera mini-cenário (3 inimigos + loot)
  4. Narrativa LLM    — enriquece com nome/descrição temáticos

Referência DSR:
  JOHNSON et al. (2022) — Procedural Content Generation in Games.
  YU et al. (2025) — RPGBENCH: representação baseada em eventos/estados.
"""

from __future__ import annotations
import random
import math
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

# ── Tipos disponíveis ────────────────────────────────────────
TIPOS_INIMIGO  = ["besta", "humanoide", "arcano", "morto-vivo", "elemental"]
TIPOS_DEFESA   = ["natural", "fisica", "arcana", "espiritual"]
QUALIDADES_ITEM = ["simples", "bom", "raro", "épico"]

# ── Mapeamento tipo → fraquezas/resistências prováveis ───────
TIPO_FRAQUEZAS: Dict[str, List[str]] = {
    "besta":      ["fogo", "luz", "acido"],
    "humanoide":  ["fogo", "frio", "arcano"],
    "arcano":     ["antimagia", "interromper_conjuracao", "fisica"],
    "morto-vivo": ["luz", "fogo", "prata"],
    "elemental":  ["agua", "frio", "eletrico", "fisica"],
}
TIPO_RESISTENCIAS: Dict[str, List[str]] = {
    "besta":      ["natural", "fisica"],
    "humanoide":  ["fisica"],
    "arcano":     ["arcana", "fogo", "frio"],
    "morto-vivo": ["arcana", "frio", "natural"],
    "elemental":  ["fogo", "natural"],
}

# ── Mapeamento tipo → ataques especiais temáticos ────────────
ATAQUES_POR_TIPO: Dict[str, List[Dict]] = {
    "besta": [
        {"nome": "Investida Selvagem", "dano_mult": 1.4, "efeito": "paralisar",   "chance": 0.30},
        {"nome": "Mordida Venenosa",   "dano_mult": 1.2, "efeito": "envenenar",   "chance": 0.35},
        {"nome": "Garrada Profunda",   "dano_mult": 1.5, "efeito": "sangrar",     "chance": 0.30},
        {"nome": "Uivo de Medo",       "dano_mult": 0.8, "efeito": "confundir",   "chance": 0.40},
    ],
    "humanoide": [
        {"nome": "Golpe Traiçoeiro",   "dano_mult": 1.6, "efeito": "sangrar",     "chance": 0.25},
        {"nome": "Arremesso de Ácido", "dano_mult": 1.0, "efeito": "queimar",     "chance": 0.35},
        {"nome": "Golpe Paralisante",  "dano_mult": 1.2, "efeito": "paralisar",   "chance": 0.30},
        {"nome": "Maldição do Berro",  "dano_mult": 0.7, "efeito": "drenar_psique","chance": 0.40},
    ],
    "arcano": [
        {"nome": "Raio de Drenagem",   "dano_mult": 0.9, "efeito": "drenar_psique","chance": 0.45},
        {"nome": "Pulso Arcano",       "dano_mult": 1.3, "efeito": "confundir",   "chance": 0.40},
        {"nome": "Chama Mística",      "dano_mult": 1.4, "efeito": "queimar",     "chance": 0.30},
        {"nome": "Gelo Arcano",        "dano_mult": 1.2, "efeito": "congelar",    "chance": 0.35},
    ],
    "morto-vivo": [
        {"nome": "Toque da Morte",     "dano_mult": 0.8, "efeito": "drenar_psique","chance": 0.50},
        {"nome": "Grito Espectral",    "dano_mult": 1.0, "efeito": "paralisar",   "chance": 0.35},
        {"nome": "Aura de Decomposição","dano_mult": 1.1,"efeito": "envenenar",   "chance": 0.40},
        {"nome": "Maldição Sombria",   "dano_mult": 0.9, "efeito": "confundir",   "chance": 0.45},
    ],
    "elemental": [
        {"nome": "Erupção Elemental",  "dano_mult": 1.6, "efeito": "queimar",     "chance": 0.30},
        {"nome": "Tempestade Gelada",  "dano_mult": 1.4, "efeito": "congelar",    "chance": 0.35},
        {"nome": "Descarga Elétrica",  "dano_mult": 1.5, "efeito": "paralisar",   "chance": 0.25},
        {"nome": "Onda Corrosiva",     "dano_mult": 1.2, "efeito": "envenenar",   "chance": 0.35},
    ],
}

# ── Prefixos/sufixos para nomes procedurais ──────────────────
PREFIXOS = {
    "besta":      ["Feroz", "Selvagem", "Sombrio", "Enraivecido", "Antigo"],
    "humanoide":  ["Renegado", "Corrupto", "Amaldiçoado", "Mercenário", "Fanático"],
    "arcano":     ["Arcano", "Místico", "Etéreo", "Corrompido", "Primordial"],
    "morto-vivo": ["Espectral", "Putrefato", "Amaldiçoado", "Sombrio", "Antigo"],
    "elemental":  ["Furioso", "Primordial", "Desencadeado", "Puro", "Colossal"],
}
BASES_NOME = {
    "besta":      ["Lobo", "Urso", "Felino", "Réptil", "Aranha", "Corvo"],
    "humanoide":  ["Guerreiro", "Arqueiro", "Feiticeiro", "Berserker", "Caçador"],
    "arcano":     ["Golem", "Elemental", "Espectro", "Entidade", "Guardião"],
    "morto-vivo": ["Esqueleto", "Zumbi", "Aparição", "Liche", "Banshee"],
    "elemental":  ["Elemental", "Colosso", "Titã", "Espírito", "Guardião"],
}

# ══════════════════════════════════════════════════════════════
#  1. FÓRMULAS DE ESCALONAMENTO
# ══════════════════════════════════════════════════════════════

def escalar_pv(nivel: int, variancia: float = 0.15) -> float:
    """
    PV por tabela — calibrado com catálogo e bosses fixos (~480 PV max).
      N1≈80  N2≈130  N3≈200  N4≈300  N5≈380  N6≈480
    """
    _bases = {1: 80, 2: 130, 3: 200, 4: 300, 5: 380, 6: 480}
    base = _bases.get(nivel, 80 + (nivel - 1) * 80)
    return round(base * random.uniform(1 - variancia, 1 + variancia))


def escalar_dano(nivel: int, variancia: float = 0.20) -> float:
    """Dano = 4 + (nivel-1) × 4 × (1 ± variancia)"""
    base = 5 + (nivel - 1) * 5  # calibrado: N1≈5-7, N2≈9-13, N3≈14-18
    return round(base * random.uniform(1 - variancia, 1 + variancia), 1)


def escalar_defesa(nivel: int, tipo_defesa: str) -> float:
    """Defesa base por nível + bônus por tipo."""
    base = 1 + (nivel - 1) * 1.8
    bonus = {"arcana": 2, "espiritual": 3, "fisica": 1, "natural": 0}
    return round(base + bonus.get(tipo_defesa, 0), 1)


def escalar_xp(nivel: int) -> int:
    return int(15 * nivel ** 1.8)


def escalar_ouro(nivel: int) -> int:
    return int(5 * nivel * random.uniform(0.8, 1.5))


# ══════════════════════════════════════════════════════════════
#  2. GERAÇÃO DE INIMIGO PROCEDURAL
# ══════════════════════════════════════════════════════════════

def gerar_inimigo(
    nivel_personagem: int,
    tipo: Optional[str] = None,
    bioma: str = "floresta",
    seed: Optional[int] = None,
) -> "Inimigo":
    """
    Gera um inimigo único balanceado pelo nível do personagem.

    nivel_personagem: nível atual do herói (1-6)
    tipo: forçar um tipo específico ou None para aleatório
    bioma: afeta tipo preferido e nome
    seed: para reprodutibilidade em testes
    """
    if seed is not None:
        random.seed(seed)

    # Nível do inimigo — próximo ao do personagem com variação
    nivel = max(1, min(6, nivel_personagem + random.randint(-1, 1)))
    if tipo is None:
        tipo = random.choice(TIPOS_INIMIGO)
    tipo_defesa = random.choice(TIPOS_DEFESA)

    # Fraquezas e resistências baseadas no tipo
    fraq_pool = TIPO_FRAQUEZAS.get(tipo, ["fogo"])
    res_pool  = TIPO_RESISTENCIAS.get(tipo, [])
    fraquezas    = random.sample(fraq_pool, min(2, len(fraq_pool)))
    resistencias = random.sample(res_pool, min(1, len(res_pool))) if res_pool else []

    # Nome procedural
    prefixo = random.choice(PREFIXOS.get(tipo, ["Desconhecido"]))
    base    = random.choice(BASES_NOME.get(tipo, ["Criatura"]))
    nome    = f"{prefixo} {base}"

    # Stats escalonados
    pv_max   = escalar_pv(nivel)
    dano     = escalar_dano(nivel)
    defesa   = escalar_defesa(nivel, tipo_defesa)
    xp       = escalar_xp(nivel)
    ouro     = escalar_ouro(nivel)

    # Ataque especial — 70% de chance de ter um
    ataques = []
    if random.random() < 0.70:
        pool_ataques = ATAQUES_POR_TIPO.get(tipo, [])
        atk = dict(random.choice(pool_ataques))  # cópia
        atk["descricao"] = f"Ataque especial de {nome.lower()}."
        ataques = [atk]

    # Loot procedural
    loot = _gerar_loot(nivel)

    # Descrição base (enriquecida por LLM se disponível)
    descricao = _descricao_base(nome, tipo, nivel)

    from inimigos import Inimigo
    ini = Inimigo(
        nome=nome,
        tipo=tipo,
        nivel=nivel,
        pv_max=pv_max,
        dano_base=dano,
        defesa=defesa,
        tipo_defesa=tipo_defesa,
        fraquezas=fraquezas,
        resistencias=resistencias,
        descricao=descricao,
        xp=xp,
        ouro=ouro,
        loot_possivel=loot,
        ataques_especiais=ataques,
    )
    ini._procedural = True  # flag para log/debug
    return ini


def _gerar_loot(nivel: int) -> List[Tuple[str, float]]:
    """Gera tabela de loot proporcional ao nível."""
    from itens import CATALOGO_ITENS
    candidatos = [
        k for k, v in CATALOGO_ITENS.items()
        if v.tipo == "arma" and v.dano_arma <= 5 + nivel * 3
    ]
    if not candidatos:
        return []
    escolhido = random.choice(candidatos)
    chance    = round(random.uniform(0.2, 0.5), 2)
    return [(escolhido, chance)]


def _descricao_base(nome: str, tipo: str, nivel: int) -> str:
    descs = {
        "besta":      f"{nome} espreitando pelas sombras. Olhos brilhantes de predador faminento.",
        "humanoide":  f"{nome} em guarda de combate. Cicatrizes de batalhas anteriores marcam seu corpo.",
        "arcano":     f"{nome} emanando energia instável. O ar ao redor crepita com poder mágico.",
        "morto-vivo": f"{nome} avançando sem parar. Sua presença faz o ar esfriar vários graus.",
        "elemental":  f"{nome} materializado de pura força natural. Sua forma muda constantemente.",
    }
    sufixo = " Extremamente perigoso." if nivel >= 4 else (" Poderoso." if nivel >= 3 else "")
    return descs.get(tipo, f"{nome} aguarda o combate.") + sufixo


# ══════════════════════════════════════════════════════════════
#  3. ENRIQUECIMENTO VIA LLM (nome + descrição únicos)
# ══════════════════════════════════════════════════════════════

_PROMPT_NOME = """Crie um nome e descrição para um inimigo de RPG brasileiro.
Tipo: {tipo} | Nível: {nivel} | Bioma: {bioma}
Fraquezas: {fraquezas}

Responda APENAS com JSON:
{{"nome": "<nome único em português>", "descricao": "<1 frase vívida de 10-15 palavras>"}}

Exemplos de nomes: "Capivara das Sombras", "Goblin Druídico", "Elemental de Brasa"
O nome deve soar brasileiro/amazônico. NÃO use nomes em inglês."""

def enriquecer_com_llm(inimigo, bioma: str = "floresta") -> None:
    """
    Enriquece o inimigo com nome e descrição gerados pelo LLM.
    Modifica o inimigo in-place. Falha silenciosamente se LLM indisponível.
    """
    try:
        from llm_backend import _chamar_ollama
        prompt = _PROMPT_NOME.format(
            tipo=inimigo.tipo,
            nivel=inimigo.nivel,
            bioma=bioma,
            fraquezas=", ".join(inimigo.fraquezas) or "nenhuma",
        )
        resp = _chamar_ollama(prompt, num_predict=80, temperature=0.7)
        m = re.search(r'\{.*\}', resp, re.DOTALL)
        if not m:
            return
        data = json.loads(m.group())
        nome_llm = data.get("nome", "").strip()
        desc_llm = data.get("descricao", "").strip()
        if nome_llm and len(nome_llm) > 3:
            inimigo.nome = nome_llm
        if desc_llm and len(desc_llm) > 10:
            inimigo.descricao = desc_llm
    except Exception:
        pass  # LLM indisponível — mantém nome/descrição procedural


# ══════════════════════════════════════════════════════════════
#  4. GERAÇÃO DE ITEM PROCEDURAL
# ══════════════════════════════════════════════════════════════

_NOMES_ARMA_FISICA = [
    "Lâmina Forjada", "Faca Afiada", "Machado Rústico",
    "Espada Improvisada", "Lança Quebrada", "Adaga Enferrujada",
]
_NOMES_ARMA_MAGICA = [
    "Cajado Rachado", "Varinha Talhada", "Orbe de Cristal",
    "Tomo Arcano", "Foco de Madeira", "Cristal Pulsante",
]
_NOMES_ARMADURA = [
    "Couro Reforçado", "Cota Improvisada", "Escudo Lascado",
    "Proteção de Osso", "Armadura Rústica",
]

def gerar_item(
    nivel_personagem: int,
    tipo_preferido: str = "arma",
    tipo_dano: str = "fisico",
    qualidade: Optional[str] = None,
) -> "Item":
    """
    Gera um item balanceado pelo nível do personagem.

    tipo_preferido: "arma" | "armadura" | "consumivel"
    tipo_dano: "fisico" | "magico"
    """
    nivel = max(1, min(6, nivel_personagem))

    if qualidade is None:
        pesos = [0.50, 0.30, 0.15, 0.05]  # simples, bom, raro, épico
        qualidade = random.choices(QUALIDADES_ITEM, weights=pesos)[0]

    mult_qual = {"simples": 0.7, "bom": 1.0, "raro": 1.35, "épico": 1.80}[qualidade]

    if tipo_preferido == "arma":
        if tipo_dano == "magico":
            nome     = random.choice(_NOMES_ARMA_MAGICA)
            dano_fis = 0.0
            dano_mag = round((4 + nivel * 3) * mult_qual, 1)
            semantica = {"elemento": 1.0, "forma": 1.0, "impacto": 0.3,
                         "corte": 0.1, "perfurar": 0.1}
            req = {"conhecimento_tacito": max(2, nivel + 1)}
        else:
            nome     = random.choice(_NOMES_ARMA_FISICA)
            dano_fis = round((6 + nivel * 3) * mult_qual, 1)
            dano_mag = 0.0
            semantica = {"corte": 1.1, "perfurar": 1.0, "impacto": 0.5,
                         "esmagamento": 0.2, "choque": 0.4}
            req = {"forca": max(4, nivel * 2)}
        defesa = 0.0
        tipo_item = "arma"

    elif tipo_preferido == "armadura":
        nome     = random.choice(_NOMES_ARMADURA)
        dano_fis = 0.0
        dano_mag = 0.0
        defesa   = round((2 + nivel * 2) * mult_qual, 1)
        semantica = {}
        req = {"vigor": max(3, nivel)}
        tipo_item = "armadura"

    else:  # consumivel
        nome      = f"Poção de {'Cura' if random.random() < 0.6 else 'Psiquê'} {'Menor' if nivel <= 2 else 'Maior'}"
        dano_fis  = 0.0
        dano_mag  = 0.0
        defesa    = 0.0
        semantica = {}
        req       = {}
        tipo_item = "consumivel"

    maestria_max = round(50 + nivel * 25 * mult_qual)

    desc_qualidade = {"simples": "artesanato básico", "bom": "bem acabado",
                      "raro": "trabalho de mestre", "épico": "obra lendária"}[qualidade]
    descricao = f"{nome} de {desc_qualidade}. Nível {nivel}."

    from itens import Item
    return Item(
        nome=nome,
        tipo=tipo_item,
        qualidade=qualidade,
        tipo_dano=tipo_dano if tipo_item == "arma" else "",
        semantica=semantica,
        requisito=req,
        dano_fisico=dano_fis,
        dano_magico=dano_mag,
        dano_arma=max(dano_fis, dano_mag),
        defesa=defesa,
        maestria_max=float(maestria_max),
        habilidades_item=[],
        descricao=descricao,
        bonus={},
    )


# ══════════════════════════════════════════════════════════════
#  5. GERAÇÃO DE MINI-CENÁRIO
# ══════════════════════════════════════════════════════════════

@dataclass
class MiniCenario:
    """Sequência de 3 batalhas procedurais + loot final."""
    titulo:    str
    descricao: str
    bioma:     str
    inimigos:  List        = field(default_factory=list)  # 3 inimigos
    loot_final: List       = field(default_factory=list)  # itens de recompensa
    nivel_medio: int       = 1


def gerar_cenario(
    nivel_personagem: int,
    bioma: str = "floresta",
    tipo_foco: Optional[str] = None,  # forçar um tipo de inimigo
    usar_llm: bool = False,
) -> MiniCenario:
    """
    Gera um mini-cenário com 3 batalhas progressivas:
      Batalha 1 — inimigo nivel-1 (aquecimento)
      Batalha 2 — inimigo mesmo nível
      Batalha 3 — inimigo nivel+1 (desafio)
    """
    nivel = max(1, nivel_personagem)

    # Tipos progressivos
    tipo1 = tipo_foco or random.choice(TIPOS_INIMIGO)
    tipo2 = tipo_foco or random.choice(TIPOS_INIMIGO)
    tipo3 = tipo_foco or tipo2  # último inimigo usa tipo similar ao anterior

    ini1 = gerar_inimigo(max(1, nivel - 1), tipo=tipo1, bioma=bioma)
    ini2 = gerar_inimigo(nivel,             tipo=tipo2, bioma=bioma)
    ini3 = gerar_inimigo(min(6, nivel + 1), tipo=tipo3, bioma=bioma)

    if usar_llm:
        for ini in [ini1, ini2, ini3]:
            enriquecer_com_llm(ini, bioma)

    # Loot final proporcional ao nível
    loot = []
    if nivel >= 2:
        loot.append(gerar_item(nivel, tipo_preferido="arma",
                               tipo_dano=random.choice(["fisico","magico"])))
    if nivel >= 3:
        loot.append(gerar_item(nivel, tipo_preferido="armadura"))
    loot.append(gerar_item(nivel, tipo_preferido="consumivel"))

    # Título e descrição do cenário
    titulos = {
        "besta":      f"Território das Feras — Nível {nivel}",
        "humanoide":  f"Emboscada dos Renegados — Nível {nivel}",
        "arcano":     f"Ruínas Arcanas — Nível {nivel}",
        "morto-vivo": f"Cripta dos Mortos — Nível {nivel}",
        "elemental":  f"Tempestade Elemental — Nível {nivel}",
    }
    titulo = titulos.get(tipo2, f"Encontro Procedural — Nível {nivel}")
    descricao = (f"Sequência de 3 batalhas progressivas no bioma {bioma}. "
                 f"Inimigos de nível {max(1,nivel-1)}/{nivel}/{min(6,nivel+1)}.")

    return MiniCenario(
        titulo=titulo,
        descricao=descricao,
        bioma=bioma,
        inimigos=[ini1, ini2, ini3],
        loot_final=loot,
        nivel_medio=nivel,
    )


# ══════════════════════════════════════════════════════════════
#  6. INTEGRAÇÃO COM O SISTEMA — inimigo procedural no bioma
# ══════════════════════════════════════════════════════════════

def proximo_inimigo_procedural(nivel_personagem: int, bioma_key: str,
                                usar_llm: bool = False):
    """
    Substituto drop-in para obter_inimigo() quando não há mais inimigos
    fixos no catálogo, ou quando o bioma está em modo procedural.
    """
    from biomas import BIOMAS
    bioma = BIOMAS.get(bioma_key, {})
    tipo_bioma = bioma.get("tipo_inimigo", "besta")

    ini = gerar_inimigo(nivel_personagem, tipo=tipo_bioma, bioma=bioma_key)
    if usar_llm:
        enriquecer_com_llm(ini, bioma_key)

    ini._bioma_tipo = tipo_bioma
    return ini


# ══════════════════════════════════════════════════════════════
#  PONTO DE TESTE RÁPIDO
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os, json as _json
    os.makedirs("jornada", exist_ok=True)
    with open("jornada/log.json","w") as f: _json.dump({"eventos":[]},f)
    with open("jornada/estado.json","w") as f:
        _json.dump({"turno":0,"personagem":{},"localizacao_atual":"",
                    "npcs_conhecidos":{},"inimigos_derrotados":[],
                    "itens_obtidos":[],"habilidades_adquiridas":[],
                    "segredos_descobertos":[],"quests_ativas":[],
                    "quests_concluidas":[],"reputacao":{}},f)

    from personagens import criar_kael, criar_lyra

    print("═" * 60)
    print("  GERAÇÃO PROCEDURAL — TESTES")
    print("═" * 60)

    print("\n── INIMIGOS PROCEDURAIS (nível 2, vários tipos) ──")
    for tipo in TIPOS_INIMIGO:
        ini = gerar_inimigo(2, tipo=tipo, seed=42)
        print(f"  [{tipo:12}] {ini.nome:30} PV={ini.pv_max:4.0f} "
              f"Dano={ini.dano_base:4.1f} Def={ini.defesa:4.1f} "
              f"Fraq={ini.fraquezas}")

    print("\n── ESCALONAMENTO POR NÍVEL (tipo: besta) ──")
    print(f"  {'Nível':6} {'Nome':28} {'PV':6} {'Dano':6} {'Defesa':8} {'XP':5}")
    print("  " + "─"*58)
    for n in range(1, 7):
        ini = gerar_inimigo(n, tipo="besta", seed=n*10)
        print(f"  {n:6} {ini.nome:28} {ini.pv_max:6.0f} {ini.dano_base:6.1f} "
              f"{ini.defesa:8.1f} {ini.xp:5}")

    print("\n── ITENS PROCEDURAIS ──")
    for nivel in [1, 2, 3]:
        for tipo_dano in ["fisico", "magico"]:
            item = gerar_item(nivel, tipo_preferido="arma", tipo_dano=tipo_dano)
            print(f"  N{nivel} {tipo_dano:6}: {item.nome:25} "
                  f"dano={item.dano_arma:5.1f} qual={item.qualidade}")

    print("\n── MINI-CENÁRIO PROCEDURAL (nível 2, floresta) ──")
    cenario = gerar_cenario(2, bioma="floresta", tipo_foco="besta")
    print(f"  Título: {cenario.titulo}")
    print(f"  {cenario.descricao}")
    for i, ini in enumerate(cenario.inimigos, 1):
        atk = ini.ataques_especiais[0]["nome"] if ini.ataques_especiais else "—"
        print(f"  Batalha {i}: {ini.nome} (N{ini.nivel}) PV={ini.pv_max:.0f} | Especial: {atk}")
    print(f"  Loot: {[it.nome for it in cenario.loot_final]}")

    print("\n── BALANCEAMENTO — inimigo vs personagem ──")
    kael = criar_kael("Max")
    for nivel_ini in [1, 2, 3]:
        ini = gerar_inimigo(nivel_ini, tipo="humanoide", seed=99)
        turnos_estimados = ini.pv_max / max(1, (25 * (0.75 ** 1.5)))
        print(f"  Kael vs N{nivel_ini} ({ini.nome[:20]:20}): "
              f"PV={ini.pv_max:.0f} → ~{turnos_estimados:.1f} turnos")
