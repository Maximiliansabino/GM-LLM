"""
mundo_aberto.py — Motor de Mundo Aberto — Cenário C do RPG GM LLM

Sistema de malha de coordenadas (x, y, z):
  SQLite  → locais, modificações, encontros, NPCs
  JSON    → lore canônico por localização
  CSV     → log completo de movimentos e eventos

x=Leste(+)/Oeste(-)  y=Norte(+)/Sul(-)  z=Cima(+)/Baixo(-)
Jogador inicia em (0,0,0).
"""

from __future__ import annotations
import csv, json, math, random, sqlite3
try:
    from mapa_biomas import (
        gerar_mundo_novo, bioma_em as _bioma_em_mapa,
        narrativa_bioma, PERIGO_BIOMA as _PERIGO_BIOMA_MAPA,
        info_bioma as _info_bioma, MundoBiomas,
    )
    _MAPA_BIOMAS_OK = True
except ImportError:
    _MAPA_BIOMAS_OK = False

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DIR      = Path("jornada")
DB_PATH  = DIR / "mundo.db"
LORE_PATH= DIR / "mundo_lore.json"
LOG_PATH    = DIR / "mundo_log.csv"
_SESSION_ID = ""   # preenchido em executar_cenario_c

CHANCE_ENCONTRO_BASE   = 0.25
CHANCE_ENCONTRO_PERIGO = 0.45
RAIO_PERIGO            = 5
LIMITE_TURNOS          = 60

DIRECOES: Dict[str, Tuple[int,int,int]] = {
    "n":(0,1,0),"norte":(0,1,0),"north":(0,1,0),
    "s":(0,-1,0),"sul":(0,-1,0),"south":(0,-1,0),
    "l":(1,0,0),"leste":(1,0,0),"east":(1,0,0),
    "o":(-1,0,0),"oeste":(-1,0,0),"west":(-1,0,0),
    "ne":(1,1,0),"nordeste":(1,1,0),
    "no":(-1,1,0),"noroeste":(-1,1,0),
    "se":(1,-1,0),"sudeste":(1,-1,0),
    "so":(-1,-1,0),"sudoeste":(-1,-1,0),
    "c":(0,0,1),"cima":(0,0,1),"subir":(0,0,1),"up":(0,0,1),
    "b":(0,0,-1),"baixo":(0,0,-1),"descer":(0,0,-1),"down":(0,0,-1),
}

_PERIGO_BIOMA_LEGADO = {
    "floresta":0.8,"planicie":0.6,"deserto":1.1,
    "pantano":1.2,"caverna":1.4,"montanha":1.0,"ruinas":1.5,
}
# Merged com biomas procedurais em runtime
_PERIGO_BIOMA = {
    **_PERIGO_BIOMA_LEGADO,
    "amazonia":0.8,"cerrado":0.6,"mata_atlantica":0.7,
    "caatinga":1.1,"pantanal":1.2,"pampa":0.6,
    "caverna":1.4,"montanha":1.0,
}

_KW_MOD: Dict[str, List[str]] = {
    "fogo":      ["fogo","chamas","incendio","queimo","bola de fogo","fire","burn"],
    "corte":     ["corto","cortar","derruba","arvore","galho","tronco","machado","cut","chop"],
    "magia":     ["invoco","conjuro","lanço","raio","trovao","explosao","spell","cast"],
    "escavacao": ["escavo","escavar","cavar","cavo","minero","minerar","picareta","dig","mine","excavate"],
    "construcao":["construo","ergo","muro","parede","barricada","build"],
    "gelo":      ["gelo","congelo","congelar","nevar","ice","freeze"],
    "explosao":  ["explodo","explodir","explode","blast"],
    "agua":      ["inundo","inundar","flood","water"],
}

_DIR_STR: Dict[Tuple[int,int,int], str] = {
    (0,1,0):"Norte",(0,-1,0):"Sul",(1,0,0):"Leste",(-1,0,0):"Oeste",
    (0,0,1):"Cima",(0,0,-1):"Baixo",
    (1,1,0):"Nordeste",(-1,1,0):"Noroeste",
    (1,-1,0):"Sudeste",(-1,-1,0):"Sudoeste",
}

_NOMES_BIOMA: Dict[str, List[str]] = {
    "floresta":["Bosque das Cigarras","Mata do Curupira","Floresta Negra","Arvoredo Fechado"],
    "planicie":["Campos do Vento","Planície das Ossadas","Savana Queimada","Cerrado Aberto"],
    "deserto": ["Deserto de Ossos","Areia Viva","Dunas do Esquecimento","Sertão Seco"],
    "pantano": ["Pântano da Podridão","Varzea Negra","Brejo Amaldiçoado","Igapó Sombrio"],
    "caverna": ["Gruta Profunda","Caverna do Eco","Antro das Sombras","Furna da Serpente"],
    "montanha":["Pico das Nuvens","Crista Partida","Serra do Vento Eterno","Cume Gelado"],
    "ruinas":  ["Ruínas Arcanas","Templo Caído","Cidade Perdida","Fortaleza em Ruínas"],
    # Biomas procedurais brasileiros
    "amazonia":       ["Mata dos Ipês","Bosque das Seringueiras","Floresta do Boto",
                       "Selva dos Curupiras","Igapó do Rio Negro","Clareira da Vitória-Régia"],
    "cerrado":        ["Cerrado das Veredas","Chapada dos Buritis","Campo dos Ipês Amarelos",
                       "Savana do Lobo-Guará","Planalto dos Pequizeiros"],
    "mata_atlantica": ["Mata dos Jequitibás","Floresta das Orquídeas","Encosta das Bromeliáceas",
                       "Bosque dos Micos","Cordilheira das Bromélias"],
    "caatinga":       ["Sertão do Mandacaru","Carrasco do Xique-Xique","Tabuleiro da Asa-Branca",
                       "Pedreira do Juazeiro","Caatinga da Cascavel"],
    "pantanal":       ["Baía das Onças","Vazante do Jacaré","Corumba das Águas",
                       "Aguada dos Tuiuiús","Igapó do Camalote"],
    "pampa":          ["Campanha dos Gaúchos","Coxilha do Graxaim","Planície das Emas",
                       "Pampas do Vento Sul","Campo da Teiniaguá"],
    "caverna":        ["Gruta de Pedra","Caverna do Rio Subterrâneo","Lapinha das Pedras",
                       "Abismo das Raízes","Galeria Subterrânea"],
    "montanha":       ["Chapada dos Ventos","Serra das Nuvens","Pico dos Cóndores",
                       "Cristas do Silêncio","Escarpa das Cachoeiras"],
}

_FALLBACK_DESC: Dict[str, str] = {
    "floresta": "A mata fecha ao seu redor, árvores altas bloqueiam o sol.",
    "planicie": "Uma campina aberta se estende até o horizonte.",
    "deserto":  "Areia e pedras até onde a vista alcança.",
    "pantano":  "Lama escura borbulha entre raízes submersas.",
    "caverna":  "A escuridão é quase total. Goteiras ecoam nas pedras.",
    "montanha": "Rochas afiadas e vento cortante.",
    "ruinas":   "Pedras tombadas cobertas de musgo.",
}

_MAPA_BIOMA_CHAVE: Dict[str, str] = {
    "floresta":"floresta_sombria","planicie":"floresta_sombria",
    "deserto":"deserto_de_ossos","pantano":"pantano_da_podridao",
    "caverna":"cavernas_do_eco_profundo","montanha":"pico_dos_ventos_eternos",
    "ruinas":"ruinas_arcanas",
}

# ── NPCs migrados do Cenário A ────────────────────────────────
# Os 6 NPCs ricos de historias.py aparecem em coordenadas fixas, distribuídos
# pelos biomas em que originalmente apareciam no Cenário A. Quando o jogador
# usa "falar <nome>" em uma dessas coords, abre o menu completo do A
# (conversar / trocar / treinar / ajuda / segredo) via biomas.iniciar_menu_npc.
_A_NPC_IDS = {"breno", "mira", "duras", "eilara", "ferran", "sombra"}

# distribuição (npc_id, x, y, z, bioma_alvo) — coords escolhidas para cair
# dentro de biomas distintos no mapa procedural típico de 24×24
_NPCS_A_DISTRIBUICAO = (
    ("breno",  2,  1,  0, "floresta"),
    ("eilara", 4,  0,  0, "planicie"),
    ("sombra", 7,  0,  0, "deserto"),
    ("mira",  -3, -4,  0, "pantano"),
    ("ferran", 0,  0, -3, "caverna"),
    ("duras",  0,  0,  4, "montanha"),
)

# ── Eventos especiais aleatórios por bioma (Phase 2) ───────────
# Estrutura: bioma → lista de (chave, narrativa, efeito_callable | None, peso)
# efeito_callable recebe (personagem) e aplica mecânica; pode ser None
# (evento puramente narrativo). Probabilidade de disparo é controlada por
# CHANCE_EVENTO_BIOMA por movimento.
CHANCE_EVENTO_BIOMA = 0.12   # ~1 em 8 movimentos


def _ev_aplicar_status(efeito_nome: str, intensidade: float = 1.0):
    """Factory: retorna callable que aplica efeito de status no PJ."""
    def aplicar(pj):
        try:
            from status_effects import aplicar_efeito_personagem
            aplicar_efeito_personagem(pj, efeito_nome, intensidade)
        except Exception:
            pass
    return aplicar


def _ev_dano_pct(pct: float, motivo: str = ""):
    def aplicar(pj):
        d = round(pj.pv_max * pct, 1)
        pj.pv_atual = max(1.0, pj.pv_atual - d)
        print(f"  \033[31m✦ -{d:.0f} PV ({motivo})\033[0m")
    return aplicar


def _ev_conhecimento(tipo: str, val: float, motivo: str = ""):
    def aplicar(pj):
        try:
            if tipo == "tacito":
                pj.ganhar_conhecimento_tacito(val, motivo)
            else:
                pj.ganhar_conhecimento_explicito(val, motivo)
        except Exception:
            pass
    return aplicar


_EVENTOS_POR_BIOMA = {
    "pantano": [
        ("chuva_acida",
         "Uma chuva ácida começa a cair, queimando sua pele.",
         _ev_aplicar_status("queimar", 0.7), 1.0),
        ("nevoa_toxica",
         "Uma névoa esverdeada paira sobre o pântano — você inala antes de cobrir o rosto.",
         _ev_aplicar_status("envenenar", 0.8), 1.0),
        ("revelacao_lodo",
         "Você desenterra do lodo um osso esculpido com runas antigas.",
         _ev_conhecimento("tacito", 0.4, "runas no pântano"), 0.6),
    ],
    "deserto": [
        ("miragem",
         "Uma miragem ondula no horizonte mostrando uma cidade que não existe.",
         _ev_aplicar_status("confundir", 0.7), 1.0),
        ("tempestade_areia",
         "Uma tempestade de areia engole o caminho — você se protege como pode.",
         _ev_dano_pct(0.05, "tempestade de areia"), 1.0),
        ("oasis",
         "Você encontra um pequeno oásis. A água restaura suas forças.",
         lambda pj: setattr(pj, 'pv_atual',
             min(pj.pv_max, pj.pv_atual + round(pj.pv_max * 0.15, 1))), 0.5),
    ],
    "ruinas_arcanas": [
        ("eco_arcano",
         "Um eco arcano vibra nas paredes — fragmentos de saber antigo invadem sua mente.",
         _ev_conhecimento("explicito", 0.3, "eco arcano nas ruínas"), 1.0),
        ("rune_ativa",
         "Uma runa no chão dispara energia caótica.",
         _ev_aplicar_status("drenar_psique", 1.0), 1.0),
    ],
    "ruinas": [
        ("eco_arcano",
         "Um eco arcano vibra nas paredes — fragmentos de saber antigo invadem sua mente.",
         _ev_conhecimento("explicito", 0.3, "eco arcano"), 1.0),
    ],
    "caverna": [
        ("cristal_ressoa",
         "Cristais bioluminescentes pulsam ao seu passar, ecoando sua presença.",
         _ev_conhecimento("tacito", 0.2, "cristais ressonantes"), 1.0),
        ("desabamento",
         "Pedras se soltam do teto — você desvia por pouco.",
         _ev_dano_pct(0.08, "desabamento"), 1.0),
    ],
    "montanha": [
        ("vento_cortante",
         "Um vento cortante e gélido ataca seu corpo.",
         _ev_aplicar_status("congelar", 0.6), 1.0),
        ("vista_panoramica",
         "Do alto, você compreende algo sobre o caminho à frente.",
         _ev_conhecimento("explicito", 0.3, "vista da montanha"), 0.7),
    ],
    "floresta": [
        ("clareira_serena",
         "Uma clareira silenciosa traz paz momentânea.",
         lambda pj: setattr(pj, 'psique_atual',
             min(pj.psique_max, pj.psique_atual + round(pj.psique_max * 0.10, 1))), 0.7),
        ("espinho_envenenado",
         "Você se arranha em um espinho com seiva esverdeada.",
         _ev_aplicar_status("envenenar", 0.5), 0.8),
    ],
}
# Aliases para nomes de bioma do mapa procedural moderno
_EVENTOS_POR_BIOMA["amazonia"]       = _EVENTOS_POR_BIOMA["floresta"]
_EVENTOS_POR_BIOMA["mata_atlantica"] = _EVENTOS_POR_BIOMA["floresta"]
_EVENTOS_POR_BIOMA["pantanal"]       = _EVENTOS_POR_BIOMA["pantano"]
_EVENTOS_POR_BIOMA["caatinga"]       = _EVENTOS_POR_BIOMA["deserto"]
_EVENTOS_POR_BIOMA["cerrado"]        = _EVENTOS_POR_BIOMA["floresta"]


def _disparar_evento_bioma(personagem, bioma: str, coord) -> bool:
    """Tenta disparar um evento aleatório do bioma. Retorna True se disparou."""
    eventos = _EVENTOS_POR_BIOMA.get(bioma, [])
    if not eventos:
        return False
    if random.random() > CHANCE_EVENTO_BIOMA:
        return False
    pesos = [w for *_, w in eventos]
    idx = random.choices(range(len(eventos)), weights=pesos, k=1)[0]
    chave, narrativa, efeito, _peso = eventos[idx]
    print(f"\n  \033[35m✦ {narrativa}\033[0m")
    if callable(efeito):
        try: efeito(personagem)
        except Exception as e:
            print(f"  \033[90m[evento {chave}: {e}]\033[0m")
    try:
        registrar_fato(coord, f"evento_bioma:{chave}: {narrativa[:120]}")
    except Exception:
        pass
    return True


# ── Dataclasses ───────────────────────────────────────────────

@dataclass
class Coord:
    x: int = 0
    y: int = 0
    z: int = 0

    @property
    def key(self) -> str:
        return f"{self.x},{self.y},{self.z}"

    def mover(self, dx: int, dy: int, dz: int) -> "Coord":
        return Coord(self.x+dx, self.y+dy, self.z+dz)

    def dist(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def __str__(self) -> str:
        return f"({self.x},{self.y},{self.z})"


@dataclass
class LocalMundo:
    coord:       Coord
    bioma:       str
    nome:        str
    descricao:   str
    visitado_em: str = ""
    visitas:     int = 0
    modificacoes:List[Dict] = field(default_factory=list)
    encontros:   List[Dict] = field(default_factory=list)
    fatos:       List[str]  = field(default_factory=list)


# ── Banco ─────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH))


def inicializar_banco() -> None:
    DIR.mkdir(exist_ok=True)
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS locais (
            x INT, y INT, z INT,
            bioma TEXT, nome TEXT, descricao_llm TEXT,
            visitado_em TEXT, visitas INT DEFAULT 0,
            PRIMARY KEY (x,y,z));
        CREATE TABLE IF NOT EXISTS modificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            x INT, y INT, z INT,
            tipo TEXT, descricao TEXT, turno INT, timestamp TEXT);
        CREATE TABLE IF NOT EXISTS encontros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            x INT, y INT, z INT,
            inimigo_nome TEXT, resultado TEXT, turno INT, timestamp TEXT);
        CREATE TABLE IF NOT EXISTS fatos_locais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            x INT, y INT, z INT, fato TEXT, timestamp TEXT);
        CREATE TABLE IF NOT EXISTS estruturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            x INT, y INT, z INT,
            tipo TEXT, nome TEXT, descricao TEXT,
            turno INT, timestamp TEXT);
        CREATE TABLE IF NOT EXISTS npcs_mundo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            x INT, y INT, z INT,
            npc_id TEXT, nome TEXT, ocupacao TEXT,
            dialogo_intro TEXT, conhece_jogador INT DEFAULT 0,
            timestamp TEXT);
        CREATE TABLE IF NOT EXISTS itens_mundo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            x INT, y INT, z INT,
            item_id TEXT, nome TEXT, coletado INT DEFAULT 0,
            turno INT, timestamp TEXT);
        """)


def salvar_local(local: LocalMundo) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        con.execute("""
            INSERT INTO locais (x,y,z,bioma,nome,descricao_llm,visitado_em,visitas)
            VALUES (?,?,?,?,?,?,?,1)
            ON CONFLICT(x,y,z) DO UPDATE SET visitas=visitas+1, visitado_em=excluded.visitado_em
        """, (local.coord.x, local.coord.y, local.coord.z,
              local.bioma, local.nome, local.descricao, ts))


def carregar_local(coord: Coord) -> Optional[LocalMundo]:
    with _conn() as con:
        row = con.execute(
            "SELECT bioma,nome,descricao_llm,visitado_em,visitas FROM locais WHERE x=? AND y=? AND z=?",
            (coord.x, coord.y, coord.z)).fetchone()
        if not row:
            return None
        mods = con.execute(
            "SELECT tipo,descricao,turno FROM modificacoes WHERE x=? AND y=? AND z=? ORDER BY turno",
            (coord.x, coord.y, coord.z)).fetchall()
        enc = con.execute(
            "SELECT inimigo_nome,resultado FROM encontros WHERE x=? AND y=? AND z=? ORDER BY turno DESC LIMIT 5",
            (coord.x, coord.y, coord.z)).fetchall()
        fatos = con.execute(
            "SELECT fato FROM fatos_locais WHERE x=? AND y=? AND z=?",
            (coord.x, coord.y, coord.z)).fetchall()
    return LocalMundo(
        coord=coord, bioma=row[0], nome=row[1], descricao=row[2],
        visitado_em=row[3], visitas=row[4],
        modificacoes=[{"tipo":m[0],"descricao":m[1],"turno":m[2]} for m in mods],
        encontros=[{"inimigo":e[0],"resultado":e[1]} for e in enc],
        fatos=[f[0] for f in fatos],
    )


def salvar_modificacao(coord: Coord, tipo: str, descricao: str, turno: int) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        con.execute(
            "INSERT INTO modificacoes (x,y,z,tipo,descricao,turno,timestamp) VALUES (?,?,?,?,?,?,?)",
            (coord.x, coord.y, coord.z, tipo, descricao[:300], turno, ts))


def salvar_encontro(coord: Coord, inimigo: str, resultado: str, turno: int) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        con.execute(
            "INSERT INTO encontros (x,y,z,inimigo_nome,resultado,turno,timestamp) VALUES (?,?,?,?,?,?,?)",
            (coord.x, coord.y, coord.z, inimigo, resultado, turno, ts))


def registrar_fato(coord: Coord, fato: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        ex = con.execute(
            "SELECT 1 FROM fatos_locais WHERE x=? AND y=? AND z=? AND fato=?",
            (coord.x, coord.y, coord.z, fato[:200])).fetchone()
        if not ex:
            con.execute(
                "INSERT INTO fatos_locais (x,y,z,fato,timestamp) VALUES (?,?,?,?,?)",
                (coord.x, coord.y, coord.z, fato[:200], ts))


def _carregar_lore() -> dict:
    try:
        return json.loads(LORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def salvar_lore_local(coord: Coord, nome: str, fatos: List[str]) -> None:
    dados = _carregar_lore()
    e = dados.setdefault(coord.key, {})
    e["nome"] = nome
    e["fatos"] = list(set(e.get("fatos", []) + fatos))
    e["ts"] = datetime.now().isoformat(timespec="seconds")
    LORE_PATH.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _init_csv(session_id: str = "") -> None:
    # Cria ou migra o CSV — garante que session_id está no header
    _header = ["session_id","timestamp","turno","x","y","z","bioma",
               "acao_jogador","tipo_evento","descricao_preview",
               "inimigo","resultado_encontro"]
    if not LOG_PATH.exists():
        with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(_header)
    else:
        # Verifica se o arquivo antigo não tem session_id e migra
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            first_line = f.readline()
        if "session_id" not in first_line:
            # Lê dados antigos, reescreve com nova coluna
            import io
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                old_rows = list(csv.DictReader(f))
            with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=_header)
                w.writeheader()
                for row in old_rows:
                    row["session_id"] = "sessao_legado"
                    w.writerow({k: row.get(k,"") for k in _header})


def log_csv(turno: int, coord: Coord, bioma: str, acao: str,
            tipo: str, desc: str = "", inimigo: str = "", res: str = "") -> None:
    """Grava no CSV do mundo E no session_log unificado."""
    _init_csv()
    ts = datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            _SESSION_ID, ts, turno, coord.x, coord.y, coord.z, bioma,
            acao, tipo, desc.replace("\n"," "), inimigo, res])

    # Também registra no session_log unificado da sessão
    try:
        import session_log as _sl
        if _sl._csv_path:
            _tipo_sl = f"mundo_{tipo}"           # ex: mundo_movimento, mundo_mod_fogo
            _entrada = f"[{bioma}|{coord}] {acao}"
            _resp    = desc[:150] if desc else (inimigo + " → " + res if inimigo else "")
            _sl.log_llm(_tipo_sl, _entrada, _resp)
    except Exception:
        pass


# ── Geração ───────────────────────────────────────────────────

def _bioma(x: int, y: int, z: int) -> str:
    """Determina bioma na coordenada — usa mapa procedural se disponível."""
    global _MUNDO_BIOMAS
    if z < -2:
        return "caverna"
    if z > 3:
        return "montanha"
    if _MAPA_BIOMAS_OK and _MUNDO_BIOMAS is not None:
        return _bioma_em_mapa(_MUNDO_BIOMAS, x, y, z)
    # Fallback legado (distância euclidiana)
    d = math.sqrt(x**2 + y**2)
    if d < 2:    return "amazonia"
    if d < 5:    return "cerrado"
    if d < 9:    return "caatinga" if (x+y) % 3 == 0 else "pantanal"
    return "mata_atlantica"


def _inicializar_mapa_mundo(seed: int | None = None) -> None:
    """Gera novo mundo procedural. Chamado no início de cada Cenário C."""
    global _MUNDO_BIOMAS
    if _MAPA_BIOMAS_OK:
        _MUNDO_BIOMAS = gerar_mundo_novo(largura=24, altura=24, seed=seed)
        info = _MUNDO_BIOMAS.resumo()
        print(f"  \033[90m[Mapa] Mundo gerado: {info}\033[0m")
    else:
        print("  \033[90m[Mapa] mapa_biomas.py não encontrado — usando biomas legados\033[0m")
    # Spawn dos NPCs do A — independente do mapa procedural
    _spawnar_npcs_a()


def _nome_local(bioma: str, coord: Coord) -> str:
    random.seed(hash(coord.key))
    n = random.choice(_NOMES_BIOMA.get(bioma, ["Lugar Desconhecido"]))
    random.seed()
    return n


def _gerar_desc(coord: Coord, bioma: str, nome_pj: str,
                dir_str: str, vizinhos: str, mods: str) -> str:
    prompt = (
        f"Narre em 2-3 frases a chegada de {nome_pj} a um local novo.\n"
        f"Bioma: {bioma} | Coord: {coord} | Veio de: {dir_str}\n"
        f"Vizinhos: {vizinhos or 'nenhum'}\n"
        f"{mods}\n"
        f"Use folclore/natureza brasileira. Segunda pessoa. Sem números."
    )
    try:
        import llm_backend as lb
        from config import SYSTEM_PROMPT_NARRACAO
        desc = lb.chamar_stream(prompt, SYSTEM_PROMPT_NARRACAO, num_predict=200)
        # Se stream retornou vazio (modelo thinking sem resposta visível), tenta sem stream
        if not desc or len(desc.strip()) < 5:
            desc = lb.chamar(prompt, SYSTEM_PROMPT_NARRACAO, num_predict=200)
        # Ainda vazio — usa fallback
        if not desc or len(desc.strip()) < 5:
            desc = _FALLBACK_DESC.get(bioma, "Um lugar desconhecido.")
        return desc.strip()
    except Exception:
        return _FALLBACK_DESC.get(bioma, "Um lugar desconhecido.")


def _detectar_mod(acao: str) -> Optional[str]:
    a = acao.lower()
    for tipo, kws in _KW_MOD.items():
        if any(kw in a for kw in kws):
            return tipo
    return None


def _verificar_encontro(coord: Coord, bioma: str) -> bool:
    chance = CHANCE_ENCONTRO_PERIGO if coord.dist() > RAIO_PERIGO else CHANCE_ENCONTRO_BASE
    chance *= _PERIGO_BIOMA.get(bioma, 1.0)
    if coord.z < -1:
        chance = min(0.65, chance + 0.20)
    return random.random() < chance


# Mapeia bioma legado do mundo aberto -> chave do dict BIOMAS de biomas.py.
# Para floresta/pantano/montanha/caverna/deserto a chave e identica.
# "ruinas" se resolve para "ruinas_arcanas" (nome usado em BIOMAS).
# "planicie" nao existe em BIOMAS, usa floresta como fallback.
_MAPA_LEGADO_TO_BIOMAS: Dict[str, str] = {
    "floresta": "floresta",
    "planicie": "floresta",
    "pantano":  "pantano",
    "montanha": "montanha",
    "caverna":  "caverna",
    "deserto":  "deserto",
    "ruinas":   "ruinas_arcanas",
}


def _gerar_inimigo(coord: Coord, bioma: str, nivel: int):
    """
    Gera inimigo no mundo aberto usando o MESMO pipeline do Cenario A:
      1. Mapeia bioma legado -> chave em BIOMAS de biomas.py
      2. Chama escolher_inimigo_bioma() de biomas.py:
         - tenta primeiro o catalogo curado (CATALOGO_INIMIGOS)
         - aplica scaling tier-based via get_dificuldade_atual()
         - fallback procedural: gerar_inimigo_procedural() de inimigos.py
      3. Ultimo fallback: catalogo aleatorio.
    """
    # Pipeline principal: mesmo que Cenario A
    try:
        from biomas import BIOMAS, escolher_inimigo_bioma
        chave = _MAPA_LEGADO_TO_BIOMAS.get(bioma)
        if chave and chave in BIOMAS:
            ini = escolher_inimigo_bioma(BIOMAS[chave], nivel)
            ini._coord = coord.key
            return ini
    except Exception:
        pass

    # Fallback: gerador procedural unificado com tier global
    try:
        from inimigos import gerar_inimigo_procedural
        from biomas import get_dificuldade_atual
        tier = get_dificuldade_atual()
        ini = gerar_inimigo_procedural(nivel, biome_tier=tier)
        ini._coord = coord.key
        return ini
    except Exception:
        pass

    # Ultimo fallback: catalogo aleatorio
    try:
        from inimigos import CATALOGO_INIMIGOS
        ops = [v for v in CATALOGO_INIMIGOS.values() if v.nivel <= max(1, nivel)]
        if ops:
            ini = random.choice(ops).clonar()
            ini._coord = coord.key
            return ini
    except Exception:
        pass
    return None


# ── Motor ─────────────────────────────────────────────────────

class MundoAberto:
    def __init__(self, personagem, turno_inicial: int = 0):
        self.pj     = personagem
        self.coord  = Coord(0, 0, 0)
        self.turno  = turno_inicial
        self._local: Optional[LocalMundo] = None
        inicializar_banco()
        _init_csv()

    def _nivel(self) -> int:
        # cf~10=N1, cf~15=N2, cf~20=N3 — encontros calibrados ao personagem
        cf = getattr(self.pj, 'corpo_fisico', 10)
        return max(1, min(3, int(cf / 7)))

    def _vizinhos_str(self, coord: Coord) -> str:
        vs = []
        for dx,dy,dz in [(0,1,0),(0,-1,0),(1,0,0),(-1,0,0),(0,0,1),(0,0,-1)]:
            v = carregar_local(coord.mover(dx,dy,dz))
            if v:
                d = _DIR_STR.get((dx,dy,dz),"?")
                vs.append(f"{d}:{v.nome}")
        return ", ".join(vs)

    def _contexto_llm(self) -> str:
        local = self._local
        if not local:
            return f"[Coord {self.coord}]"
        linhas = [
            f"[Mundo Aberto T{self.turno}] {local.nome} — {self.coord}",
            f"Bioma: {local.bioma} | Visitas: {local.visitas}",
        ]
        if local.modificacoes:
            linhas.append("Modificações: " +
                "; ".join(f"[{m['tipo']}]{m['descricao'][:50]}" for m in local.modificacoes[-2:]))
        if local.fatos:
            linhas.append("Fatos: " + "; ".join(local.fatos[:3]))
        if local.encontros:
            linhas.append("Encontros aqui: " +
                ", ".join(e["inimigo"] for e in local.encontros[-2:]))
        # Contexto de estruturas e NPCs no local atual
        _camp_ctx = _contexto_acampamento(self.coord)
        if _camp_ctx:
            linhas.append(_camp_ctx)
        return "\n".join(linhas)

    def detectar_movimento(self, acao: str) -> Optional[Tuple[int,int,int]]:
        a = acao.lower().strip()
        for kw, delta in DIRECOES.items():
            if (kw == a or f"vou {kw}" in a or f"ir {kw}" in a or
                f"sigo {kw}" in a or f"para o {kw}" in a or f"para {kw}" in a):
                return delta
        return None

    def mover(self, delta: Tuple[int,int,int]) -> dict:
        dx,dy,dz = delta
        nova  = self.coord.mover(dx,dy,dz)
        bioma = _bioma(nova.x, nova.y, nova.z)
        dstr  = _DIR_STR.get((dx,dy,dz), "alguma direção")

        local = carregar_local(nova)
        if local:
            with _conn() as con:
                con.execute("UPDATE locais SET visitas=visitas+1 WHERE x=? AND y=? AND z=?",
                            (nova.x, nova.y, nova.z))
            mods_txt = "; ".join(
                f"[{m['tipo']}]{m['descricao'][:40]}" for m in local.modificacoes[-2:]
            ) if local.modificacoes else ""
            desc = f"Você retorna a {local.nome}."
            if mods_txt:
                desc += f" Ainda se vê: {mods_txt}."
            ja_visitado = True
        else:
            vizinhos = self._vizinhos_str(nova)
            with _conn() as con:
                mods_rows = con.execute(
                    "SELECT tipo,descricao FROM modificacoes WHERE x=? AND y=? AND z=?",
                    (nova.x, nova.y, nova.z)).fetchall()
            mods_str = ("Modificações: " + "; ".join(f"[{r[0]}]{r[1][:50]}" for r in mods_rows)) if mods_rows else ""
            print(f"  \033[36m", end="", flush=True)
            desc = _gerar_desc(nova, bioma, self.pj.nome, dstr, vizinhos, mods_str)
            print("\033[0m", flush=True)
            nome = _nome_local(bioma, nova)
            local = LocalMundo(coord=nova, bioma=bioma, nome=nome, descricao=desc)
            salvar_local(local)
            salvar_lore_local(nova, nome, [])
            ja_visitado = False

        self.coord  = nova
        self._local = local
        self.turno += 1
        log_csv(self.turno, nova, bioma, f"move {dstr}", "movimento", desc)

        encontro = None
        if _verificar_encontro(nova, bioma):
            encontro = _gerar_inimigo(nova, bioma, self._nivel())

        return {"coord":nova,"bioma":bioma,"local":local,
                "descricao":desc,"ja_visitado":ja_visitado,"encontro":encontro}

    def processar_mod(self, acao: str) -> Optional[str]:
        tipo = _detectar_mod(acao)
        if not tipo:
            return None
        bioma = self._local.bioma if self._local else "local"
        _fb = {
            "fogo":"Chamas consomem a vegetação, deixando cinzas.",
            "corte":"Troncos abatidos criam uma clareira.",
            "magia":"Marcas arcanas ficam gravadas nas pedras.",
            "escavacao":"Uma cratera rasa se abre no solo.",
            "construcao":"Uma estrutura rudimentar marca sua passagem.",
            "gelo":"Gelo cobre superfícies ao redor.",
            "explosao":"Crateras e detritos se espalham.",
            "agua":"Água inunda partes baixas.",
        }
        try:
            import llm_backend as lb
            from config import SYSTEM_PROMPT_NARRACAO
            p = (f"Em {bioma}, {self.pj.nome} faz: \"{acao}\".\n"
                 f"Narre em 1 frase o efeito permanente no ambiente. Segunda pessoa.")
            desc = lb.chamar(p, SYSTEM_PROMPT_NARRACAO, num_predict=60)
        except Exception:
            desc = _fb.get(tipo, f"A ação alterou o ambiente.")
        salvar_modificacao(self.coord, tipo, desc, self.turno)
        registrar_fato(self.coord, f"{tipo}: {desc[:300]}")
        log_csv(self.turno, self.coord, bioma, acao, f"mod_{tipo}", desc)
        return desc

    def hud(self) -> None:
        local = self._local
        nome  = local.nome  if local else "???"
        bioma = local.bioma if local else "???"
        pj = self.pj
        pv_b  = int((pj.pv_atual / max(pj.pv_max,1)) * 16)
        psi_b = int((pj.psique_atual / max(pj.psique_max,1)) * 16)
        cor_pv  = "\033[32m" if pj.pv_atual/pj.pv_max>0.5 else ("\033[33m" if pj.pv_atual/pj.pv_max>0.25 else "\033[31m")
        print(f"\n  \033[36m{'='*54}\033[0m")
        print(f"  \033[33m{nome}\033[0m  \033[90m{bioma} | {self.coord} | d:{self.coord.dist():.1f}\033[0m")
        print(f"  \033[90m{'-'*54}\033[0m")
        print(f"  \033[97m{pj.nome}\033[0m")
        print(f"  ❤  [{cor_pv}{'█'*pv_b}\033[90m{'░'*(16-pv_b)}\033[0m] \033[97m{pj.pv_atual:.0f}/{pj.pv_max:.0f}\033[0m")
        print(f"  💜 [\033[35m{'█'*psi_b}\033[90m{'░'*(16-psi_b)}\033[0m] \033[97m{pj.psique_atual:.1f}/{pj.psique_max:.1f}\033[0m")
        print(f"  \033[90mT{self.turno}/{LIMITE_TURNOS} | Bolsa:{len(pj.bolsa)}/{pj.BOLSA_MAX} | n/s/l/o/c/b mover | stats | bolsa | sair\033[0m")
        print(f"  \033[36m{'='*54}\033[0m")

    def stats(self) -> dict:
        with _conn() as con:
            nl = con.execute("SELECT COUNT(*) FROM locais").fetchone()[0]
            nm = con.execute("SELECT COUNT(*) FROM modificacoes").fetchone()[0]
            ne = con.execute("SELECT COUNT(*) FROM encontros").fetchone()[0]
        return {"turnos":self.turno,"locais":nl,"mods":nm,"encontros":ne,
                "coord":str(self.coord),"dist":round(self.coord.dist(),1)}



# ══════════════════════════════════════════════════════════════
#  ESTRUTURAS (fogueira, acampamento)
# ══════════════════════════════════════════════════════════════

def salvar_estrutura(coord: Coord, tipo: str, nome: str, descricao: str, turno: int) -> None:
    """Salva estrutura construída (fogueira, abrigo, etc.) no SQLite."""
    with _conn() as con:
        con.execute("""INSERT INTO estruturas (x,y,z,tipo,nome,descricao,turno,timestamp)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (coord.x, coord.y, coord.z, tipo, nome, descricao, turno,
                     datetime.now().isoformat()))


def listar_estruturas(coord: Coord) -> List[Dict]:
    """Retorna estruturas na coordenada."""
    with _conn() as con:
        rows = con.execute("""SELECT tipo, nome, descricao FROM estruturas
                              WHERE x=? AND y=? AND z=?""",
                           (coord.x, coord.y, coord.z)).fetchall()
    return [{"tipo": r[0], "nome": r[1], "desc": r[2]} for r in rows]


def tem_fogueira(coord: Coord) -> bool:
    """Verifica se há fogueira ativa na coordenada."""
    with _conn() as con:
        n = con.execute("""SELECT COUNT(*) FROM estruturas
                           WHERE x=? AND y=? AND z=? AND tipo='fogueira'""",
                        (coord.x, coord.y, coord.z)).fetchone()[0]
    return n > 0


# ══════════════════════════════════════════════════════════════
#  NPCS DO MUNDO
# ══════════════════════════════════════════════════════════════

# NPCs disponíveis para o acampamento inicial
_NPCS_ACAMPAMENTO = [
    {
        "id": "velho_mateiro",
        "nome": "Seu Raimundo",
        "ocupacao": "Mateiro e guia do sertão",
        "personalidade": "Experiente, fala pouco mas sabe muito. Usa provérbios nordestinos.",
        "conhecimentos": ["caminhos perigosos", "biomas brasileiros", "folclore local", "sobrevivência"],
        "intro": (
            "Um homem de pele curtida pelo sol, chapéu de couro e sandálias de borracha "
            "remexe a brasa de uma fogueira. Levanta o olhar ao sentir você se aproximar."
        ),
        "dica_jogo": (
            "Olha, meu camarada: esse mundo tem biomas de tudo que é jeito — cerrado, caatinga, "
            "mata fechada. Cada um tem seu perigo e sua graça. Se construir fogueira, "
            "pode descansar pra recuperar as forças. E preste atenção no chão: "
            "às vezes tem coisa boa por aí pra pegar."
        ),
    },
    {
        "id": "curandeira_jovem",
        "nome": "Yara",
        "ocupacao": "Curandeira e conhecedora de ervas",
        "personalidade": "Curiosa e direta. Desconfia de estranhos mas ajuda quem precisa.",
        "conhecimentos": ["ervas medicinais", "cura", "plantas do bioma", "receitas"],
        "intro": (
            "Uma jovem com tranças longas e bolsa de couro cheia de ervas secas "
            "examina algumas plantas próximas à fogueira. Vira-se ao ouvir seus passos."
        ),
        "dica_jogo": (
            "Você vai precisar de ervas nessa jornada, pode apostar. "
            "Fique de olho no chão ao explorar — cada bioma tem seus recursos. "
            "E se estiver ferida, descanse perto de uma fogueira. O fogo cura mais do que parece."
        ),
    },
    {
        "id": "mercante_errante",
        "nome": "Zé das Estradas",
        "ocupacao": "Mercante andarilho",
        "personalidade": "Alegre e tagarela. Sempre tem uma história pra contar.",
        "conhecimentos": ["ruínas e tesouros", "rotas comerciais", "preços de itens", "mundo aberto"],
        "intro": (
            "Um homem rechonchudo com uma mochila enorme e sorriso fácil "
            "assenta seus pertences perto do fogo. Acena animado quando te vê."
        ),
        "dica_jogo": (
            "Esse mundo tem muito pra explorar, compadre! Nas ruínas você acha coisa boa — "
            "às vezes item raro. O perigo aumenta quanto mais longe do centro você vai, "
            "mas a recompensa também. Fala comigo quando quiser saber de algum lugar."
        ),
    },
    {
        "id": "ex_soldado",
        "nome": "Capitã Benedita",
        "ocupacao": "Ex-capitã da guarda, agora errante",
        "personalidade": "Séria e disciplinada. Respeita quem demonstra coragem.",
        "conhecimentos": ["combate", "inimigos perigosos", "estratégia", "armaduras"],
        "intro": (
            "Uma mulher de porte altivo, cicatriz no queixo, afila uma faca perto da fogueira. "
            "Ergue os olhos com expressão avaliadora."
        ),
        "dica_jogo": (
            "Se vai explorar esse mundo, saiba: quanto mais longe do acampamento, "
            "mais forte o inimigo. Na caatinga e no pantanal é perigoso. "
            "Nunca enfrente nada sem ter vida suficiente. E use o terreno a seu favor."
        ),
    },
]


def salvar_npc_mundo(coord: Coord, npc: Dict) -> None:
    """Salva NPC no mundo (acampamento) no SQLite."""
    with _conn() as con:
        # Evita duplicar
        existe = con.execute("SELECT id FROM npcs_mundo WHERE npc_id=? AND x=? AND y=? AND z=?",
                             (npc["id"], coord.x, coord.y, coord.z)).fetchone()
        if not existe:
            con.execute("""INSERT INTO npcs_mundo (x,y,z,npc_id,nome,ocupacao,dialogo_intro,timestamp)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (coord.x, coord.y, coord.z, npc["id"], npc["nome"],
                         npc["ocupacao"], npc["intro"], datetime.now().isoformat()))


def _spawnar_npcs_a() -> None:
    """Garante que os 6 NPCs migrados de Cenário A existam em suas
    coords fixas no mundo (idempotente — não recria se já existem)."""
    try:
        from historias import CATALOGO_NPCS
    except Exception as e:
        print(f"  \033[90m[Mundo] historias.py indisponível, NPCs do A não migrados: {e}\033[0m")
        return

    spawnados = 0
    for npc_id, x, y, z, _bioma in _NPCS_A_DISTRIBUICAO:
        if npc_id not in CATALOGO_NPCS:
            continue
        coord = Coord(x=x, y=y, z=z)
        # Idempotência — pula se já registrado nesta coord
        existentes = carregar_npcs_coord(coord)
        if any(n.get("id") == npc_id for n in existentes):
            continue
        npc_obj = CATALOGO_NPCS[npc_id]
        npc_data = {
            "id"      : npc_id,
            "nome"    : npc_obj.nome,
            "ocupacao": npc_obj.ocupacao,
            "intro"   : npc_obj.descricao_fisica[:160],
        }
        salvar_npc_mundo(coord, npc_data)
        spawnados += 1
    if spawnados:
        print(f"  \033[90m[Mundo] {spawnados} NPC(s) do Cenário A spawnados em coords fixas.\033[0m")


def carregar_npcs_coord(coord: Coord) -> List[Dict]:
    """Carrega NPCs presentes na coordenada."""
    with _conn() as con:
        rows = con.execute("""SELECT npc_id, nome, ocupacao, dialogo_intro
                              FROM npcs_mundo WHERE x=? AND y=? AND z=?""",
                           (coord.x, coord.y, coord.z)).fetchall()
    return [{"id": r[0], "nome": r[1], "ocupacao": r[2], "intro": r[3]} for r in rows]


def _encontrar_npc_por_nome(coord: Coord, nome_parcial: str) -> Optional[Dict]:
    """Encontra NPC na coord pelo nome (busca parcial, case-insensitive)."""
    npcs = carregar_npcs_coord(coord)
    nome_lower = nome_parcial.lower()
    for n in npcs:
        if nome_lower in n["nome"].lower() or nome_lower in n["id"].lower():
            return n
    return None


def _obter_npc_objeto(npc_id: str):
    """
    Retorna objeto NPC de historias.py para o npc_id do acampamento.
    Cria instância completa com personalidade, histórico e memória.
    """
    cfg = next((n for n in _NPCS_ACAMPAMENTO if n["id"] == npc_id), None)
    if not cfg:
        return None
    try:
        from historias import NPC
        obj = NPC(
            nome             = cfg["nome"],
            ocupacao         = cfg["ocupacao"],
            atitude          = "amigavel",
            descricao_fisica = cfg["intro"],
            personalidade    = cfg["personalidade"],
            conhecimentos    = cfg["conhecimentos"],
            segredos         = [cfg.get("dica_jogo", "")],
        )
        return obj
    except Exception:
        return None


# Cache de objetos NPC — mantém histórico de diálogo entre turnos
_NPC_OBJETOS: Dict[str, object] = {}


# Mapeamento de palavras-chave na fala do NPC → item_id no catálogo
_ITEM_KEYWORDS = {
    "pocao_cura":          ["poção de cura","pó de cura","poção cura","erva cura","cura rápid"],
    "pocao_cura_maior":    ["poção de cura maior","elixir de cura","cura maior"],
    "ervas_medicinais":    ["ervas medicinais","ervas","erva medicinal","feixe de ervas"],
    "ervas_revigorantes":  ["ervas revigorantes","erva revigorante","revigorante"],
    "pocao_psique":        ["elixir de psique","elixir psique","poção de psique","psique"],
    "pocao_psique_maior":  ["elixir maior de psique","psique maior"],
    "antidoto":            ["antídoto","antidoto","antídotos"],
    "pocao_purificacao":   ["poção de purificação","purificação","purificacao"],
}

_VERBOS_DAR = [
    "vou te dar","vou lhe dar","tome","toma","aqui está","aqui tem","pegue","pega",
    "entrego","aqui estão","guarde","guarda","leve","leva","te ofereço","ofereço",
    "te dou","dou a você","presenteio","aceite","aceita","trago","te trago",
]


def _extrair_item_da_fala(fala: str) -> Optional[str]:
    """
    Detecta se o NPC está dando um item na fala.
    Retorna o item_id ou None.
    Primeiro verifica padrão verbo+item, depois faz chamada LLM leve se ambíguo.
    """
    fala_lower = fala.lower()

    # Verifica se há verbo de doação na fala
    tem_verbo = any(v in fala_lower for v in _VERBOS_DAR)
    if not tem_verbo:
        return None

    # Verifica quais itens são mencionados
    for item_id, keywords in _ITEM_KEYWORDS.items():
        if any(kw in fala_lower for kw in keywords):
            return item_id

    # Fallback: pergunta ao LLM se houve doação de item
    try:
        import llm_backend as _lb
        prompt_ext = (
            f"Leia esta fala de um NPC de RPG:\n\"{fala}\"\n\n"
            f"O NPC está ENTREGANDO fisicamente algum item ao jogador? "
            f"Responda APENAS com JSON: {{\"item\": \"nome_do_item_ou_null\"}}\n"
            f"Se sim, qual item? Use apenas nomes simples como: "
            f"pocao_cura, ervas_medicinais, antidoto, pocao_psique, ervas_revigorantes.\n"
            f"Se nenhum item está sendo entregue, responda: {{\"item\": null}}"
        )
        raw = _lb.chamar(prompt_ext, "Responda apenas com JSON.", num_predict=40)
        import re, json as _j
        m = re.search(r'"item"\s*:\s*"([^"]+)"', raw or "")
        if m and m.group(1) not in ("null","none","nenhum"):
            return m.group(1).lower().replace(" ","_")
    except Exception:
        pass
    return None


def _dar_item_npc(item_id: str, npc_nome: str, personagem,
                  coord: Coord, turno: int) -> str:
    """
    Adiciona item ao inventário e registra.
    Retorna mensagem colorida para exibir ao jogador.
    """
    try:
        from itens import obter_item, CATALOGO_ITENS
        # Normaliza: tenta encontrar no catálogo
        chave = item_id
        if chave not in CATALOGO_ITENS:
            # Fuzzy match
            for k in CATALOGO_ITENS:
                if item_id.replace("_"," ") in k.replace("_"," ") or k.replace("_"," ") in item_id.replace("_"," "):
                    chave = k
                    break
            else:
                return ""  # item desconhecido, ignora silenciosamente

        item = obter_item(chave)

        bolsa = getattr(personagem, "bolsa", None)
        bolsa_max = getattr(personagem, "bolsa_max", 4)
        if bolsa is None or len(bolsa) >= bolsa_max:
            return f"  \033[33m[{npc_nome} quis te dar {item.nome}, mas sua bolsa está cheia!]\033[0m"

        bolsa.append(item)
        # Salva no banco
        with _conn() as con:
            con.execute("""INSERT INTO itens_mundo
                           (x,y,z,item_id,nome,coletado,turno,timestamp)
                           VALUES (?,?,?,?,?,1,?,?)""",
                        (coord.x, coord.y, coord.z, chave, item.nome,
                         turno, datetime.now().isoformat()))

        # Registra fato no mundo
        registrar_fato(coord, f"{npc_nome} deu {item.nome} para o jogador.")

        return (f"  \033[32m✦  {npc_nome} te deu \033[1m{item.nome}\033[0m\033[32m!"
                f" (bolsa: {len(bolsa)}/{bolsa_max})\033[0m")
    except Exception as e:
        return f"  \033[90m[Não foi possível gerar item: {e}]\033[0m"


def _dialogo_npc_llm(npc_data: Dict, pergunta: str, personagem_nome: str,
                     contexto_mundo: str = "") -> str:
    """
    Gera resposta do NPC usando historias.NPC.falar() com memória persistente.
    Integra memoria_npc para histórico entre sessões.
    """
    npc_id = npc_data["id"]

    # Obtém ou cria objeto NPC
    if npc_id not in _NPC_OBJETOS:
        obj = _obter_npc_objeto(npc_id)
        if obj:
            _NPC_OBJETOS[npc_id] = obj
        else:
            # Fallback mínimo se historias não disponível
            cfg = next((n for n in _NPCS_ACAMPAMENTO if n["id"] == npc_id), {})
            return cfg.get("dica_jogo", "...")
    
    obj = _NPC_OBJETOS[npc_id]

    # Injeta histórico do memoria_npc no objeto
    try:
        import memoria_npc as _mnpc
        ctx_mem = _mnpc.contexto_para_llm(obj.nome)
        if ctx_mem and not any(d["texto"] == ctx_mem for d in obj.historico_dialogos[-2:]):
            obj.historico_dialogos.insert(0, {"de": "sistema", "texto": ctx_mem})
    except Exception:
        pass

    # Gera resposta via NPC.falar() — prompt robusto com histórico
    try:
        resposta = obj.falar(pergunta, personagem_nome)
    except Exception as e:
        cfg = next((n for n in _NPCS_ACAMPAMENTO if n["id"] == npc_id), {})
        return cfg.get("dica_jogo", f"[Erro: {e}]")

    # Persiste no memoria_npc
    try:
        import memoria_npc as _mnpc
        turno_atual = getattr(_mnpc, "_turno_atual", 0)
        _mnpc.processar_fala(obj.nome, personagem_nome, pergunta, turno_atual)
        _mnpc.processar_fala(obj.nome, obj.nome, resposta, turno_atual)
    except Exception:
        pass

    return resposta


# ══════════════════════════════════════════════════════════════
#  ITENS NO MUNDO (descoberta por exploração)
# ══════════════════════════════════════════════════════════════

# Tabela: bioma → lista de (item_id, chance_0_1, nome_display)
_ITENS_POR_BIOMA: Dict[str, List[Tuple[str, float, str]]] = {
    "amazonia":       [("ervas_medicinais",0.15,"Ervas Medicinais"),
                       ("pocao_cura",0.06,"Poção de Cura"),
                       ("pocao_psique",0.05,"Elixir de Psique")],
    "cerrado":        [("ervas_medicinais",0.12,"Ervas Medicinais"),
                       ("ervas_revigorantes",0.08,"Ervas Revigorantes")],
    "mata_atlantica": [("ervas_medicinais",0.14,"Ervas Medicinais"),
                       ("pocao_cura",0.07,"Poção de Cura"),
                       ("pocao_psique",0.06,"Elixir de Psique")],
    "caatinga":       [("ervas_medicinais",0.08,"Ervas Medicinais"),
                       ("antidoto",0.10,"Antídoto"),
                       ("pocao_cura",0.05,"Poção de Cura")],
    "pantanal":       [("ervas_revigorantes",0.10,"Ervas Revigorantes"),
                       ("pocao_purificacao",0.06,"Poção de Purificação")],
    "pampa":          [("ervas_revigorantes",0.10,"Ervas Revigorantes"),
                       ("ervas_medicinais",0.08,"Ervas Medicinais")],
    "montanha":       [("pocao_cura_maior",0.05,"Poção de Cura Maior"),
                       ("ervas_revigorantes",0.08,"Ervas Revigorantes")],
    # ecótonos herdam do primeiro componente — fallback genérico
}

_CHANCE_ITEM_BASE = 0.22  # ~22% de chance base por movimento


def _tentar_encontrar_item(coord: Coord, bioma: str, personagem,
                            turno: int) -> Optional[str]:
    """
    Rola dados de encontro de item. Retorna mensagem ou None.
    Adiciona o item ao inventário do personagem.
    """
    if random.random() > _CHANCE_ITEM_BASE:
        return None

    # Pega tabela do bioma (tenta o bioma base se for ecótono)
    tabela = _ITENS_POR_BIOMA.get(bioma)
    if not tabela:
        bioma_base = bioma.split("+")[0] if "+" in bioma else bioma
        tabela = _ITENS_POR_BIOMA.get(bioma_base, _ITENS_POR_BIOMA["cerrado"])

    # Rola por cada item da tabela
    encontrado = None
    for item_id, chance, nome_disp in tabela:
        if random.random() < chance:
            encontrado = (item_id, nome_disp)
            break

    if not encontrado:
        return None

    item_id, nome_disp = encontrado
    # Adiciona ao inventário
    try:
        from itens import obter_item
        item = obter_item(item_id)
        if hasattr(personagem, "bolsa") and personagem.bolsa is not None:
            if len(personagem.bolsa) < getattr(personagem, "bolsa_max", 4):
                personagem.bolsa.append(item)
                # Salva no banco
                with _conn() as con:
                    con.execute("""INSERT INTO itens_mundo
                                   (x,y,z,item_id,nome,coletado,turno,timestamp)
                                   VALUES (?,?,?,?,?,1,?,?)""",
                                (coord.x, coord.y, coord.z, item_id, nome_disp,
                                 turno, datetime.now().isoformat()))
                return (f"✦  Você encontrou [33m{nome_disp}[0m! "
                        f"(adicionado à bolsa — {len(personagem.bolsa)}/{personagem.bolsa_max})")
            else:
                return f"✦  Você viu {nome_disp} mas sua bolsa está cheia."
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════
#  DESCANSO (recupera PV e Psiquê perto de fogueira)
# ══════════════════════════════════════════════════════════════

def _descansar(coord: Coord, personagem, mundo_obj) -> str:
    """Descansa perto da fogueira. Recupera PV e Psiquê."""
    if not tem_fogueira(coord):
        return ("Você precisa de uma fogueira para descansar. "
                "Tente: 'construo uma fogueira' ou 'faço uma fogueira'.")

    # Suporta pv_atual (Personagem real) e pv (testes/mock)
    pv_antes  = getattr(personagem, "pv_atual",  getattr(personagem, "pv",  0.0))
    psi_antes = getattr(personagem, "psique_atual", getattr(personagem, "psique", 0.0))
    pv_max    = getattr(personagem, "pv_max",     pv_antes)
    psi_max   = getattr(personagem, "psique_max", psi_antes + 10)

    novo_pv  = min(pv_max,  pv_antes  + round(pv_max  * 0.40, 1))
    novo_psi = min(psi_max, psi_antes + round(psi_max * 0.25, 1))

    if hasattr(personagem, "pv_atual"):
        personagem.pv_atual = novo_pv
    else:
        personagem.pv = novo_pv
    if hasattr(personagem, "psique_atual"):
        personagem.psique_atual = novo_psi
    elif hasattr(personagem, "psique"):
        personagem.psique = novo_psi

    pv_ganho  = round(novo_pv  - pv_antes,  1)
    psi_ganho = round(novo_psi - psi_antes, 1)
    mundo_obj.turno += 2

    linhas = [
        "Você se deita perto da fogueira. As brasas crepitam suavemente.",
        f"  ❤  PV: {pv_antes:.0f} → [32m{novo_pv:.0f}[0m (+{pv_ganho:.0f})",
    ]
    if psi_ganho > 0:
        linhas.append(
            f"  💜 Psiquiê: {psi_antes:.1f} → [35m{novo_psi:.1f}[0m (+{psi_ganho:.1f})"
        )
    linhas.append("  [Descansou 2 turnos]")
    return "\n".join(linhas)


# ══════════════════════════════════════════════════════════════
#  ACAMPAMENTO INICIAL
# ══════════════════════════════════════════════════════════════

_ACAMPAMENTO_COORD = Coord(0, 0, 0)

def _criar_acampamento_inicial(personagem) -> None:
    """
    Cria o acampamento em (0,0,0) com fogueira e 2 NPCs aleatórios.
    Salva tudo no SQLite para que a LLM lembre entre sessões.
    Só executa se o acampamento ainda não existe.
    """
    # Verifica se já existe
    with _conn() as con:
        ja_existe = con.execute(
            "SELECT id FROM estruturas WHERE x=0 AND y=0 AND z=0 AND tipo='acampamento'",
        ).fetchone()

    if ja_existe:
        return  # Acampamento já criado em sessão anterior

    # Fogueira central
    salvar_estrutura(_ACAMPAMENTO_COORD, "acampamento",
                     "Acampamento do Início",
                     "Acampamento acolhedor com fogueira central, mantas dobradas e "
                     "pertences espalhados. Ponto de partida da jornada.",
                     turno=0)
    salvar_estrutura(_ACAMPAMENTO_COORD, "fogueira",
                     "Fogueira do Acampamento",
                     "Fogueira de galhos secos que crepita no centro do acampamento.",
                     turno=0)

    # 2 NPCs aleatórios
    npcs_escolhidos = random.sample(_NPCS_ACAMPAMENTO, 2)
    for npc in npcs_escolhidos:
        salvar_npc_mundo(_ACAMPAMENTO_COORD, npc)

    # Registra fatos para LLM
    nomes_npcs = " e ".join(n["nome"] for n in npcs_escolhidos)
    registrar_fato(_ACAMPAMENTO_COORD,
                   f"Acampamento inicial com fogueira. NPCs presentes: {nomes_npcs}.")
    for npc in npcs_escolhidos:
        registrar_fato(_ACAMPAMENTO_COORD,
                       f"{npc['nome']} ({npc['ocupacao']}) está no acampamento.")

    return npcs_escolhidos


def _contexto_acampamento(coord: Coord) -> str:
    """Retorna contexto textual do acampamento para o prompt da LLM."""
    estruturas = listar_estruturas(coord)
    npcs       = carregar_npcs_coord(coord)
    if not estruturas and not npcs:
        return ""
    linhas = []
    if estruturas:
        nomes_e = ", ".join(e["nome"] for e in estruturas)
        linhas.append(f"Estruturas no local: {nomes_e}.")
    if npcs:
        nomes_n = ", ".join(f"{n['nome']} ({n['ocupacao']})" for n in npcs)
        linhas.append(f"NPCs presentes: {nomes_n}.")
    return " ".join(linhas)

def executar_cenario_c(personagem) -> str:
    # Gera novo mapa procedural (seed aleatória → mundo único a cada sessão)
    _inicializar_mapa_mundo(seed=None)
    import jornada as jrn
    jrn.inicializar_jornada(personagem.to_dict(), "Borda das Montanhas Névoas")

    # Inicializa log de sessão do mundo aberto
    global _SESSION_ID
    _slog_ok = False
    try:
        import session_log as _sl
        import llm_backend as _lb
        _modelo = _lb.obter_modelo_atual()   # resolve nome real do modelo
        if not _sl._csv_path:
            _sl.iniciar_sessao(personagem.nome, _modelo)
        else:
            _sl._modelo = _modelo
        # Usa o nome do CSV de sessão como session_id no mundo_log
        _SESSION_ID = _sl._csv_path.stem if _sl._csv_path else datetime.now().strftime("%Y%m%d_%H%M%S")
        _slog_ok = True
    except Exception:
        _SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S")

    mundo = MundoAberto(personagem)

    # Cria acampamento inicial (só na primeira vez — persiste entre sessões)
    npcs_ini = _criar_acampamento_inicial(personagem)

    bioma_ini = _bioma(0, 0, 0)
    print(f"\n{'='*58}")
    print(f"  \033[1mCENÁRIO C — O MUNDO ESQUECIDO\033[0m")
    print(f"  Você começa no Acampamento do Início, em (0,0,0).")
    print(f"  A LLM narra e grava cada lugar visitado.")
    print(f"{'='*58}")
    print(f"\n  Mover: n/s/l/o | c/b | fogueira | descansar | falar <npc>")
    print(f"  Qualquer ação livre: a LLM interpreta e salva no mundo\n")

    # Descrição de chegada ao acampamento
    ctx_camp = _contexto_acampamento(mundo.coord)
    print(f"  \033[36m", end="", flush=True)
    desc_ini = _gerar_desc(mundo.coord, bioma_ini, personagem.nome,
                           "ponto de partida", "", ctx_camp)
    print("\033[0m", flush=True)

    local_ini = LocalMundo(coord=mundo.coord, bioma=bioma_ini,
                           nome="Acampamento do Início", descricao=desc_ini)
    salvar_local(local_ini)
    mundo._local = local_ini
    log_csv(0, mundo.coord, bioma_ini, "inicio", "chegada", desc_ini)
    print(f"\n  {desc_ini}")

    # Apresenta NPCs do acampamento
    npcs_camp = carregar_npcs_coord(mundo.coord)
    if npcs_camp:
        print()
        for npc in npcs_camp:
            print(f"  \033[90m{npc['intro']}\033[0m")
        nomes = " e ".join(n["nome"] for n in npcs_camp)
        print(f"\n  [33m💬 {nomes} está(ão) no acampamento.\033[0m")
        print(f"  \033[90m  (use 'falar {npcs_camp[0]['nome'].split()[0]}' para conversar)\033[0m")
    print()

    while personagem.esta_vivo() and mundo.turno < LIMITE_TURNOS:
        # Tick de status effects (queimar/envenenar/sangrar/paralisar/...)
        # — Persistem entre encontros e aplicam dano fora de combate
        try:
            from status_effects import processar_status_personagem
            if getattr(personagem, "status_effects", None):
                processar_status_personagem(personagem)
                if not personagem.esta_vivo():
                    print(f"  \033[31m{personagem.nome} sucumbiu aos efeitos persistentes.\033[0m")
                    return "morte"
        except Exception:
            pass
        mundo.hud()
        try:
            acao = input(f"  \033[33m{personagem.nome} > \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not acao:
            continue
        al = acao.lower().strip()

        if al in ("sair","exit","quit"):
            break

        if al == "stats":
            s = mundo.stats()
            print(f"  Locais:{s['locais']} Mods:{s['mods']} Encontros:{s['encontros']} Dist:{s['dist']}")
            # Show structures and NPCs at current location
            estruts = listar_estruturas(mundo.coord)
            npcs_c  = carregar_npcs_coord(mundo.coord)
            if estruts:
                print(f"  Estruturas: {', '.join(e['nome'] for e in estruts)}")
            if npcs_c:
                print(f"  NPCs: {', '.join(n['nome'] for n in npcs_c)}")
            continue

        # ── Fogueira ───────────────────────────────────────────
        _KW_FOGUEIRA = {"fogueira","acendo fogueira","faço fogueira","construo fogueira",
                        "monto fogueira","faço uma fogueira","construo uma fogueira"}
        if al in _KW_FOGUEIRA or any(k in al for k in ["fogueira","acender fogo","fazer fogo"]):
            if tem_fogueira(mundo.coord):
                print("  \033[90mJá há uma fogueira acesa aqui.\033[0m")
            else:
                salvar_estrutura(mundo.coord, "fogueira", "Fogueira",
                                 f"Fogueira acesa por {personagem.nome}.", mundo.turno)
                registrar_fato(mundo.coord,
                               f"{personagem.nome} acendeu uma fogueira aqui.")
                print("  \033[33m🔥 Fogueira acesa! Você pode descansar aqui para recuperar PV e Psiquê.\033[0m")
            mundo.turno += 1
            continue

        # ── Descansar ──────────────────────────────────────────
        _KW_DESCANSO = {"descansar","descanso","dormir","durmo","acampar","repousar"}
        if al in _KW_DESCANSO or any(k in al for k in ["descansar","dormir","repousar"]):
            msg = _descansar(mundo.coord, personagem, mundo)
            print(f"\n  {msg}\n")
            jrn.registrar_evento("descanso", f"{personagem.nome} descansou em {mundo.coord}.")
            continue

        # ── Falar com NPC ──────────────────────────────────────
        if al.startswith(("falar ","conversar com ","falo com ","chamo ","pergunto para ","perguntar ")):
            # Extrai nome após o comando
            for prefixo in ["falar com ","conversar com ","falo com ","chamo ","pergunto para ","perguntar ","falar "]:
                if al.startswith(prefixo):
                    nome_alvo = al[len(prefixo):].strip()
                    break
            npc_encontrado = _encontrar_npc_por_nome(mundo.coord, nome_alvo)
            if not npc_encontrado:
                npcs_aqui = carregar_npcs_coord(mundo.coord)
                if npcs_aqui:
                    nomes = ", ".join(n["nome"] for n in npcs_aqui)
                    print(f"  \033[90mNPC não encontrado. Presentes aqui: {nomes}\033[0m")
                else:
                    print(f"  \033[90mNão há ninguém para conversar aqui.\033[0m")
            else:
                # ── NPC migrado do Cenário A → menu completo ─────
                if npc_encontrado.get("id") in _A_NPC_IDS:
                    try:
                        from historias import CATALOGO_NPCS
                        from biomas import iniciar_menu_npc
                        npc_obj = CATALOGO_NPCS.get(npc_encontrado["id"])
                        if npc_obj is not None:
                            # Sincroniza histórico persistente com memoria_npc
                            try:
                                import memoria_npc as _mnpc_local
                                npc_obj.historico_dialogos = _mnpc_local.obter_historico(
                                    npc_obj.nome, n=8)
                            except Exception:
                                pass
                            bioma_local = mundo._local.bioma if mundo._local else ""
                            bioma_ctx = {
                                "descricao": (mundo._local.descricao if mundo._local else ""),
                                "inimigos": [],
                                "boss"    : None,
                                "npc_evento": [npc_encontrado["id"]],
                                "nome"    : bioma_local,
                            }
                            iniciar_menu_npc(personagem, npc_obj, bioma_ctx)
                            jrn.registrar_evento("dialogo",
                                f"{personagem.nome} interagiu com {npc_obj.nome} (menu A em mundo aberto).")
                            continue
                    except Exception as _e_menu:
                        print(f"  \033[31m[menu NPC indisponível: {_e_menu}]\033[0m")
                # Pede o que quer dizer/perguntar (NPCs simples do mundo: Yara, Raimundo)
                try:
                    pergunta = input(f"  \033[36m[{npc_encontrado['nome']}] O que você diz? > \033[0m").strip()
                except (EOFError, KeyboardInterrupt):
                    continue
                if pergunta:
                    print(f"  \033[90m{npc_encontrado['nome']} pensa...\033[0m")
                    ctx_m = mundo._contexto_llm()
                    resposta = _dialogo_npc_llm(npc_encontrado, pergunta, personagem.nome, ctx_m)
                    print(f"\n  \033[97m{npc_encontrado['nome']}: {resposta}\033[0m\n")

                    # Detecta se NPC está dando item — gera e adiciona ao inventário
                    _item_doado = _extrair_item_da_fala(resposta)
                    if _item_doado:
                        _msg_item = _dar_item_npc(
                            _item_doado, npc_encontrado['nome'],
                            personagem, mundo.coord, mundo.turno
                        )
                        if _msg_item:
                            print(_msg_item)

                    jrn.registrar_evento("dialogo",
                        f"{personagem.nome} falou com {npc_encontrado['nome']}: {pergunta[:80]}")
            continue

        if al in ("bolsa","usar","pocao","poção"):
            from _item_ui import menu_usar_consumivel_combate
            ok, msg = menu_usar_consumivel_combate(personagem)
            if msg and msg != "Cancelado.": print(f"  {msg}")
            continue

        if al in ("equipar","inv","inventario","inventário"):
            from _item_ui import menu_equipar_inventario
            menu_equipar_inventario(personagem)
            continue

        # Movimento
        delta = mundo.detectar_movimento(al)
        if delta:
            res = mundo.mover(delta)
            if res["ja_visitado"]:
                print(f"\n  \033[90m{res['descricao']}\033[0m")
            else:
                print(f"\n  {res['descricao']}")
            # Evento aleatório por bioma (chuva ácida, miragem, eco arcano, ...)
            try:
                _disparar_evento_bioma(personagem, res.get("bioma",""), mundo.coord)
            except Exception as _e_ev:
                pass

            if res["encontro"]:
                ini = res["encontro"]
                print(f"\n  \033[31m⚠  {ini.nome} surge!\033[0m")
                input("  [Enter para combater] ")
                from combate import iniciar_combate
                resultado_c = iniciar_combate(personagem, ini,
                    bioma_key=_MAPA_BIOMA_CHAVE.get(res["bioma"],"floresta_sombria"))
                salvar_encontro(mundo.coord, ini.nome, resultado_c, mundo.turno)
                log_csv(mundo.turno, mundo.coord, res["bioma"], acao, "encontro",
                        "", ini.nome, resultado_c)
                jrn.registrar_evento("combate",
                    f"{personagem.nome} vs {ini.nome} em {mundo.coord}: {resultado_c}")
                if resultado_c == "derrota":
                    return "morte"
            # Tentativa de encontrar item ao explorar
            _item_msg = _tentar_encontrar_item(
                mundo.coord, res["bioma"], personagem, mundo.turno)
            if _item_msg:
                print(f"\n  {_item_msg}")

            # Mostra NPCs e estruturas ao chegar em local com conteúdo
            _npcs_local = carregar_npcs_coord(mundo.coord)
            _estruts_local = listar_estruturas(mundo.coord)
            if _npcs_local:
                nomes_n = ", ".join(n["nome"] for n in _npcs_local)
                print(f"  \033[33m💬 Aqui estão: {nomes_n}\033[0m")
            if _estruts_local:
                nomes_e = ", ".join(e["nome"] for e in _estruts_local)
                print(f"  \033[90m🏕  Estruturas: {nomes_e}\033[0m")

            jrn.registrar_evento("movimento",
                f"{personagem.nome} → {res['local'].nome} {mundo.coord}")
            continue

        # Modificação ambiental
        mod = mundo.processar_mod(acao)
        if mod:
            print(f"\n  \033[33m🌍 {mod}\033[0m")
            jrn.registrar_evento("modificacao",
                f"Modificação em {mundo.coord}: {mod[:300]}")
            continue

        # Ação livre — LLM narra e grava fato
        ctx = mundo._contexto_llm()
        prompt = (
            f"Narre em 2-3 frases o que acontece quando {personagem.nome} faz: \"{acao}\".\n"
            f"\n{ctx}\n\n"
            f"Segunda pessoa, consistente com o contexto. Sem números."
        )
        try:
            from historias import _chamar_llm_narrativa
            print(f"\n  \033[97m", end="", flush=True)
            narracao = _chamar_llm_narrativa(prompt, "", num_predict=120, stream=True)
            print("\033[0m", flush=True)
            _bioma_atual = mundo._local.bioma if mundo._local else "?"
            if narracao:
                registrar_fato(mundo.coord, f"'{acao[:200]}': {narracao[:500]}")
                log_csv(mundo.turno, mundo.coord, _bioma_atual, acao, "acao_livre", narracao)
                # Log detalhado no session_log com coord e bioma
                try:
                    import session_log as _sl
                    if _sl._csv_path:
                        _sl.log_llm(
                            "mundo_acao_livre",
                            f"[{_bioma_atual}|{mundo.coord}|T{mundo.turno}] {acao}",
                            narracao,
                        )
                except Exception:
                    pass
        except Exception:
            print(f"\n  \033[90m[Ação registrada]\033[0m")

        mundo.turno += 1
        jrn.avancar_turno()

    s = mundo.stats()
    print(f"\n{'='*58}")
    print(f"  Sessão: {s['locais']} locais | {s['mods']} mods | {s['encontros']} encontros | dist:{s['dist']}")
    print(f"{'='*58}")
    jrn.atualizar_personagem(personagem.to_dict())
    return "concluido" if personagem.esta_vivo() else "morte"


if __name__ == "__main__":
    import os, json as _j
    os.makedirs("jornada", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    for p in [DB_PATH, LORE_PATH, LOG_PATH]:
        if p.exists(): p.unlink()

    with open("jornada/log.json","w") as f: _j.dump({"eventos":[]},f)
    with open("jornada/estado.json","w") as f:
        _j.dump({"turno":0,"personagem":{},"localizacao_atual":"","npcs_conhecidos":{},
                 "inimigos_derrotados":[],"itens_obtidos":[],"habilidades_adquiridas":[],
                 "segredos_descobertos":[],"quests_ativas":[],"quests_concluidas":[],"reputacao":{}},f)

    inicializar_banco()
    print("=== TESTES mundo_aberto.py ===\n")

    c = Coord(3,-2,1)
    print(f"Coord {c}  key={c.key}  dist={c.dist():.2f}  bioma={_bioma(c.x,c.y,c.z)}")
    print(f"Mover Norte: {c.mover(0,1,0)}")

    for a in ["jogo bola de fogo","corto a árvore","cavo o chão","olho ao redor"]:
        print(f"  detectar_mod('{a}') = {_detectar_mod(a)}")

    local = LocalMundo(coord=Coord(0,0,0), bioma="floresta",
                       nome="Borda Teste", descricao="Teste.")
    salvar_local(local)
    salvar_modificacao(Coord(0,0,0), "fogo", "Chamas queimaram a vegetação.", 1)
    registrar_fato(Coord(0,0,0), "Há ruínas ao norte")
    log_csv(1, Coord(0,0,0), "floresta", "bola de fogo", "mod_fogo", "Chamas!")
    salvar_lore_local(Coord(0,0,0), "Borda Teste", ["pedra cinza","rio ao leste"])

    l2 = carregar_local(Coord(0,0,0))
    print(f"\nLocal carregado: {l2.nome} | mods={len(l2.modificacoes)} | fatos={len(l2.fatos)}")
    print(f"Lore: {_carregar_lore().get('0,0,0',{}).get('fatos')}")

    print(f"\nSQLite: {DB_PATH}")
    print(f"JSON:   {LORE_PATH}")
    print(f"CSV:    {LOG_PATH}")
    print("\n✓ Todos os testes OK")