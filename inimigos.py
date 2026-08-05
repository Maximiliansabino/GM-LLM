"""
inimigos.py
─────────────────────────────────────────────────────────────
Catálogo de inimigos e gerador procedural de monstros.

Cada inimigo tem:
  - atributos de combate (PV, defesa, dano, fraquezas)
  - tipo de defesa (usado no cálculo de eficiência)
  - recompensas ao ser derrotado
  - loot (itens e quantidades)
─────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import random
import copy


# ══════════════════════════════════════════════════════════════
#  DATA CLASS
# ══════════════════════════════════════════════════════════════

@dataclass
class Inimigo:
    nome: str
    tipo: str                          # "humanoide" | "besta" | "arcano" | "morto-vivo" | "elemental"
    nivel: int
    pv_max: float
    pv_atual: float = field(init=False)
    defesa: float = 0.0
    dano_base: float = 5.0
    tipo_defesa: str = "fisica"        # "fisica" | "arcana" | "natural" | "espiritual"
    fraquezas: List[str] = field(default_factory=list)
    resistencias: List[str] = field(default_factory=list)
    descricao: str = ""
    # Recompensas
    xp: int = 0
    ouro: int = 0
    loot_possivel: List[Tuple[str, float]] = field(default_factory=list)  # (chave_item, chance 0-1)
    # Ataques especiais: lista de dicts com nome, dano_mult, efeito, descricao, chance
    # Ex: {"nome": "Mordida de Fogo", "dano_mult": 1.5, "efeito": "queimar",
    #       "descricao": "Queima com fogo eterno!", "chance": 0.35}
    ataques_especiais: List[dict] = field(default_factory=list)
    # Estado
    ativo: bool = True
    status_effects: List[str] = field(default_factory=list)
    _chave: str = field(default='', repr=False)
    name_en: str = field(default='', repr=False)
    name_pt: str = field(default='', repr=False)

    def __post_init__(self):
        if not self.name_pt:
            self.name_pt = self.nome
        self.pv_atual = self.pv_max

    def receber_dano(self, dano: float) -> float:
        """Aplica dano e retorna o dano real sofrido."""
        dano_real = max(0, dano - self.defesa)
        self.pv_atual = max(0, self.pv_atual - dano_real)
        if self.pv_atual <= 0:
            self.ativo = False
        return dano_real

    def esta_vivo(self) -> bool:
        return self.pv_atual > 0

    def atacar(self) -> float:
        """
        Retorna o dano base do ataque (sem efeitos especiais).
        Usado pelo motor de combate para calcular dano recebido.
        """
        variacao = random.uniform(0.85, 1.15)
        return self.dano_base * variacao

    def escolher_ataque(self) -> dict:
        """
        Seleciona um ataque (básico ou especial) com base nas chances.
        Retorna dict com: nome, dano, descricao, efeito (opcional).
        """
        # Tenta cada ataque especial
        for atk in self.ataques_especiais:
            if random.random() <= atk.get("chance", 0.3):
                dano = self.dano_base * atk.get("dano_mult", 1.0) * random.uniform(0.85, 1.15)
                return {
                    "nome"     : atk["nome"],
                    "dano"     : round(dano, 1),
                    "descricao": atk.get("descricao", ""),
                    "efeito"   : atk.get("efeito", None),
                    "especial" : True,
                }
        # Ataque básico
        return {
            "nome"     : "Ataque",
            "dano"     : round(self.dano_base * random.uniform(0.85, 1.15), 1),
            "descricao": "",
            "efeito"   : None,
            "especial" : False,
        }

    def gerar_loot(self) -> List[str]:
        """Rola chance de cada item de loot e retorna lista de chaves."""
        from itens import obter_item
        resultado = []
        for chave, chance in self.loot_possivel:
            if random.random() <= chance:
                resultado.append(chave)
        return resultado

    def to_dict(self) -> dict:
        return {
            "nome": self.nome,
            "tipo": self.tipo,
            "nivel": self.nivel,
            "pv_atual": self.pv_atual,
            "pv_max": self.pv_max,
            "defesa": self.defesa,
            "dano_base": self.dano_base,
            "tipo_defesa": self.tipo_defesa,
            "fraquezas": self.fraquezas,
            "ativo": self.ativo,
        }

    def clonar(self):
        clone = copy.deepcopy(self)
        clone.pv_atual = clone.pv_max
        clone.ativo = True
        clone.status_effects = []
        return clone

    def _set_chave(self, chave: str):
        self._chave = chave
        return self

    def ficha(self) -> str:
        from arte_inimigos import obter_arte
        barra = int((self.pv_atual / max(self.pv_max, 1)) * 20)
        hp_bar = "█" * barra + "░" * (20 - barra)
        arte = obter_arte(self._chave, self.tipo)
        arte_fmt = "\n".join(f"  {l}" for l in arte.strip("\n").split("\n"))
        return (
            f"\n{arte_fmt}\n"
            f"  {'─'*44}\n"
            f"  {self.nome}  (Nível {self.nivel} | {self.tipo.upper()})\n"
            f"  PV  [{hp_bar}] {self.pv_atual:.0f}/{self.pv_max:.0f}\n"
            f"  Defesa: {self.defesa}  Dano base: {self.dano_base}  "
            f"Def.tipo: {self.tipo_defesa}"
        )


# ══════════════════════════════════════════════════════════════
#  CATÁLOGO DE INIMIGOS
# ══════════════════════════════════════════════════════════════

# ── Nível 1 ───────────────────────────────────────────────────

GOBLIN_BATEDEIRO = Inimigo(
    nome="Goblin Batedeiro", name_en="Scout Goblin",
    tipo="humanoide",
    nivel=1,
    pv_max=80.0,
    defesa=1.0,
    dano_base=5.0,
    tipo_defesa="fisica",
    fraquezas=["fogo", "luz"],
    descricao="Goblin ágil que ataca em bando. Perigoso quando não está sozinho.",
    xp=15,
    ouro=5,
    loot_possivel=[("faca_enferrujada", 0.4)],
)

LOBO_DA_FLORESTA = Inimigo(
    nome="Lobo da Floresta", name_en="Forest Wolf",
    tipo="besta",
    nivel=1,
    pv_max=100.0,
    defesa=1.0,
    dano_base=7.0,
    tipo_defesa="natural",
    fraquezas=["fogo"],
    resistencias=["frio"],
    descricao="Lobo territorial de pelagem cinzenta. Ataca em grupo se houver oportunidade.",
    xp=20,
    ouro=0,
    loot_possivel=[("ervas_medicinais", 0.3)],
)

# ── Nível 2 ───────────────────────────────────────────────────

ESQUELETO_GUERREIRO = Inimigo(
    nome="Esqueleto Guerreiro", name_en="Warrior Skeleton",
    tipo="morto-vivo",
    nivel=2,
    pv_max=140.0,
    defesa=3.0,
    dano_base=9.0,
    tipo_defesa="espiritual",
    fraquezas=["luz", "fogo"],
    resistencias=["fisica", "frio"],
    descricao="Ossada animada por energia sombria. Imune a dor; reage mal à luz sagrada.",
    xp=35,
    ouro=10,
    loot_possivel=[("escudo_madeira", 0.25), ("pocao_cura", 0.3)],
)

TROLL_DAS_PEDRAS = Inimigo(
    nome="Troll das Pedras", name_en="Stone Troll",
    tipo="besta",
    nivel=2,
    pv_max=220.0,
    defesa=6.0,
    dano_base=12.0,
    tipo_defesa="natural",
    fraquezas=["fogo", "acido"],
    descricao="Criatura rochosa de regeneração lenta. Fogo impede sua regeneração.",
    xp=60,
    ouro=15,
    loot_possivel=[("amuleto_protetor", 0.2)],
)

# ── Nível 3 ───────────────────────────────────────────────────

MAGO_RENEGADO = Inimigo(
    nome="Mago Renegado", name_en="Renegade Mage",
    tipo="humanoide",
    nivel=3,
    pv_max=180.0,
    defesa=2.0,
    dano_base=14.0,
    tipo_defesa="arcana",
    fraquezas=["fisica", "interromper_conjuracao"],
    resistencias=["arcana"],
    descricao=(
        "Estudioso corrompido pelo poder. Usa feitiços de área e escudos arcanos. "
        "Interromper sua concentração anula o escudo."
    ),
    xp=80,
    ouro=30,
    loot_possivel=[("anel_do_estudioso", 0.3), ("cajado_arcano", 0.15)],
)

ELEMENTAL_DE_PEDRA = Inimigo(
    nome="Elemental de Pedra", name_en="Stone Elemental",
    tipo="elemental",
    nivel=3,
    pv_max=300.0,
    defesa=10.0,
    dano_base=17.0,
    tipo_defesa="natural",
    fraquezas=["acido", "arcano"],
    resistencias=["fisica", "fogo", "frio"],
    descricao="Manifestação da terra com defesa colossal. Apenas ataques arcanos ou ácidos penetram.",
    xp=100,
    ouro=20,
    loot_possivel=[("amuleto_protetor", 0.4)],
)

# ── Boss ──────────────────────────────────────────────────────

SENHOR_DAS_SOMBRAS = Inimigo(
    nome="Senhor das Sombras", name_en="Shadow Lord",
    tipo="arcano",
    nivel=5,
    pv_max=480.0,
    defesa=8.0,
    dano_base=22.0,
    tipo_defesa="espiritual",
    fraquezas=["luz", "conhecimento_antigo"],
    resistencias=["fisica", "arcana", "frio"],
    descricao=(
        "Entidade sombria de poder imenso. Absorve ataques físicos diretos. "
        "Conhecimento dos rituais antigos reduz sua resistência."
    ),
    xp=300,
    ouro=100,
    loot_possivel=[("chapeu_do_mago", 0.5), ("anel_do_estudioso", 0.5)],
)


CATALOGO_INIMIGOS: dict = {
    "goblin_batedeiro"    : GOBLIN_BATEDEIRO,
    "lobo_da_floresta"    : LOBO_DA_FLORESTA,
    "esqueleto_guerreiro" : ESQUELETO_GUERREIRO,
    "troll_das_pedras"    : TROLL_DAS_PEDRAS,
    "mago_renegado"       : MAGO_RENEGADO,
    "elemental_de_pedra"  : ELEMENTAL_DE_PEDRA,
    "senhor_das_sombras"  : SENHOR_DAS_SOMBRAS,
}


def obter_inimigo(chave: str) -> Inimigo:
    if chave not in CATALOGO_INIMIGOS:
        raise KeyError(f"Inimigo '{chave}' não encontrado.")
    clone = CATALOGO_INIMIGOS[chave].clonar()
    clone._chave = chave
    return clone


# ══════════════════════════════════════════════════════════════
#  GERADOR PROCEDURAL
# ══════════════════════════════════════════════════════════════

def gerar_inimigo_procedural(nivel_jogador: int, tipo: Optional[str] = None,
                              biome_tier: int = 1) -> Inimigo:
    """
    Gera um inimigo escalado ao tier do bioma atual.
    biome_tier 1-11 controla PV/dano/defesa base.
    nivel_jogador adiciona variação aleatória menor.
    """
    tipos = ["humanoide", "besta", "arcano", "morto-vivo", "elemental"]
    tipo_escolhido = tipo if tipo in tipos else random.choice(tipos)

    nomes_por_tipo = {
        "humanoide" : ["Bandido Corrupto", "Mercenário", "Saqueador", "Assassino", "Guarda Desonesto"],
        "besta"     : ["Urso Selvagem", "Jacaré Gigante", "Pantera Noturna", "Lobo Alfa", "Serpente Colossal"],
        "arcano"    : ["Construct Arcano", "Guardião Rúnico", "Sombra Errante", "Espectro Arcano", "Golem Menor"],
        "morto-vivo": ["Zumbi Antigo", "Espectro", "Vampiro Menor", "Esqueleto Errante", "Lich Menor"],
        "elemental" : ["Elemental de Fogo", "Elemental de Gelo", "Vórtice Arcano", "Golem de Pedra", "Elemental de Trovão"],
    }

    # Base stats scale with biome tier (starts gentle, grows with tier)
    tf = 1.0 + (biome_tier - 1) * 0.40
    base_pv  = round(75  * (tf ** 1.6) + random.uniform(-10, 20), 0)
    base_dmg = round(5   * (tf ** 1.3) + random.uniform(-1,  2),  1)
    base_def = round(max(1, (biome_tier - 1) * 0.8) + random.uniform(0, 1), 1)

    nome = random.choice(nomes_por_tipo.get(tipo_escolhido, ["Criatura Desconhecida"]))
    nome = f"{nome} (T{biome_tier})"

    ini = Inimigo(
        nome=nome,
        tipo=tipo_escolhido,
        nivel=nivel_jogador,
        pv_max=max(50, base_pv),
        defesa=max(1, base_def),
        dano_base=max(5, base_dmg),
        tipo_defesa=random.choice(["fisica", "arcana", "natural", "espiritual"]),
        fraquezas=random.sample(["fogo", "luz", "acido", "arcano", "fisica"], k=random.randint(1, 2)),
        resistencias=[],
        descricao=f"Criatura do bioma tier {biome_tier}.",
        xp=int(15 * tf),
        ouro=int(8 * tf),
    )
    ini._chave = tipo_escolhido.replace('-', '_').replace(' ', '_')
    return ini



# ══════════════════════════════════════════════════════════════
#  FOLCLORE BRASILEIRO — Novos Inimigos
# ══════════════════════════════════════════════════════════════

# ── Fauna brasileira base ─────────────────────────────────────

CAPIVARA = Inimigo(
    nome="Capivara", name_en="Capybara",
    tipo="besta", nivel=1,
    pv_max=120.0, defesa=2.0, dano_base=6.0,
    tipo_defesa="natural", fraquezas=["fogo"],
    descricao="O maior roedor do mundo. Defensiva mas poderosa quando acuada.",
    xp=18, ouro=3,
    loot_possivel=[("ervas_medicinais", 0.35)],
)

CAPIVARA_FANTASMA = Inimigo(
    nome="Capivara Fantasma", name_en="Ghost Capybara",
    tipo="morto-vivo", nivel=2,
    pv_max=160.0, defesa=4.0, dano_base=12.0,
    tipo_defesa="espiritual", fraquezas=["luz", "fogo"],
    descricao="Espectro de capivara errante entre o mundo dos vivos e dos mortos.",
    xp=40, ouro=8,
    loot_possivel=[("amuleto_protetor", 0.25), ("pocao_cura", 0.3)],
)

CUTIA = Inimigo(
    nome="Cutia", name_en="Agouti",
    tipo="besta", nivel=1,
    pv_max=60.0, defesa=1.0, dano_base=5.0,
    tipo_defesa="natural", fraquezas=["fogo"],
    descricao="Roedor ágil de dentes afiados. Ataca em grupos e some na mata.",
    xp=12, ouro=2,
    loot_possivel=[("ervas_medicinais", 0.2)],
)

ARARA_GUERREIRA = Inimigo(
    nome="Arara Guerreira", name_en="Warrior Macaw",
    tipo="besta", nivel=2,
    pv_max=110.0, defesa=3.0, dano_base=11.0,
    tipo_defesa="natural", fraquezas=["frio"],
    descricao="Arara de plumagem carmesim que ataca com bico e garras afiadas.",
    xp=30, ouro=5,
    loot_possivel=[("arco_simples", 0.15)],
)

ARARA_ARCANA = Inimigo(
    nome="Arara Arcana", name_en="Arcane Macaw",
    tipo="arcano", nivel=3,
    pv_max=155.0, defesa=5.0, dano_base=16.0,
    tipo_defesa="arcana", fraquezas=["fisica"],
    descricao="Arara imbuída de energia arcana. Seus gritos lançam magia caótica.",
    xp=55, ouro=12,
    loot_possivel=[("anel_do_estudioso", 0.2)],
)

JACARA = Inimigo(
    nome="Jacaré", name_en="Caiman",
    tipo="besta", nivel=2,
    pv_max=200.0, defesa=8.0, dano_base=14.0,
    tipo_defesa="natural", fraquezas=["arcano", "fogo"],
    resistencias=["fisica"],
    descricao="Réptil couraçado do pantanal. Defesa natural poderosa.",
    xp=45, ouro=8,
    loot_possivel=[("armadura_couro", 0.2), ("pocao_cura", 0.25)],
)

JACARA_SOMBRIO = Inimigo(
    nome="Jacaré Sombrio", name_en="Shadow Caiman",
    tipo="arcano", nivel=3,
    pv_max=260.0, defesa=10.0, dano_base=20.0,
    tipo_defesa="arcana", fraquezas=["luz"],
    resistencias=["fisica", "natural"],
    descricao="Jacaré corrompido pela sombra das ruínas. Morde com veneno arcano.",
    xp=80, ouro=18,
    loot_possivel=[("escudo_madeira", 0.2), ("anel_do_estudioso", 0.15)],
)

GIBOIA = Inimigo(
    nome="Giboia", name_en="Boa Constrictor",
    tipo="besta", nivel=2,
    pv_max=180.0, defesa=5.0, dano_base=13.0,
    tipo_defesa="natural", fraquezas=["fogo", "frio"],
    descricao="Serpente constritora da floresta amazônica. Imobiliza a presa.",
    xp=38, ouro=6,
    loot_possivel=[("amuleto_protetor", 0.2)],
)

GIBOIA_VENENOSA = Inimigo(
    nome="Giboia Venenosa", name_en="Venomous Boa",
    tipo="besta", nivel=3,
    pv_max=230.0, defesa=6.0, dano_base=18.0,
    tipo_defesa="natural", fraquezas=["fogo"],
    descricao="Giboia com veneno paralisante. Cada mordida drena Psiquê.",
    xp=65, ouro=14,
    loot_possivel=[("ervas_medicinais", 0.4), ("pocao_cura", 0.3)],
)

# ── Folclore brasileiro — Criaturas ──────────────────────────

CAIPORA = Inimigo(
    nome="Caipora", name_en="Caipora",
    tipo="arcano", nivel=3,
    pv_max=220.0, defesa=7.0, dano_base=17.0,
    tipo_defesa="natural", fraquezas=["fogo", "conhecimento_antigo"],
    resistencias=["fisica"],
    descricao=(
        "Protetora das matas, pequena e selvagem. Monta em um porco selvagem "
        "e usa fumo como arma. Desorienta com ilusões."
    ),
    xp=75, ouro=20,
    loot_possivel=[("ervas_medicinais", 0.5), ("amuleto_protetor", 0.25)],
)

CAIPORA_DA_VARZEA = Inimigo(
    nome="Caipora da Várzea", name_en="Floodplain Caipora",
    tipo="arcano", nivel=4,
    pv_max=300.0, defesa=9.0, dano_base=22.0,
    tipo_defesa="natural", fraquezas=["fogo"],
    descricao="Caipora das terras alagadas. Comanda as feras do pantanal.",
    xp=110, ouro=30,
    loot_possivel=[("cachimbo_caipora", 0.15), ("ervas_medicinais", 0.4)],
)

CURUPIRA = Inimigo(
    nome="Curupira", name_en="Curupira",
    tipo="arcano", nivel=2,
    pv_max=170.0, defesa=5.0, dano_base=14.0,
    tipo_defesa="natural", fraquezas=["fogo"],
    resistencias=["fisica"],
    descricao=(
        "Guardião da floresta de pés virados para trás. "
        "Cria trilhas falsas e desorenta caçadores."
    ),
    xp=55, ouro=15,
    loot_possivel=[("ervas_medicinais", 0.5)],
)

CURUPIRA_ANCESTRAL = Inimigo(
    nome="Curupira Ancestral", name_en="Ancestral Curupira",
    tipo="arcano", nivel=4,
    pv_max=320.0, defesa=10.0, dano_base=24.0,
    tipo_defesa="natural", fraquezas=["fogo", "conhecimento_antigo"],
    descricao="Curupira de poderes ampliados. Senhor de toda floresta virgem.",
    xp=130, ouro=40,
    loot_possivel=[("pe_virado_curupira", 0.2), ("anel_do_estudioso", 0.2)],
)

MULA_SEM_CABECA = Inimigo(
    nome="Mula Sem Cabeça", name_en="Headless Mule",
    tipo="morto-vivo", nivel=4,
    pv_max=380.0, defesa=12.0, dano_base=26.0,
    tipo_defesa="espiritual", fraquezas=["luz", "fogo"],
    resistencias=["fisica"],
    descricao=(
        "Mulher amaldiçoada transformada em mula que corre cuspindo fogo. "
        "Aparece às sextas-feiras entre igrejas."
    ),
    xp=140, ouro=35,
    loot_possivel=[("ferradura_amaldicoada", 0.15), ("pocao_cura", 0.35)],
)

SACI_PERERE = Inimigo(
    nome="Saci-Pererê", name_en="Saci-Perere",
    tipo="arcano", nivel=2,
    pv_max=130.0, defesa=3.0, dano_base=13.0,
    tipo_defesa="arcana", fraquezas=["agua"],
    resistencias=["fisica"],
    descricao=(
        "Menino de uma perna só com gorro vermelho mágico. "
        "Teleporta, cria redemoinhos e prega peças."
    ),
    xp=50, ouro=12,
    loot_possivel=[("ervas_medicinais", 0.3), ("pocao_cura", 0.25)],
)

BOTO_COR_DE_ROSA = Inimigo(
    nome="Boto Cor-de-Rosa", name_en="Pink River Dolphin",
    tipo="arcano", nivel=3,
    pv_max=240.0, defesa=6.0, dano_base=16.0,
    tipo_defesa="arcana", fraquezas=["fogo", "conhecimento_antigo"],
    descricao=(
        "Boto encantado que se transforma em homem galante. "
        "Usa sedução e magia da água para confundir."
    ),
    xp=80, ouro=22,
    loot_possivel=[("anel_do_estudioso", 0.2), ("amuleto_protetor", 0.2)],
)

IARA = Inimigo(
    nome="Iara", name_en="Iara",
    tipo="arcano", nivel=4,
    pv_max=300.0, defesa=8.0, dano_base=22.0,
    tipo_defesa="arcana", fraquezas=["fogo"],
    resistencias=["agua", "fisica"],
    descricao=(
        "Sereia dos rios amazônicos. Canto hipnótico drena Psiquê. "
        "Meia mulher, meia peixe, completamente letal."
    ),
    xp=120, ouro=38,
    loot_possivel=[("cajado_arcano", 0.2), ("anel_do_estudioso", 0.25)],
)

MAPINGUARI = Inimigo(
    nome="Mapinguari", name_en="Mapinguari",
    tipo="besta", nivel=4,
    pv_max=420.0, defesa=14.0, dano_base=28.0,
    tipo_defesa="natural", fraquezas=["fogo", "arcano"],
    resistencias=["fisica"],
    descricao=(
        "Gigante peludo e fétido da Amazônia. Boca no ventre, garra invencível. "
        "Possível preguiça-gigante sobrevivente."
    ),
    xp=160, ouro=45,
    loot_possivel=[("armadura_couro", 0.25), ("amuleto_protetor", 0.2)],
)

PISADEIRA = Inimigo(
    nome="Pisadeira", name_en="Pisadeira",
    tipo="morto-vivo", nivel=3,
    pv_max=200.0, defesa=6.0, dano_base=18.0,
    tipo_defesa="espiritual", fraquezas=["luz"],
    descricao=(
        "Velha de unhas longas que senta no peito de quem dorme de barriga cheia. "
        "Causa paralisia e drena Psiquê."
    ),
    xp=70, ouro=16,
    loot_possivel=[("pocao_cura", 0.4), ("amuleto_protetor", 0.2)],
)

ANHANGA = Inimigo(
    nome="Anhangá", name_en="Anhanga",
    tipo="morto-vivo", nivel=3,
    pv_max=210.0, defesa=7.0, dano_base=19.0,
    tipo_defesa="espiritual", fraquezas=["luz", "fogo"],
    descricao=(
        "Espírito protetor da caça que pune quem mata sem necessidade. "
        "Assume forma de veado com fogo nos olhos."
    ),
    xp=75, ouro=18,
    loot_possivel=[("amuleto_protetor", 0.3)],
)

# ── BOSSES — Folclore Brasileiro ─────────────────────────────

BOI_TATA = Inimigo(
    nome="Boi Tatá", name_en="Boi Tata",
    tipo="elemental", nivel=5,
    pv_max=0.0,  # override by BOSS_STATS
    defesa=0.0,
    dano_base=0.0,
    tipo_defesa="espiritual", fraquezas=["agua", "conhecimento_antigo"],
    resistencias=["fisica", "fogo"],
    descricao=(
        "Serpente de fogo que protege os campos. Seu olhar de brasa cega permanentemente. "
        "Diz-se que nasceu de uma criança abandonada nas águas."
    ),
    xp=350, ouro=100,
    loot_possivel=[("olho_boi_tata", 1.0)],
)

LOBISOMEM = Inimigo(
    nome="Lobisomem", name_en="Werewolf",
    tipo="morto-vivo", nivel=5,
    pv_max=0.0,
    defesa=0.0,
    dano_base=0.0,
    tipo_defesa="natural", fraquezas=["luz", "prata"],
    resistencias=["fisica"],
    descricao=(
        "Sétimo filho homem amaldiçoado que se transforma em lobo às sextas-feiras. "
        "Regenera rapidamente e ataca com fúria incontrolável."
    ),
    xp=380, ouro=110,
    loot_possivel=[("garra_lobisomem", 1.0)],
)

DRAGAO_SOMBRIO = Inimigo(
    nome="Dragão Sombrio", name_en="Shadow Dragon",
    tipo="arcano", nivel=6,
    pv_max=0.0,
    defesa=0.0,
    dano_base=0.0,
    tipo_defesa="arcana", fraquezas=["luz", "conhecimento_antigo"],
    resistencias=["fisica", "fogo", "frio"],
    descricao=(
        "Dragão nascido da sombra das ruínas arcanas brasileiras. "
        "Sopra sombra corrosiva que drena Psiquê."
    ),
    xp=450, ouro=150,
    loot_possivel=[("escama_dragao_sombrio", 1.0)],
)

CAIPORA_BOSS = Inimigo(
    nome="Grande Caipora", name_en="Great Caipora",
    tipo="arcano", nivel=5,
    pv_max=0.0,
    defesa=0.0,
    dano_base=0.0,
    tipo_defesa="natural", fraquezas=["fogo"],
    resistencias=["fisica", "natural"],
    descricao=(
        "A Caipora em sua forma ancestral, senhora de toda a mata virgem. "
        "Comanda hordas de animais e dissolve-se na floresta."
    ),
    xp=360, ouro=120,
    loot_possivel=[("cachimbo_caipora", 1.0)],
)

CURUPIRA_BOSS = Inimigo(
    nome="Curupira Primordial", name_en="Primordial Curupira",
    tipo="arcano", nivel=5,
    pv_max=0.0,
    defesa=0.0,
    dano_base=0.0,
    tipo_defesa="natural", fraquezas=["fogo", "conhecimento_antigo"],
    resistencias=["fisica", "natural"],
    descricao=(
        "O primeiro Curupira, guardião das florestas desde os tempos imemoriais. "
        "Seus pés criam labirintos intransponíveis."
    ),
    xp=360, ouro=120,
    loot_possivel=[("pe_virado_curupira", 1.0)],
)

MULA_BOSS = Inimigo(
    nome="Mula Sem Cabeça Furiosa", name_en="Furious Headless Mule",
    tipo="morto-vivo", nivel=5,
    pv_max=0.0,
    defesa=0.0,
    dano_base=0.0,
    tipo_defesa="espiritual", fraquezas=["luz", "fogo"],
    resistencias=["fisica"],
    descricao=(
        "A maldição em sua forma mais furiosa. Corre entre igrejas lançando "
        "chamas e destruindo tudo pelo caminho."
    ),
    xp=370, ouro=115,
    loot_possivel=[("ferradura_amaldicoada", 1.0)],
)

# Adicionar ao catálogo
CATALOGO_INIMIGOS.update({
    # Fauna
    "capivara"              : CAPIVARA,
    "capivara_fantasma"     : CAPIVARA_FANTASMA,
    "cutia"                 : CUTIA,
    "arara_guerreira"       : ARARA_GUERREIRA,
    "arara_arcana"          : ARARA_ARCANA,
    "jacara"                : JACARA,
    "jacara_sombrio"        : JACARA_SOMBRIO,
    "giboia"                : GIBOIA,
    "giboia_venenosa"       : GIBOIA_VENENOSA,
    # Folclore
    "caipora"               : CAIPORA,
    "caipora_da_varzea"     : CAIPORA_DA_VARZEA,
    "curupira"              : CURUPIRA,
    "curupira_ancestral"    : CURUPIRA_ANCESTRAL,
    "mula_sem_cabeca"       : MULA_SEM_CABECA,
    "saci_perere"           : SACI_PERERE,
    "boto_cor_de_rosa"      : BOTO_COR_DE_ROSA,
    "iara"                  : IARA,
    "mapinguari"            : MAPINGUARI,
    "pisadeira"             : PISADEIRA,
    "anhanga"               : ANHANGA,
    # Bosses
    "boi_tata"              : BOI_TATA,
    "lobisomem"             : LOBISOMEM,
    "dragao_sombrio"        : DRAGAO_SOMBRIO,
    "caipora_boss"          : CAIPORA_BOSS,
    "curupira_boss"         : CURUPIRA_BOSS,
    "mula_boss"             : MULA_BOSS,
})


# ══════════════════════════════════════════════════════════════
#  INIMIGOS RESTANTES (reintegrados ao catálogo)
# ══════════════════════════════════════════════════════════════

ELEMENTAL_AREIA = Inimigo(
    nome="Elemental de Areia", name_en="Sand Elemental",
    tipo="elemental", nivel=2,
    pv_max=140.0, defesa=3.0, dano_base=9.0,
    tipo_defesa="natural", fraquezas=["agua", "arcano"],
    resistencias=["fisica", "fogo"],
    descricao="Espiral de areia animada por energia elementar. Abraça e sufoca.",
    xp=40, ouro=8,
    loot_possivel=[("amuleto_protetor", 0.2)],
)

ESCORPIAO_GIGANTE = Inimigo(
    nome="Escorpião Gigante", name_en="Giant Scorpion",
    tipo="besta", nivel=2,
    pv_max=160.0, defesa=5.0, dano_base=11.0,
    tipo_defesa="natural", fraquezas=["fogo", "arcano"],
    resistencias=["fisica"],
    descricao="Escorpião de carapaça blindada. Ferrão com veneno paralisante.",
    xp=45, ouro=10,
    loot_possivel=[("ervas_medicinais", 0.3)],
)

AGUIA_DAS_NEVES = Inimigo(
    nome="Águia das Neves", name_en="Snow Eagle",
    tipo="besta", nivel=2,
    pv_max=130.0, defesa=4.0, dano_base=13.0,
    tipo_defesa="natural", fraquezas=["fogo", "arcano"],
    descricao="Rapina de asas brancas dos picos eternos. Mergulha em alta velocidade.",
    xp=35, ouro=6,
    loot_possivel=[("arco_simples", 0.15)],
)

URSO_DAS_PEDRAS = Inimigo(
    nome="Urso das Pedras", name_en="Stone Bear",
    tipo="besta", nivel=2,
    pv_max=200.0, defesa=7.0, dano_base=15.0,
    tipo_defesa="natural", fraquezas=["fogo", "arcano"],
    resistencias=["fisica"],
    descricao="Urso de pelagem pétrea adaptado às altitudes. Abraço esmagador.",
    xp=55, ouro=12,
    loot_possivel=[("amuleto_protetor", 0.2)],
)

FUNGO_PARASITA = Inimigo(
    nome="Fungo Parasita", name_en="Parasite Fungus",
    tipo="arcano", nivel=1,
    pv_max=80.0, defesa=1.0, dano_base=6.0,
    tipo_defesa="arcana", fraquezas=["fogo", "luz"],
    descricao="Fungo que controla hospedeiros. Libera esporos que drenam Psiquê.",
    xp=20, ouro=3,
    loot_possivel=[("ervas_medicinais", 0.4)],
)

CONSTRUCT_DE_PEDRA = Inimigo(
    nome="Construct de Pedra", name_en="Stone Construct",
    tipo="arcano", nivel=2,
    pv_max=180.0, defesa=8.0, dano_base=9.0,
    tipo_defesa="arcana", fraquezas=["acido", "arcano"],
    resistencias=["fisica"],
    descricao="Golem primitivo criado por magia antiga. Lento mas destrutivo.",
    xp=45, ouro=8,
    loot_possivel=[("escudo_madeira", 0.2)],
)

SOMBRA_ERRANTE = Inimigo(
    nome="Sombra Errante", name_en="Wandering Shadow",
    tipo="arcano", nivel=2,
    pv_max=110.0, defesa=3.0, dano_base=11.0,
    tipo_defesa="espiritual", fraquezas=["luz", "fogo"],
    resistencias=["fisica"],
    descricao="Sombra sem dono que vaga pelas ruínas. Drena calor e Psiquê.",
    xp=40, ouro=10,
    loot_possivel=[("amuleto_protetor", 0.25)],
)

GOLEM_ARCANO = Inimigo(
    nome="Golem Arcano", name_en="Arcane Golem",
    tipo="arcano", nivel=3,
    pv_max=260.0, defesa=10.0, dano_base=13.0,
    tipo_defesa="arcana", fraquezas=["acido", "conhecimento_antigo"],
    resistencias=["fisica", "fogo"],
    descricao="Golem de cristal arcano. Reflete feitiços menores de volta ao conjurador.",
    xp=85, ouro=20,
    loot_possivel=[("anel_do_estudioso", 0.15)],
)

SAQUEADOR_CORRUPTO = Inimigo(
    nome="Saqueador Corrupto", name_en="Corrupt Raider",
    tipo="humanoide", nivel=1,
    pv_max=90.0, defesa=1.0, dano_base=7.0,
    tipo_defesa="fisica", fraquezas=["luz", "arcano"],
    descricao="Ladrão corrompido por riqueza proibida. Ataca em bando, foge sozinho.",
    xp=20, ouro=15,
    loot_possivel=[("faca_enferrujada", 0.4), ("pocao_cura", 0.2)],
)

GUARDA_FANTASMA = Inimigo(
    nome="Guarda Fantasma", name_en="Ghost Guard",
    tipo="morto-vivo", nivel=2,
    pv_max=150.0, defesa=4.0, dano_base=9.0,
    tipo_defesa="espiritual", fraquezas=["luz", "conhecimento_antigo"],
    resistencias=["fisica"],
    descricao="Guarda morto ainda em serviço eterno. Protege ruínas com lança espectral.",
    xp=45, ouro=12,
    loot_possivel=[("escudo_madeira", 0.15), ("amuleto_protetor", 0.15)],
)

AUTOMATO_SENTINELA = Inimigo(
    nome="Autômato Sentinela", name_en="Sentinel Automaton",
    tipo="arcano", nivel=2,
    pv_max=160.0, defesa=6.0, dano_base=10.0,
    tipo_defesa="arcana", fraquezas=["acido", "eletrico"],
    resistencias=["fisica", "fogo"],
    descricao="Robô guardião de instalação tecno-arcana. Dispara raios de energia.",
    xp=50, ouro=15,
    loot_possivel=[("amuleto_protetor", 0.2)],
)

DRON_DE_VIGILANCIA = Inimigo(
    nome="Drone de Vigilância", name_en="Surveillance Drone",
    tipo="arcano", nivel=1,
    pv_max=70.0, defesa=2.0, dano_base=6.0,
    tipo_defesa="arcana", fraquezas=["acido", "eletrico"],
    descricao="Drone voador de monitoramento. Pequeno mas veloz e preciso.",
    xp=18, ouro=8,
    loot_possivel=[],
)

ENGENHEIRO_RENEGADO = Inimigo(
    nome="Engenheiro Renegado", name_en="Renegade Engineer",
    tipo="humanoide", nivel=1,
    pv_max=95.0, defesa=1.0, dano_base=8.0,
    tipo_defesa="fisica", fraquezas=["arcano"],
    descricao="Engenheiro tecno-arcano que abandonou seus ideais. Usa gadgets perigosos.",
    xp=25, ouro=20,
    loot_possivel=[("pocao_cura", 0.25)],
)

APRENDIZ_CORROMPIDO = Inimigo(
    nome="Aprendiz Corrompido", name_en="Corrupt Apprentice",
    tipo="humanoide", nivel=2,
    pv_max=120.0, defesa=1.0, dano_base=10.0,
    tipo_defesa="arcana", fraquezas=["fisica", "luz"],
    resistencias=["arcana"],
    descricao="Mago iniciante corrompido pelo poder proibido. Lança feitiços instáveis.",
    xp=40, ouro=15,
    loot_possivel=[("cajado_arcano", 0.1), ("anel_do_estudioso", 0.15)],
)

ELEMENTAL_ARCANO = Inimigo(
    nome="Elemental Arcano", name_en="Arcane Elemental",
    tipo="elemental", nivel=2,
    pv_max=140.0, defesa=3.0, dano_base=11.0,
    tipo_defesa="arcana", fraquezas=["fisica", "antimagia"],
    resistencias=["arcana", "fogo", "frio"],
    descricao="Puro energia arcana condensada em forma. Instável e imprevisível.",
    xp=55, ouro=18,
    loot_possivel=[("anel_do_estudioso", 0.2)],
)

INQUISIDOR_FERVOROSO = Inimigo(
    nome="Inquisidor Fervoroso", name_en="Zealous Inquisitor",
    tipo="humanoide", nivel=2,
    pv_max=145.0, defesa=5.0, dano_base=11.0,
    tipo_defesa="espiritual", fraquezas=["arcano", "sombra"],
    resistencias=["luz"],
    descricao="Paladino fanático que caça o sobrenatural. Usa fogo sagrado.",
    xp=55, ouro=20,
    loot_possivel=[("amuleto_protetor", 0.2)],
)

PALADINO_CAIDO = Inimigo(
    nome="Paladino Caído", name_en="Fallen Paladin",
    tipo="humanoide", nivel=3,
    pv_max=220.0, defesa=7.0, dano_base=14.0,
    tipo_defesa="espiritual", fraquezas=["luz", "conhecimento_antigo"],
    descricao="Paladino que abandonou seus votos. Poder sem propósito — perigoso.",
    xp=80, ouro=30,
    loot_possivel=[("escudo_madeira", 0.25), ("amuleto_protetor", 0.2)],
)

MAQUINA_DE_GUERRA = Inimigo(
    nome="Máquina de Guerra", name_en="War Machine",
    tipo="arcano", nivel=3,
    pv_max=270.0, defesa=9.0, dano_base=16.0,
    tipo_defesa="arcana", fraquezas=["acido", "eletrico"],
    resistencias=["fisica", "fogo"],
    descricao="Colosso mecânico de guerra. Lento, maciço, devastador.",
    xp=90, ouro=35,
    loot_possivel=[("armadura_couro", 0.2)],
)

CATALOGO_INIMIGOS.update({
    "elemental_areia"       : ELEMENTAL_AREIA,
    "escorpiao_gigante"     : ESCORPIAO_GIGANTE,
    "aguia_das_neves"       : AGUIA_DAS_NEVES,
    "urso_das_pedras"       : URSO_DAS_PEDRAS,
    "fungo_parasita"        : FUNGO_PARASITA,
    "construct_de_pedra"    : CONSTRUCT_DE_PEDRA,
    "sombra_errante"        : SOMBRA_ERRANTE,
    "golem_arcano"          : GOLEM_ARCANO,
    "saqueador_corrupto"    : SAQUEADOR_CORRUPTO,
    "guarda_fantasma"       : GUARDA_FANTASMA,
    "automato_sentinela"    : AUTOMATO_SENTINELA,
    "dron_de_vigilancia"    : DRON_DE_VIGILANCIA,
    "engenheiro_renegado"   : ENGENHEIRO_RENEGADO,
    "aprendiz_corrompido"   : APRENDIZ_CORROMPIDO,
    "elemental_arcano"      : ELEMENTAL_ARCANO,
    "inquisidor_fervoroso"  : INQUISIDOR_FERVOROSO,
    "paladino_caido"        : PALADINO_CAIDO,
    "maquina_de_guerra"     : MAQUINA_DE_GUERRA,
})



ZUMBI_DO_PANTANO = Inimigo(
    nome="Zumbi do Pântano", name_en="Swamp Zombie",
    tipo="morto-vivo", nivel=1,
    pv_max=110.0, defesa=1.0, dano_base=7.0,
    tipo_defesa="espiritual", fraquezas=["luz", "fogo"],
    descricao="Cadáver reanimado pelas águas pútridas do pântano. Lento e persistente.",
    xp=22, ouro=4,
    loot_possivel=[("ervas_medicinais", 0.3), ("pocao_cura", 0.2)],
)
CATALOGO_INIMIGOS["zumbi_do_pantano"] = ZUMBI_DO_PANTANO


# ══════════════════════════════════════════════════════════════
#  ATAQUES ESPECIAIS — aplicados após criação do catálogo
# ══════════════════════════════════════════════════════════════

def _add_attacks(chave: str, ataques: list):
    """Adiciona ataques especiais a um inimigo do catálogo."""
    if chave in CATALOGO_INIMIGOS:
        CATALOGO_INIMIGOS[chave].ataques_especiais = ataques

# ── Fauna brasileira ──────────────────────────────────────────
_add_attacks("capivara", [
    {"nome": "Chafurdada", "dano_mult": 1.3,
     "efeito": "paralisar",
     "descricao": "Arremessa toda a massa corporal!", "chance": 0.30},
    {"nome": "Mordida de Defesa", "dano_mult": 1.5,
     "efeito": "sangrar",
     "descricao": "Morde com força desesperada.", "chance": 0.25},
])

_add_attacks("capivara_fantasma", [
    {"nome": "Uivo Espectral", "dano_mult": 0.8,
     "efeito": "drenar_psique",
     "descricao": "Grito que congela a alma.", "chance": 0.40},
    {"nome": "Mordida Sombria", "dano_mult": 1.6,
     "efeito": "sangrar",
     "descricao": "Dentes etéreos rasgam corpo e espírito.", "chance": 0.25},
])

_add_attacks("jacara", [
    {"nome": "Cauda Devastadora", "dano_mult": 1.4,
     "efeito": "paralisar",
     "descricao": "Golpe de cauda que derruba!", "chance": 0.35},
    {"nome": "Mordida Colossal", "dano_mult": 2.0,
     "efeito": "sangrar",
     "descricao": "Trinca ossos com pressão brutal.", "chance": 0.20},
])

_add_attacks("jacara_sombrio", [
    {"nome": "Mordida Venenosa", "dano_mult": 1.5,
     "efeito": "drenar_psique",
     "descricao": "Veneno arcano corrói a mente.", "chance": 0.35},
    {"nome": "Cauda das Sombras", "dano_mult": 1.8,
     "efeito": "confundir",
     "descricao": "Golpe que cria ilusões de trevas.", "chance": 0.25},
    {"nome": "Mergulho Sombrio", "dano_mult": 2.2,
     "efeito": "sangrar",
     "descricao": "Emerge das sombras em ataque fulminante!", "chance": 0.15},
])

_add_attacks("giboia", [
    {"nome": "Constrição", "dano_mult": 1.6,
     "efeito": "paralisar",
     "descricao": "Enrola e aperta — impossível se mover.", "chance": 0.35},
    {"nome": "Bote Relâmpago", "dano_mult": 1.8,
     "efeito": "sangrar",
     "descricao": "Boca rasgando em velocidade máxima.", "chance": 0.25},
])

_add_attacks("giboia_venenosa", [
    {"nome": "Veneno Paralisante", "dano_mult": 1.2,
     "efeito": "paralisar",
     "descricao": "Paralisa membros em segundos.", "chance": 0.40},
    {"nome": "Constrição Fatal", "dano_mult": 2.0,
     "efeito": "drenar_psique",
     "descricao": "Aperta até o desespero total.", "chance": 0.25},
    {"nome": "Bote Venenoso", "dano_mult": 1.5,
     "efeito": "sangrar",
     "descricao": "Inocula veneno hemorrágico.", "chance": 0.30},
])

_add_attacks("arara_guerreira", [
    {"nome": "Bico Perfurante", "dano_mult": 1.6,
     "efeito": "sangrar",
     "descricao": "Bico como lança atravessa armaduras.", "chance": 0.30},
    {"nome": "Grito de Guerra", "dano_mult": 0.5,
     "efeito": "confundir",
     "descricao": "Grito ensurdecedor desorienta completamente.", "chance": 0.35},
])

_add_attacks("arara_arcana", [
    {"nome": "Pluma Arcana", "dano_mult": 1.4,
     "efeito": "drenar_psique",
     "descricao": "Penas imbuídas de magia roubam concentração.", "chance": 0.35},
    {"nome": "Grito Caótico", "dano_mult": 1.2,
     "efeito": "confundir",
     "descricao": "Onda arcana embaralha os sentidos.", "chance": 0.30},
    {"nome": "Mergulho Arcano", "dano_mult": 2.0,
     "efeito": "sangrar",
     "descricao": "Ataque em picada com energia arcana máxima!", "chance": 0.15},
])

# ── Folclore ──────────────────────────────────────────────────
_add_attacks("caipora", [
    {"nome": "Ilusão da Mata", "dano_mult": 0.6,
     "efeito": "confundir",
     "descricao": "Cria trilhas falsas — você ataca o vazio.", "chance": 0.45},
    {"nome": "Fumo Mágico", "dano_mult": 1.0,
     "efeito": "drenar_psique",
     "descricao": "Baforada de fumo enfraquece a mente.", "chance": 0.30},
])

_add_attacks("caipora_da_varzea", [
    {"nome": "Chamado das Feras", "dano_mult": 1.5,
     "efeito": "paralisar",
     "descricao": "Invoca ataques simultâneos de jacarés!", "chance": 0.35},
    {"nome": "Fumo da Várzea", "dano_mult": 1.0,
     "efeito": "drenar_psique",
     "descricao": "Fumo das plantas alagadas drena energia.", "chance": 0.30},
    {"nome": "Labirinto Aquático", "dano_mult": 0.8,
     "efeito": "confundir",
     "descricao": "Cria ilusões no reflexo da água.", "chance": 0.35},
])

_add_attacks("curupira", [
    {"nome": "Rastro Falso", "dano_mult": 0.5,
     "efeito": "confundir",
     "descricao": "Você perde o sentido — ataca a si mesmo!", "chance": 0.45},
    {"nome": "Pé Virado", "dano_mult": 1.4,
     "efeito": "paralisar",
     "descricao": "Pisão dos pés ao contrário desequilibra.", "chance": 0.30},
])

_add_attacks("curupira_ancestral", [
    {"nome": "Floresta Viva", "dano_mult": 1.8,
     "efeito": "paralisar",
     "descricao": "Raízes e galhos atacam por conta própria!", "chance": 0.35},
    {"nome": "Labirinto Eterno", "dano_mult": 0.6,
     "efeito": "confundir",
     "descricao": "Cria um labirinto de trilhas intransponível.", "chance": 0.40},
    {"nome": "Uivo da Floresta", "dano_mult": 1.2,
     "efeito": "drenar_psique",
     "descricao": "Grito que ecoa por toda a floresta primordial.", "chance": 0.25},
])

_add_attacks("mula_sem_cabeca", [
    {"nome": "Cuspe de Brasa", "dano_mult": 1.8,
     "efeito": "queimar",
     "descricao": "Chamas sem cabeça queimam tudo ao redor.", "chance": 0.35},
    {"nome": "Coice Espiritual", "dano_mult": 1.5,
     "efeito": "paralisar",
     "descricao": "Coice com força sobrenatural.", "chance": 0.30},
])

_add_attacks("saci_perere", [
    {"nome": "Redemoinho", "dano_mult": 1.3,
     "efeito": "confundir",
     "descricao": "Teleporta criando redemoinhos que desorientam.", "chance": 0.40},
    {"nome": "Perna de Pau", "dano_mult": 1.6,
     "efeito": "paralisar",
     "descricao": "Golpe surpresa com a perna de pau.", "chance": 0.30},
])

_add_attacks("boto_cor_de_rosa", [
    {"nome": "Canto Hipnótico", "dano_mult": 0.7,
     "efeito": "drenar_psique",
     "descricao": "Melodia encantada drena vontade e Psiquê.", "chance": 0.45},
    {"nome": "Magia das Águas", "dano_mult": 1.5,
     "efeito": "confundir",
     "descricao": "Ilusões aquáticas confundem os sentidos.", "chance": 0.30},
])

_add_attacks("iara", [
    {"nome": "Canto da Sereia", "dano_mult": 0.5,
     "efeito": "drenar_psique",
     "descricao": "Canto irresistível esvazia a mente completamente.", "chance": 0.50},
    {"nome": "Abraço das Águas", "dano_mult": 1.7,
     "efeito": "paralisar",
     "descricao": "Puxa para as profundezas do rio.", "chance": 0.30},
    {"nome": "Toque Encantado", "dano_mult": 1.2,
     "efeito": "confundir",
     "descricao": "Toque que faz esquecer quem você é.", "chance": 0.35},
])

_add_attacks("mapinguari", [
    {"nome": "Boca do Ventre", "dano_mult": 2.2,
     "efeito": "sangrar",
     "descricao": "A boca no ventre devora com força descomunal!", "chance": 0.30},
    {"nome": "Garra Invencível", "dano_mult": 1.8,
     "efeito": "paralisar",
     "descricao": "Garras que nenhuma armadura resiste.", "chance": 0.35},
    {"nome": "Fedor Paralisante", "dano_mult": 0.8,
     "efeito": "confundir",
     "descricao": "Odor nauseante que desabilita os sentidos.", "chance": 0.40},
])

_add_attacks("pisadeira", [
    {"nome": "Pesadelo", "dano_mult": 0.8,
     "efeito": "drenar_psique",
     "descricao": "Senta no peito — Psiquê despenca.", "chance": 0.50},
    {"nome": "Unhas Longas", "dano_mult": 1.6,
     "efeito": "sangrar",
     "descricao": "Arranha com unhas compridas e afiadas.", "chance": 0.30},
])

_add_attacks("anhanga", [
    {"nome": "Olhar de Fogo", "dano_mult": 1.3,
     "efeito": "queimar",
     "descricao": "Olhos flamejantes do veado espiritual.", "chance": 0.35},
    {"nome": "Maldição do Caçador", "dano_mult": 1.0,
     "efeito": "drenar_psique",
     "descricao": "Amaldiçoa quem mata sem necessidade.", "chance": 0.40},
])

# ── BOSSES ────────────────────────────────────────────────────
_add_attacks("boi_tata", [
    {"nome": "Olhar de Brasa", "dano_mult": 1.8,
     "efeito": "queimar",
     "descricao": "Olhar incandescente queima e cega permanentemente!", "chance": 0.40},
    {"nome": "Chamas Eternas", "dano_mult": 2.2,
     "efeito": "drenar_psique",
     "descricao": "Rio de fogo eterno devasta tudo!", "chance": 0.30},
    {"nome": "Investida Flamejante", "dano_mult": 2.5,
     "efeito": "sangrar",
     "descricao": "Corre em chamas — destruição total no caminho!", "chance": 0.20},
])

_add_attacks("lobisomem", [
    {"nome": "Uivo da Maldição", "dano_mult": 1.0,
     "efeito": "drenar_psique",
     "descricao": "Uivo que ressoa na alma e drena coragem.", "chance": 0.40},
    {"nome": "Fúria Selvagem", "dano_mult": 2.0,
     "efeito": "sangrar",
     "descricao": "Série de arranhões e mordidas imparáveis!", "chance": 0.35},
    {"nome": "Mordida da Maldição", "dano_mult": 2.5,
     "efeito": "paralisar",
     "descricao": "Morde com toda força da maldição lunar.", "chance": 0.20},
])

_add_attacks("dragao_sombrio", [
    {"nome": "Sopro Sombrio", "dano_mult": 2.0,
     "efeito": "drenar_psique",
     "descricao": "Sopro de sombra corrosiva que devora Psiquê!", "chance": 0.40},
    {"nome": "Garra das Trevas", "dano_mult": 1.8,
     "efeito": "sangrar",
     "descricao": "Garras sombrias que rasgam corpo e espírito.", "chance": 0.30},
    {"nome": "Voo das Sombras", "dano_mult": 2.8,
     "efeito": "confundir",
     "descricao": "Mergulho em alta velocidade das trevas totais!", "chance": 0.20},
])

_add_attacks("caipora_boss", [
    {"nome": "Horda da Mata", "dano_mult": 2.0,
     "efeito": "paralisar",
     "descricao": "Todos os animais da mata atacam juntos!", "chance": 0.35},
    {"nome": "Fumo Ancestral", "dano_mult": 1.2,
     "efeito": "drenar_psique",
     "descricao": "Fumo primordial esvazia a mente completamente.", "chance": 0.40},
    {"nome": "Labirinto da Mata Virgem", "dano_mult": 0.8,
     "efeito": "confundir",
     "descricao": "Labirinto impossível — você ataca o ar.", "chance": 0.40},
])

_add_attacks("curupira_boss", [
    {"nome": "Floresta Primordial", "dano_mult": 2.5,
     "efeito": "paralisar",
     "descricao": "A floresta toda ataca como um ser vivo!", "chance": 0.30},
    {"nome": "Pés do Início dos Tempos", "dano_mult": 1.5,
     "efeito": "confundir",
     "descricao": "Cria labirinto tão perfeito que é impossível sair.", "chance": 0.45},
    {"nome": "Uivo Primordial", "dano_mult": 1.8,
     "efeito": "drenar_psique",
     "descricao": "Grito que ressoa desde o início do mundo.", "chance": 0.30},
])

_add_attacks("mula_boss", [
    {"nome": "Rio de Fogo", "dano_mult": 2.3,
     "efeito": "queimar",
     "descricao": "Escarra chamas por quilômetros!", "chance": 0.35},
    {"nome": "Coice da Fúria", "dano_mult": 2.0,
     "efeito": "paralisar",
     "descricao": "Coice que parte pedra e osso!", "chance": 0.35},
    {"nome": "Galope Infernal", "dano_mult": 2.8,
     "efeito": "sangrar",
     "descricao": "Galopa em frenesi destruindo tudo no caminho!", "chance": 0.20},
])


def gerar_inimigo_rico(nivel_jogador: int, tipo: Optional[str] = None,
                        biome_tier: int = 1, bioma: str = "floresta",
                        usar_llm: bool = False) -> Inimigo:
    """
    Versão enriquecida de gerar_inimigo_procedural.
    Usa geracao_procedural.py para nome/descrição únicos via LLM.
    """
    ini = gerar_inimigo_procedural(nivel_jogador, tipo=tipo, biome_tier=biome_tier)
    try:
        from geracao_procedural import enriquecer_com_llm
        if usar_llm:
            enriquecer_com_llm(ini, bioma)
    except ImportError:
        pass
    ini._bioma_tipo = tipo or "besta"
    return ini
