"""
i18n.py
─────────────────────────────────────────────────────────────
Internacionalização do jogo.
Idiomas suportados: "pt" (português) | "en" (inglês)

Uso:
    from i18n import t, set_lang, LANG
    t("combat.your_action")   → traduz para o idioma atual
    set_lang("en")            → muda o idioma globalmente
─────────────────────────────────────────────────────────────
"""

# Idioma ativo — alterado por set_lang()
LANG: str = "pt"

# ══════════════════════════════════════════════════════════════
#  STRINGS DE INTERFACE
# ══════════════════════════════════════════════════════════════

_STRINGS: dict = {

    # ── Menu principal ──────────────────────────────────────
    "menu.start":           {"pt": "Iniciar Jogo",        "en": "Start Game"},
    "menu.settings":        {"pt": "Configurações",       "en": "Settings"},
    "menu.info":            {"pt": "Info",                 "en": "Info"},
    "menu.quit":            {"pt": "Sair",                 "en": "Quit"},
    "menu.language":        {"pt": "Idioma",               "en": "Language"},
    "menu.language_set":    {"pt": "Idioma definido: Português",
                             "en": "Language set: English"},
    "menu.choose_language": {"pt": "Escolha o idioma / Choose language:",
                             "en": "Escolha o idioma / Choose language:"},
    "menu.settings_title":  {"pt": "CONFIGURAÇÕES",       "en": "SETTINGS"},
    "menu.back":            {"pt": "Voltar",               "en": "Back"},

    # ── Seleção de personagem ───────────────────────────────
    "char.choose_name":     {"pt": "Como você se chama, aventureiro?",
                             "en": "What is your name, adventurer?"},
    "char.name_prompt":     {"pt": "Nome",                 "en": "Name"},
    "char.choose_path":     {"pt": "Escolha seu caminho:", "en": "Choose your path:"},
    "char.path_fight":      {"pt": "Caminho da Luta",      "en": "Path of Combat"},
    "char.path_wisdom":     {"pt": "Caminho da Sabedoria", "en": "Path of Wisdom"},
    "char.welcome":         {"pt": "Bem-vindo à jornada",  "en": "Welcome to the journey"},

    # ── Seleção de bioma ────────────────────────────────────
    "biome.choose_initial": {"pt": "Escolha seu bioma inicial:",
                             "en": "Choose your starting biome:"},
    "biome.choose_next":    {"pt": "Escolha o próximo bioma:",
                             "en": "Choose the next biome:"},
    "biome.completed":      {"pt": "Bioma concluído!",     "en": "Biome completed!"},
    "biome.enemies":        {"pt": "Inimigos predominantes",
                             "en": "Predominant enemies"},
    "biome.battle":         {"pt": "Batalha",              "en": "Battle"},
    "biome.boss_battle":    {"pt": "BATALHA FINAL — BOSS DO BIOMA!",
                             "en": "FINAL BATTLE — BIOME BOSS!"},

    # ── Combate ─────────────────────────────────────────────
    "combat.your_action":   {"pt": "Sua ação",             "en": "Your action"},
    "combat.flee":          {"pt": "Você foge do combate!","en": "You flee from combat!"},
    "combat.flee_cmd":      {"pt": "fugir,fuga,correr",    "en": "flee,run,escape"},
    "combat.no_knowledge":  {"pt": "Você não tem conhecimento o bastante para executar este movimento.",
                             "en": "You don't have enough knowledge to execute this move."},
    "combat.limit":         {"pt": "Limite",               "en": "Limit"},
    "combat.your_act":      {"pt": "Sua ação",             "en": "Your action"},
    "combat.rewrite":       {"pt": "Reescreva com até",    "en": "Rewrite with up to"},
    "combat.chars":         {"pt": "caracteres",           "en": "characters"},
    "combat.creativity":    {"pt": "Criatividade",         "en": "Creativity"},
    "combat.efficiency":    {"pt": "Eficiência",           "en": "Efficiency"},
    "combat.damage":        {"pt": "Dano causado",         "en": "Damage dealt"},
    "combat.victory":       {"pt": "VITÓRIA!",             "en": "VICTORY!"},
    "combat.defeat":        {"pt": "DERROTA!",             "en": "DEFEAT!"},
    "combat.skill_menu":    {"pt": "Usar uma habilidade?", "en": "Use an ability?"},
    "combat.no_skill":      {"pt": "Nenhuma",              "en": "None"},
    "combat.skill_used":    {"pt": "ativada!",             "en": "activated!"},
    "combat.psique_return": {"pt": "Psiquê devolvida",     "en": "Psique returned"},
    "combat.action_limit":  {"pt": "Limite de ação",       "en": "Action limit"},
    "combat.loot":          {"pt": "Loot",                 "en": "Loot"},
    "combat.inv_full":      {"pt": "inventário cheio, item perdido.",
                             "en": "inventory full, item lost."},
    "combat.game_over":     {"pt": "Sua jornada termina aqui.",
                             "en": "Your journey ends here."},

    # ── Descanso ────────────────────────────────────────────
    "rest.title":           {"pt": "DESCANSO — Você tem um momento de respiro.",
                             "en": "REST — You have a moment to breathe."},
    "rest.train":           {"pt": "Treinar  — +1.0 em Força ou Vigor",
                             "en": "Train    — +1.0 Strength or Vigor"},
    "rest.sleep":           {"pt": "Dormir   — restaura tudo + organiza o que aprendeu (+Conhecimento)",
                             "en": "Sleep    — restores everything + organizes what you learned (+Knowledge)"},
    "rest.train_what":      {"pt": "O que você treina?",  "en": "What do you train?"},
    "rest.strength":        {"pt": "Força (+1.0)",         "en": "Strength (+1.0)"},
    "rest.vigor":           {"pt": "Vigor (+1.0)",         "en": "Vigor (+1.0)"},
    "rest.sleep_narr":      {"pt": "Enquanto dorme, sua mente organiza as experiências do dia...",
                             "en": "As you sleep, your mind organizes the day's experiences..."},
    "rest.knowledge_gain":  {"pt": "Conhecimento Explícito",
                             "en": "Explicit Knowledge"},
    "rest.knowledge_total": {"pt": "Conhecimento total agora",
                             "en": "Total knowledge now"},

    # ── Pós-batalha ─────────────────────────────────────────
    "post.title":           {"pt": "PÓS-BATALHA",         "en": "POST-BATTLE"},
    "post.view_attrs":      {"pt": "Ver atributos completos",
                             "en": "View full attributes"},
    "post.use_item":        {"pt": "Usar item consumível", "en": "Use consumable item"},
    "post.continue":        {"pt": "Continuar",            "en": "Continue"},
    "post.no_consumables":  {"pt": "Você não tem itens consumíveis.",
                             "en": "You have no consumable items."},
    "post.consumables":     {"pt": "Consumíveis disponíveis:",
                             "en": "Available consumables:"},

    # ── NPC ─────────────────────────────────────────────────
    "npc.encounter":        {"pt": "ENCONTRO",             "en": "ENCOUNTER"},
    "npc.talk":             {"pt": "Conversar",            "en": "Talk"},
    "npc.trade":            {"pt": "Trocar item",          "en": "Trade item"},
    "npc.help":             {"pt": "Ajudar em uma situação","en": "Help with a situation"},
    "npc.proceed":          {"pt": "Prosseguir para as lutas",
                             "en": "Proceed to battles"},
    "npc.farewell":         {"pt": "Você se despede e segue em frente.",
                             "en": "You say goodbye and move forward."},
    "npc.talk_prompt":      {"pt": "(Enter vazio = voltar ao menu do NPC)",
                             "en": "(Empty Enter = back to NPC menu)"},
    "npc.help_prompt":      {"pt": "Como você ajuda?",     "en": "How do you help?"},
    "npc.no_items":         {"pt": "Você não tem itens para trocar.",
                             "en": "You have no items to trade."},
    "npc.offers":           {"pt": "oferece",              "en": "offers"},
    "npc.trade_which":      {"pt": "Qual item você oferece em troca?",
                             "en": "Which item do you offer in exchange?"},
    "npc.trade_cancel":     {"pt": "Troca cancelada.",     "en": "Trade cancelled."},
    "npc.trade_done":       {"pt": "Troca realizada",      "en": "Trade completed"},
    "npc.no_intervene":     {"pt": "Você decide não intervir desta vez.",
                             "en": "You decide not to intervene this time."},

    # ── Boss reward ─────────────────────────────────────────
    "boss.reward":          {"pt": "BOSS DERROTADO! Escolha sua recompensa:",
                             "en": "BOSS DEFEATED! Choose your reward:"},
    "boss.inv_full":        {"pt": "Inventário cheio. Descarte um item:",
                             "en": "Inventory full. Discard an item:"},
    "boss.refuse":          {"pt": "Recompensa recusada.",  "en": "Reward refused."},
    "boss.added":           {"pt": "adicionado ao inventário!",
                             "en": "added to inventory!"},

    # ── Ficha / atributos ───────────────────────────────────
    "attr.hp":              {"pt": "PV",                   "en": "HP"},
    "attr.psique":          {"pt": "Psiquê",               "en": "Psique"},
    "attr.strength":        {"pt": "Força",                "en": "Strength"},
    "attr.vigor":           {"pt": "Vigor",                "en": "Vigor"},
    "attr.body":            {"pt": "Corpo Físico",         "en": "Physical Body"},
    "attr.tac_know":        {"pt": "Conh. Tácito",         "en": "Tacit Know."},
    "attr.exp_know":        {"pt": "Conh. Explícito",      "en": "Explicit Know."},
    "attr.knowledge":       {"pt": "Conhecimento",         "en": "Knowledge"},
    "attr.psique_base":     {"pt": "Psiquê Base",          "en": "Base Psique"},
    "attr.psique_total":    {"pt": "Psiquê Total",         "en": "Total Psique"},
    "attr.damage":          {"pt": "Dano Pessoal",         "en": "Personal Damage"},
    "attr.defense":         {"pt": "Defesa Base",          "en": "Base Defense"},
    "attr.equipped":        {"pt": "Item",                 "en": "Item"},
    "attr.inventory":       {"pt": "Inv",                  "en": "Inv"},
    "attr.slots":           {"pt": "slots",                "en": "slots"},
    "attr.consumables":     {"pt": "consumíveis",          "en": "consumables"},
    "attr.activate":        {"pt": "Ativar",               "en": "Activate"},
    "attr.passive":         {"pt": "Passiva",              "en": "Passive"},
    "attr.extras":          {"pt": "Extras",               "en": "Extras"},
    "attr.none":            {"pt": "Nenhum",               "en": "None"},
    "attr.path":            {"pt": "CAMINHO",              "en": "PATH"},

    # ── Info screen ─────────────────────────────────────────
    "info.objective":       {"pt": "OBJETIVO",             "en": "OBJECTIVE"},
    "info.characters":      {"pt": "PERSONAGENS",          "en": "CHARACTERS"},
    "info.combat":          {"pt": "COMBATE",              "en": "COMBAT"},
    "info.attributes":      {"pt": "ATRIBUTOS PRINCIPAIS", "en": "MAIN ATTRIBUTES"},
    "info.psique_mana":     {"pt": "PSIQUÊ (MANA)",        "en": "PSIQUE (MANA)"},
    "info.inventory":       {"pt": "INVENTÁRIO",           "en": "INVENTORY"},
    "info.skills":          {"pt": "HABILIDADES",          "en": "SKILLS"},
    "info.biome":           {"pt": "BIOMA",                "en": "BIOME"},
    "info.commands":        {"pt": "COMANDOS EM COMBATE",  "en": "COMBAT COMMANDS"},

    # ── Sistema ─────────────────────────────────────────────
    "sys.invalid":          {"pt": "Opção inválida.",      "en": "Invalid option."},
    "sys.enter_continue":   {"pt": "Pressione Enter para continuar...",
                             "en": "Press Enter to continue..."},
    "sys.game_over_title":  {"pt": "FIM DE JOGO.",         "en": "GAME OVER."},
    "sys.biomes_done":      {"pt": "Biomas completados",   "en": "Biomes completed"},
    "sys.press_menu":       {"pt": "Pressione Enter para voltar ao menu...",
                             "en": "Press Enter to return to menu..."},
    "sys.ollama_warn":      {"pt": "Ollama não detectado em localhost:11434.\n     Inicie com: ollama serve\n     Modelo:     ollama pull llama3.1:8b",
                             "en": "Ollama not detected at localhost:11434.\n     Start with: ollama serve\n     Model:      ollama pull llama3.1:8b"},
}

# ══════════════════════════════════════════════════════════════
#  API
# ══════════════════════════════════════════════════════════════

def set_lang(lang: str) -> None:
    """Define o idioma ativo globalmente. 'pt' ou 'en'."""
    global LANG
    if lang in ("pt", "en"):
        LANG = lang


def t(key: str, lang: str = None) -> str:
    """
    Retorna a string traduzida para o idioma atual (ou `lang` se fornecido).
    Se a chave não existir, retorna a própria chave entre colchetes.
    """
    l = lang or LANG
    entry = _STRINGS.get(key)
    if entry is None:
        return f"[{key}]"
    return entry.get(l, entry.get("pt", f"[{key}]"))


def name(obj, lang: str = None) -> str:
    """
    Retorna o nome traduzido de um objeto de jogo (item, inimigo, habilidade, bioma).
    Espera que o objeto tenha atributos `name_pt` e `name_en`,
    ou apenas `nome` como fallback.
    """
    l = lang or LANG
    if l == "en" and hasattr(obj, "name_en") and obj.name_en:
        return obj.name_en
    if hasattr(obj, "name_pt") and obj.name_pt:
        return obj.name_pt
    return getattr(obj, "nome", str(obj))


if __name__ == "__main__":
    set_lang("pt")
    print(t("menu.start"), "|", t("combat.your_action"), "|", t("attr.hp"))
    set_lang("en")
    print(t("menu.start"), "|", t("combat.your_action"), "|", t("attr.hp"))
