"""
_item_ui.py
─────────────────────────────────────────────────────────────
Shared UI for receiving items — called from combate.py,
biomas.py (boss reward, NPC trade) and any other loot source.

receber_item(personagem, item):
  - If non-consumable and inventory full → ask discard or refuse
  - If consumable and bolsa full → ask discard from bolsa or refuse
  - Otherwise add silently

mostrar_inventario(personagem):
  - Shows inventory + bolsa + item skills/attributes
─────────────────────────────────────────────────────────────
"""

from i18n import t, name as iname


# ══════════════════════════════════════════════════════════════
#  RECEIVE ITEM  (unified entry point for all loot)
# ══════════════════════════════════════════════════════════════

def receber_item(personagem, item) -> bool:
    """
    Tries to add item to the right container.
    If full, shows a menu: discard one existing item or refuse the new one.
    Returns True if the item was received.
    """
    if item.tipo == "consumivel":
        return _receber_consumivel(personagem, item)
    else:
        return _receber_normal(personagem, item)


def _receber_normal(personagem, item) -> bool:
    if not personagem.inventario_cheio():
        personagem.inventario.append(item)
        _anunciar(item, personagem)
        return True

    print(f"\n  {'─'*52}")
    print(f"  📦 {t('boss.inv_full')}")
    print(f"  {t('attr.inventory')} ({len(personagem._itens_que_ocupam_slot())}/{personagem.slots_disponiveis}):")
    for i, it in enumerate(personagem._itens_que_ocupam_slot()):
        idx_real = personagem.inventario.index(it)
        hab_str = _hab_str(it)
        print(f"    [{i+1}] {iname(it):25} def={it.defesa:.0f} dano={it.dano_arma:.0f}{hab_str}")
    print(f"    [0] {t('boss.refuse')} ({iname(item)})")

    while True:
        op = input("  > ").strip()
        if op == "0":
            print(f"  {t('boss.refuse')}")
            return False
        if op.isdigit():
            slot_items = personagem._itens_que_ocupam_slot()
            idx_lista = int(op) - 1
            if 0 <= idx_lista < len(slot_items):
                descartado = slot_items[idx_lista]
                personagem.inventario.remove(descartado)
                personagem.inventario.append(item)
                print(f"  ↩  {iname(descartado)} descartado → ✦ {iname(item)} {t('boss.added')}")
                return True
        print(f"  {t('sys.invalid')}")


def _mostrar_efeitos(item) -> None:
    """Imprime os efeitos de um consumível."""
    b = item.bonus
    partes = []
    if b.get("cura"):        partes.append(f"+{b['cura']:.0f} PV")
    if b.get("cura_psique"): partes.append(f"+{b['cura_psique']:.1f} Psi")
    rm = b.get("remove_status", [])
    if rm == "todos":        partes.append("limpa todos os status")
    elif rm:                 partes.append(f"remove: {', '.join(rm)}")
    if partes:
        print(f"  [90mEfeitos: {' | '.join(partes)}[0m")


def _resumo_efeitos(item) -> str:
    """Retorna string resumida dos efeitos para listas."""
    b = item.bonus
    partes = []
    if b.get("cura"):        partes.append(f"+{b['cura']:.0f}PV")
    if b.get("cura_psique"): partes.append(f"+{b['cura_psique']:.1f}Psi")
    rm = b.get("remove_status", [])
    if rm == "todos":        partes.append("limpa status")
    elif rm:                 partes.append(f"rm:{','.join(rm)}")
    return " | ".join(partes) if partes else ""


def _receber_consumivel(personagem, item) -> bool:
    if not personagem.bolsa_cheia():
        personagem.bolsa.append(item)
        _anunciar(item, personagem)
        return True

    # Bolsa cheia — menu de troca
    print(f"\n  {'─'*52}")
    print(f"  🎒 Bolsa cheia! Recebeu: [33m{iname(item)}[0m")
    _mostrar_efeitos(item)
    print(f"  O que deseja fazer?")
    print(f"    [T] Trocar por um item da bolsa")
    print(f"    [F] Jogar fora {iname(item)} (recusar)")
    print(f"    [0] Cancelar (manter bolsa, perder item)")

    while True:
        op = input("  > ").strip().upper()

        if op in ("0", ""):
            print(f"  {iname(item)} deixado para trás.")
            return False

        if op == "F":
            print(f"  {iname(item)} descartado.")
            return False

        if op == "T":
            print(f"\n  Bolsa ({len(personagem.bolsa)}/{personagem.BOLSA_MAX}) — escolha o que trocar:")
            for i, it in enumerate(personagem.bolsa):
                efeitos = _resumo_efeitos(it)
                print(f"    [{i+1}] {iname(it):28} {efeitos}")
            print(f"    [0] Cancelar")
            while True:
                sub = input("  > ").strip()
                if sub == "0":
                    break
                if sub.isdigit():
                    idx = int(sub) - 1
                    if 0 <= idx < len(personagem.bolsa):
                        descartado = personagem.bolsa.pop(idx)
                        personagem.bolsa.append(item)
                        print(f"  ↩  {iname(descartado)} descartado  →  ✦ {iname(item)} guardado!")
                        return True
                print(f"  Opção inválida.")
            continue

        print(f"  Opção inválida. [T]rocar / [F]ora / [0]cancelar")


def comparar_itens(item_novo, item_atual) -> str:
    """Retorna string de comparação visual entre item novo e equipado atual."""
    if item_atual is None:
        return "  (sem item equipado para comparar)"

    lines = [f"  Comparação: {item_atual.nome}  →  {item_novo.nome}"]
    delta_dano = item_novo.dano_arma - item_atual.dano_arma
    delta_def  = item_novo.defesa    - item_atual.defesa

    if delta_dano != 0:
        cor   = "\033[32m" if delta_dano > 0 else "\033[31m"
        sinal = "+" if delta_dano > 0 else ""
        lines.append(f"  Dano:   {item_atual.dano_arma:.1f} → {item_novo.dano_arma:.1f}"
                     f" ({cor}{sinal}{delta_dano:.1f}\033[0m)")
    if delta_def != 0:
        cor   = "\033[32m" if delta_def > 0 else "\033[31m"
        sinal = "+" if delta_def > 0 else ""
        lines.append(f"  Defesa: {item_atual.defesa:.1f} → {item_novo.defesa:.1f}"
                     f" ({cor}{sinal}{delta_def:.1f}\033[0m)")
    if item_novo.requisito:
        lines.append(f"  Req.: {item_novo.requisito}")
    if item_novo.habilidades_item:
        lines.append(f"  Habs.: {', '.join(item_novo.habilidades_item)}")
    return "\n".join(lines)


def menu_usar_consumivel_combate(personagem) -> tuple:
    """Menu rápido para usar consumível DURANTE o combate. Retorna (usado, msg)."""
    if not personagem.bolsa:
        return False, "Bolsa vazia."

    print(f"\n  🎒 Bolsa ({len(personagem.bolsa)}/{personagem.BOLSA_MAX}):")
    for i, it in enumerate(personagem.bolsa):
        efeitos = []
        if it.bonus.get("cura"):       efeitos.append(f"+{it.bonus['cura']:.0f} PV")
        if it.bonus.get("cura_psique"):efeitos.append(f"+{it.bonus['cura_psique']:.1f} Psique")
        rm = it.bonus.get("remove_status", [])
        if rm == "todos": efeitos.append("limpa status")
        elif rm:          efeitos.append(f"remove: {', '.join(rm)}")
        print(f"    [{i+1}] {it.nome:28} {'  |  '.join(efeitos) or 'sem efeito'}")
    print("    [0] Cancelar")

    op = input("  > ").strip()
    if not op.isdigit() or int(op) == 0:
        return False, "Cancelado."
    idx = int(op) - 1
    ok, msg = personagem.usar_consumivel(idx)
    if ok:
        import jornada as jrn
        jrn.atualizar_personagem(personagem.to_dict())
    return ok, msg


def menu_equipar_inventario(personagem) -> bool:
    """Menu para equipar item do inventário. Retorna True se equipou."""
    equipaveis = [i for i in personagem.inventario
                  if i.tipo in ("arma", "armadura", "acessorio")]
    if not equipaveis:
        print("  Nenhum item equipável no inventário.")
        return False

    print(f"\n  📦 Equipar item:")
    for i, it in enumerate(equipaveis):
        print(f"    [{i+1}] {it.nome:30} dano={it.dano_arma:.1f} def={it.defesa:.1f} [{it.qualidade}]")
        if personagem.item_equipado:
            comp = comparar_itens(it, personagem.item_equipado)
            for l in comp.split("\n")[1:]:
                print(f"         {l.strip()}")
    print("    [0] Cancelar")

    op = input("  > ").strip()
    if not op.isdigit() or int(op) == 0:
        return False
    idx = int(op) - 1
    if 0 <= idx < len(equipaveis):
        return personagem.equipar(equipaveis[idx])
    return False


def _anunciar(item, personagem) -> None:
    container = "🎒 Bolsa" if item.tipo == "consumivel" else f"📦 {t('attr.inventory')}"
    hab_str = _hab_str(item)
    print(f"  ✦ {container}: {iname(item)}{hab_str} → {t('boss.added')}")


def _req_str(item) -> str:
    """Formata o requisito do item para exibição: [Força≥10]"""
    req = item.requisito if item.requisito else {}
    if not req:
        return ""
    labels = {
        "forca": "For", "vigor": "Vig",
        "conhecimento_tacito": "C.Tac", "conhecimento_explicito": "C.Exp"
    }
    parts = [f"{labels.get(k,k)}≥{int(v)}" for k, v in req.items()]
    return f" [33m[{', '.join(parts)}][0m"


def _hab_str(item) -> str:
    if item.habilidades_item:
        from habilidades import CATALOGO_HABILIDADES
        nomes = []
        for chave in item.habilidades_item:
            hab = CATALOGO_HABILIDADES.get(chave)
            nomes.append(iname(hab) if hab else chave)
        return f" | hab: {', '.join(nomes)}"
    return ""


# ══════════════════════════════════════════════════════════════
#  SHOW INVENTORY  (post-battle panel)
# ══════════════════════════════════════════════════════════════

def mostrar_inventario(personagem) -> None:
    """Display full inventory + bolsa with item skills."""
    W = 54
    print(f"\n  {'═'*W}")
    print(f"  {'INVENTÁRIO / BOLSA':^{W}}")
    print(f"  {'─'*W}")

    # Main inventory
    slot_items = personagem._itens_que_ocupam_slot()
    print(f"  📦 {t('attr.inventory')} ({len(slot_items)}/{personagem.slots_disponiveis} {t('attr.slots')}):")
    if slot_items:
        for it in slot_items:
            equipped = " ◄ equipado" if it is personagem.item_equipado else ""
            hab = _hab_str(it)
            req = _req_str(it)
            print(f"    • {iname(it):25} dano={it.dano_arma:.0f} def={it.defesa:.0f} "
                  f"maestria={it.maestria_atual:.0f}/{it.maestria_max:.0f}{hab}{req}{equipped}")
    else:
        print(f"    ({t('attr.none')})")

    print(f"  {'─'*W}")

    # Bolsa
    print(f"  🎒 Bolsa ({len(personagem.bolsa)}/{personagem.BOLSA_MAX} slots consumíveis):")
    if personagem.bolsa:
        for it in personagem.bolsa:
            cura = it.bonus.get("cura", 0)
            veneno = " | cura veneno" if it.bonus.get("cura_veneno") else ""
            print(f"    • {iname(it):25} +{cura:.0f} PV{veneno}")
    else:
        print(f"    ({t('attr.none')})")

    print(f"  {'═'*W}")
