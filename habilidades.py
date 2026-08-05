"""
habilidades.py
─────────────────────────────────────────────────────────────
Catálogo de habilidades.

Tipos:
  "ativar"  — custam Psiquê (mana) para usar (limite: 4)
  "passiva" — sempre ativas, sem custo (limite: 3)
  "extra"   — sem limite; somam bônus a atributos ou slots

Custo de Psiquê variável: habilidades mais poderosas custam mais.
Habilidades "mochila_extra" e "cinto_utilidades" expandem inventário.
─────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass, field
from typing import Dict, Callable, Optional
import copy


@dataclass
class Habilidade:
    nome: str
    tipo: str
    descricao: str
    custo_psique: float = 0.0
    name_en: str = ""       # English name (i18n)
    name_pt: str = ""       # Portuguese name

    def __post_init__(self):
        if not self.name_pt:
            self.name_pt = self.nome
    bonus_atributo: Dict[str, float] = field(default_factory=dict)
    slots_inventario: int = 0
    ativa: bool = True
    efeito_fn: Optional[Callable] = field(default=None, repr=False)

    def aplicar_efeito(self, contexto: dict) -> dict:
        if self.efeito_fn and self.ativa:
            return self.efeito_fn(contexto)
        return {}

    def clonar(self):
        return copy.deepcopy(self)

    def __hash__(self):
        return hash(self.nome)


# ── Funções de efeito ─────────────────────────────────────────

def _efeito_corte_duplo(ctx):
    return {"multiplicador_golpes": 2, "fator_dano": 0.7, "descricao_efeito": "Corte Duplo!"}

def _efeito_golpe_rapido(ctx):
    return {"eficiencia_bonus": 0.2, "descricao_efeito": "Golpe Rápido!"}

def _efeito_pulso_arcano(ctx):
    return {"dano_bonus": 8.0, "tipo_dano": "arcano", "descricao_efeito": "Pulso Arcano!"}

def _efeito_tiro_preciso(ctx):
    return {"criatividade_bonus": 0.15, "descricao_efeito": "Tiro Preciso!"}

def _efeito_analise_vulnerabilidade(ctx):
    return {"eficiencia_bonus": 0.3, "descricao_efeito": "Vulnerabilidade explorada!"}

def _efeito_investida(ctx):
    return {"dano_bonus": 5.0, "fator_dano": 1.3, "descricao_efeito": "Investida brutal!"}

def _efeito_barreira_arcana(ctx):
    return {"defesa_bonus_turno": 8.0, "descricao_efeito": "Barreira Arcana erguida!"}

def _efeito_cura_menor(ctx):
    return {"cura": 15.0, "descricao_efeito": "Ferimentos amenizados."}

# ── Habilidades de Ativar ─────────────────────────────────────

HABILIDADE_CORTE_DUPLO = Habilidade(
    nome="Corte Duplo", name_en="Double Slash", tipo="ativar", custo_psique=2.0,
    descricao="Dois golpes (70% dano cada). Custo: 2 Ψ.",
    efeito_fn=_efeito_corte_duplo)

HABILIDADE_GOLPE_RAPIDO = Habilidade(
    nome="Golpe Rápido", name_en="Quick Strike", tipo="ativar", custo_psique=1.5,
    descricao="+0.2 eficiência. Custo: 1.5 Ψ.",
    efeito_fn=_efeito_golpe_rapido)

HABILIDADE_PULSO_ARCANO = Habilidade(
    nome="Pulso Arcano", name_en="Arcane Pulse", tipo="ativar", custo_psique=3.0,
    descricao="+8 dano arcano. Custo: 3 Ψ.",
    efeito_fn=_efeito_pulso_arcano)

HABILIDADE_TIRO_PRECISO = Habilidade(
    nome="Tiro Preciso", name_en="Precise Shot", tipo="ativar", custo_psique=1.5,
    descricao="+0.15 criatividade. Custo: 1.5 Ψ.",
    efeito_fn=_efeito_tiro_preciso)

HABILIDADE_ANALISE_VULNERABILIDADE = Habilidade(
    nome="Análise de Vulnerabilidade", name_en="Vulnerability Analysis", tipo="ativar", custo_psique=2.5,
    descricao="+0.3 eficiência. Custo: 2.5 Ψ.",
    efeito_fn=_efeito_analise_vulnerabilidade)

HABILIDADE_INVESTIDA = Habilidade(
    nome="Investida", name_en="Charge", tipo="ativar", custo_psique=2.0,
    descricao="+5 dano, fator 1.3x. Custo: 2 Ψ.",
    efeito_fn=_efeito_investida)

HABILIDADE_BARREIRA_ARCANA = Habilidade(
    nome="Barreira Arcana", name_en="Arcane Barrier", tipo="ativar", custo_psique=3.5,
    descricao="+8 defesa no turno. Custo: 3.5 Ψ.",
    efeito_fn=_efeito_barreira_arcana)

HABILIDADE_CURA_MENOR = Habilidade(
    nome="Cura Menor", name_en="Minor Heal", tipo="ativar", custo_psique=4.0,
    descricao="Restaura 15 PV. Custo: 4 Ψ.",
    efeito_fn=_efeito_cura_menor)

# ── Habilidades Passivas ──────────────────────────────────────

HABILIDADE_RESISTENCIA = Habilidade(
    nome="Resistência", name_en="Resistance", tipo="passiva",
    descricao="+3 Vigor permanente.",
    bonus_atributo={"vigor": 3.0})

HABILIDADE_DOBRAR_CONHECIMENTO = Habilidade(
    nome="Dobrar Conhecimento", name_en="Double Knowledge", tipo="passiva",
    descricao="Todo conhecimento obtido é dobrado.")

HABILIDADE_BLOQUEIO = Habilidade(
    nome="Bloqueio", name_en="Block", tipo="passiva",
    descricao="+4 Defesa Base.",
    bonus_atributo={"defesa": 4.0})

HABILIDADE_ESQUIVA_INSTINTIVA = Habilidade(
    nome="Esquiva Instintiva", name_en="Instinctive Dodge", tipo="passiva",
    descricao="Reduz 10% do dano recebido.",
    bonus_atributo={"reducao_dano_pct": 0.10})

HABILIDADE_MEMORIZAR_LECOES = Habilidade(
    nome="Memorizar Lições", name_en="Memorize Lessons", tipo="passiva",
    descricao="+2 Conhecimento Explícito.",
    bonus_atributo={"conhecimento_explicito": 2.0})

HABILIDADE_CANAL_PSIQUICO = Habilidade(
    nome="Canal Psíquico", name_en="Psychic Channel", tipo="passiva",
    descricao="Regen Psiquê pós-batalha: +5% extra (total 15%).",
    bonus_atributo={"regen_psique_bonus": 0.05})

HABILIDADE_FOCO_MENTAL = Habilidade(
    nome="Foco Mental", name_en="Mental Focus", tipo="passiva",
    descricao="+20% Psiquê máxima.",
    bonus_atributo={"psique_bonus_pct": 0.20})

# ── Habilidades Extras ────────────────────────────────────────

HABILIDADE_CULINARIA = Habilidade(
    nome="Culinária", name_en="Cooking", tipo="extra",
    descricao="+0.5 Vigor. Refeições recuperam PV.",
    bonus_atributo={"vigor": 0.5})

HABILIDADE_ACAMPAR = Habilidade(
    nome="Acampar", name_en="Camping", tipo="extra",
    descricao="+0.5 Vigor. Melhora recuperação ao dormir.",
    bonus_atributo={"vigor": 0.5})

HABILIDADE_SALTADOR = Habilidade(
    nome="Saltador", name_en="Jumper", tipo="extra",
    descricao="+0.3 Força.",
    bonus_atributo={"forca": 0.3})

HABILIDADE_ALPINISTA = Habilidade(
    nome="Alpinista", name_en="Climber", tipo="extra",
    descricao="+0.3 Força, +0.2 Vigor.",
    bonus_atributo={"forca": 0.3, "vigor": 0.2})

HABILIDADE_LEITURA_DINAMICA = Habilidade(
    nome="Leitura Dinâmica", name_en="Speed Reading", tipo="extra",
    descricao="+0.8 Conhecimento Explícito.",
    bonus_atributo={"conhecimento_explicito": 0.8})

HABILIDADE_ANALISE_FRAQUEZA = Habilidade(
    nome="Análise de Fraqueza", name_en="Weakness Analysis", tipo="extra",
    descricao="+0.5 Conhecimento Tácito.",
    bonus_atributo={"conhecimento_tacito": 0.5})

HABILIDADE_RASTREADOR = Habilidade(
    nome="Rastreador", name_en="Tracker", tipo="extra",
    descricao="+0.4 Conhecimento Tácito.",
    bonus_atributo={"conhecimento_tacito": 0.4})

HABILIDADE_PRIMEIRO_SOCORROS = Habilidade(
    nome="Primeiros Socorros", name_en="First Aid", tipo="extra",
    descricao="+0.3 Vigor. 5 PV fora de combate por cena.",
    bonus_atributo={"vigor": 0.3})

HABILIDADE_NEGOCIADOR = Habilidade(
    nome="Negociador", name_en="Negotiator", tipo="extra",
    descricao="+0.5 Conhecimento Explícito.",
    bonus_atributo={"conhecimento_explicito": 0.5})

HABILIDADE_FURTIVIDADE = Habilidade(
    nome="Furtividade", name_en="Stealth", tipo="extra",
    descricao="+0.3 criatividade em surpresa.",
    bonus_atributo={"criatividade_bonus": 0.3})

HABILIDADE_MEDITACAO = Habilidade(
    nome="Meditação", name_en="Meditation", tipo="extra",
    descricao="+5% regen Psiquê após batalha.",
    bonus_atributo={"regen_psique_bonus": 0.05})

HABILIDADE_MOCHILA_EXTRA = Habilidade(
    nome="Mochila Extra", name_en="Extra Backpack", tipo="extra",
    descricao="+1 slot de inventário (máx. 5).",
    slots_inventario=1)

HABILIDADE_CINTO_UTILIDADES = Habilidade(
    nome="Cinto de Utilidades", name_en="Utility Belt", tipo="extra",
    descricao="+1 slot de inventário (máx. 5).",
    slots_inventario=1)

# ── Catálogo ──────────────────────────────────────────────────

CATALOGO_HABILIDADES: dict = {
    "corte_duplo"             : HABILIDADE_CORTE_DUPLO,
    "golpe_rapido"            : HABILIDADE_GOLPE_RAPIDO,
    "pulso_arcano"            : HABILIDADE_PULSO_ARCANO,
    "tiro_preciso"            : HABILIDADE_TIRO_PRECISO,
    "analise_vulnerabilidade" : HABILIDADE_ANALISE_VULNERABILIDADE,
    "investida"               : HABILIDADE_INVESTIDA,
    "barreira_arcana"         : HABILIDADE_BARREIRA_ARCANA,
    "cura_menor"              : HABILIDADE_CURA_MENOR,
    "resistencia"             : HABILIDADE_RESISTENCIA,
    "dobrar_conhecimento"     : HABILIDADE_DOBRAR_CONHECIMENTO,
    "bloqueio"                : HABILIDADE_BLOQUEIO,
    "esquiva_instintiva"      : HABILIDADE_ESQUIVA_INSTINTIVA,
    "memorizar_lecoes"        : HABILIDADE_MEMORIZAR_LECOES,
    "canal_psiquico"          : HABILIDADE_CANAL_PSIQUICO,
    "foco_mental"             : HABILIDADE_FOCO_MENTAL,
    "culinaria"               : HABILIDADE_CULINARIA,
    "acampar"                 : HABILIDADE_ACAMPAR,
    "saltador"                : HABILIDADE_SALTADOR,
    "alpinista"               : HABILIDADE_ALPINISTA,
    "leitura_dinamica"        : HABILIDADE_LEITURA_DINAMICA,
    "analise_fraqueza"        : HABILIDADE_ANALISE_FRAQUEZA,
    "rastreador"              : HABILIDADE_RASTREADOR,
    "primeiro_socorros"       : HABILIDADE_PRIMEIRO_SOCORROS,
    "negociador"              : HABILIDADE_NEGOCIADOR,
    "furtividade"             : HABILIDADE_FURTIVIDADE,
    "meditacao"               : HABILIDADE_MEDITACAO,
    "mochila_extra"           : HABILIDADE_MOCHILA_EXTRA,
    "cinto_utilidades"        : HABILIDADE_CINTO_UTILIDADES,
}


def obter_habilidade(chave: str) -> Habilidade:
    if chave not in CATALOGO_HABILIDADES:
        raise KeyError(f"Habilidade '{chave}' não encontrada.")
    return CATALOGO_HABILIDADES[chave].clonar()


if __name__ == "__main__":
    for chave, h in CATALOGO_HABILIDADES.items():
        custo = f"Ψ{h.custo_psique:.1f}" if h.custo_psique else "     "
        slots = f" +{h.slots_inventario}slot" if h.slots_inventario else ""
        print(f"  [{h.tipo:7}] {custo} {h.nome:28}{slots} — {h.descricao[:50]}")