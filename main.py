"""
main.py — RPG LLM entry point
"""
import os, sys, requests

# ── Force UTF-8 on Windows terminal ─────────────────────────
# Prevents UnicodeEncodeError when printing emoji on cp1252 terminals.
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace"
    )
    # Also set console code page to UTF-8
    os.system("chcp 65001 >nul 2>&1")
import i18n
from i18n import t, set_lang, LANG
from config import CHARS_POR_CONHECIMENTO, FREQUENCIA_DESCANSO

# ── Debug automático via env var ─────────────────────────────
_DEBUG_NIVEL = int(os.environ.get("DEBUG_RPG", "0"))
if _DEBUG_NIVEL > 0:
    import debugger
    debugger.ativar(_DEBUG_NIVEL)
    debugger.instalar()

BANNER = """
\033[36m
  ██████╗ ██████╗  ██████╗     ██╗     ██╗     ███╗   ███╗
  ██╔══██╗██╔══██╗██╔════╝     ██║     ██║     ████╗ ████║
  ██████╔╝██████╔╝██║  ███╗    ██║     ██║     ██╔████╔██║
  ██╔══██╗██╔═══╝ ██║   ██║    ██║     ██║     ██║╚██╔╝██║
  ██║  ██║██║     ╚██████╔╝    ███████╗███████╗██║ ╚═╝ ██║
  ╚═╝  ╚═╝╚═╝      ╚═════╝     ╚══════╝╚══════╝╚═╝     ╚═╝
\033[0m
  \033[33m  -----------------------------------------------\033[0m
  \033[90m  ..........................................\033[0m
"""

def _info_text() -> str:
    lang = i18n.LANG
    if lang == "en":
        return """
\033[36m╔══════════════════════════════════════════════════════════╗
║                  HOW TO PLAY — INFORMATION               ║
╚══════════════════════════════════════════════════════════╝\033[0m

\033[1mOBJECTIVE\033[0m
  Explore biomes, win 10 battles per biome (including a boss)
  and evolve your character throughout the journey.

\033[1mCHARACTERS\033[0m
  • Kael — Path of Combat: High Physical Body, more HP and damage.
    Shorter action limit (low Knowledge).
  • Lyra — Path of Wisdom: High Knowledge, more characters per action.
    Lower HP, but high Psique for arcane abilities.

\033[1mCOMBAT\033[0m
  Describe your action in free text. The more creative and
  efficient the attack, the higher the damage dealt.

  Action character limit = Knowledge × {chars}
  (Increasing Knowledge expands what you can describe.)

  If your action exceeds the limit:
  \033[31m  "You don't have enough knowledge to execute this move."\033[0m

\033[1mMAIN ATTRIBUTES\033[0m
  • Physical Body (Strength + Vigor) — HP and base damage
  • Knowledge (Tacit/2 + Explicit/3) — action limit
  • Psique (Mana) — used for active abilities

\033[1mPSIQUE (MANA)\033[0m
  Active abilities consume Psique.
  Regenerates 10% after each battle. Full restore when sleeping.

\033[1mINVENTORY\033[0m
  3 base slots. "Extra Backpack" and "Utility Belt" add +1 slot each (max 5).
  Consumables do NOT use inventory slots.

\033[1mSKILLS\033[0m
  • Active  (max 4) — cost Psique, unlocked by item mastery
  • Passive (max 3) — always active, unlocked by item mastery
  • Extras  (no limit) — small bonuses, acquired on the journey

\033[1mBIOME\033[0m
  Each biome has 10 battles:
  • Battle 5  → NPC encounter (talk, trade item, help)
  • Battle 10 → BOSS (scaled to your level)
  • Boss win  → Choose 1 of 3 reward items

  Train (+Strength or +Vigor) and Sleep (full restore)
  available every {freq}rd battle (except battles 5 and 10).
  After each battle: view your attributes and use consumables.

\033[1mCOMBAT COMMANDS\033[0m
  Type your action freely.
  "flee" / "run" / "escape" → attempt to flee.

\033[90m  Press Enter to return to menu.\033[0m
""".format(chars=CHARS_POR_CONHECIMENTO, freq=FREQUENCIA_DESCANSO)
    else:
        return """
\033[36m╔══════════════════════════════════════════════════════════╗
║                  COMO JOGAR — INFORMAÇÕES                ║
╚══════════════════════════════════════════════════════════╝\033[0m

\033[1mOBJETIVO\033[0m
  Explore biomas, vença 10 batalhas por bioma (incluindo um boss)
  e evolua seu personagem ao longo da jornada.

\033[1mPERSONAGENS\033[0m
  • Kael — Caminho da Luta: Alto Corpo Físico, mais PV e dano.
    Limite de ação mais curto (Conhecimento baixo).
  • Lyra — Caminho da Sabedoria: Alto Conhecimento, mais caracteres.
    PV menor, mas Psiquê elevada para habilidades arcanas.

\033[1mCOMBATE\033[0m
  Descreva sua ação em texto livre. Quanto mais criativo e
  eficiente o ataque, maior o dano causado.

  Limite de caracteres por ação = Conhecimento × {chars}
  Se sua ação ultrapassar o limite:
  \033[31m  "Você não tem conhecimento o bastante para executar este movimento."\033[0m

\033[1mATRIBUTOS PRINCIPAIS\033[0m
  • Corpo Físico (Força + Vigor) — PV e dano base
  • Conhecimento (Tácito/2 + Explícito/3) — limite de ação
  • Psiquê (Mana) — usada para habilidades de ativar

\033[1mPSIQUÊ (MANA)\033[0m
  Habilidades de ativar consomem Psiquê.
  Regenera 10% após cada batalha. Recupera 100% dormindo.

\033[1mINVENTÁRIO\033[0m
  3 slots base. Mochila Extra e Cinto de Utilidades adicionam +1 cada (máx 5).
  Consumíveis NÃO ocupam slots de inventário.

\033[1mHABILIDADES\033[0m
  • Ativar  (máx. 4) — custam Psiquê, desbloqueadas por maestria
  • Passivas (máx. 3) — sempre ativas, desbloqueadas por maestria
  • Extras  (sem limite) — bônus pequenos, adquiridas na jornada

\033[1mBIOMA\033[0m
  Cada bioma tem 10 batalhas:
  • Batalha 5  → Encontro com NPC (conversar, trocar item, ajudar)
  • Batalha 10 → BOSS (escalonado ao seu nível)
  • Vitória boss → Escolha 1 entre 3 itens de recompensa
  Após cada batalha: veja seus atributos e use consumíveis.

\033[1mCOMANDOS EM COMBATE\033[0m
  Digite sua ação livremente.
  "fugir" / "fuga" / "correr" → tenta fugir.

\033[90m  Pressione Enter para voltar ao menu.\033[0m
""".format(chars=CHARS_POR_CONHECIMENTO, freq=FREQUENCIA_DESCANSO)


BIOMAS_INICIAIS = ["floresta", "deserto", "pantano", "montanha",
                   "caverna", "ruinas_arcanas"]


# ══════════════════════════════════════════════════════════════
#  MENUS
# ══════════════════════════════════════════════════════════════

def _menu_idioma() -> None:
    """Language / Idioma selector — bilingual by design."""
    while True:
        os.system("clear" if os.name == "posix" else "cls")
        print(BANNER)
        print("  ┌──────────────────────────────────────┐")
        print(f"  │  {t('menu.choose_language'):<38}│")
        print("  ├──────────────────────────────────────┤")
        print("  │  [1]  Português 🇧🇷                   │")
        print("  │  [2]  English  🇺🇸                    │")
        print(f"  │  [0]  {t('menu.back'):<33}│")
        print("  └──────────────────────────────────────┘")

        op = input("\n  > ").strip()
        if op == "1":
            set_lang("pt")
            print(f"\n  {t('menu.language_set')}")
            input(f"  {t('sys.enter_continue')}")
            return
        elif op == "2":
            set_lang("en")
            print(f"\n  {t('menu.language_set')}")
            input(f"  {t('sys.enter_continue')}")
            return
        elif op == "0":
            return


def _menu_configuracoes() -> None:
    while True:
        os.system("clear" if os.name == "posix" else "cls")
        print(BANNER)
        print(f"  ╔══════════════════════════════╗")
        print(f"  ║  {t('menu.settings_title'):<28}║")
        print(f"  ╠══════════════════════════════╣")
        print(f"  ║  [1]  {t('menu.language'):<24}║")
        print(f"  ║  [0]  {t('menu.back'):<24}║")
        print(f"  ╚══════════════════════════════╝")

        op = input("\n  > ").strip()
        if op == "1":
            _menu_idioma()
        elif op == "0":
            return


def menu_principal() -> str:
    while True:
        os.system("clear" if os.name == "posix" else "cls")
        print(BANNER)
        print(f"  ┌──────────────────────────────┐")
        from debugger import nivel_atual as _dbg_nivel
        dbg_status = f"ON [{_dbg_nivel()}]" if _dbg_nivel() > 0 else "off"
        print(f"  │  [1]  {t('menu.start'):<24}│")
        print(f"  │  [2]  {t('menu.settings'):<24}│")
        print(f"  │  [3]  {t('menu.info'):<24}│")
        print(f"  │  [5]  Debug: {dbg_status:<20}│")
        print(f"  │  [4]  {t('menu.quit'):<24}│")
        print(f"  └──────────────────────────────┘")

        op = input("\n  > ").strip()
        if op == "1":
            return "start"
        elif op == "2":
            _menu_configuracoes()
        elif op == "3":
            os.system("clear" if os.name == "posix" else "cls")
            print(_info_text())
            input()
        elif op == "5":
            import debugger
            debugger.menu_debug()
        elif op == "4":
            print(f"\n  {t('npc.farewell')}\n")
            sys.exit(0)


# ══════════════════════════════════════════════════════════════
#  CHARACTER AND BIOME SELECTION
# ══════════════════════════════════════════════════════════════

def _mostrar_resumo_personagem(p) -> None:
    """Exibe habilidades e item equipado após escolher o personagem."""
    from i18n import name as iname
    print()
    if p.item_equipado:
        print(f"  [{p.nome} {t('attr.equipped')}: {iname(p.item_equipado)}]")
    for h in p.habilidades_passivas:
        print(f"  [+ {iname(h)} ({t('attr.passive').lower()})]")
    for h in p.habilidades_extras:
        print(f"  [+ {iname(h)} ({t('attr.extras').lower()})]")
    print()


def pedir_nome() -> str:
    print(f"\n\033[1m  {t('char.choose_name')}\033[0m")
    while True:
        nome = input(f"  {t('char.name_prompt')} > ").strip()
        if nome:
            return nome
        print(f"  {t('sys.invalid')}")


def escolher_personagem():
    from personagens import criar_kael, criar_lyra
    from combate import limite_chars

    nome = pedir_nome()

    print(f"\n\033[1m  {t('char.choose_path')}\033[0m\n")

    kael_tmp = criar_kael()
    lyra_tmp = criar_lyra()

    print(f"  [1] \033[33m{t('char.path_fight')}\033[0m")
    print(f"      {t('attr.body')}: {kael_tmp.corpo_fisico:.0f} | "
          f"HP: {kael_tmp.pv_max:.0f} | "
          f"{t('attr.knowledge')}: {kael_tmp.conhecimento:.1f} | "
          f"{t('combat.action_limit')}: {limite_chars(kael_tmp)} {t('combat.chars')}")
    print(f"      \"{kael_tmp.descricao}\"")
    print()
    print(f"  [2] \033[36m{t('char.path_wisdom')}\033[0m")
    print(f"      {t('attr.body')}: {lyra_tmp.corpo_fisico:.0f} | "
          f"HP: {lyra_tmp.pv_max:.0f} | "
          f"{t('attr.knowledge')}: {lyra_tmp.conhecimento:.1f} | "
          f"{t('combat.action_limit')}: {limite_chars(lyra_tmp)} {t('combat.chars')}")
    print(f"      \"{lyra_tmp.descricao}\"")

    while True:
        op = input("\n  > ").strip()
        if op == "1":
            p = criar_kael(nome_jogador=nome)
            print(f"\n  {t('char.welcome')}, \033[33m{nome}\033[0m!")
            _mostrar_resumo_personagem(p)
            return p
        if op == "2":
            p = criar_lyra(nome_jogador=nome)
            print(f"\n  {t('char.welcome')}, \033[36m{nome}\033[0m!")
            _mostrar_resumo_personagem(p)
            return p
        print(f"  {t('sys.invalid')}")


def escolher_bioma_inicial() -> str:
    from biomas import BIOMAS

    print(f"\n\033[1m  {t('biome.choose_initial')}\033[0m\n")
    for i, chave in enumerate(BIOMAS_INICIAIS):
        b = BIOMAS[chave]
        nome_b = b.get("name_en", b["nome"]) if i18n.LANG == "en" else b["nome"]
        print(f"  [{i+1}] {b['cor']}  {nome_b:35} ({b['tipo_inimigo']})")
        print(f"       {b['descricao']}")
        print()

    while True:
        op = input("  > ").strip()
        if op.isdigit() and 1 <= int(op) <= len(BIOMAS_INICIAIS):
            return BIOMAS_INICIAIS[int(op) - 1]
        print(f"  {t('sys.invalid')}")


# ══════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════

def main():
    import llm_backend as lb
    import importlib; importlib.reload(lb)

    # Verifica conectividade apenas para o backend configurado
    if lb._BACKEND == "ollama":
        try:
            requests.get("http://localhost:11434", timeout=3)
        except Exception:
            print(f"\n  \033[31m⚠  {t('sys.ollama_warn')}\033[0m\n")
    elif lb._BACKEND == "lmstudio":
        try:
            requests.get(lb._LM_BASE, timeout=3)
        except Exception:
            print(f"\n  \033[33m⚠  LM Studio não detectado em {lb._LM_BASE}\033[0m")
            print(f"  \033[90m     Abra o LM Studio → Local Server → Start Server\033[0m\n")

    info = lb.get_info()
    print(f"  \033[90m[{info['backend'].upper()}] {info['model']}\033[0m")

    menu_principal()

    import jornada as jrn
    from biomas import executar_bioma, escolher_proximo_bioma

    personagem  = escolher_personagem()

    # ── Inicia log de sessão AQUI — antes de qualquer modo de jogo ──
    # Garante que TODA linha do CSV (questionário, combate, mundo) tem o modelo correto
    import session_log as _slog
    import llm_backend as _lb
    import importlib as _il
    _il.reload(_lb)
    _MODELO_SESSAO = _lb.obter_modelo_atual()
    _slog.iniciar_sessao(personagem.nome, _MODELO_SESSAO)
    print(f"  \033[90m[LOG] Modelo: {_MODELO_SESSAO}\033[0m")

    # ── Questionário inicial (agora APÓS log iniciado com modelo correto) ──
    from perguntas_iniciais import executar_perguntas_iniciais
    executar_perguntas_iniciais(personagem)

    # ── Seleção de modo de jogo ───────────────────────────
    print(f"\n  \033[1m  Escolha o modo de jogo:\033[0m")
    print(f"  [1] Cenário A/B — Biomas (combate e diálogo)")
    print(f"  [2] Cenário C   — Mundo Aberto (exploração livre)")
    print()
    modo = input("  > ").strip()

    if modo == "2":
        from mundo_aberto import executar_cenario_c
        resultado = executar_cenario_c(personagem)
        print(f"\n  Jornada encerrada: {resultado}")
        try:
            _slog.exibir_stats_sessao()
        except Exception:
            pass
        return

    # Cenário A/B — fluxo normal
    bioma_atual = escolher_bioma_inicial()
    biomas_ok   = []

    jrn.inicializar_jornada(personagem.to_dict(), bioma_atual)

    print("\n" + personagem.ficha())
    input(f"\n  {t('sys.enter_continue')}")

    while True:
        resultado = executar_bioma(personagem, bioma_atual)

        if resultado == "morte":
            print(f"\n  \033[31m{t('sys.game_over_title')}\033[0m")
            print(f"  {t('sys.biomes_done')}: {len(biomas_ok)} — {biomas_ok}")
            input(f"\n  {t('sys.press_menu')}")
            main()
            return

        biomas_ok.append(bioma_atual)
        from biomas import set_biomas_completados
        set_biomas_completados(len(biomas_ok))

        print(f"\n  \033[32m{t('biome.completed')}\033[0m "
              f"{t('sys.biomes_done')}: {len(biomas_ok)}")
        print(personagem.ficha())

        bioma_atual = escolher_proximo_bioma(bioma_atual)


if __name__ == "__main__":
    main()