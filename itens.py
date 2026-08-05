"""
itens.py
─────────────────────────────────────────────────────────────
Catálogo de itens do jogo.
Cada item possui: dano_arma, defesa, maestria, habilidades
e uma função de progressão de maestria.

Regra de maestria:
  - Ao atingir maestria_max, a habilidade do item é transferida
    permanentemente ao personagem (via combate.aplicar_maestria).
  - A maestria continua crescendo além do máximo inicial se o item
    for aprimorado (por uso ou aprendizado com NPCs).
─────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass, field
from typing import List, Optional
import copy


# ══════════════════════════════════════════════════════════════
#  DATA CLASS
# ══════════════════════════════════════════════════════════════

@dataclass
class Item:
    nome: str
    tipo: str                          # "arma" | "armadura" | "acessorio" | "consumivel"
    qualidade: str                     # "ruim" | "neutro" | "bom"
    name_en: str = ""                  # English name (i18n)
    name_pt: str = ""                  # Portuguese name (same as nome by default)

    # Tipo de dano da arma — define a fonte de dano
    # "fisico"  → escala com Corpo Físico (espada, faca, arco, machado...)
    # "magico"  → escala com Conhecimento  (cajado, varinha, tomo...)
    # "misto"   → usa o maior entre os dois (armas encantadas)
    # ""        → não é arma (armadura, acessório)
    tipo_dano: str = ""

    # Semântica de uso — define multiplicadores por tipo de ação
    # Preenchido apenas para armas com tipo_dano != ""
    # Ex: {"corte": 1.1, "perfurar": 1.1, "impacto": 0.4, "esmagamento": 0.1}
    semantica: dict = None

    # Restrições de uso — o cajado exige forma/elemento; não pode combinar movimento+magia
    restricoes: list = None   # ex: ["requer_forma_ou_elemento", "penalidade_movimento"]

    # Requisito de atributo para equipar/usar o item
    # Chave = nome do atributo | valor = mínimo exigido
    # Armas físicas  → forca
    # Armas mágicas  → conhecimento_tacito
    # Armaduras      → vigor (só quando defesa > limiar)
    # Acessórios     → conhecimento_explicito
    requisito: dict = None   # ex: {"forca": 10}  {"vigor": 8}  {"conhecimento_explicito": 12}

    dano_fisico: float = 0.0   # dano base físico da arma
    dano_magico: float = 0.0   # dano base mágico da arma
    dano_arma: float = 0.0     # legacy — mantido para compatibilidade (= max(dano_fisico, dano_magico))
    defesa: float = 0.0
    maestria_atual: float = 0.0
    maestria_max: float = 100.0
    habilidades_item: List[str] = field(default_factory=list)
    descricao: str = ""
    # Atributos bônus diretos (ex: anel de força)
    bonus: dict = field(default_factory=dict)

    # ── Progressão de Maestria ────────────────────────────────

    def ganhar_maestria(self, qtd: float, motivo: str = "") -> bool:
        """
        Incrementa maestria. Retorna True se atingiu maestria_max
        pela primeira vez (gatilho para transferir habilidade).
        """
        ja_completo = self.maestria_atual >= self.maestria_max
        self.maestria_atual = min(self.maestria_atual + qtd, self.maestria_max * 2)
        agora_completo = self.maestria_atual >= self.maestria_max
        if motivo:
            print(f"  [{self.nome}] Maestria: {self.maestria_atual:.1f}/{self.maestria_max:.1f} — {motivo}")
        return (not ja_completo) and agora_completo

    def progresso_maestria(self) -> str:
        pct = min(100, (self.maestria_atual / self.maestria_max) * 100)
        blocos = int(pct / 5)
        barra = "█" * blocos + "░" * (20 - blocos)
        return f"[{barra}] {pct:.0f}%  ({self.maestria_atual:.0f}/{self.maestria_max:.0f})"

    def __post_init__(self):
        if not self.name_pt:
            self.name_pt = self.nome
        if self.dano_arma == 0.0:
            self.dano_arma = max(self.dano_fisico, self.dano_magico)
        if self.semantica is None:
            self.semantica = {}
        if self.restricoes is None:
            self.restricoes = []
        if self.requisito is None:
            self.requisito = {}

    def to_dict(self) -> dict:
        return {
            "nome": self.nome,
            "tipo": self.tipo,
            "qualidade": self.qualidade,
            "tipo_dano": self.tipo_dano,
            "requisito": self.requisito,
            "dano_fisico": self.dano_fisico,
            "dano_magico": self.dano_magico,
            "dano_arma": self.dano_arma,
            "defesa": self.defesa,
            "maestria_atual": self.maestria_atual,
            "maestria_max": self.maestria_max,
            "habilidades_item": self.habilidades_item,
            "bonus": self.bonus,
        }

    def clonar(self):
        """Retorna uma cópia independente do item."""
        return copy.deepcopy(self)


# ══════════════════════════════════════════════════════════════
#  CATÁLOGO DE ITENS
# ══════════════════════════════════════════════════════════════

# ── Armas ─────────────────────────────────────────────────────

ESPADA_LONGA = Item(
    nome="Espada Longa", name_en="Long Sword",
    tipo="arma", qualidade="bom",
    tipo_dano="fisico",
    dano_fisico=15.0, defesa=5.0,
    maestria_max=100.0,
    requisito={"forca": 10},
    habilidades_item=["corte_duplo"],
    semantica={
        "corte"      : 1.10,   # golpe com a lâmina
        "perfurar"   : 1.10,   # estocada
        "impacto"    : 0.40,   # golpe com a guarda/pommel
        "esmagamento": 0.10,   # ineficaz — não é para isso
        "choque"     : 0.40,   # colisão com o corpo da espada
    },
    descricao=(
        "Lâmina equilibrada de aço temperado. Versátil em combate corpo a corpo. "
        "Ideal para cortes e estocadas — ineficaz como martelo."
    ),
)

FACA_ENFERRUJADA = Item(
    nome="Faca Enferrujada", name_en="Rusty Knife",
    tipo="arma", qualidade="ruim",
    tipo_dano="fisico",
    dano_fisico=5.0, defesa=0.0,
    maestria_max=60.0,
    requisito={"forca": 4},
    habilidades_item=["golpe_rapido"],
    semantica={
        "corte"      : 1.00,
        "perfurar"   : 1.10,
        "impacto"    : 0.30,
        "esmagamento": 0.10,
        "choque"     : 0.30,
    },
    descricao="Uma faca velha e enferrujada. Melhor para espetar do que para cortar.",
)

CAJADO_ARCANO = Item(
    nome="Cajado Arcano", name_en="Arcane Staff",
    tipo="arma", qualidade="bom",
    tipo_dano="magico",
    dano_magico=10.0, defesa=3.0,
    maestria_max=120.0,
    requisito={"conhecimento_tacito": 4},
    habilidades_item=["pulso_arcano"],
    bonus={"conhecimento_explicito": 2.0},
    semantica={
        "elemento"   : 1.00,   # lançar elemento (fogo, gelo...)
        "forma"      : 1.00,   # dar forma à magia (bola, cone...)
        "impacto"    : 0.30,   # pancada física com o cajado
        "esmagamento": 0.20,
        "corte"      : 0.10,   # muito ineficaz
        "perfurar"   : 0.10,
    },
    restricoes=["requer_forma_ou_elemento", "penalidade_movimento"],
    descricao=(
        "Cajado entalhado com runas. Amplifica o conhecimento do portador. "
        "Permite dar forma e lançar elementos. Uso físico é muito ineficaz."
    ),
)

ARCO_SIMPLES = Item(
    nome="Arco Simples", name_en="Simple Bow",
    tipo="arma", qualidade="neutro",
    tipo_dano="fisico",
    dano_fisico=8.0, defesa=0.0,
    maestria_max=80.0,
    requisito={"forca": 7},
    habilidades_item=["tiro_preciso"],
    semantica={
        "perfurar"   : 1.20,   # flecha é especializada em perfurar
        "corte"      : 0.20,   # a flecha não é para cortar
        "impacto"    : 0.50,   # tiro na força do impacto
        "esmagamento": 0.10,
        "choque"     : 0.40,
    },
    descricao="Arco de madeira flexível. Especializado em perfurar à distância.",
)

# ── Armaduras / Proteções ─────────────────────────────────────

ARMADURA_COURO = Item(
    nome="Armadura de Couro", name_en="Leather Armor",
    tipo="armadura",
    qualidade="neutro",
    dano_arma=0.0,
    defesa=8.0,
    maestria_max=150.0,
    requisito={"vigor": 4},
    habilidades_item=["esquiva_instintiva"],
    descricao="Proteção leve de couro curtido. Não limita o movimento.",
)

ESCUDO_MADEIRA = Item(
    nome="Escudo de Madeira", name_en="Wooden Shield",
    tipo="armadura",
    qualidade="neutro",
    dano_arma=0.0,
    defesa=6.0,
    maestria_max=80.0,
    requisito={"vigor": 4},
    habilidades_item=["bloqueio"],
    descricao="Escudo robusto de carvalho reforçado com metal.",
)

# ── Acessórios ────────────────────────────────────────────────

CHAPEU_DO_MAGO = Item(
    nome="Chapéu do Mago", name_en="Wizard's Hat",
    tipo="acessorio",
    qualidade="bom",
    dano_arma=0.0,
    defesa=5.0,
    maestria_max=150.0,
    requisito={"conhecimento_explicito": 10},
    habilidades_item=["dobrar_conhecimento"],
    descricao=(
        "Chapéu pontiagudo de veludo profundo. "
        "Passivamente dobra o conhecimento obtido pelo portador."
    ),
)

AMULETO_PROTETOR = Item(
    nome="Amuleto Protetor", name_en="Protective Amulet",
    tipo="acessorio",
    qualidade="bom",
    dano_arma=0.0,
    defesa=4.0,
    maestria_max=100.0,
    requisito={"conhecimento_explicito": 4},
    habilidades_item=[],
    bonus={"vigor": 2.0},
    descricao="Amuleto de jade. Fortalece sutilmente a vitalidade do portador.",
)

ANEL_DO_ESTUDIOSO = Item(
    nome="Anel do Estudioso", name_en="Scholar's Ring",
    tipo="acessorio",
    qualidade="bom",
    dano_arma=0.0,
    defesa=0.0,
    maestria_max=200.0,
    habilidades_item=["memorizar_lecoes"],
    bonus={"conhecimento_explicito": 3.0},
    descricao="Anel de prata gravado com alfabetos antigos. Facilita a retenção de conhecimento.",
)

# ── Consumíveis ───────────────────────────────────────────────

POCAO_CURA = Item(
    nome="Poção de Cura", name_en="Healing Potion",
    tipo="consumivel",
    qualidade="neutro",
    dano_arma=0.0,
    defesa=0.0,
    maestria_max=1.0,
    descricao="Líquido avermelhado em frasco pequeno. Restaura 20 PV ao ser ingerido.",
    bonus={"cura": 20.0},
)

ERVAS_MEDICINAIS = Item(
    nome="Ervas Medicinais", name_en="Medicinal Herbs",
    tipo="consumivel",
    qualidade="bom",
    dano_arma=0.0,
    defesa=0.0,
    maestria_max=1.0,
    descricao="Feixe de ervas secas. Restaura 10 PV e cura venenos leves.",
    bonus={"cura": 10.0, "cura_veneno": True},
)

# ── Novos consumíveis ────────────────────────────────────────

POCAO_PSIQUE = Item(
    nome="Elixir de Psique", name_en="Psi Elixir", name_pt="Elixir de Psique",
    tipo="consumivel", qualidade="bom",
    dano_arma=0.0, defesa=0.0, maestria_max=1.0,
    descricao="Frasco azulado que restaura concentracao. Recupera 4.0 Psique.",
    bonus={"cura_psique": 4.0},
)

POCAO_PSIQUE_MAIOR = Item(
    nome="Elixir de Psique Maior", name_en="Greater Psi Elixir", name_pt="Elixir de Psique Maior",
    tipo="consumivel", qualidade="raro",
    dano_arma=0.0, defesa=0.0, maestria_max=1.0,
    descricao="Elixir concentrado. Restaura toda a Psique imediatamente.",
    bonus={"cura_psique": 999.0},
)

ANTIDOTO = Item(
    nome="Antidoto", name_en="Antidote", name_pt="Antidoto",
    tipo="consumivel", qualidade="bom",
    dano_arma=0.0, defesa=0.0, maestria_max=1.0,
    descricao="Remove veneno e sangramento. Ingredientes da floresta.",
    bonus={"remove_status": ["envenenar", "sangrar"], "cura": 5.0},
)

POCAO_PURIFICACAO = Item(
    nome="Pocao de Purificacao", name_en="Purification Potion", name_pt="Pocao de Purificacao",
    tipo="consumivel", qualidade="raro",
    dano_arma=0.0, defesa=0.0, maestria_max=1.0,
    descricao="Remove todos os efeitos negativos. Rara e valiosa.",
    bonus={"remove_status": "todos", "cura": 15.0},
)

POCAO_CURA_MAIOR = Item(
    nome="Pocao de Cura Maior", name_en="Greater Healing Potion", name_pt="Pocao de Cura Maior",
    tipo="consumivel", qualidade="raro",
    dano_arma=0.0, defesa=0.0, maestria_max=1.0,
    descricao="Pocao concentrada. Restaura 50 PV.",
    bonus={"cura": 50.0},
)

ERVAS_REVIGORANTES = Item(
    nome="Ervas Revigorantes", name_en="Invigorating Herbs", name_pt="Ervas Revigorantes",
    tipo="consumivel", qualidade="simples",
    dano_arma=0.0, defesa=0.0, maestria_max=1.0,
    descricao="Ervas raras que restauram corpo e mente. +10 PV, +2 Psique.",
    bonus={"cura": 10.0, "cura_psique": 2.0},
)

# ── Catálogo completo ─────────────────────────────────────────

CATALOGO_ITENS: dict = {
    "espada_longa"       : ESPADA_LONGA,
    "faca_enferrujada"   : FACA_ENFERRUJADA,
    "cajado_arcano"      : CAJADO_ARCANO,
    "arco_simples"       : ARCO_SIMPLES,
    "armadura_couro"     : ARMADURA_COURO,
    "escudo_madeira"     : ESCUDO_MADEIRA,
    "chapeu_do_mago"     : CHAPEU_DO_MAGO,
    "amuleto_protetor"   : AMULETO_PROTETOR,
    "anel_do_estudioso"  : ANEL_DO_ESTUDIOSO,
    "pocao_cura"         : POCAO_CURA,
    "ervas_medicinais"   : ERVAS_MEDICINAIS,
    "pocao_psique"        : POCAO_PSIQUE,
    "pocao_psique_maior"  : POCAO_PSIQUE_MAIOR,
    "antidoto"            : ANTIDOTO,
    "pocao_purificacao"   : POCAO_PURIFICACAO,
    "pocao_cura_maior"    : POCAO_CURA_MAIOR,
    "ervas_revigorantes"  : ERVAS_REVIGORANTES,
}


def obter_item(chave: str) -> Item:
    """Retorna uma cópia fresca do item pelo nome-chave."""
    if chave not in CATALOGO_ITENS:
        raise KeyError(f"Item '{chave}' não encontrado no catálogo.")
    return CATALOGO_ITENS[chave].clonar()


# ══════════════════════════════════════════════════════════════
#  PONTO DE TESTE RÁPIDO
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    for chave, item in CATALOGO_ITENS.items():
        print(f"{item.nome:25} | tipo={item.tipo:10} | dano={item.dano_arma:5.1f} | def={item.defesa:4.1f} | maestria={item.progresso_maestria()}")


# ══════════════════════════════════════════════════════════════
#  ITENS ÚNICOS DE BOSS — Folclore Brasileiro
# ══════════════════════════════════════════════════════════════

# ── Boss: Boi Tatá ────────────────────────────────────────────
OLHO_DO_BOI_TATA = Item(
    nome="Olho do Boi Tatá", name_en="Boi Tata's Eye",
    tipo="acessorio", qualidade="bom",
    dano_arma=0, defesa=6,
    descricao="Fragmento incandescente do olho do Boi Tatá. Queima com fogo eterno.",
    requisito={"conhecimento_explicito": 8},
    habilidades_item=["pulso_arcano"],
    bonus={"elemento_fogo": True, "reducao_dano_pct": 0.15},
    maestria_max=200,
)

# ── Boss: Lobisomem ───────────────────────────────────────────
GARRA_DO_LOBISOMEM = Item(
    nome="Garra do Lobisomem", name_en="Werewolf Claw",
    tipo="arma", qualidade="bom",
    dano_arma=22, defesa=2,
    descricao="Garra amaldiçoada que escurece sob a lua. Ataca com fúria selvagem.",
    requisito={"forca": 12},
    habilidades_item=["corte_duplo", "esquiva_instintiva"],
    maestria_max=150,
)

# ── Boss: Dragão Sombrio ──────────────────────────────────────
ESCAMA_DO_DRAGAO_SOMBRIO = Item(
    nome="Escama do Dragão Sombrio", name_en="Shadow Dragon Scale",
    tipo="armadura", qualidade="bom",
    dano_arma=0, defesa=18,
    descricao="Escama negra que absorve magia sombria. Proteção lendária.",
    requisito={"vigor": 12},
    habilidades_item=["barreira_arcana", "resistencia"],
    bonus={"reducao_dano_pct": 0.20},
    maestria_max=250,
)

# ── Boss: Caipora ─────────────────────────────────────────────
CACHIMBO_DA_CAIPORA = Item(
    nome="Cachimbo da Caipora", name_en="Caipora's Pipe",
    tipo="acessorio", qualidade="bom",
    dano_arma=0, defesa=3,
    descricao="Cachimbo mágico da protetora das matas. Confunde os inimigos.",
    requisito={"conhecimento_explicito": 6},
    habilidades_item=["analise_vulnerabilidade", "furtividade"],
    bonus={"conhecimento_tacito": 2.0},
    maestria_max=150,
)

# ── Boss: Curupira ────────────────────────────────────────────
PE_VIRADO_DO_CURUPIRA = Item(
    nome="Pé Virado do Curupira", name_en="Curupira's Backward Foot",
    tipo="acessorio", qualidade="bom",
    dano_arma=0, defesa=4,
    descricao="Amuleto dos pés ao contrário do Curupira. Confunde rastreadores.",
    requisito={"conhecimento_explicito": 5},
    habilidades_item=["furtividade", "esquiva_instintiva"],
    bonus={"vigor": 2.0, "conhecimento_tacito": 1.5},
    maestria_max=150,
)

# ── Boss: Mula Sem Cabeça ─────────────────────────────────────
FERRADURA_AMALDICOADAA = Item(
    nome="Ferradura Amaldiçoada", name_en="Cursed Horseshoe",
    tipo="acessorio", qualidade="bom",
    dano_arma=8, defesa=5,
    descricao="Ferradura da Mula Sem Cabeça. Golpeia com fúria espiritual.",
    requisito={"vigor": 6},
    habilidades_item=["investida", "canal_psiquico"],
    bonus={"psique_bonus_pct": 0.15},
    maestria_max=150,
)

# Adicionar ao catálogo
CATALOGO_ITENS.update({
    "olho_boi_tata"         : OLHO_DO_BOI_TATA,
    "garra_lobisomem"       : GARRA_DO_LOBISOMEM,
    "escama_dragao_sombrio" : ESCAMA_DO_DRAGAO_SOMBRIO,
    "cachimbo_caipora"      : CACHIMBO_DA_CAIPORA,
    "pe_virado_curupira"    : PE_VIRADO_DO_CURUPIRA,
    "ferradura_amaldicoada" : FERRADURA_AMALDICOADAA,
})
