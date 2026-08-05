"""
status_effects.py
─────────────────────────────────────────────────────────────
Sistema de efeitos de status para personagens e inimigos.

EFEITOS DISPONÍVEIS:
  queimar      — dano por turno (fogo/chamas)
  congelar     — reduz ação do inimigo / limita personagem
  paralisar    — perde próxima ação (trovão/relâmpago)
  envenenar    — dano crescente por turno (veneno/ácido)
  sangrar      — dano fixo por turno (corte profundo)
  drenar_psique— drena Psiquê por turno (sombra/trevas/arcano)
  confundir    — penaliza criatividade / ataque errático

MAPEAMENTO ELEMENTO → EFEITO (para detecção automática):
  fogo/chamas/incêndio    → queimar
  gelo/frio/neve/geada    → congelar
  trovão/raio/elétrico    → paralisar
  veneno/ácido/tóxico     → envenenar
  sombra/trevas/escuridão → drenar_psique
  arcano/caos/magia negra → confundir
  sangue/lâmina (crítico) → sangrar
"""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from personagens import Personagem
    from inimigos import Inimigo

# ── Definições dos efeitos ────────────────────────────────────

EFEITOS = {
    "queimar": {
        "icone":    "🔥",
        "cor":      "\033[31m",
        "duracao":  3,       # turnos
        "dano_pct": 0.08,    # % do PV max por turno
        "desc":     "em chamas — perdendo PV a cada turno",
    },
    "congelar": {
        "icone":    "❄️",
        "cor":      "\033[96m",
        "duracao":  2,
        "pen_acao": 0.5,     # ação do inimigo reduzida a 50% | personagem: -30% dano
        "desc":     "congelado — movimentos lentos",
    },
    "paralisar": {
        "icone":    "⚡",
        "cor":      "\033[33m",
        "duracao":  1,
        "perde_acao": True,  # perde 1 turno inteiro
        "desc":     "paralisado — perde o próximo turno",
    },
    "envenenar": {
        "icone":    "☠️",
        "cor":      "\033[32m",
        "duracao":  4,
        "dano_base": 0.05,   # % PV max no turno 1; cresce 0.02 por turno
        "desc":     "envenenado — dano crescente a cada turno",
    },
    "sangrar": {
        "icone":    "🩸",
        "cor":      "\033[31m",
        "duracao":  3,
        "dano_pct": 0.05,    # % PV max por turno
        "desc":     "sangrando — perdendo PV a cada turno",
    },
    "drenar_psique": {
        "icone":    "💜",
        "cor":      "\033[35m",
        "duracao":  2,
        "drain_pct": 0.10,   # % Psiquê max drenada por turno
        "desc":     "drenado — perdendo Psiquê a cada turno",
    },
    "confundir": {
        "icone":    "💫",
        "cor":      "\033[36m",
        "duracao":  2,
        "pen_cri":  0.20,    # -0.20 de criatividade
        "desc":     "confuso — criatividade penalizada",
    },
}

# ── Mapeamento elemento → efeito ─────────────────────────────

_KW_EFEITO: dict[str, list[str]] = {
    "queimar":       ["fogo","chamas","incêndio","incendio","flamejante","ardente",
                      "labaredas","brasa","fogueira","piromantico"],
    "congelar":      ["gelo","frio","neve","geada","glacial","congelar","congelante",
                      "ártico","artico","nevasca","blizzard","crionico"],
    "paralisar":     ["trovão","trovao","raio","relâmpago","relampago","elétrico",
                      "eletrico","lightning","choque elétrico","descarga"],
    "envenenar":     ["veneno","ácido","acido","tóxico","toxico","corrosivo",
                      "peçonha","peconha","venenoso","contaminado"],
    "drenar_psique": ["sombra","trevas","escuridão","escuridao","necro","maldição",
                      "maldicao","amaldiçoado","abissal","vazio","almas"],
    "confundir":     ["arcano","caos","ilusão","ilusao","psíquico","psiquico",
                      "mental","mente","alucinação","alucinacao"],
    "sangrar":       ["sangue","lâmina profunda","fio da lâmina","serrilhado"],
}


def detectar_efeito_acao(acao: str, componentes: list, tipo_dano_fisico: str,
                          criatividade: float) -> str | None:
    """
    Detecta se a ação do jogador deve aplicar um efeito de status ao inimigo.
    Regras:
      - Precisa de elemento ou magia nos componentes
      - Criatividade >= 0.65 para aplicar (ações fracas não causam efeito)
      - Palavras-chave do elemento determinam o efeito
      - Corte com criatividade >= 0.80 → sangrar (acerto preciso)
    """
    a = acao.lower()
    tem_elemento = "elemento" in componentes or "magia" in componentes

    # Corte preciso com espada → sangrar
    if (tipo_dano_fisico == "corte" and criatividade >= 0.80
            and "sangrar" not in a):
        return "sangrar"

    if not tem_elemento or criatividade < 0.65:
        return None

    for efeito, kws in _KW_EFEITO.items():
        if any(kw in a for kw in kws):
            return efeito

    return None


def aplicar_efeito_inimigo(inimigo, efeito: str, intensidade: float = 1.0) -> None:
    """Aplica efeito de status ao inimigo."""
    if efeito not in EFEITOS:
        return
    defn = EFEITOS[efeito]
    inimigo.status_effects = getattr(inimigo, "status_effects", [])
    # Remove efeito anterior do mesmo tipo
    inimigo.status_effects = [e for e in inimigo.status_effects
                               if e["nome"] != efeito]
    inimigo.status_effects.append({
        "nome":       efeito,
        "duracao":    defn["duracao"],
        "turno_ini":  0,
        "intensidade": intensidade,
        "icone":      defn["icone"],
        "cor":        defn["cor"],
    })
    print(f"  {defn['cor']}{defn['icone']} {inimigo.nome} está {defn['desc']}!\033[0m")


def aplicar_efeito_personagem(personagem, efeito: str, intensidade: float = 1.0) -> None:
    """Aplica efeito de status ao personagem."""
    if efeito not in EFEITOS:
        return
    defn = EFEITOS[efeito]
    personagem.status_effects[efeito] = {
        "duracao":    defn["duracao"],
        "intensidade": intensidade,
        "icone":      defn["icone"],
        "cor":        defn["cor"],
    }
    print(f"  {defn['cor']}{defn['icone']} {personagem.nome} está {defn['desc']}!\033[0m")


def processar_status_personagem(personagem) -> bool:
    """
    Aplica os efeitos ativos no personagem no início do turno.
    Retorna True se o personagem perde o turno (paralisado).
    """
    if not personagem.status_effects:
        return False

    perde_turno = False
    expirados = []

    for nome, estado in list(personagem.status_effects.items()):
        if nome not in EFEITOS:
            expirados.append(nome)
            continue
        defn  = EFEITOS[nome]
        inten = estado.get("intensidade", 1.0)
        cor   = defn["cor"]
        icone = defn["icone"]

        if nome == "queimar":
            dano = round(personagem.pv_max * defn["dano_pct"] * inten, 1)
            personagem.pv_atual = max(0, personagem.pv_atual - dano)
            print(f"  {cor}{icone} Queimadura: -{dano:.1f} PV "
                  f"({personagem.pv_atual:.0f}/{personagem.pv_max:.0f})\033[0m")

        elif nome == "envenenar":
            turno = defn["duracao"] - estado["duracao"] + 1
            dano_pct = defn["dano_base"] + (turno - 1) * 0.02
            dano = round(personagem.pv_max * dano_pct * inten, 1)
            personagem.pv_atual = max(0, personagem.pv_atual - dano)
            print(f"  {cor}{icone} Veneno (turno {turno}): -{dano:.1f} PV "
                  f"({personagem.pv_atual:.0f}/{personagem.pv_max:.0f})\033[0m")

        elif nome == "sangrar":
            dano = round(personagem.pv_max * defn["dano_pct"] * inten, 1)
            personagem.pv_atual = max(0, personagem.pv_atual - dano)
            print(f"  {cor}{icone} Sangramento: -{dano:.1f} PV "
                  f"({personagem.pv_atual:.0f}/{personagem.pv_max:.0f})\033[0m")

        elif nome == "drenar_psique":
            drain = round(personagem.psique_max * defn["drain_pct"] * inten, 1)
            personagem.psique_atual = max(0, personagem.psique_atual - drain)
            print(f"  {cor}{icone} Drenagem: -{drain:.1f} Ψ "
                  f"({personagem.psique_atual:.1f}/{personagem.psique_max:.1f})\033[0m")

        elif nome == "paralisar":
            perde_turno = True
            print(f"  {cor}{icone} {personagem.nome} está paralisado — perde este turno!\033[0m")

        elif nome == "congelar":
            print(f"  {cor}{icone} {personagem.nome} está congelado — -30% dano neste turno.\033[0m")

        elif nome == "confundir":
            print(f"  {cor}{icone} {personagem.nome} está confuso — criatividade penalizada.\033[0m")

        # Decrementa duração
        estado["duracao"] -= 1
        if estado["duracao"] <= 0:
            expirados.append(nome)

    for nome in expirados:
        personagem.status_effects.pop(nome, None)
        if nome in EFEITOS:
            print(f"  \033[90m✓ {EFEITOS[nome]['icone']} {nome.capitalize()} expirou.\033[0m")

    return perde_turno


def processar_status_inimigo(inimigo) -> tuple[float, bool]:
    """
    Aplica os efeitos ativos no inimigo no início do turno do inimigo.
    Retorna (dano_extra, perde_turno).
    """
    effects = getattr(inimigo, "status_effects", [])
    if not effects:
        return 0.0, False

    dano_total = 0.0
    perde_turno = False
    expirados = []

    for estado in effects:
        nome  = estado["nome"]
        if nome not in EFEITOS:
            expirados.append(estado)
            continue
        defn  = EFEITOS[nome]
        inten = estado.get("intensidade", 1.0)
        cor   = defn["cor"]
        icone = defn["icone"]

        if nome == "queimar":
            dano = round(inimigo.pv_max * defn["dano_pct"] * inten, 1)
            inimigo.pv_atual = max(0, inimigo.pv_atual - dano)
            dano_total += dano
            print(f"  {cor}{icone} {inimigo.nome} queima: -{dano:.1f} PV "
                  f"({inimigo.pv_atual:.0f}/{inimigo.pv_max:.0f})\033[0m")

        elif nome == "envenenar":
            turno_idx = defn["duracao"] - estado["duracao"] + 1
            dano_pct = defn["dano_base"] + (turno_idx - 1) * 0.02
            dano = round(inimigo.pv_max * dano_pct * inten, 1)
            inimigo.pv_atual = max(0, inimigo.pv_atual - dano)
            dano_total += dano
            print(f"  {cor}{icone} {inimigo.nome} envenenado (t{turno_idx}): -{dano:.1f} PV\033[0m")

        elif nome == "sangrar":
            dano = round(inimigo.pv_max * defn["dano_pct"] * inten, 1)
            inimigo.pv_atual = max(0, inimigo.pv_atual - dano)
            dano_total += dano
            print(f"  {cor}{icone} {inimigo.nome} sangra: -{dano:.1f} PV\033[0m")

        elif nome == "drenar_psique":
            print(f"  {cor}{icone} {inimigo.nome} drena energia — enfraquecido.\033[0m")

        elif nome == "paralisar":
            perde_turno = True
            print(f"  {cor}{icone} {inimigo.nome} está paralisado — não ataca!\033[0m")

        elif nome == "congelar":
            perde_turno = True
            print(f"  {cor}{icone} {inimigo.nome} está congelado — não ataca!\033[0m")

        elif nome == "confundir":
            print(f"  {cor}{icone} {inimigo.nome} está confuso — ataque errático.\033[0m")

        estado["duracao"] -= 1
        if estado["duracao"] <= 0:
            expirados.append(estado)

    for e in expirados:
        inimigo.status_effects.remove(e)
        print(f"  \033[90m✓ {EFEITOS[e['nome']]['icone']} {e['nome'].capitalize()} expirou em {inimigo.nome}.\033[0m")

    return dano_total, perde_turno


def exibir_status_personagem(personagem) -> None:
    """Exibe barra de status ativos do personagem (usada no HUD)."""
    if not personagem.status_effects:
        return
    tags = []
    for nome, estado in personagem.status_effects.items():
        if nome in EFEITOS:
            d = EFEITOS[nome]
            tags.append(f"{d['cor']}{d['icone']} {nome}({estado['duracao']}t)\033[0m")
    if tags:
        print(f"  Status: {' '.join(tags)}")


def exibir_status_inimigo(inimigo) -> None:
    """Exibe status ativos no painel do inimigo."""
    effects = getattr(inimigo, "status_effects", [])
    if not effects:
        return
    tags = []
    for e in effects:
        if e["nome"] in EFEITOS:
            d = EFEITOS[e["nome"]]
            tags.append(f"{d['cor']}{d['icone']}({e['duracao']}t)\033[0m")
    if tags:
        print(f"  {' '.join(tags)}", end="  ")
