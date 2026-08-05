"""
biomas.py
─────────────────────────────────────────────────────────────
Define os biomas e orquestra o loop de 10 batalhas.

Estrutura por bioma:
  Batalha 1–4  → combate normal
  Batalha 5    → combate + evento NPC após
  Batalha 6–9  → combate normal
  Batalha 10   → BOSS

Após CADA batalha:
  → Painel pós-batalha: ver atributos e usar itens usáveis

Treinar / Dormir:
  → Disponível apenas nas batalhas múltiplas de FREQUENCIA_DESCANSO
    (padrão 3), exceto batalha 5 (NPC) e batalha 10 (boss).
─────────────────────────────────────────────────────────────
"""

import random
from typing import Dict
from i18n import t, name as iname, LANG

# Biome base difficulty — all biomes start at tier 1.
# Difficulty scales dynamically by how many biomes the player has cleared.
# Use get_dificuldade_atual() to get the current scaling tier.
BIOME_TIER_BASE = {chave: 1 for chave in [
    "floresta", "deserto", "pantano", "montanha", "caverna",
    "ruinas_arcanas", "cidade_antiga", "cidade_robotica",
    "cidade_magica", "cidade_religiosa", "cidade_tecnologica",
]}

# Player progression counter — incremented in main.py after each biome clear
_biomas_completados: int = 0

def set_biomas_completados(n: int) -> None:
    global _biomas_completados
    _biomas_completados = n

def get_dificuldade_atual() -> int:
    """
    Returns current difficulty tier based on number of cleared biomes.
    Tier 1 on first biome, grows by 1 every 2 clears, capped at 11.
    """
    return min(11, 1 + _biomas_completados // 2)
from config import (
    COMBATES_POR_BIOMA, BATALHA_NPC_EVENTO, BATALHA_BOSS,
    ITENS_ESCOLHA_BOSS, FREQUENCIA_DESCANSO,
)


# ══════════════════════════════════════════════════════════════
#  BIOMAS
# ══════════════════════════════════════════════════════════════

BIOMAS: Dict[str, dict] = {
    "floresta": {
        "nome": "Floresta Sombria", "name_en": "Dark Forest", "cor": "🌲",
        "descricao": "Árvores centenárias bloqueiam a luz. Sons de criaturas espreitam.",
        "tipo_inimigo": "besta",
        "inimigos": ["lobo_da_floresta", "capivara", "cutia", "goblin_batedeiro", "curupira"],
        "boss": "curupira_boss",
        "loot_bioma": ["armadura_couro", "arco_simples", "ervas_medicinais",
                       "amuleto_protetor", "faca_enferrujada"],
        "npc_evento": ["breno", "ferran"],
    },
    "deserto": {
        "nome": "Deserto de Ossos", "name_en": "Bone Desert", "cor": "🏜️",
        "descricao": "Calor escaldante, dunas sem fim e ruínas enterradas na areia.",
        "tipo_inimigo": "elemental",
        "inimigos": ["elemental_areia", "escorpiao_gigante", "arara_guerreira", "giboia"],
        "boss": "elemental_de_pedra",
        "loot_bioma": ["espada_longa", "amuleto_protetor", "pocao_cura",
                       "anel_do_estudioso", "escudo_madeira"],
        "npc_evento": ["eilara", "sombra"],
    },
    "pantano": {
        "nome": "Pântano da Podridão", "name_en": "Rotting Swamp", "cor": "🌿",
        "descricao": "Névoa espessa, chão instável e odor de decomposição.",
        "tipo_inimigo": "morto-vivo",
        "inimigos": ["jacara", "giboia_venenosa", "boto_cor_de_rosa", "capivara_fantasma", "zumbi_do_pantano"],
        "boss": "boi_tata",
        "loot_bioma": ["cajado_arcano", "chapeu_do_mago", "pocao_cura",
                       "anel_do_estudioso", "ervas_medicinais"],
        "npc_evento": ["mira", "sombra"],
    },
    "montanha": {
        "nome": "Pico dos Ventos Eternos", "name_en": "Peak of Eternal Winds", "cor": "⛰️",
        "descricao": "Frio cortante, precipícios e criaturas adaptadas à altitude.",
        "tipo_inimigo": "besta",
        "inimigos": ["aguia_das_neves", "urso_das_pedras", "troll_das_pedras", "arara_arcana"],
        "boss": "gigante_de_gelo",
        "loot_bioma": ["espada_longa", "armadura_couro", "amuleto_protetor",
                       "escudo_madeira", "pocao_cura"],
        "npc_evento": ["ferran", "duras"],
    },
    "caverna": {
        "nome": "Cavernas do Eco Profundo", "name_en": "Deep Echo Caverns", "cor": "🕯️",
        "descricao": "Escuridão quase total, cristais bioluminescentes e ecos perturbadores.",
        "tipo_inimigo": "arcano",
        "inimigos": ["fungo_parasita", "construct_de_pedra", "pisadeira", "anhanga"],
        "boss": "mago_renegado",
        "loot_bioma": ["cajado_arcano", "anel_do_estudioso", "chapeu_do_mago",
                       "pocao_cura", "faca_enferrujada"],
        "npc_evento": ["sombra", "mira"],
    },
    "ruinas_arcanas": {
        "nome": "Ruínas Arcanas de Vel'Khar", "name_en": "Arcane Ruins of Vel'Khar", "cor": "✨",
        "descricao": "Estruturas flutuantes, portais instáveis e construtos mágicos errantes.",
        "tipo_inimigo": "arcano",
        "inimigos": ["golem_arcano", "sombra_errante", "jacara_sombrio", "curupira_ancestral"],
        "boss": "dragao_sombrio",
        "loot_bioma": ["anel_do_estudioso", "cajado_arcano", "chapeu_do_mago",
                       "amuleto_protetor", "pocao_cura"],
        "npc_evento": ["eilara", "sombra"],
    },
    "cidade_antiga": {
        "nome": "Cidade Perdida de Aurath", "name_en": "Lost City of Aurath", "cor": "🏛️",
        "descricao": "Metrópole abandonada com arquitetura impossível e habitantes fantasmais.",
        "tipo_inimigo": "humanoide",
        "inimigos": ["saqueador_corrupto", "guarda_fantasma", "saci_perere", "mula_sem_cabeca"],
        "boss": "mula_boss",
        "loot_bioma": ["espada_longa", "escudo_madeira", "anel_do_estudioso",
                       "amuleto_protetor", "pocao_cura"],
        "npc_evento": ["breno", "eilara", "duras"],
    },
    "cidade_robotica": {
        "nome": "Nexus Mecânico Sigma-7", "name_en": "Mechanical Nexus Sigma-7", "cor": "⚙️",
        "descricao": "Engrenagens colossais, vapores de óleo e autômatos sem propósito.",
        "tipo_inimigo": "arcano",
        "inimigos": ["automato_sentinela", "dron_de_vigilancia", "engenheiro_renegado", "maquina_de_guerra"],
        "boss": "nucleo_central",
        "loot_bioma": ["anel_do_estudioso", "amuleto_protetor", "cajado_arcano",
                       "pocao_cura", "armadura_couro"],
        "npc_evento": ["ferran", "eilara"],
    },
    "cidade_magica": {
        "nome": "Arcádia, a Cidade Flutuante", "name_en": "Arcadia, the Floating City", "cor": "🔮",
        "descricao": "Torres de cristal, magos em duelo e energia arcana no ar.",
        "tipo_inimigo": "arcano",
        "inimigos": ["aprendiz_corrompido", "elemental_arcano", "iara", "caipora_da_varzea"],
        "boss": "lobisomem",
        "loot_bioma": ["chapeu_do_mago", "cajado_arcano", "anel_do_estudioso",
                       "pocao_cura", "amuleto_protetor"],
        "npc_evento": ["mira", "eilara"],
    },
    "cidade_religiosa": {
        "nome": "Santuário de Luz Eterna", "name_en": "Eternal Light Sanctuary", "cor": "⛪",
        "descricao": "Templos dourados, fanáticos armados e relíquias de poder imenso.",
        "tipo_inimigo": "humanoide",
        "inimigos": ["inquisidor_fervoroso", "paladino_caido", "mapinguari", "senhor_das_sombras"],
        "boss": "caipora_boss",
        "loot_bioma": ["escudo_madeira", "amuleto_protetor", "pocao_cura",
                       "espada_longa", "ervas_medicinais"],
        "npc_evento": ["mira", "duras", "breno"],
    },
    "cidade_tecnologica": {
        "nome": "Porto Eletrovapor", "name_en": "Electrovapor Port", "cor": "🔧",
        "descricao": "Mistura de vapor e eletricidade. Engenhocas experimentais.",
        "tipo_inimigo": "humanoide",
        "inimigos": ["mago_renegado", "esqueleto_guerreiro", "caipora"],
        "boss": "protocolo_omega",
        "loot_bioma": ["arco_simples", "armadura_couro", "anel_do_estudioso",
                       "pocao_cura", "amuleto_protetor"],
        "npc_evento": ["ferran", "eilara"],
    },
}


# ══════════════════════════════════════════════════════════════
#  AUXILIARES
# ══════════════════════════════════════════════════════════════

def listar_biomas() -> None:
    print("\n  Biomas disponíveis:")
    from i18n import LANG
    for chave, b in BIOMAS.items():
        nome_b = b.get("name_en", b["nome"]) if LANG == "en" else b["nome"]
        print(f"    [{chave:20}] {b['cor']} {nome_b:35} — {b['descricao'][:50]}")


def obter_bioma(chave: str) -> dict:
    chave = chave.lower().replace(" ", "_")
    if chave not in BIOMAS:
        raise KeyError(f"Bioma '{chave}' não encontrado.")
    return BIOMAS[chave]


def _salvar_amizades_npcs() -> None:
    """Persiste o estado de amizade de todos os NPCs."""
    import jornada as jrn
try:
    import memoria_npc as _mnpc
    _MNPC_ATIVO = True
except ImportError:
    _MNPC_ATIVO = False
    from historias import CATALOGO_NPCS
    amizades = {k: {"amizade": v.amizade} for k, v in CATALOGO_NPCS.items()}
    jrn.salvar_amizade_npcs(amizades)


def _carregar_amizades_npcs() -> None:
    """Restaura o estado de amizade dos NPCs a partir do save."""
    import jornada as jrn
    from historias import CATALOGO_NPCS
    dados = jrn.carregar_amizade_npcs()
    for chave, npc in CATALOGO_NPCS.items():
        if chave in dados:
            npc.amizade = dados[chave].get("amizade", 0.0)


def escolher_inimigo_bioma(bioma: dict, nivel: int = 1):
    from inimigos import CATALOGO_INIMIGOS, gerar_inimigo_procedural
    tier = get_dificuldade_atual()
    candidatos = [c for c in bioma["inimigos"] if c in CATALOGO_INIMIGOS]
    if candidatos:
        chave = random.choice(candidatos)
        base  = CATALOGO_INIMIGOS[chave].clonar()
        base._chave = chave   # preserve key for ASCII art lookup
        # Scale stats by tier beyond the enemy's native tier
        native_pv = base.pv_max
        tf_extra = max(1.0, 1.0 + (tier - base.nivel) * 0.2)
        base.pv_max    = round(native_pv * tf_extra, 0)
        base.pv_atual  = base.pv_max
        base.dano_base = round(base.dano_base * (tf_extra ** 0.8), 1)
        base.defesa    = round(base.defesa    * (tf_extra ** 0.6), 1)
        return base
    return gerar_inimigo_procedural(nivel, tipo=bioma.get("tipo_inimigo"), biome_tier=tier)


def escolher_boss_bioma(bioma: dict, nivel: int = 1):
    from inimigos import CATALOGO_INIMIGOS, gerar_inimigo_procedural
    from _inimigos_rebalance import BOSS_STATS
    tier  = get_dificuldade_atual()
    pv, dano, defesa = BOSS_STATS.get(tier, BOSS_STATS[11])

    chave = bioma.get("boss")
    if chave and chave in CATALOGO_INIMIGOS:
        boss = CATALOGO_INIMIGOS[chave].clonar()
    else:
        boss = gerar_inimigo_procedural(nivel + 2, tipo=bioma.get("tipo_inimigo"), biome_tier=tier)

    # Override with tier-calibrated boss stats
    boss.pv_max    = float(pv)
    boss.pv_atual  = float(pv)
    boss.dano_base = float(dano)
    boss.defesa    = float(defesa)
    return boss


def sortear_loot_boss(bioma: dict) -> list:
    from itens import CATALOGO_ITENS
    pool    = bioma.get("loot_bioma", list(CATALOGO_ITENS.keys()))
    amostra = random.sample(pool, min(ITENS_ESCOLHA_BOSS, len(pool)))
    return [CATALOGO_ITENS[c].clonar() for c in amostra if c in CATALOGO_ITENS]


def escolher_npc_evento(bioma: dict):
    from historias import CATALOGO_NPCS
    candidatos = [c for c in bioma["npc_evento"] if c in CATALOGO_NPCS]
    if not candidatos:
        candidatos = list(CATALOGO_NPCS.keys())
    return CATALOGO_NPCS[random.choice(candidatos)]


# ══════════════════════════════════════════════════════════════
#  PAINEL PÓS-BATALHA
# ══════════════════════════════════════════════════════════════

def _painel_pos_batalha(personagem) -> None:
    """
    Exibido após cada batalha (vitória ou fuga).
    Permite ver atributos e usar itens consumíveis.
    """
    while True:
        print(f"\n{'─'*58}")
        print(f"  {t('post.title')}")
        print(f"{'─'*58}")
        print(f"  [1] {t('post.view_attrs')}")
        print(f"  [2] {t('post.use_item')}")
        print(f"  [3] {t('post.continue')}")

        op = input("  > ").strip()

        if op == "1":
            print()
            print(personagem.ficha())
            from _item_ui import mostrar_inventario
            mostrar_inventario(personagem)

        elif op == "2":
            _usar_consumivel(personagem)

        elif op == "3":
            break
        else:
            print(f"  {t('sys.invalid')}")


def _usar_consumivel(personagem) -> None:
    """Lista consumíveis da bolsa e aplica efeito — delega ao sistema unificado."""
    from _item_ui import menu_usar_consumivel_combate
    ok, msg = menu_usar_consumivel_combate(personagem)
    if msg and msg != "Cancelado.":
        print(f"  {msg}")


# ══════════════════════════════════════════════════════════════
#  LOOP DO BIOMA
# ══════════════════════════════════════════════════════════════

def executar_bioma(personagem, chave_bioma: str) -> str:
    """Orquestra as 10 batalhas. Retorna 'concluido' | 'morte'."""
    bioma  = obter_bioma(chave_bioma)
    bioma['_chave'] = chave_bioma  # needed for tier lookup
    nivel  = max(1, int(personagem.corpo_fisico / 5))

    from i18n import LANG, t
    nome_bioma = bioma.get("name_en", bioma["nome"]) if LANG == "en" else bioma["nome"]
    print(f"\n{'═'*58}")
    print(f"  {bioma['cor']}  {t('biome.completed').split('!')[0].upper()}: {nome_bioma.upper()}")
    print(f"  {bioma['descricao']}")
    print(f"  {t('biome.enemies')}: {bioma['tipo_inimigo']}")
    print(f"{'═'*58}")

    import jornada as jrn
    jrn.mover_para(bioma["nome"])
    _carregar_amizades_npcs()   # Restaura amizades da sessão anterior

    for batalha_num in range(1, COMBATES_POR_BIOMA + 1):

        print(f"\n  ── Batalha {batalha_num}/{COMBATES_POR_BIOMA} "
              f"{'[BOSS]' if batalha_num == BATALHA_BOSS else ''} ──")

        inimigo = (escolher_boss_bioma(bioma, nivel)
                   if batalha_num == BATALHA_BOSS
                   else escolher_inimigo_bioma(bioma, nivel))

        if batalha_num == BATALHA_BOSS:
            print(f"\n  ☠  {t('biome.boss_battle')}")

        from combate import iniciar_combate
        resultado = iniciar_combate(personagem, inimigo, bioma_key=chave_bioma)

        if resultado == "derrota":
            print("\n  Sua jornada termina aqui.")
            return "morte"

        # Regeneração de Psiquê após batalha
        personagem.regenerar_pos_batalha()
        jrn.atualizar_personagem(personagem.to_dict())

        # ── Boss concluído ────────────────────────────────────
        if batalha_num == BATALHA_BOSS:
            _painel_pos_batalha(personagem)
            _evento_escolha_item_boss(personagem, bioma)
            return "concluido"

        # ── Painel pós-batalha (toda batalha não-boss) ────────
        _painel_pos_batalha(personagem)

        # ── Evento NPC (batalha 5) ────────────────────────────
        if batalha_num == BATALHA_NPC_EVENTO:
            _evento_npc(personagem, bioma)

        # ── Presente do NPC (batalha 9, amizade >= 70) ───────
        if batalha_num == 9:
            _verificar_presente_npc(personagem, bioma)

        # ── Treinar / Dormir (batalhas múltiplas de FREQUENCIA_DESCANSO,
        #    exceto batalha 5 que já teve evento NPC, e batalha 10) ──
        eh_multiplo   = (batalha_num % FREQUENCIA_DESCANSO == 0)
        eh_especial   = (batalha_num in (BATALHA_NPC_EVENTO, BATALHA_BOSS))
        if eh_multiplo and not eh_especial:
            _evento_descanso(personagem)

    # Persiste amizades ao concluir o bioma
    _salvar_amizades_npcs()
    return "concluido"


# ══════════════════════════════════════════════════════════════
#  EVENTOS
# ══════════════════════════════════════════════════════════════

def _evento_descanso(personagem) -> None:
    """Treinar ou Dormir — disponível apenas em batalhas selecionadas."""
    print(f"\n{'─'*58}")
    print(f"  {t('rest.title')}")
    print(f"  PV: {personagem.pv_atual:.0f}/{personagem.pv_max:.0f}  "
          f"| Psique: {personagem.psique_atual:.1f}/{personagem.psique_max:.1f}")
    print(f"  [T] {t('rest.train')}")
    print(f"  [D] {t('rest.sleep')}")

    while True:
        op = input("  > ").strip().upper()
        if op == "T":
            _treinar(personagem)
            break
        elif op == "D":
            _dormir_com_reflexao(personagem)
            break
        else:
            print("  Digite T ou D.")


def _dormir_com_reflexao(personagem) -> None:
    """
    Dormir restaura PV e Psiquê completamente.
    Além disso, o personagem organiza mentalmente o que viveu
    e converte parte do Conhecimento Tácito acumulado em
    Conhecimento Explícito — e ganha um bônus fixo de reflexão.
    """
    import jornada as jrn

    personagem.dormir()

    # Organizar o que aprendeu: converte 20% do tácito acumulado
    # em explícito (representa reflexão e consolidação de memória)
    tacito_acumulado = personagem.conhecimento_tacito
    conversao = round(tacito_acumulado * 0.20, 2)

    # Bônus fixo de reflexão noturna (insights do dia)
    bonus_reflexao = 0.3

    ganho_total = conversao + bonus_reflexao
    personagem.ganhar_conhecimento_explicito(
        ganho_total,
        f"reflexão noturna (conversão tácito→explícito: {conversao:.2f} + insight: {bonus_reflexao})"
    )

    print(f"\n  {t('rest.sleep_narr')}")
    print(f"  +{ganho_total:.2f} {t('rest.knowledge_gain')}")
    print(f"  {t('rest.knowledge_total')}: {personagem.conhecimento:.2f}")

    jrn.registrar_evento(
        "narrativa",
        f"{personagem.nome} dormiu e organizou o conhecimento do dia.",
        {"ganho_conhecimento": ganho_total}
    )
    jrn.atualizar_personagem(personagem.to_dict())


def _treinar(personagem) -> None:
    print(f"  {t('rest.train_what')}")
    print(f"  [F] {t('rest.strength')}")
    print(f"  [V] {t('rest.vigor')}")
    while True:
        op = input("  > ").strip().upper()
        if op == "F":
            personagem.treinar(forca=1.0)
            print(f"  Corpo Físico: {personagem.corpo_fisico:.1f} | "
                  f"PV Máx: {personagem.pv_max:.0f}")
            break
        elif op == "V":
            personagem.treinar(vigor=1.0)
            print(f"  Corpo Físico: {personagem.corpo_fisico:.1f} | "
                  f"PV Máx: {personagem.pv_max:.0f}")
            break
        else:
            print("  Digite F ou V.")
    import jornada as jrn
    jrn.registrar_evento("narrativa", f"{personagem.nome} treinou.")
    jrn.atualizar_personagem(personagem.to_dict())


def _exibir_menu_npc(npc, relacao: float = 0) -> None:
    """
    Exibe o menu do NPC com barra de amizade persistente.
    relacao = npc.amizade (0-100), persiste entre biomas.
    """
    amt = int(relacao)
    bar = "█" * (amt // 10) + "░" * (10 - amt // 10)
    col = npc.amizade_cor() if hasattr(npc, "amizade_cor") else (
        "[32m" if amt >= 60 else ("[33m" if amt >= 30 else "[90m"))
    label = npc.amizade_label() if hasattr(npc, "amizade_label") else ""
    ajuda_tag = ""
    if hasattr(npc, "ajuda_disponivel") and not npc.ajuda_disponivel:
        ajuda_tag = "  [90m[ajuda usada][0m" if npc.ajuda_resultado != "fuga" else "  [31m[fugiu da luta][0m"
    print(f"\n{'─'*58}")
    print(f"  👤 {t('npc.encounter')} — [33m{npc.nome}[0m  "
          f"({npc.ocupacao}  |  {npc.atitude})")
    print(f"  {npc.descricao_fisica}")
    print(f"  [90m{npc.personalidade[:70]}[0m")
    print(f"  {col}♥ Amizade [{bar}] {amt}/100  {label}[0m")
    print(f"{'─'*58}")
    print(f"  [1] {t('npc.talk')}")
    print(f"  [2] {t('npc.trade')}")
    print(f"  [3] {t('npc.help')}{ajuda_tag}")
    if amt >= 60:
        print(f"  [5] Pedir segredo  [33m(amizade alta desbloqueou)[0m")
    print(f"  [4] {t('npc.proceed')}")


def _evento_npc(personagem, bioma: dict, npc=None) -> None:
    import jornada as jrn
    from historias import narrar_cena
    if npc is None:
        npc = escolher_npc_evento(bioma)
    npc.registrar_na_jornada()

    # ── Cena de abertura gerada pela LLM ────────────────────
    ctx_bioma = bioma.get("descricao", "")
    prompt_abertura = (
        f"Você é o narrador de um RPG. Descreva em 2-3 frases a cena em que "
        f"{personagem.nome} encontra {npc.nome} ({npc.ocupacao}) "
        f"no ambiente: {ctx_bioma}. "
        f"Aparência do NPC: {npc.descricao_fisica}. "
        f"Personalidade: {npc.personalidade}. "
        f"Tom: narrativo, segunda pessoa, épico mas acessível."
    )
    print(f"\n{'═'*58}")
    cena = narrar_cena(prompt_abertura, personagem.to_dict())
    if cena and "[Ollama" not in cena and "[ERRO" not in cena:
        print(f"  {cena}")
    else:
        print(f"  Você encontra {npc.nome} no caminho.")
    print(f"{'═'*58}")

    # Reseta ajuda para este bioma
    npc.resetar_para_bioma()

    while True:
        _exibir_menu_npc(npc, npc.amizade)
        op = input("  > ").strip()

        if op == "1":
            _conversar_npc(personagem, npc)
            # amizade +5/turno é gerenciada dentro de _conversar_npc

        elif op == "2":
            sucesso = _evento_troca_item(personagem, npc)
            if sucesso:
                npc.ganhar_amizade(20, "troca de item")

        elif op == "3":
            if not npc.ajuda_disponivel:
                if npc.ajuda_resultado == "fuga":
                    print(f"  [33m{npc.nome} ainda parece chateado com a última vez...[0m")
                else:
                    print(f"  [90mVocê já ajudou {npc.nome} neste bioma.[0m")
            else:
                _evento_ajuda_combate(personagem, npc, bioma)

        elif op == "5" and npc.amizade >= 60:
            _revelar_segredo(personagem, npc, bioma)
            npc.ganhar_amizade(-10, "segredo revelado")

        elif op == "4":
            print(f"\n  {t('npc.farewell')} {npc.nome}")
            break

        else:
            print(f"  {t('sys.invalid')}")

    jrn.atualizar_personagem(personagem.to_dict())


def _conversar_npc(personagem, npc) -> None:
    """
    Loop de diálogo com o NPC. A LLM detecta se o jogador está:
    - fazendo uma pergunta simples → resposta direta
    - pedindo dica sobre o bioma  → NPC usa seus 'conhecimentos'
    - tentando persuadir/intimidar → resposta condizente com atitude
    O bônus de Conh. Explícito só é dado se a pergunta for substantiva (> 3 palavras).
    """
    print(f"\n  ── Conversando com {npc.nome} ──")
    print(f"  \033[90m(Enter em branco para encerrar)\033[0m")

    turnos = 0
    while True:
        pergunta = input(f"\n  {personagem.nome} > ").strip()
        if not pergunta:
            break

        # Injeta histórico persistente antes de falar
        if _MNPC_ATIVO:
            npc.historico_dialogos = _mnpc.obter_historico(npc.nome, n=8)
        resposta = npc.falar(pergunta, personagem.nome)
        print(f"\n  \033[33m{npc.nome}:\033[0m {resposta}")

        # Bônus limitado por sistema de memória NPC
        import jornada as _jrn_local
        turno_atual = _jrn_local.obter_estado().get("turno", 0)
        if _MNPC_ATIVO:
            bonus = _mnpc.processar_fala(
                npc.nome, personagem.nome, pergunta, turno_atual, amizade_delta=5.0
            )
            _mnpc.processar_fala(npc.nome, npc.nome, resposta, turno_atual)
            if bonus > 0:
                personagem.ganhar_conhecimento_explicito(round(bonus, 2), f"conversa com {npc.nome}")
                print(f"  \033[90m+{bonus:.2f} Conh. Explícito "
                      f"({personagem.conhecimento:.2f}) "
                      f"[sessão: {_mnpc.stats_ganhos_sessao()['ganho_total']:.2f}/"
                      f"{_mnpc.LIMITE_TOTAL_SESSAO:.1f}]\033[0m")
        else:
            # Fallback sem memória — limita manualmente
            palavras = len(pergunta.split())
            if palavras >= 4:
                bonus = min(0.2, 0.1 + palavras * 0.01)
                personagem.ganhar_conhecimento_explicito(round(bonus, 2), f"conversa com {npc.nome}")
        npc.ganhar_amizade(5, "conversa")
        turnos += 1


def _revelar_segredo(personagem, npc, bioma: dict = None) -> None:
    """
    NPC revela segredo + efeito mecânico único por NPC:
      Ferran    → aumenta maestria_max da arma equipada em +50
      outros    → entrega item aleatório do pool de loot do bioma atual
    A narração é gerada pela LLM em primeira pessoa.
    """
    import jornada as jrn
    from historias import _chamar_llm_narrativa
    from config import LLM_TOKENS_NPC

    if not npc.segredos:
        print(f"\n  {npc.nome}: 'Não tenho segredos para compartilhar agora...'")
        return

    segredo = npc.segredos[0]

    # ── Narração via LLM ─────────────────────────────────────
    prompt = (
        f"Você é {npc.nome}, {npc.ocupacao}. Personalidade: {npc.personalidade}. "
        f"Depois de ganhar confiança genuína, você decide revelar: '{segredo}'. "
        f"Narre em 2-3 frases, em primeira pessoa, com peso emocional autêntico."
    )
    resposta = _chamar_llm_narrativa(
        prompt, jrn.obter_contexto_compacto(),
        num_predict=LLM_TOKENS_NPC, stream=False
    )

    print(f"\n  {'─'*54}")
    print(f"  \033[33m{npc.nome} (em voz baixa):\033[0m")
    print(f"  {resposta or segredo.capitalize()+'.'}")
    print(f"  {'─'*54}")

    # ── Efeito mecânico ──────────────────────────────────────
    if npc.ocupacao == "Ferreiro":
        _segredo_ferran(personagem)
    else:
        _segredo_item_bioma(personagem, npc, bioma)

    # Bônus de conhecimento tácito — apenas se ainda não recebeu este segredo
    if _MNPC_ATIVO:
        if _mnpc.pode_ganhar_segredo(npc.nome):
            personagem.ganhar_conhecimento_tacito(0.5, f"segredo de {npc.nome}")
            _mnpc.registrar_ganho(npc.nome, "conhecimento_tacito", 0.5, f"segredo de {npc.nome}")
            _mnpc.registrar_lore(npc.nome, segredo[:200], "segredo")
            print("  \033[90m+0.5 Conh. Tácito (segredo único)\033[0m")
        else:
            print(f"  \033[90m(segredo de {npc.nome} já conhecido — sem bônus adicional)\033[0m")
    else:
        personagem.ganhar_conhecimento_tacito(0.5, f"segredo de {npc.nome}")
    jrn.registrar_evento("descoberta", f"{personagem.nome} soube segredo de {npc.nome}.",
                         {"segredo": segredo[:100]})


def _segredo_ferran(personagem) -> None:
    """
    Ferran aprimora a arma equipada: maestria_max +50.
    Simula o ferreiro reforçando a arma com seu conhecimento secreto de forja.
    """
    item = personagem.item_equipado
    if not item:
        print(f"  \033[33mFerran examina suas mãos vazias. 'Volte quando tiver uma arma.'\033[0m")
        return
    if item.tipo != "arma":
        print(f"  \033[33mFerran franze o cenho. 'Isso não é arma. Não posso trabalhar nisso.'\033[0m")
        return

    antes = item.maestria_max
    item.maestria_max += 50
    print(f"\n  \033[33m🔨 Ferran passa horas reforçando sua {item.nome} com técnicas secretas.\033[0m")
    print(f"  \033[32m✦ {item.nome}: Maestria máx {antes:.0f} → {item.maestria_max:.0f} (+50)\033[0m")
    print(f"  \033[90mAgora você pode desbloquear habilidades mais poderosas com ela.\033[0m")


def _segredo_item_bioma(personagem, npc, bioma: dict) -> None:
    """
    NPCs não-ferreiro entregam um item aleatório do pool de loot do bioma.
    Prioriza itens que o personagem ainda não tem no inventário.
    """
    from inimigos import CATALOGO_INIMIGOS
    from itens import CATALOGO_ITENS
    from _item_ui import receber_item
    import jornada as jrn

    # Monta pool de loot do bioma
    loot_pool = set()
    if bioma:
        todos_inimigos = bioma.get("inimigos", []) + ([bioma["boss"]] if bioma.get("boss") else [])
        for ik in todos_inimigos:
            ini = CATALOGO_INIMIGOS.get(ik)
            if ini:
                for loot_key, _ in ini.loot_possivel:
                    loot_pool.add(loot_key)

    # Fallback: itens do catálogo geral se bioma sem loot mapeado
    if not loot_pool:
        candidatos = list(CATALOGO_ITENS.values())
    else:
        candidatos = [CATALOGO_ITENS[k] for k in loot_pool if k in CATALOGO_ITENS]

    if not candidatos:
        print(f"  {npc.nome}: 'Queria te dar algo, mas não tenho nada agora...'")
        return

    # Prefere itens que o jogador ainda não possui
    nomes_inventario = {i.nome for i in personagem.inventario + personagem.bolsa}
    novos = [i for i in candidatos if i.nome not in nomes_inventario]
    pool_final = novos if novos else candidatos

    presente = random.choice(pool_final).clonar()

    print(f"\n  \033[33m{npc.nome} tira algo escondido e oferece a você:\033[0m")
    print(f"  \033[32m🎁 {presente.nome}\033[0m  \033[90m({presente.descricao[:60]})\033[0m")
    receber_item(personagem, presente)
    jrn.registrar_item_obtido(presente.nome, f"segredo_{npc.nome}")


def _evento_troca_item(personagem, npc) -> bool:
    """
    Troca de item com o NPC.
    - NPC oferece item condizente com sua ocupação (ponderado por tipo)
    - Exibe requisito de atributo do item ofertado
    - Verifica se personagem atende requisito antes de aceitar
    - Retorna True se troca realizada (para atualizar relação)
    """
    from itens import CATALOGO_ITENS
    import jornada as jrn

    itens_npc = personagem.inventario + list(CATALOGO_ITENS.values())
    if not personagem.inventario:
        print(f"  {t('npc.no_items')}")
        input("  Enter para voltar...")
        return False

    # NPC oferece item coerente com sua ocupação
    tipo_pref = {
        "Ferreiro":    ["arma"],
        "Mercante":    ["acessorio","consumivel"],
        "Curandeira":  ["consumivel","acessorio"],
        "Taverneiro":  ["consumivel"],
        "Informante":  ["acessorio"],
    }.get(npc.ocupacao, None)

    candidatos = list(CATALOGO_ITENS.values())
    if tipo_pref:
        filtrados = [i for i in candidatos if i.tipo in tipo_pref]
        candidatos = filtrados if filtrados else candidatos
    oferta_npc = random.choice(candidatos).clonar()

    # Monta display do item ofertado com requisito
    req = oferta_npc.requisito or {}
    _labels = {"forca":"Força","vigor":"Vigor","conhecimento_tacito":"C.Tácito","conhecimento_explicito":"C.Explícito"}
    req_str = "  ".join(
        f"{_labels.get(k,k)} ≥ {int(v)}"
        for k,v in req.items()
    ) if req else "—"
    dano_str = (f"Dano Físico: {oferta_npc.dano_fisico:.0f}" if oferta_npc.tipo_dano == "fisico"
                else f"Dano Mágico: {oferta_npc.dano_magico:.0f}" if oferta_npc.tipo_dano == "magico"
                else f"Dano: {oferta_npc.dano_arma:.0f}")
    hab = f" | hab: {oferta_npc.habilidades_item}" if oferta_npc.habilidades_item else ""

    print(f"\n  {'─'*54}")
    print(f"  {npc.nome} {t('npc.offers')}: \033[33m{iname(oferta_npc)}\033[0m "
          f"\033[90m[{oferta_npc.qualidade}]\033[0m")
    print(f"    {oferta_npc.descricao}")
    print(f"    {dano_str}  |  Def: {oferta_npc.defesa:.0f}{hab}")
    print(f"    \033[33mRequisito: {req_str}\033[0m")
    print(f"  {'─'*54}")

    # Verifica requisito
    ok, msg_req = personagem.verificar_requisito(oferta_npc)
    if not ok:
        print(f"  \033[31m⚠  {msg_req}\033[0m")
        print(f"  Você não tem os atributos necessários para usar este item.")
        aceitar = input("  Aceitar mesmo assim? [s/n] > ").strip().lower()
        if aceitar != "s":
            print(f"  {t('npc.trade_cancel')}")
            return False

    print("\n  Seu inventário:")
    for i, it in enumerate(personagem.inventario):
        req_it = it.requisito or {}
        req_it_str = ", ".join(f"{k}≥{int(v)}" for k,v in req_it.items()) if req_it else ""
        req_tag = f" \033[33m[{req_it_str}]\033[0m" if req_it_str else ""
        print(f"    [{i+1}] {iname(it):28} def={it.defesa:.0f} dano={it.dano_arma:.0f}{req_tag}")
    print(f"    [0] Cancelar")

    escolha = input("\n  Qual item você oferece em troca? > ").strip()
    if escolha == "0" or not escolha.isdigit():
        print(f"  {t('npc.trade_cancel')}")
        return False

    idx = int(escolha) - 1
    if 0 <= idx < len(personagem.inventario):
        dado = personagem.inventario.pop(idx)
        print(f"\n  ✓ Troca: \033[31m{iname(dado)}\033[0m → \033[32m{iname(oferta_npc)}\033[0m")
        from _item_ui import receber_item as _recv
        _recv(personagem, oferta_npc)
        jrn.registrar_item_obtido(oferta_npc.nome, f"troca_{npc.nome}")
        return True
    else:
        print("  Inválido.")
        return False


def _evento_ajuda(personagem, npc, bioma: dict = None) -> bool:
    """
    Missão de ajuda contextualizada:
    - Situação gerada pela LLM com base na ocupação do NPC e no bioma
    - O jogador descreve livremente como age
    - A LLM avalia a criatividade/adequação da ação (sem Psiquê neste contexto)
    - Recompensa varia por qualidade da resposta: Conh. Tácito + chance de cura
    - Retorna True se o jogador agiu (para atualizar relação)
    """
    from historias import narrar_cena, _chamar_llm_narrativa
    import jornada as jrn
    from config import LLM_TOKENS_NPC

    # ── Gera situação contextualizada ────────────────────────
    ctx_bioma = bioma.get("descricao", "um ambiente perigoso") if bioma else "um caminho solitário"
    ocupacoes_situacoes = {
        "Taverneiro":  "perdeu suas provisões numa emboscada e precisa de ajuda para recuperá-las",
        "Curandeira":  "encontrou feridos no caminho e seus suprimentos acabaram",
        "Ferreiro":    "tem ferramentas preciosas presas num local perigoso",
        "Mercante":    "foi roubado e precisa rastrear os ladrões antes que fujam",
        "Informante":  "descobriu algo perigoso e precisa de escolta para escapar",
    }
    situacao_base = ocupacoes_situacoes.get(
        npc.ocupacao,
        f"está em apuros e precisa de ajuda urgente"
    )
    prompt_situacao = (
        f"Em 1-2 frases, descreva como {npc.nome} ({npc.ocupacao}, personalidade: {npc.personalidade}) "
        f"explica sua situação: ele/ela {situacao_base}. "
        f"O ambiente é: {ctx_bioma}. Fale em primeira pessoa como o NPC."
    )
    situacao_narrada = _chamar_llm_narrativa(
        prompt_situacao, jrn.obter_contexto_compacto(),
        num_predict=LLM_TOKENS_NPC, stream=False
    )

    print(f"\n  {'─'*54}")
    print(f"  \033[33m{npc.nome}:\033[0m {situacao_narrada or situacao_base.capitalize()+'.'}")
    print(f"  {'─'*54}")
    print(f"  Como você age?  \033[90m(Enter para não intervir)\033[0m")

    acao = input(f"  {personagem.nome} > ").strip()
    if not acao:
        print(f"  Você hesita e decide não intervir desta vez.")
        npc.historico_dialogos.append({"de": "narrador", "texto": f"{personagem.nome} recusou ajudar."})
        return False

    # ── Narração do resultado ─────────────────────────────────
    prompt_resultado = (
        f"Narre em 2-3 frases o resultado da seguinte ação de {personagem.nome} "
        f"ajudando {npc.nome} ({npc.ocupacao}): '{acao}'. "
        f"Contexto: {situacao_narrada or situacao_base}. "
        f"Tom épico, segunda pessoa para {personagem.nome}."
    )
    narracao = narrar_cena(prompt_resultado, personagem.to_dict())
    print(f"\n  {narracao}")

    # ── Recompensas escaladas pela qualidade da ação ──────────
    palavras = len(acao.split())
    bonus_tacito = 0.3 + min(0.7, palavras * 0.04)  # 0.3-1.0 baseado em elaboração
    personagem.ganhar_conhecimento_tacito(round(bonus_tacito, 1), "")
    print(f"  \033[90m+{bonus_tacito:.1f} Conh. Tácito\033[0m")

    # Ação elaborada (>=8 palavras) → cura PV também
    if palavras >= 8:
        cura = round(personagem.vigor * 1.5, 1)
        pv_antes = personagem.pv_atual
        personagem.pv_atual = min(personagem.pv_max, personagem.pv_atual + cura)
        ganho = personagem.pv_atual - pv_antes
        if ganho > 0:
            print(f"  \033[32m{npc.nome} agradece e cuida dos seus ferimentos. +{ganho:.0f} PV\033[0m")

    jrn.registrar_evento("narrativa", f"{personagem.nome} ajudou {npc.nome}.",
                         {"acao": acao[:100], "bonus_tacito": bonus_tacito})
    npc.historico_dialogos.append({"de": personagem.nome, "texto": f"[ajudou] {acao[:60]}"})
    return True


def _verificar_presente_npc(personagem, bioma: dict) -> None:
    """
    Na batalha 9, se o NPC do bioma tiver amizade >= 70, ele aparece
    e entrega um item ao jogador como gesto de gratidão.
    """
    from historias import CATALOGO_NPCS, _chamar_llm_narrativa
    import jornada as jrn
    from config import LLM_TOKENS_NPC
    from itens import CATALOGO_ITENS

    # Encontra o NPC com maior amizade entre os do bioma
    candidatos = [c for c in bioma.get("npc_evento", []) if c in CATALOGO_NPCS]
    if not candidatos:
        return
    npc = max((CATALOGO_NPCS[k] for k in candidatos), key=lambda n: n.amizade)

    LIMIAR_AMIZADE_PRESENTE = 70
    if npc.amizade < LIMIAR_AMIZADE_PRESENTE:
        return  # não atingiu amizade suficiente

    # Seleciona item condizente com ocupação do NPC
    tipo_pref = {
        "Ferreiro"  : ["arma"],
        "Mercante"  : ["acessorio", "consumivel"],
        "Curandeira": ["consumivel", "acessorio"],
        "Taverneiro": ["consumivel"],
        "Informante": ["acessorio"],
    }.get(npc.ocupacao, None)

    candidatos_item = list(CATALOGO_ITENS.values())
    if tipo_pref:
        filtrados = [i for i in candidatos_item if i.tipo in tipo_pref]
        candidatos_item = filtrados if filtrados else candidatos_item
    import random
    presente = random.choice(candidatos_item).clonar()

    # Fala narrativa do NPC
    prompt_presente = (
        f"Você é {npc.nome}, {npc.ocupacao}. Personalidade: {npc.personalidade}. "
        f"Você tem uma relação de amizade forte com {personagem.nome} (amizade {npc.amizade:.0f}/100). "
        f"Você aparece de surpresa antes da batalha final e entrega '{presente.nome}' como presente. "
        f"Em 2 frases curtas e em primeira pessoa, explique o gesto com emoção genuína."
    )
    fala = _chamar_llm_narrativa(
        prompt_presente, jrn.obter_contexto_compacto(),
        num_predict=LLM_TOKENS_NPC, stream=False
    )

    print(f"\n  {'═'*58}")
    print(f"  🎁  {npc.nome} aparece antes da batalha final!")
    print(f"  {'═'*58}")
    print(f"  [33m{npc.nome}:[0m {fala or f'Tome, {personagem.nome}. Você merece isso.'}")
    print(f"\n  Presente: [32m{presente.nome}[0m")
    print(f"  {presente.descricao}")

    from _item_ui import receber_item
    receber_item(personagem, presente)
    jrn.registrar_item_obtido(presente.nome, f"presente_{npc.nome}")
    jrn.registrar_evento("item_obtido", f"{npc.nome} presenteou {personagem.nome}.",
                         {"item": presente.nome, "amizade": npc.amizade})
    print(f"  {'═'*58}")
    input("  [Enter para continuar...]")


def _evento_ajuda_combate(personagem, npc, bioma: dict) -> None:
    """
    Missão de ajuda: 3 rounds de combate contra inimigos únicos do bioma.
    - Vitória em todos → NPC elogia, amizade +35
    - Fuga em qualquer round → NPC fica chateado, amizade −10
    - Após este evento, ajuda_disponivel = False para o bioma atual
    """
    from historias import _chamar_llm_narrativa
    import jornada as jrn
    from combate import iniciar_combate
    from config import LLM_TOKENS_NPC

    # ── Gera situação narrativa de pedido de ajuda ────────────
    ctx_bioma = bioma.get("descricao", "um local perigoso")
    prompt_pedido = (
        f"Você é {npc.nome}, {npc.ocupacao}. Personalidade: {npc.personalidade}. "
        f"Você está em perigo no ambiente: {ctx_bioma}. "
        f"Em 2 frases curtas, peça urgentemente ajuda a {personagem.nome} para enfrentar "
        f"criaturas que te ameaçam. Fale em primeira pessoa, com urgência e emoção autêntica."
    )
    pedido = _chamar_llm_narrativa(
        prompt_pedido, jrn.obter_contexto_compacto(),
        num_predict=LLM_TOKENS_NPC, stream=False
    )

    print(f"\n  {'═'*58}")
    print(f"  ⚔  MISSÃO: Ajudar {npc.nome}")
    print(f"  {'═'*58}")
    print(f"  [33m{npc.nome}:[0m {pedido or 'Por favor, me ajude! Estão me atacando!'}")
    print(f"\n  Você terá que enfrentar 3 ondas de inimigos do bioma.")
    print(f"  [Enter para aceitar  |  'não' para recusar]")

    resp = input(f"  {personagem.nome} > ").strip().lower()
    if resp in ("não","nao","n","no"):
        print(f"  Você declina o pedido de {npc.nome}.")
        npc.ajuda_disponivel = False
        npc.ajuda_resultado = "fuga"
        npc.ganhar_amizade(-5, "recusou ajudar")
        return

    # ── 3 rounds de combate ──────────────────────────────────
    vitorias = 0
    fugiu = False
    nivel = get_dificuldade_atual()

    for round_num in range(1, 4):
        inimigo = escolher_inimigo_bioma(bioma, nivel)
        print(f"\n  {'─'*58}")
        print(f"  ⚔  Onda {round_num}/3  —  {inimigo.nome} aparece!")
        print(f"  {'─'*58}")

        resultado = iniciar_combate(personagem, inimigo)

        if resultado == "derrota":
            # Morte real — retorna para o loop principal lidar
            npc.ajuda_disponivel = False
            npc.ajuda_resultado = "fuga"
            return

        elif resultado == "fuga":
            fugiu = True
            print(f"\n  [33mVocê recuou na batalha {round_num}...[0m")
            break

        else:  # vitoria
            vitorias += 1
            personagem.regenerar_pos_batalha()
            if round_num < 3:
                print(f"\n  [32mOnda {round_num} vencida! Mais uma se aproxima...[0m")

    # ── Reação do NPC ────────────────────────────────────────
    npc.ajuda_disponivel = False

    if fugiu:
        npc.ajuda_resultado = "fuga"
        # NPC fica chateado/zangado
        prompt_reacao = (
            f"Você é {npc.nome}, {npc.ocupacao}. Personalidade: {npc.personalidade}. "
            f"{personagem.nome} estava te ajudando mas fugiu da luta após {vitorias} de 3 ondas, "
            f"te deixando em perigo. "
            f"Em 2 frases curtas e em primeira pessoa, expresse raiva ou decepção genuína. "
            f"Seja autêntico com sua personalidade — não seja genérico."
        )
        npc.ganhar_amizade(-10, "fugiu da missão de ajuda")
        tag = "[31m😠"
    else:
        npc.ajuda_resultado = "vitoria"
        # NPC elogia o jogador
        prompt_reacao = (
            f"Você é {npc.nome}, {npc.ocupacao}. Personalidade: {npc.personalidade}. "
            f"{personagem.nome} acabou de vencer 3 ondas de inimigos para te salvar. "
            f"Em 2 frases curtas e em primeira pessoa, elogie genuinamente e com emoção. "
            f"Seja autêntico com sua personalidade — não seja genérico."
        )
        npc.ganhar_amizade(35, "venceu missão de ajuda")
        # Bônus para o jogador
        bonus_tacito = 1.0
        personagem.ganhar_conhecimento_tacito(bonus_tacito, f"missão de {npc.nome}")
        cura = round(personagem.vigor * 2.0, 1)
        personagem.pv_atual = min(personagem.pv_max, personagem.pv_atual + cura)
        print(f"  [32m{npc.nome} cuida dos seus ferimentos. +{cura:.0f} PV[0m")
        tag = "[32m🎉"

    reacao = _chamar_llm_narrativa(
        prompt_reacao, jrn.obter_contexto_compacto(),
        num_predict=LLM_TOKENS_NPC, stream=False
    )
    print(f"\n  {tag} {npc.nome}:[0m {reacao or ('Inacreditável...' if fugiu else 'Obrigado de verdade!')}")

    jrn.registrar_evento(
        "combate",
        f"{personagem.nome} {'fugiu de' if fugiu else 'completou'} missão de {npc.nome}.",
        {"vitorias": vitorias, "fugiu": fugiu, "amizade_nova": npc.amizade}
    )
    jrn.atualizar_personagem(personagem.to_dict())


def _evento_escolha_item_boss(personagem, bioma: dict) -> None:
    opcoes = sortear_loot_boss(bioma)
    if not opcoes:
        print("  Nenhum item disponível como recompensa.")
        return

    print(f"\n{'═'*58}")
    print(f"  🏆 {t('boss.reward')}")
    print(f"{'═'*58}")
    for i, item in enumerate(opcoes):
        hab = f" | hab: {item.habilidades_item}" if item.habilidades_item else ""
        print(f"  [{i+1}] {item.nome:25} dano={item.dano_arma:.0f} "
              f"def={item.defesa:.0f}{hab}")
        print(f"       {item.descricao}")

    while True:
        op = input("  Sua escolha > ").strip()
        if op.isdigit() and 1 <= int(op) <= len(opcoes):
            escolhido = opcoes[int(op) - 1]
            break
        print("  Inválido.")

    if personagem.inventario_cheio():
        print(f"\n  Inventário cheio ({personagem.slots_disponiveis} slots).")
        print("  Descarte um item para carregar a recompensa:")
        for i, it in enumerate(personagem.inventario):
            print(f"    [{i+1}] {it.nome}")
        print(f"    [0] Recusar a recompensa")
        while True:
            op = input("  > ").strip()
            if op == "0":
                print("  Recompensa recusada.")
                return
            if op.isdigit() and 1 <= int(op) <= len(personagem.inventario):
                descartado = personagem.inventario.pop(int(op) - 1)
                print(f"  {descartado.nome} descartado.")
                break
            print("  Inválido.")

    from _item_ui import receber_item
    import jornada as jrn
    receber_item(personagem, escolhido)
    jrn.registrar_item_obtido(escolhido.nome, f"boss_{bioma['nome']}")
    jrn.atualizar_personagem(personagem.to_dict())


# ══════════════════════════════════════════════════════════════
#  ESCOLHA DO PRÓXIMO BIOMA
# ══════════════════════════════════════════════════════════════

def escolher_proximo_bioma(bioma_atual: str) -> str:
    print(f"\n{'═'*58}")
    print(f"  🗺️  {t('biome.choose_next')}")
    print(f"{'═'*58}")
    disponiveis = {k: v for k, v in BIOMAS.items() if k != bioma_atual}
    chaves = list(disponiveis.keys())
    for i, (chave, b) in enumerate(disponiveis.items()):
        print(f"  [{i+1:2}] {b['cor']} {b['nome']:35} ({b['tipo_inimigo']})")

    while True:
        op = input("  > ").strip()
        if op.isdigit() and 1 <= int(op) <= len(chaves):
            escolhido = chaves[int(op) - 1]
            print(f"\n  → Rumo a: {BIOMAS[escolhido]['nome']}")
            return escolhido
        print("  Inválido.")


if __name__ == "__main__":
    listar_biomas()


# ══════════════════════════════════════════════════════════════
#  API pública para reuso fora do Cenário A (ex: mundo aberto)
# ══════════════════════════════════════════════════════════════

def iniciar_menu_npc(personagem, npc, bioma_ctx: dict | None = None) -> None:
    """
    Abre o menu pós-NPC (conversar / trocar item / treinar / ajuda contextual /
    pedir segredo) com um NPC específico, fora do contexto de biomas A.

    Usado pelo Cenário C para que NPCs migrados (Breno, Mira, Capitão Duras,
    Eilara, Ferran, Sombra) tenham o mesmo menu rico ao serem encontrados em
    coords fixas no mundo aberto.

    bioma_ctx: dict opcional com 'descricao', 'inimigos', 'boss', 'npc_evento'.
    Se None, usa contexto mínimo (sem loot por bioma — segredos com presente
    caem em fallback do catálogo geral de itens).
    """
    if bioma_ctx is None:
        bioma_ctx = {"descricao": "", "inimigos": [], "boss": None,
                     "npc_evento": []}
    _evento_npc(personagem, bioma_ctx, npc=npc)
