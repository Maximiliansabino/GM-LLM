"""
mapa_biomas.py — Gerador procedural de malha de biomas brasileiros
Port fiel de biomas.js + gerador.js (Gibbs sampling / Potts model)

Uso:
    from mapa_biomas import gerar_mundo_novo, bioma_em, info_bioma

    # Gera um mundo 20×20 com seed aleatória
    mundo = gerar_mundo_novo(largura=20, altura=20)

    # Consulta bioma de uma coordenada de jogo
    bioma = bioma_em(mundo, x=3, y=-2)
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ══════════════════════════════════════════════════════════════
#  BIOMAS BASE (port de biomas.js)
# ══════════════════════════════════════════════════════════════

BIOMAS_BASE: Dict[str, Dict] = {
    "amazonia":      {"nome": "Amazônia",        "cor": "#1e5f3a", "icone": "🌳"},
    "cerrado":       {"nome": "Cerrado",          "cor": "#b8893a", "icone": "🌾"},
    "mata_atlantica":{"nome": "Mata Atlântica",   "cor": "#2d7a4f", "icone": "🌲"},
    "caatinga":      {"nome": "Caatinga",         "cor": "#c87850", "icone": "🌵"},
    "pantanal":      {"nome": "Pantanal",         "cor": "#5a8b7c", "icone": "💧"},
    "pampa":         {"nome": "Pampa",            "cor": "#9bb36a", "icone": "🌿"},
}

# Ecótonos (misturas) — chave sempre em ordem alfabética
_MISTURAS: Dict[str, Dict] = {
    "amazonia+cerrado":        {"nome": "Mata dos Cocais",   "cor": "#6d8a3a", "icone": "🌴"},
    "caatinga+mata_atlantica": {"nome": "Agreste",           "cor": "#a08858", "icone": "🌾"},
    "amazonia+pantanal":       {"nome": "Mata de Igapó",     "cor": "#2e6d5a", "icone": "🌊"},
    "cerrado+pantanal":        {"nome": "Complexo Chaco",    "cor": "#8a9550", "icone": "🌾"},
    "caatinga+cerrado":        {"nome": "Cerrado Seco",      "cor": "#c28a42", "icone": "🏜️"},
    "mata_atlantica+pampa":    {"nome": "Mata de Araucárias","cor": "#3d7a52", "icone": "🌲"},
    "pampa+pantanal":          {"nome": "Várzea Sulina",     "cor": "#7ba072", "icone": "🌿"},
    "amazonia+mata_atlantica": {"nome": "Floresta Úmida",    "cor": "#256644", "icone": "🌳"},
    "amazonia+caatinga":       {"nome": "Mata Seca",         "cor": "#7d7540", "icone": "🌴"},
    "caatinga+pantanal":       {"nome": "Brejo Salgado",     "cor": "#9a8460", "icone": "🌾"},
    "caatinga+pampa":          {"nome": "Campo Seco",        "cor": "#b29458", "icone": "🌾"},
    "cerrado+mata_atlantica":  {"nome": "Mata Semidecídua",  "cor": "#7a8f3e", "icone": "🌳"},
    "amazonia+pampa":          {"nome": "Savana Úmida",      "cor": "#5a8a50", "icone": "🌿"},
}

TODOS_IDS = list(BIOMAS_BASE.keys())

# Dados narrativos por bioma — usados no SYSTEM_PROMPT e descrições
DADOS_NARRATIVOS: Dict[str, Dict] = {
    "amazonia":      {
        "descricao": "floresta tropical densa",
        "flora":     ["seringueiras", "castanheiras", "vitórias-régias"],
        "fauna":     ["onças", "araras", "piranhas", "boto-cor-de-rosa"],
        "folclore":  ["Curupira", "Boitatá", "Cobra Grande", "Mapinguari"],
        "perigo":    0.8,
    },
    "cerrado":       {
        "descricao": "savana tropical com árvores retorcidas",
        "flora":     ["ipês", "buriti", "pequizeiro", "cagaita"],
        "fauna":     ["lobo-guará", "tamanduá-bandeira", "ema", "pato-do-mato"],
        "folclore":  ["Caipora", "Saci-Pererê", "Mula-sem-Cabeça"],
        "perigo":    0.6,
    },
    "mata_atlantica":{
        "descricao": "floresta costeira úmida e exuberante",
        "flora":     ["bromélias", "orquídeas", "jequitibás", "cedros"],
        "fauna":     ["mico-leão-dourado", "jaguatirica", "sabiá", "cascavel"],
        "folclore":  ["Iara", "Saci-Pererê", "Lobisomem"],
        "perigo":    0.7,
    },
    "caatinga":      {
        "descricao": "sertão seco com cactos e mandacaru",
        "flora":     ["mandacaru", "xique-xique", "umbu", "jurema"],
        "fauna":     ["cascavel", "asa-branca", "preá", "tatu-peba"],
        "folclore":  ["Lampião (fantasma)", "Bode do Diabo", "Pisadeira"],
        "perigo":    1.1,
    },
    "pantanal":      {
        "descricao": "planície alagada com rios serpenteando",
        "flora":     ["aguapé", "camalote", "paratudeiro", "acuri"],
        "fauna":     ["onça-pintada", "jacaré", "tuiuiú", "sucuri"],
        "folclore":  ["Mãe-do-Rio", "Anhangá das Águas", "Boca da Noite"],
        "perigo":    1.2,
    },
    "pampa":         {
        "descricao": "campos abertos e ventos cortantes do sul",
        "flora":     ["capim-annoni", "araucária", "erva-mate"],
        "fauna":     ["veado-campeiro", "ema", "cará", "graxaim"],
        "folclore":  ["Negrinho do Pastoreio", "Teiniaguá", "Gauchão Fantasma"],
        "perigo":    0.6,
    },
}

# Ecótonos herdam narrativa do primeiro componente
for chave, mist in _MISTURAS.items():
    a, b = chave.split("+")
    if a in DADOS_NARRATIVOS:
        base = DADOS_NARRATIVOS[a]
        DADOS_NARRATIVOS[chave] = {
            "descricao": f"zona de transição entre {BIOMAS_BASE[a]['nome']} e {BIOMAS_BASE[b]['nome']}",
            "flora":     base["flora"][:2] + (DADOS_NARRATIVOS.get(b, {}).get("flora", [])[:1]),
            "fauna":     base["fauna"][:2] + (DADOS_NARRATIVOS.get(b, {}).get("fauna", [])[:1]),
            "folclore":  base["folclore"][:2],
            "perigo":    (base["perigo"] + DADOS_NARRATIVOS.get(b, {}).get("perigo", 0.8)) / 2,
        }


def chave_mistura(a: str, b: str) -> str:
    return "+".join(sorted([a, b]))


def get_mistura(a: str, b: str) -> Optional[Dict]:
    if a == b:
        return None
    return _MISTURAS.get(chave_mistura(a, b))


def info_bioma(bid: str) -> Dict:
    """Retorna metadados do bioma (base ou ecótono)."""
    if bid in BIOMAS_BASE:
        return BIOMAS_BASE[bid]
    if "+" in bid:
        a, b = bid.split("+", 1)
        m = get_mistura(a, b)
        if m:
            return m
        # fallback sem regra definida
        A, B = BIOMAS_BASE.get(a), BIOMAS_BASE.get(b)
        if A and B:
            return {"nome": f"{A['nome']} + {B['nome']}", "cor": "#888888", "icone": "〰️"}
    return {"nome": bid, "cor": "#888888", "icone": "?"}


def narrativa_bioma(bid: str) -> Dict:
    """Retorna dados narrativos do bioma."""
    if bid in DADOS_NARRATIVOS:
        return DADOS_NARRATIVOS[bid]
    if "+" in bid:
        return DADOS_NARRATIVOS.get(bid, DADOS_NARRATIVOS.get(bid.split("+")[0], {}))
    return {}


# ══════════════════════════════════════════════════════════════
#  GERADOR (port de gerador.js)
# ══════════════════════════════════════════════════════════════

@dataclass
class Centro:
    id:    str
    x:     float
    y:     float
    peso:  float = 1.0
    raio:  float = 5.0


def influencia(centro: Centro, x: float, y: float) -> float:
    """Influência gaussiana de um centro sobre (x, y)."""
    d2 = (x - centro.x) ** 2 + (y - centro.y) ** 2
    return centro.peso * math.exp(-d2 / (2 * centro.raio ** 2))


def pesos_na_celula(centros: List[Centro], x: float, y: float) -> Dict[str, float]:
    """Soma das influências de todos os centros por bioma base."""
    pesos = {bid: 0.0 for bid in TODOS_IDS}
    for c in centros:
        pesos[c.id] = pesos.get(c.id, 0.0) + influencia(c, x + 0.5, y + 0.5)
    return pesos


def _componentes(bid: str) -> List[str]:
    return bid.split("+") if "+" in bid else [bid]


def _peso_centro_para(bid: str, pesos_base: Dict[str, float]) -> float:
    comps = _componentes(bid)
    vals = [pesos_base.get(c, 0.0) for c in comps]
    return sum(vals) / len(vals)


def bioma_dominante(centros: List[Centro], x: int, y: int,
                    limiar_mistura: float = 0.15) -> Tuple[str, Dict[str, float]]:
    """Determina bioma dominante ou ecótono na célula."""
    pesos = pesos_na_celula(centros, x, y)
    ord_ = sorted(pesos.items(), key=lambda kv: kv[1], reverse=True)
    top1, p1 = ord_[0]
    top2, p2 = ord_[1] if len(ord_) > 1 else (None, 0.0)

    if p1 < 1e-9:
        return "cerrado", pesos

    if top2 and p2 > 0 and p1 > 0:
        delta = (p1 - p2) / max(p1, 1e-6)
        if delta < limiar_mistura:
            m = get_mistura(top1, top2)
            if m:
                return chave_mistura(top1, top2), pesos

    return top1, pesos


def _softmax(arr: List[float]) -> List[float]:
    m = max(arr)
    exps = [math.exp(v - m) for v in arr]
    s = sum(exps)
    return [e / s for e in exps]


def _sample_weighted(itens: List[str], probs: List[float], rng: random.Random) -> str:
    r = rng.random()
    acc = 0.0
    for item, p in zip(itens, probs):
        acc += p
        if r < acc:
            return item
    return itens[-1]


def _gibbs_iteracao(mapa: List[List[str]], centros: List[Centro],
                    beta: float, rng: random.Random) -> List[List[str]]:
    """Uma iteração de Gibbs sampling (modelo de Potts com ecótonos)."""
    altura = len(mapa)
    largura = len(mapa[0])
    novo = [linha[:] for linha in mapa]

    for y in range(altura):
        for x in range(largura):
            vizinhos = []
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < largura and 0 <= ny < altura:
                    vizinhos.append(mapa[ny][nx])

            pesos_base = pesos_na_celula(centros, x, y)
            candidatos: set = set(TODOS_IDS + vizinhos)

            # Adiciona ecótono plausível do top-2
            top2 = sorted(pesos_base.items(), key=lambda kv: kv[1], reverse=True)[:2]
            if len(top2) == 2:
                m = get_mistura(top2[0][0], top2[1][0])
                if m:
                    candidatos.add(chave_mistura(top2[0][0], top2[1][0]))

            arr = list(candidatos)
            logits = []
            for bid in arr:
                pc = _peso_centro_para(bid, pesos_base)
                interacao = 0.0
                comps_b = _componentes(bid)
                for v in vizinhos:
                    if v == bid:
                        interacao += 1.0
                    else:
                        comps_v = _componentes(v)
                        shared = sum(1 for c in comps_b if c in comps_v)
                        if shared:
                            interacao += 0.4 * shared / max(len(comps_b), len(comps_v))
                logits.append(pc * 3 + beta * interacao)

            probs = _softmax(logits)
            novo[y][x] = _sample_weighted(arr, probs, rng)

    return novo


def gerar_mapa(largura: int, altura: int, centros: List[Centro],
               limiar_mistura: float = 0.15) -> List[List[str]]:
    """Gera mapa inicial por bioma dominante em cada célula."""
    mapa = []
    for y in range(altura):
        linha = []
        for x in range(largura):
            bid, _ = bioma_dominante(centros, x, y, limiar_mistura)
            linha.append(bid)
        mapa.append(linha)
    return mapa


def suavizar(mapa: List[List[str]], centros: List[Centro],
             beta: float = 1.2, iteracoes: int = 3,
             rng: Optional[random.Random] = None) -> List[List[str]]:
    """Aplica múltiplas iterações de Gibbs para suavizar fronteiras."""
    if rng is None:
        rng = random.Random()
    m = mapa
    for _ in range(iteracoes):
        m = _gibbs_iteracao(m, centros, beta, rng)
    return m


# ── Altura (value noise determinístico) ───────────────────────

def _mulberry32(seed: int):
    """PRNG determinístico (port de mulberry32)."""
    a = seed & 0xFFFFFFFF
    def next_val():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = (t ^ (t >> 15)) & 0xFFFFFFFF
        t = (t * (t | 1)) & 0xFFFFFFFF
        t ^= (t + ((t ^ (t >> 7)) & 0xFFFFFFFF) * (t | 61)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return next_val


def gerar_altura(largura: int, altura: int,
                 seed: int = 42, escala: float = 0.25) -> List[List[float]]:
    """Value noise com 4 oitavas. Retorna valores em [-1, 1]."""
    rng = _mulberry32(seed)
    grade: Dict[str, float] = {}

    def rand(gx: int, gy: int) -> float:
        k = f"{gx},{gy}"
        if k not in grade:
            grade[k] = rng() * 2 - 1
        return grade[k]

    def smooth(t: float) -> float:
        return t * t * (3 - 2 * t)

    def val(x: float, y: float) -> float:
        x0, y0 = int(math.floor(x)), int(math.floor(y))
        x1, y1 = x0 + 1, y0 + 1
        sx, sy = smooth(x - x0), smooth(y - y0)
        a, b = rand(x0, y0), rand(x1, y0)
        c, d = rand(x0, y1), rand(x1, y1)
        return (a*(1-sx) + b*sx) * (1-sy) + (c*(1-sx) + d*sx) * sy

    mapa = []
    for y in range(altura):
        linha = []
        for x in range(largura):
            v, amp, freq, norm = 0.0, 1.0, escala, 0.0
            for _ in range(4):
                v += amp * val(x * freq, y * freq)
                norm += amp
                amp *= 0.5
                freq *= 2.0
            linha.append(v / norm)
        mapa.append(linha)
    return mapa


_BONUS_ALTURA = {
    "amazonia": -1, "cerrado": 1, "mata_atlantica": 0,
    "caatinga": 2, "pantanal": -3, "pampa": 0,
}


def altura_z(raw: float, bioma: str) -> float:
    """Converte altura raw em Z de jogo (~[-10, +10])."""
    if bioma in _BONUS_ALTURA:
        b = _BONUS_ALTURA[bioma]
    elif "+" in bioma:
        comps = bioma.split("+")
        b = sum(_BONUS_ALTURA.get(c, 0) for c in comps) / len(comps)
    else:
        b = 0
    return raw * 8 + b


# ── Centros iniciais ──────────────────────────────────────────

def centros_iniciais(largura: int, altura: int,
                     seed: Optional[int] = None) -> List[Centro]:
    """
    Gera centros com distribuição geograficamente plausível.
    seed=None → aleatório (novo mundo a cada sessão).
    """
    rng = random.Random(seed)

    # Base: 4 centros fixos com posições plausíveis
    raio_base = max(largura, altura) * 0.28
    centros = [
        Centro("amazonia",      largura*0.25, altura*0.20, 1.0, raio_base*1.1),
        Centro("cerrado",       largura*0.50, altura*0.50, 0.9, raio_base),
        Centro("mata_atlantica",largura*0.80, altura*0.55, 0.85, raio_base*0.8),
        Centro("caatinga",      largura*0.75, altura*0.25, 0.9, raio_base*0.8),
    ]

    # Perturbação aleatória nas posições (novo mapa a cada sessão)
    for c in centros:
        c.x += rng.uniform(-largura * 0.12, largura * 0.12)
        c.y += rng.uniform(-altura * 0.12, altura * 0.12)
        c.peso *= rng.uniform(0.8, 1.2)
        c.raio *= rng.uniform(0.85, 1.15)
        # Mantém dentro dos limites
        c.x = max(1.0, min(largura - 2.0, c.x))
        c.y = max(1.0, min(altura - 2.0, c.y))

    # 30% de chance de adicionar pantanal ou pampa
    extras = [
        ("pantanal", largura*0.30, altura*0.70),
        ("pampa",    largura*0.50, altura*0.85),
    ]
    for bid, bx, by in extras:
        if rng.random() < 0.30:
            centros.append(Centro(
                bid,
                bx + rng.uniform(-largura*0.1, largura*0.1),
                by + rng.uniform(-altura*0.1, altura*0.1),
                rng.uniform(0.7, 1.0),
                raio_base * rng.uniform(0.6, 0.9),
            ))

    return centros


# ══════════════════════════════════════════════════════════════
#  MUNDO — estrutura completa para uso no jogo
# ══════════════════════════════════════════════════════════════

@dataclass
class MundoBiomas:
    largura:  int
    altura:   int
    offset_x: int           # coord de jogo = índice mapa + offset
    offset_y: int
    mapa:     List[List[str]]
    alt_raw:  List[List[float]]
    centros:  List[Centro]
    seed:     int

    def bioma_em(self, gx: int, gy: int) -> str:
        """Bioma em coordenada de jogo. Retorna bioma mais próximo se fora."""
        mx = gx - self.offset_x
        my = gy - self.offset_y
        mx = max(0, min(self.largura - 1, mx))
        my = max(0, min(self.altura - 1, my))
        return self.mapa[my][mx]

    def altura_em(self, gx: int, gy: int) -> float:
        mx = max(0, min(self.largura-1, gx - self.offset_x))
        my = max(0, min(self.altura-1, gy - self.offset_y))
        return self.alt_raw[my][mx]

    def resumo(self) -> str:
        """Resumo para logs."""
        todos: set = set()
        for linha in self.mapa:
            todos |= set(linha)
        nomes = [info_bioma(b)["nome"] for b in sorted(todos)]
        return f"seed={self.seed} | {self.largura}×{self.altura} | {', '.join(nomes)}"


def gerar_mundo_novo(largura: int = 20, altura: int = 20,
                     seed: Optional[int] = None,
                     beta: float = 1.2, iteracoes: int = 3,
                     limiar: float = 0.15) -> MundoBiomas:
    """
    Gera um mundo procedural completo.
    seed=None → novo mundo aleatório a cada chamada.
    offset posiciona o mapa para que (0,0) fique no centro.
    """
    if seed is None:
        seed = random.randint(1, 999_999)

    rng = random.Random(seed)
    centros = centros_iniciais(largura, altura, seed=seed)
    mapa = gerar_mapa(largura, altura, centros, limiar)
    mapa = suavizar(mapa, centros, beta, iteracoes, rng)
    alt  = gerar_altura(largura, altura, seed=seed)

    # Offset: (0,0) do jogo → centro do mapa
    offset_x = -(largura // 2)
    offset_y = -(altura // 2)

    return MundoBiomas(
        largura=largura, altura=altura,
        offset_x=offset_x, offset_y=offset_y,
        mapa=mapa, alt_raw=alt,
        centros=centros, seed=seed,
    )


# ══════════════════════════════════════════════════════════════
#  HELPERS PARA mundo_aberto.py
# ══════════════════════════════════════════════════════════════

def bioma_em(mundo: MundoBiomas, gx: int, gy: int, gz: int = 0) -> str:
    """
    Bioma final considerando z:
      z < -2 → caverna  (independe do mapa)
      z > 3  → montanha (independe do mapa — compatível com mundo_aberto)
      outros → lookup no mapa procedural
    """
    if gz < -2:
        return "caverna"
    if gz > 3:
        return "montanha"
    return mundo.bioma_em(gx, gy)


# Perigo por bioma (usada em mundo_aberto._verificar_encontro)
PERIGO_BIOMA: Dict[str, float] = {b: d["perigo"]
                                   for b, d in DADOS_NARRATIVOS.items()
                                   if "perigo" in d}


if __name__ == "__main__":
    mundo = gerar_mundo_novo(largura=20, altura=20)
    print(f"Mundo gerado: {mundo.resumo()}")
    print(f"Offset: ({mundo.offset_x}, {mundo.offset_y})")
    print(f"Bioma em (0,0): {bioma_em(mundo, 0, 0)}")
    print(f"Bioma em (5,5): {bioma_em(mundo, 5, 5)}")
    print(f"Caverna z=-3:   {bioma_em(mundo, 0, 0, gz=-3)}")
    print()
    # Imprime mapa
    for y, linha in enumerate(mundo.mapa):
        print(" ".join(info_bioma(b)["icone"] for b in linha))
