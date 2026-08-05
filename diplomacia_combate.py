"""
diplomacia_combate.py
─────────────────────────────────────────────────────────────
Mecânica de Diplomacia em Combate — RPG GM LLM

Quando o jogador envia uma ação de carinho/amizade durante o combate
(beijo, abraço, aperto de mão, aceno, etc.), o sistema detecta a intenção
e resolve três possíveis desfechos baseados no estado do inimigo:

  AMIZADE  — inimigo aceita, para de lutar e doa um item
  FUGA     — inimigo fraco (PV < 33%) cria oportunidade e escapa,
              podendo roubar um consumível do jogador
  REJEIÇÃO — inimigo ignora ou fica ainda mais agressivo

Regras de probabilidade:
  PV > 66%  → sempre rejeita (inimigo forte, não precisa de amizade)
  PV 33-66% → 25% amizade | 10% fuga | 65% rejeição
  PV < 33%  → 20% amizade | 50% fuga | 30% rejeição

Tipo também influencia:
  besta      → mais provável aceitar (instinto animal)
  humanoide  → mais provável aceitar se PV baixo
  morto-vivo → nunca aceita
  elemental  → nunca aceita
  arcano     → raramente aceita

Fugas dramáticas por tipo:
  arcano     → "some em fumaça negra"
  besta      → "desaparece na mata / mergulha na água"
  humanoide  → "gira e corre gritando"
  morto-vivo → impossível (não foge)
  elemental  → "se dissolve no ambiente"
"""

from __future__ import annotations
import random
from typing import Optional, Tuple
from dataclasses import dataclass

# ── Keywords de diplomacia (PT + EN) ─────────────────────────
KW_CARINHO = {
    # Português
    "beijo", "beijar", "beijinho", "beijoca",
    "abraço", "abraçar", "abraco", "abracar",
    "aperto de mão", "apertar a mão", "apertar mão",
    "afago", "carinho", "carinhoso", "acariciar",
    "aceno", "acenar", "aceno de cabeça",
    "aperto de mão", "cumprimentar", "cumprimento",
    "aperto", "abanar", "passar a mão",
    "amizade", "ser amigo", "fazer amigo", "fazer amizade",
    "paz", "oferecer paz", "trégua", "propor trégua",
    "gentileza", "ser gentil", "bondade",
    "sorriso", "sorrir", "sorrio",
    "aceno", "acenar", "tchau", "oi",
    # Inglês
    "hug", "hugging", "embrace",
    "kiss", "kissing",
    "handshake", "shake hands",
    "pat", "pet", "caress",
    "wave", "waving", "smile",
    "friend", "friendly", "peace",
    "truce", "offer peace",
}

# Tipos que nunca aceitam diplomacia
TIPOS_IMUNES = {"morto-vivo", "elemental"}

# Tipos que podem aceitar com probabilidade aumentada
TIPOS_RECEPTIVOS = {"besta", "humanoide"}


@dataclass
class ResultadoDiplomacia:
    desfecho:       str          # "amizade" | "fuga" | "rejeicao"
    mensagem:       str          # exibida ao jogador
    item_doado:     Optional[object] = None   # item dado pelo inimigo (amizade)
    item_roubado:   Optional[object] = None   # item roubado pelo inimigo (fuga)
    narração:       str = ""


def detectar_diplomacia(acao: str) -> bool:
    """Retorna True se a ação é uma tentativa de diplomacia/carinho."""
    a = acao.lower().strip()
    return any(kw in a for kw in KW_CARINHO)


def _pv_pct(inimigo) -> float:
    return inimigo.pv_atual / max(1, inimigo.pv_max)


def _chance_por_tipo(tipo: str, pv_pct: float) -> Tuple[float, float]:
    """Retorna (chance_amizade, chance_fuga) para o tipo e PV dados."""
    if tipo in TIPOS_IMUNES:
        return 0.0, 0.0

    if pv_pct > 0.66:
        return 0.0, 0.0  # muito forte — ignora completamente

    if pv_pct > 0.33:  # PV médio
        base_ami = 0.20 if tipo in TIPOS_RECEPTIVOS else 0.08
        base_fug = 0.08
    else:              # PV baixo (< 33%)
        base_ami = 0.25 if tipo in TIPOS_RECEPTIVOS else 0.10
        base_fug = 0.50 if tipo not in TIPOS_IMUNES else 0.0

    # Ajuste por tipo específico
    mult = {
        "besta":      (1.3, 1.2),
        "humanoide":  (1.2, 1.0),
        "arcano":     (0.5, 0.8),
        "morto-vivo": (0.0, 0.0),
        "elemental":  (0.0, 0.0),
    }.get(tipo, (1.0, 1.0))

    return min(0.6, base_ami * mult[0]), min(0.8, base_fug * mult[1])


def _gerar_item_doado(inimigo) -> Optional[object]:
    """Gera um item que o inimigo poderia dar como presente."""
    try:
        from itens import CATALOGO_ITENS
        # Loot do inimigo se tiver
        if inimigo.loot_possivel:
            pool = [k for k, _ in inimigo.loot_possivel if k in CATALOGO_ITENS]
            if pool:
                return CATALOGO_ITENS[random.choice(pool)]
        # Fallback: consumível básico
        consumiveis = [v for v in CATALOGO_ITENS.values() if v.tipo == "consumivel"]
        if consumiveis:
            return random.choice(consumiveis)
    except Exception:
        pass
    return None


def _roubar_item(personagem) -> Optional[object]:
    """Remove e retorna um consumível aleatório da bolsa do jogador."""
    if not personagem.bolsa:
        return None
    idx = random.randrange(len(personagem.bolsa))
    return personagem.bolsa.pop(idx)


def _mensagem_fuga(inimigo) -> str:
    """Gera mensagem de fuga dramática específica por tipo."""
    nome = inimigo.nome
    fugas = {
        "arcano": [
            f"{nome} abre um portal de sombras e desaparece num clarão roxo!",
            f"{nome} se dissolve em fumaça negra, deixando apenas um eco de riso!",
            f"Um redemoinho arcano envolve {nome} — ele some antes que você possa reagir!",
        ],
        "besta": [
            f"{nome} dá um salto desesperado e some na mata fechada!",
            f"Com um grito agudo, {nome} vira e desaparece entre as árvores!",
            f"{nome} aproveita um segundo de distração e mergulha nas sombras da floresta!",
        ],
        "humanoide": [
            f"{nome} joga areia nos seus olhos e corre gritando!",
            f"— Desta vez você se safou! — grita {nome} enquanto foge tropeçando!",
            f"{nome} empurra você e dispara pela saída mais próxima!",
        ],
        "elemental": [
            f"{nome} se fragmenta em mil partículas e se dissolve no ambiente!",
            f"A forma de {nome} perde a coesão e se espalha como neblina!",
        ],
    }
    pool = fugas.get(inimigo.tipo, [f"{nome} aproveita a distração e escapa!"])
    return random.choice(pool)


def _mensagem_amizade(inimigo, acao: str) -> str:
    """Gera mensagem de aceitação de amizade."""
    nome = inimigo.nome
    respostas = {
        "besta": [
            f"{nome} para de rosnar. Seus olhos mudam de expressão — e ele se aproxima com cautela.",
            f"Inesperadamente, {nome} abaixa a cabeça em sinal de submissão.",
            f"{nome} fareja sua mão e, após um momento tenso, afasta-se pacificamente.",
        ],
        "humanoide": [
            f"{nome} hesita. — Você é louco... mas tudo bem. — Ele baixa a arma.",
            f"— Espera. Você realmente fez isso? — {nome} olha confuso, mas curioso.",
            f"{nome} solta uma risada nervosa. — Tudo bem. Hoje você tem sorte.",
        ],
        "arcano": [
            f"Uma pausa. {nome} parece calcular algo... e decide que você não vale o esforço.",
            f"{nome} observa você por um longo momento antes de recuar silenciosamente.",
        ],
    }
    pool = respostas.get(inimigo.tipo, [f"{nome} surpreendentemente aceita o gesto."])
    return random.choice(pool)


def _mensagem_rejeicao(inimigo, acao: str) -> str:
    """Gera mensagem de rejeição da diplomacia."""
    nome = inimigo.nome
    rejeicoes = {
        "besta": [
            f"{nome} rosnna mais alto — seu gesto só irritou a criatura!",
            f"{nome} avança com mais fúria que antes!",
        ],
        "humanoide": [
            f"— Você está me provocando?! — {nome} fica ainda mais agressivo!",
            f"{nome} ri com desdém. — Esse truque não funciona comigo!",
        ],
        "morto-vivo": [
            f"{nome} não tem memória de compaixão — apenas o impulso de destruir.",
            f"O gesto passa completamente em branco para {nome}.",
        ],
        "elemental": [
            f"{nome} não possui consciência para reconhecer o gesto.",
            f"Forças elementais não entendem de diplomacia.",
        ],
        "arcano": [
            f"{nome} observa com frieza. — Patético. — E retoma o ataque.",
            f"O gesto não encontra nenhum eco em {nome}.",
        ],
    }
    pool = rejeicoes.get(inimigo.tipo, [f"{nome} ignora completamente e ataca!"])
    return random.choice(pool)


# ══════════════════════════════════════════════════════════════
#  FUNÇÃO PRINCIPAL
# ══════════════════════════════════════════════════════════════

def resolver_diplomacia(
    acao: str,
    personagem,
    inimigo,
    usar_llm: bool = False,
) -> ResultadoDiplomacia:
    """
    Resolve uma tentativa de diplomacia/carinho durante o combate.

    Retorna ResultadoDiplomacia com o desfecho e consequências.
    O chamador é responsável por aplicar item_doado/item_roubado.
    """
    pv_pct = _pv_pct(inimigo)
    tipo   = inimigo.tipo

    chance_ami, chance_fug = _chance_por_tipo(tipo, pv_pct)

    roll = random.random()

    # ── IMUNE — morto-vivo e elemental nunca reagem ───────────
    if tipo in TIPOS_IMUNES:
        return ResultadoDiplomacia(
            desfecho  = "rejeicao",
            mensagem  = _mensagem_rejeicao(inimigo, acao),
        )

    # ── MUITO FORTE — ignora completamente ────────────────────
    if pv_pct > 0.66:
        return ResultadoDiplomacia(
            desfecho = "rejeicao",
            mensagem = _mensagem_rejeicao(inimigo, acao),
        )

    # ── RESOLUÇÃO ─────────────────────────────────────────────
    if roll < chance_ami:
        # Amizade — inimigo aceita e doa item
        item = _gerar_item_doado(inimigo)
        msg  = _mensagem_amizade(inimigo, acao)
        if item:
            msg += f"\n  \033[32m✦ {inimigo.nome} deixa {item.nome} para você antes de ir.\033[0m"

        # Narração LLM opcional
        narr = ""
        if usar_llm:
            narr = _narrar_diplomacia(acao, inimigo, personagem, "amizade")

        return ResultadoDiplomacia(
            desfecho   = "amizade",
            mensagem   = msg,
            item_doado = item,
            narração   = narr,
        )

    elif roll < chance_ami + chance_fug:
        # Fuga — inimigo escapa, possivelmente roubando item
        item_roubado = None
        msg = _mensagem_fuga(inimigo)

        # 40% de chance de roubar um consumível ao fugir
        if personagem.bolsa and random.random() < 0.40:
            item_roubado = _roubar_item(personagem)
            if item_roubado:
                msg += f"\n  \033[31m⚠ {inimigo.nome} levou {item_roubado.nome} ao fugir!\033[0m"

        narr = ""
        if usar_llm:
            narr = _narrar_diplomacia(acao, inimigo, personagem, "fuga")

        return ResultadoDiplomacia(
            desfecho     = "fuga",
            mensagem     = msg,
            item_roubado = item_roubado,
            narração     = narr,
        )

    else:
        # Rejeição
        return ResultadoDiplomacia(
            desfecho = "rejeicao",
            mensagem = _mensagem_rejeicao(inimigo, acao),
        )


def _narrar_diplomacia(acao: str, inimigo, personagem, desfecho: str) -> str:
    """Narração LLM para o momento de diplomacia (50 tokens)."""
    try:
        from llm_backend import _chamar_ollama
        desc = {
            "amizade": "aceitou a paz e parou de lutar",
            "fuga":    "fugiu aproveitando a distração",
            "rejeicao":"ignorou e ficou ainda mais agressivo",
        }[desfecho]
        prompt = (
            f"Narre em 1-2 frases o seguinte momento de combate:\n"
            f"{personagem.nome} tentou '{acao}' contra {inimigo.nome} ({inimigo.tipo}), "
            f"que {desc}. PV do inimigo: {inimigo.pv_atual:.0f}/{inimigo.pv_max:.0f}.\n"
            f"Segunda pessoa para {personagem.nome}. Sem números. Dramático e específico."
        )
        return _chamar_ollama(prompt, num_predict=80, temperature=0.8)
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════
#  EXIBIÇÃO DO RESULTADO
# ══════════════════════════════════════════════════════════════

def exibir_resultado_diplomacia(res: ResultadoDiplomacia) -> None:
    """Imprime o resultado da diplomacia no terminal com formatação."""
    icone = {"amizade": "🤝", "fuga": "💨", "rejeicao": "⚔"}[res.desfecho]
    cor   = {"amizade": "\033[32m", "fuga": "\033[33m", "rejeicao": "\033[31m"}[res.desfecho]

    print(f"\n  {cor}{icone} {res.mensagem}\033[0m")

    if res.narração:
        print(f"  \033[97m{res.narração}\033[0m")


# ══════════════════════════════════════════════════════════════
#  PONTO DE TESTE
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os, json
    os.makedirs("jornada", exist_ok=True)
    with open("jornada/log.json","w") as f: json.dump({"eventos":[]},f)
    with open("jornada/estado.json","w") as f:
        json.dump({"turno":0,"personagem":{},"localizacao_atual":"","npcs_conhecidos":{},
                   "inimigos_derrotados":[],"itens_obtidos":[],"habilidades_adquiridas":[],
                   "segredos_descobertos":[],"quests_ativas":[],"quests_concluidas":[],"reputacao":{}},f)

    from personagens import criar_kael
    from inimigos import CATALOGO_INIMIGOS
    from itens import POCAO_PSIQUE

    kael = criar_kael("Max")
    kael.bolsa = [POCAO_PSIQUE]  # item que pode ser roubado

    print("=== DETECÇÃO DE DIPLOMACIA ===")
    acoes = ["beijo", "abraço", "aperto de mão", "bola de fogo",
             "ataco", "sorrio", "ofereço paz", "hug", "corto"]
    for a in acoes:
        d = detectar_diplomacia(a)
        print(f"  {a!r:25} → {'✓ diplomacia' if d else '✗ combate'}")

    print()
    print("=== SIMULAÇÃO DE DESFECHOS (1000 rolls) ===")
    from collections import Counter
    inimigos_teste = [
        ("capivara",       "PV alto (80%)"),
        ("capivara",       "PV médio (50%)"),
        ("capivara",       "PV baixo (25%)"),
        ("lobo_da_floresta","PV baixo (25%)"),
    ]

    for ini_key, label in inimigos_teste:
        from inimigos import CATALOGO_INIMIGOS
        ini = CATALOGO_INIMIGOS[ini_key].clonar()
        pct = float(label.split("(")[1].split("%")[0]) / 100
        ini.pv_atual = ini.pv_max * pct

        resultados = Counter()
        for _ in range(1000):
            r = resolver_diplomacia("beijo", kael, ini)
            resultados[r.desfecho] += 1

        print(f"  {ini.nome} ({label}): "
              f"amizade={resultados['amizade']/10:.1f}%  "
              f"fuga={resultados['fuga']/10:.1f}%  "
              f"rejeição={resultados['rejeicao']/10:.1f}%")

    print()
    print("=== EXEMPLO DE RESULTADO COMPLETO ===")
    saci_like = CATALOGO_INIMIGOS["capivara"].clonar()
    saci_like.pv_atual = saci_like.pv_max * 0.25
    kael.bolsa = [POCAO_PSIQUE]

    random.seed(42)
    for tentativa in range(5):
        kael.bolsa = [POCAO_PSIQUE]  # repõe bolsa
        r = resolver_diplomacia("abraço", kael, saci_like)
        print(f"  Tentativa {tentativa+1}: [{r.desfecho.upper()}]")
        import re as _re
        msg_limpa = _re.sub(r'\x1b\[[0-9;]*m', '', r.mensagem)
        print(f"    {msg_limpa[:100]}")
        if r.item_doado:   print(f"    → Item doado: {r.item_doado.nome}")
        if r.item_roubado: print(f"    → Item roubado: {r.item_roubado.nome}")
