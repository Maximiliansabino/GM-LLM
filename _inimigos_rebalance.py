"""
Rebalance script — patches CATALOGO_INIMIGOS with new stats
and rewrites gerar_inimigo_procedural to scale by biome order.

Biome progression (11 biomes, ordered):
  B1 floresta       → tier 1  (easy)
  B2 deserto        → tier 2
  B3 pantano        → tier 3
  B4 montanha       → tier 4
  B5 caverna        → tier 5
  B6 ruinas_arcanas → tier 6
  B7 cidade_antiga  → tier 7
  B8 cidade_robotica→ tier 8
  B9 cidade_magica  → tier 9
  B10 cidade_religiosa → tier 10
  B11 cidade_tecnologica → tier 11

Enemy stat scaling per tier:
  PV      = base_pv  * tier_factor^1.8
  dano    = base_dmg * tier_factor^1.4
  defesa  = base_def * tier_factor^1.2
where tier_factor = 1 + (tier-1) * 0.45
"""

import math

def tier_factor(tier: int) -> float:
    return 1.0 + (tier - 1) * 0.45

def scale(base, tier, exp):
    return round(base * (tier_factor(tier) ** exp), 1)

# Base stats for each enemy archetype
ARCHETYPES = {
    # key: (base_pv, base_dano, base_defesa, tipo, tier_nativo)
    "goblin_batedeiro":        (80,   8,  3, "humanoide", 1),
    "lobo_da_floresta":        (110, 10,  4, "besta",     1),
    "esqueleto_guerreiro":     (160, 13,  7, "morto-vivo",2),
    "troll_das_pedras":        (280, 18, 14, "besta",     2),
    "mago_renegado":           (220, 22,  6, "humanoide", 3),
    "elemental_de_pedra":      (380, 25, 22, "elemental", 3),
    "senhor_das_sombras":      (600, 32, 20, "arcano",    5),
    "elemental_areia":         (180, 14,  8, "elemental", 2),
    "escorpiao_gigante":       (210, 16, 11, "besta",     2),
    "zumbi_do_pantano":        (140, 10,  4, "morto-vivo",1),
    "aguia_das_neves":         (160, 15,  6, "besta",     2),
    "urso_das_pedras":         (260, 19, 12, "besta",     2),
    "gigante_de_gelo":         (500, 28, 18, "elemental", 4),
    "fungo_parasita":          (100,  9,  5, "arcano",    1),
    "construct_de_pedra":      (230, 14, 16, "arcano",    2),
    "golem_arcano":            (320, 20, 20, "arcano",    3),
    "sombra_errante":          (170, 17,  7, "arcano",    2),
    "guardiao_da_ruina":       (480, 26, 17, "arcano",    4),
    "saqueador_corrupto":      (120, 11,  5, "humanoide", 1),
    "guarda_fantasma":         (190, 13,  8, "morto-vivo",2),
    "rei_espectral":           (540, 27, 17, "morto-vivo",4),
    "automato_sentinela":      (200, 15, 14, "arcano",    2),
    "dron_de_vigilancia":      (90,  10,  6, "arcano",    1),
    "nucleo_central":          (560, 30, 20, "arcano",    4),
    "aprendiz_corrompido":     (150, 15,  5, "humanoide", 2),
    "elemental_arcano":        (170, 17,  7, "arcano",    2),
    "arquimago_cadente":       (450, 35, 10, "humanoide", 5),
    "inquisidor_fervoroso":    (180, 16, 10, "humanoide", 2),
    "paladino_caido":          (280, 21, 15, "humanoide", 3),
    "sumo_sacerdote_corrompido":(480, 28, 14,"humanoide", 4),
    "engenheiro_renegado":     (120, 12,  5, "humanoide", 1),
    "maquina_de_guerra":       (340, 23, 18, "arcano",    3),
    "protocolo_omega":         (520, 30, 18, "arcano",    4),
}

# Boss PV/dano/defesa by biome tier
BOSS_STATS = {
    1:  (350,  15,  4),
    2:  (600,  20,  7),
    3:  (900,  28, 10),
    4: (1400,  35, 13),
    5: (2000,  45, 15),
    6: (2800,  55, 18),
    7: (3800,  65, 22),
    8: (5000,  78, 26),
    9: (6500,  92, 30),
   10: (8500, 108, 34),
   11:(11000, 128, 40),
}

if __name__ == "__main__":
    # Print sample scaling
    for chave in ["goblin_batedeiro", "senhor_das_sombras", "arquimago_cadente"]:
        bp, bd, bdef, tipo, tier = ARCHETYPES[chave]
        print(f"{chave}: PV={bp} dano={bd} def={bdef} (tier {tier})")
    print()
    print("Boss progression:")
    for tier, (pv, dano, defesa) in BOSS_STATS.items():
        print(f"  Bioma {tier:2d}: PV={pv:5} dano={dano:3} def={defesa:3}")
