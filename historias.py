"""
historias.py
─────────────────────────────────────────────────────────────
Motor narrativo e catálogo de NPCs.

Responsabilidades:
  - Gerar narração via LLM usando o contexto da jornada
  - Gerenciar diálogos com NPCs
  - Fornecer três cenários/histórias pré-definidos para os
    estudos de caso (Combate, Investigação, Mundo Aberto)
  - Registrar todos os eventos na jornada (anti-alucinação)
─────────────────────────────────────────────────────────────
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from config import (
    OLLAMA_API_URL, LLM_MODEL, LLM_TEMPERATURE,
    LLM_TOKENS_NARRATIVA, LLM_TOKENS_NPC, SYSTEM_PROMPT,
)
from loading import spinner
import jornada as jrn
try:
    import memoria_rag as _rag
    _RAG_DISPONIVEL = True
except ImportError:
    _RAG_DISPONIVEL = False


# ══════════════════════════════════════════════════════════════
#  CHAMADA À LLM (narrativa)
# ══════════════════════════════════════════════════════════════

def _chamar_llm_narrativa(prompt: str, contexto_jornada: str = "",
                          num_predict: int = None, stream: bool = True) -> str:
    import llm_backend as lb
    """
    Calls the LLM for narrative content.
    stream=True: tokens printed as they arrive (no loading bar needed).
    stream=False: wait + loading bar.
    """
    from config import get_estilo_narrativa, get_lingua_narrativa
    if num_predict is None:
        num_predict = LLM_TOKENS_NARRATIVA

    try:
        from config import SYSTEM_PROMPT_NARRACAO
        _sys_base = SYSTEM_PROMPT_NARRACAO
    except ImportError:
        _sys_base = "Você é um Mestre de RPG narrando em português. Narre de forma vívida e direta."

    system = (
        f"{_sys_base}\n"
        f"Estilo: {get_estilo_narrativa()}. Idioma: {get_lingua_narrativa()}."
        f"{(' ' + contexto_jornada) if contexto_jornada else ''}"
    )
    payload = {
        "model"   : LLM_MODEL,
        "stream"  : stream,
        "options" : {"temperature": LLM_TEMPERATURE, "num_predict": num_predict},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
    }
    try:
        if stream:
            return lb.chamar_stream(prompt, system,
                                    num_predict=num_predict)
        else:
            result = [None]
            def _call():
                result[0] = lb.chamar(prompt, system,
                                      num_predict=num_predict)
            with spinner("Narrando..."):
                _call()
            return result[0] or "[sem resposta]"
    except OSError:
        return "\033[33m[Ollama indisponível — execute: ollama serve]\033[0m"
    except Exception as e:
        return f"\033[31m[ERRO NARRATIVO: {type(e).__name__}]\033[0m"


# ══════════════════════════════════════════════════════════════
#  NPC
# ══════════════════════════════════════════════════════════════

@dataclass
class NPC:
    nome: str
    ocupacao: str
    atitude: str          # "amigavel" | "neutro" | "hostil" | "aliado"
    descricao_fisica: str
    personalidade: str
    conhecimentos: List[str] = field(default_factory=list)   # tópicos que sabe
    segredos: List[str] = field(default_factory=list)         # revela sob condições
    historico_dialogos: List[Dict] = field(default_factory=list)

    # ── Amizade (0–100) ───────────────────────────────────────
    # Persiste entre biomas via jornada.py
    # 0-29  → desconhecido   30-59 → conhecido   60-89 → amigo   90+ → aliado
    # Conversar +5/turno | Trocar item +20 | Ajudar (vitória) +35 | Ajudar (fuga) −10
    amizade: float = field(default=0.0, init=False)

    # ── Controle de ajuda por bioma ───────────────────────────
    ajuda_disponivel: bool = field(default=True, init=False)   # False após ajuda/fuga
    ajuda_resultado: str = field(default="", init=False)        # "vitoria"|"fuga"|""

    def amizade_label(self) -> str:
        if self.amizade >= 90: return "Aliado"
        if self.amizade >= 60: return "Amigo"
        if self.amizade >= 30: return "Conhecido"
        return "Desconhecido"

    def amizade_cor(self) -> str:
        if self.amizade >= 90: return "[92m"
        if self.amizade >= 60: return "[32m"
        if self.amizade >= 30: return "[33m"
        return "[90m"

    def ganhar_amizade(self, delta: float, motivo: str = "") -> None:
        antes = self.amizade
        self.amizade = max(0, min(100, self.amizade + delta))
        ganho = self.amizade - antes
        if ganho != 0:
            sinal = "+" if ganho > 0 else ""
            col = "[32m" if ganho > 0 else "[31m"
            print(f"  {col}♥ {sinal}{ganho:.0f} Amizade → {self.amizade:.0f}/100  [{self.amizade_label()}][0m")
        # Persiste na jornada
        import jornada as jrn
        jrn.registrar_evento("amizade", f"{self.nome}: {motivo}", {"delta": ganho, "total": self.amizade})

    def resetar_para_bioma(self) -> None:
        """Chamado ao entrar em novo bioma — libera ajuda novamente."""
        self.ajuda_disponivel = True
        self.ajuda_resultado = ""

    def falar(self, pergunta: str, personagem_nome: str) -> str:
        """
        Gera uma resposta do NPC via LLM, mantendo consistência
        com o histórico de diálogos anteriores.
        """
        if _RAG_DISPONIVEL:
            contexto_jornada = _rag.obter_contexto_rag(query=pergunta, max_tokens=600)
        else:
            contexto_jornada = jrn.obter_contexto_compacto()

        historico_fmt = ""
        if self.historico_dialogos:
            historico_fmt = "\n".join(
                f"  {d['de']}: {d['texto']}" for d in self.historico_dialogos[-6:]
            )
            historico_fmt = f"\nHistórico desta conversa:\n{historico_fmt}\n"

        prompt = (
            f"Você é {self.nome}, {self.ocupacao}.\n"
            f"Aparência: {self.descricao_fisica}\n"
            f"Personalidade: {self.personalidade}\n"
            f"Atitude em relação ao(à) aventureiro(a): {self.atitude}\n"
            f"Você sabe sobre: {', '.join(self.conhecimentos) or 'assuntos cotidianos'}.\n"
            f"{historico_fmt}\n"
            f"{personagem_nome} pergunta/diz: \"{pergunta}\"\n\n"
            f"Responda APENAS como {self.nome} falaria, em primeira pessoa, "
            f"de forma consistente com sua personalidade. Máximo 4 linhas."
        )

        from i18n import LANG
        lang_instrucao = "Respond in English." if LANG == "en" else "Responda em português."
        prompt += f"\n{lang_instrucao}"
        resposta = _chamar_llm_narrativa(
            prompt, contexto_jornada,
            num_predict=LLM_TOKENS_NPC, stream=False
        )

        # Registrar no histórico
        self.historico_dialogos.append({"de": personagem_nome, "texto": pergunta})
        self.historico_dialogos.append({"de": self.nome, "texto": resposta})

        # Gravar na jornada
        jrn.registrar_evento(
            "dialogo",
            f"{personagem_nome} conversou com {self.nome}.",
            {"pergunta": pergunta[:100], "resposta": resposta[:200]},
        )
        return resposta

    def registrar_na_jornada(self):
        jrn.registrar_npc(
            self.nome,
            f"{self.ocupacao}. {self.descricao_fisica[:80]}",
            self.atitude,
            {"personalidade": self.personalidade, "conhecimentos": self.conhecimentos},
        )


# ══════════════════════════════════════════════════════════════
#  CATÁLOGO DE NPCs
# ══════════════════════════════════════════════════════════════

BRENO_TAVERNEIRO = NPC(
    nome="Breno",
    ocupacao="Taverneiro",
    atitude="amigavel",
    descricao_fisica="Homem robusto, cabelos grisalhos, avental surrado, sorriso fácil.",
    personalidade="Conversador e otimista. Adora fofocas e repassa rumores com entusiasmo exagerado.",
    conhecimentos=["rumores da vila", "estradas perigosas", "preços de mercado", "história local"],
    segredos=["sabe onde fica a caverna oculta ao sul, mas só conta para quem confia"],
)

VELHA_MIRA = NPC(
    nome="Mira, a Anciã",
    ocupacao="Curandeira e guardiã do saber antigo",
    atitude="neutro",
    descricao_fisica="Mulher muito velha, olhos claros penetrantes, dedos nodosos, sempre carrega ervas.",
    personalidade=(
        "Lacônica e enigmática. Responde perguntas com mais perguntas. "
        "Desconfia de estranhos, mas respeita aqueles que demonstram conhecimento."
    ),
    conhecimentos=["rituais antigos", "plantas medicinais", "o Senhor das Sombras", "segredos do templo"],
    segredos=["conhece a fraqueza do Senhor das Sombras; só revela se o personagem tiver Psiquê >= 8"],
)

CAPITAO_DURAS = NPC(
    nome="Capitão Duras",
    ocupacao="Líder da guarda local",
    atitude="neutro",
    descricao_fisica="Homem alto e severo, cicatriz no queixo, armadura com insígnia da cidade.",
    personalidade="Direto e desconfiado. Valoriza fatos, não histórias. Respeita competência demonstrada.",
    conhecimentos=["atividades criminosas", "layout da cidade", "rotas de patrulha", "lei local"],
    segredos=["suspeita que um conselheiro está colaborando com bandidos"],
)

EILARA_MERCANTE = NPC(
    nome="Eilara",
    ocupacao="Mercante de itens raros",
    atitude="amigavel",
    descricao_fisica="Mulher de meia idade, roupas coloridas, olhos espertos, sempre contando moedas.",
    personalidade="Negociante habilidosa. Amigável na superfície; sempre procura vantagem.",
    conhecimentos=["valor de itens", "artefatos mágicos", "rotas comerciais", "demanda do mercado negro"],
    segredos=["tem um chapéu do mago à venda para quem pagar certo preço ou resolver um favor"],
)

FERRAN_FERREIRO = NPC(
    nome="Ferran",
    ocupacao="Ferreiro",
    atitude="amigavel",
    descricao_fisica="Homem baixo e musculoso, braços queimados por fagulhas, barba espessa.",
    personalidade="Prático e honesto. Orgulhoso do próprio trabalho. Fala pouco, faz muito.",
    conhecimentos=["aprimoramento de armas", "maestria com ferramentas", "técnicas de forja"],
    segredos=["pode aprimorar maestria_max de armas em +50 por um favor ou pagamento justo"],
)

SOMBRA_SEM_NOME = NPC(
    nome="Sombra",
    ocupacao="Informante desconhecido",
    atitude="neutro",
    descricao_fisica="Encapuzado, rosto sempre oculto, voz sussurrada.",
    personalidade="Misterioso e calculista. Só aparece quando o jogador está sozinho e em apuros.",
    conhecimentos=["localização de artefatos perdidos", "identidade do traidor", "acesso ao boss"],
    segredos=["é um antigo aventureiro que se esconde do Senhor das Sombras"],
)

CATALOGO_NPCS: dict = {
    "breno"     : BRENO_TAVERNEIRO,
    "mira"      : VELHA_MIRA,
    "duras"     : CAPITAO_DURAS,
    "eilara"    : EILARA_MERCANTE,
    "ferran"    : FERRAN_FERREIRO,
    "sombra"    : SOMBRA_SEM_NOME,
}


# ══════════════════════════════════════════════════════════════
#  CENÁRIOS / HISTÓRIAS PRÉ-DEFINIDAS
# ══════════════════════════════════════════════════════════════

CENARIOS = {
    "A": {
        "nome"      : "A Fortaleza Sitiada",
        "foco"      : "combate",
        "descricao" : (
            "Uma fortaleza fronteiriça foi tomada por criaturas do submundo. "
            "O objetivo é avançar pelos andares, derrotar os guardiões e eliminar "
            "o chefe no topo da torre. Testa geração de monstros e mecânicas de combate."
        ),
        "localizacao_inicial": "Portão da Fortaleza Caída",
        "inimigos_sequencia" : ["goblin_batedeiro", "esqueleto_guerreiro", "troll_das_pedras"],
        "npcs_presentes"     : ["duras", "ferran"],
        "objetivo"           : "Derrotar todos os guardas e o chefe da torre.",
    },
    "B": {
        "nome"      : "O Mistério da Biblioteca",
        "foco"      : "investigacao",
        "descricao" : (
            "Um manuscrito foi roubado da biblioteca do reino. "
            "O personagem precisa interrogar NPCs, analisar pistas e descobrir "
            "o culpado antes que o conhecimento seja destruído. "
            "Testa memória de longo prazo e qualidade narrativa."
        ),
        "localizacao_inicial": "Biblioteca Real — Sala de Leitura",
        "inimigos_sequencia" : ["mago_renegado"],
        "npcs_presentes"     : ["breno", "mira", "eilara", "sombra"],
        "objetivo"           : "Identificar o ladrão e recuperar o manuscrito.",
    },
    "C": {
        "nome"      : "O Mundo Esquecido",
        "foco"      : "mundo_aberto",
        "descricao" : (
            "Uma região inexplorada além das montanhas. "
            "O jogador pode seguir qualquer caminho: explorar ruínas, negociar "
            "com tribos, desafiar criaturas ou buscar artefatos. "
            "Testa geração procedural de cenários e liberdade narrativa."
        ),
        "localizacao_inicial": "Borda das Montanhas Névoas",
        "inimigos_sequencia" : [],   # geração procedural
        "npcs_presentes"     : ["mira", "sombra"],
        "objetivo"           : "Livre — o jogador define seus próprios objetivos.",
    },
}


# ══════════════════════════════════════════════════════════════
#  MOTOR NARRATIVO
# ══════════════════════════════════════════════════════════════

def narrar_cena(descricao_acao: str, personagem_dict: dict) -> str:
    """
    Gera narração para uma ação do jogador fora de combate.
    Sempre injeta o contexto da jornada para evitar alucinações.
    """
    contexto = _rag.obter_contexto_rag(max_tokens=400) if _RAG_DISPONIVEL else jrn.obter_contexto_compacto()
    prompt = (
        f"O aventureiro {personagem_dict.get('nome', '?')} faz o seguinte:\n"
        f"\"{descricao_acao}\"\n\n"
        f"Narre o resultado desta ação em 3–5 linhas. "
        f"Seja consistente com o contexto fornecido. Não invente fatos novos."
    )
    narração = _chamar_llm_narrativa(prompt, contexto, stream=True)
    jrn.registrar_evento("narrativa", f"Ação narrada: {descricao_acao[:60]}", {"narracao": narração[:200]})
    return narração


def iniciar_cenario(letra: str, personagem) -> None:
    """
    Configura a jornada para o cenário escolhido e exibe a introdução.
    letra: "A" | "B" | "C"
    """
    if letra not in CENARIOS:
        print(f"  [ERRO] Cenário '{letra}' não existe.")
        return

    cen = CENARIOS[letra]
    print(f"\n{'═'*55}")
    print(f"  CENÁRIO {letra}: {cen['nome'].upper()}")
    print(f"  Foco: {cen['foco']}")
    print(f"{'═'*55}")
    print(f"  {cen['descricao']}")
    print(f"\n  Objetivo: {cen['objetivo']}")
    print(f"{'═'*55}\n")

    jrn.inicializar_jornada(personagem.to_dict(), cen["localizacao_inicial"])

    # Registrar NPCs do cenário
    for npc_chave in cen["npcs_presentes"]:
        if npc_chave in CATALOGO_NPCS:
            CATALOGO_NPCS[npc_chave].registrar_na_jornada()

    # Gerar introdução narrativa
    contexto = _rag.obter_contexto_rag(max_tokens=400) if _RAG_DISPONIVEL else jrn.obter_contexto_compacto()
    prompt = (
        f"Inicie a aventura do Cenário {letra} — '{cen['nome']}'. "
        f"Descreva a cena inicial em {cen['localizacao_inicial']} com 5–8 linhas. "
        f"Apresente a atmosfera, elementos visuais e o gancho inicial da história. "
        f"O personagem é {personagem.nome} ({personagem.caminho})."
    )
    introducao = _chamar_llm_narrativa(prompt, contexto, stream=True)
    print(introducao)
    jrn.registrar_evento("narrativa", f"Início do Cenário {letra}.", {"introducao": introducao[:300]})


# ══════════════════════════════════════════════════════════════
#  PONTO DE TESTE RÁPIDO (sem LLM)
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("── Cenários disponíveis ──")
    for letra, cen in CENARIOS.items():
        print(f"  [{letra}] {cen['nome']} | Foco: {cen['foco']}")
        print(f"      {cen['descricao'][:80]}...")
        print()

    print("── NPCs disponíveis ──")
    for chave, npc in CATALOGO_NPCS.items():
        print(f"  {npc.nome:20} | {npc.ocupacao:30} | {npc.atitude}")
