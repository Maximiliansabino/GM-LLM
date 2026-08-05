"""
personagens.py
─────────────────────────────────────────────────────────────
Personagens jogáveis com Psiquê funcionando como mana.

Psiquê máxima = psique_base + (Conhecimento + Corpo Físico)/4
Psiquê atual  = começa cheia; usada para ativar habilidades
Recuperação:
  - Após batalha: +10% do máximo (+ bônus de passivas/extras)
  - Dormir: 100% do máximo

Inventário:
  - 3 slots base
  - +1 por "Mochila Extra" (extra)
  - +1 por "Cinto de Utilidades" (extra)
  - máximo 5 slots
─────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass, field
from typing import List, Optional
from i18n import t, name as iname
from config import (
    SLOTS_INVENTARIO_BASE, SLOTS_INVENTARIO_MAX,
    PSIQUE_REGEN_POR_BATALHA, PSIQUE_REGEN_DORMIR,
    MAX_HABILIDADES_ATIVAR, MAX_HABILIDADES_PASSIVAS,
)


@dataclass
class Personagem:
    nome: str
    caminho: str
    descricao: str

    forca: float = 0.0
    vigor: float = 0.0
    conhecimento_tacito: float = 0.0
    conhecimento_explicito: float = 0.0
    psique_base: float = 0.0

    inventario: List = field(default_factory=list)
    bolsa: List = field(default_factory=list)  # consumable bag — 4 slots
    item_equipado: Optional[object] = None
    BOLSA_MAX: int = field(default=4, init=False, repr=False)

    habilidades_ativar: List = field(default_factory=list)
    habilidades_passivas: List = field(default_factory=list)
    habilidades_extras: List = field(default_factory=list)

    pv_atual: float = field(init=False, default=0.0)
    psique_atual: float = field(init=False, default=0.0)
    defesa_bonus_turno: float = field(init=False, default=0.0)  # barreira arcana etc.

    # ── Status effects ativos ─────────────────────────────────
    # dict: {nome_efeito: {duracao: int, intensidade: float, ...}}
    status_effects: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        self.pv_atual = self.pv_max
        self.psique_atual = self.psique_max
        self.status_effects = {}

    # ── Atributos derivados ───────────────────────────────────

    @property
    def corpo_fisico(self) -> float:
        base = self.forca + self.vigor
        for h in self.habilidades_extras:
            base += h.bonus_atributo.get("forca", 0)
            base += h.bonus_atributo.get("vigor", 0)
        for h in self.habilidades_passivas:
            base += h.bonus_atributo.get("vigor", 0)
            base += h.bonus_atributo.get("forca", 0)
        return base

    @property
    def conhecimento(self) -> float:
        base = (self.conhecimento_tacito / 2) + (self.conhecimento_explicito / 3)
        for h in self.habilidades_extras:
            base += h.bonus_atributo.get("conhecimento_tacito", 0) / 2
            base += h.bonus_atributo.get("conhecimento_explicito", 0) / 3
        for h in self.habilidades_passivas:
            base += h.bonus_atributo.get("conhecimento_explicito", 0) / 3
        # Habilidade passiva dobrar_conhecimento
        for h in self.habilidades_passivas:
            if "dobrar_conhecimento" in h.nome.lower() and h.ativa:
                base *= 2
                break
        return base

    @property
    def psique_max(self) -> float:
        base = self.psique_base + (self.conhecimento + self.corpo_fisico) / 4
        # Foco Mental: +20%
        for h in self.habilidades_passivas:
            pct = h.bonus_atributo.get("psique_bonus_pct", 0)
            if pct:
                base *= (1 + pct)
        return base

    @property
    def pv_max(self) -> float:
        """
        PV depende exclusivamente do Vigor — sobrevivência vs dano são atributos distintos.
        Vigor × 10  (Kael: 12×10=120  Lyra: 5×10=50)
        Habilidades passivas com bonus "vigor" também contribuem.
        """
        base = self.vigor
        for h in self.habilidades_passivas + self.habilidades_extras:
            base += h.bonus_atributo.get("vigor", 0)
        return base * 10

    @property
    def dano_arma(self) -> float:
        """Legacy — retorna o maior entre dano físico e mágico da arma."""
        return self.item_equipado.dano_arma if self.item_equipado else 5.0

    @property
    def dano_fisico_arma(self) -> float:
        """Dano físico base da arma equipada (0 se cajado ou sem arma)."""
        if self.item_equipado and self.item_equipado.tipo_dano in ("fisico", "misto"):
            return self.item_equipado.dano_fisico
        return 0.0

    @property
    def dano_magico_arma(self) -> float:
        """Dano mágico base da arma equipada (0 se espada ou sem arma)."""
        if self.item_equipado and self.item_equipado.tipo_dano in ("magico", "misto"):
            return self.item_equipado.dano_magico
        return 0.0

    @property
    def semantica_arma(self) -> dict:
        """Multiplicadores semânticos da arma equipada."""
        if self.item_equipado:
            return self.item_equipado.semantica or {}
        return {}

    @property
    def restricoes_arma(self) -> list:
        """Restrições de uso da arma equipada."""
        if self.item_equipado:
            return self.item_equipado.restricoes or []
        return []

    @property
    def defesa_base(self) -> float:
        base = 0.0
        if self.item_equipado:
            base += self.item_equipado.defesa
        for h in self.habilidades_passivas:
            base += h.bonus_atributo.get("defesa", 0)
        return base

    @property
    def slots_disponiveis(self) -> int:
        bonus = sum(h.slots_inventario for h in self.habilidades_extras)
        return min(SLOTS_INVENTARIO_BASE + bonus, SLOTS_INVENTARIO_MAX)

    def _itens_que_ocupam_slot(self) -> list:
        """Consumíveis não ocupam slot de inventário."""
        return [i for i in self.inventario if i.tipo != "consumivel"]

    @property
    def regen_psique_pct(self) -> float:
        """
        Regeneração de Psiquê por batalha:
          base 5% + Vigor/200 + Conhecimento/300 + bônus de habilidades
          Kael: 5% + 12/200 + 5.5/300 ≈ 11.8%
          Lyra: 5% + 5/200  + 8.7/300 ≈ 8.4%  (recupera mais via Foco Mental)
        """
        base = 0.05
        base += self.vigor / 200
        base += self.conhecimento / 300
        for h in self.habilidades_passivas + self.habilidades_extras:
            base += h.bonus_atributo.get("regen_psique_bonus", 0)
        return base

    # ── Combate ───────────────────────────────────────────────

    def dano_personagem(self) -> float:
        """Legacy — retorna a soma de físico+mágico para compatibilidade."""
        return self.dano_fisico_base() + self.dano_magico_base()

    def dano_fisico_base(self) -> float:
        """
        Dano físico = (dano_fisico_arma/10) × Força² × 0.15 / ESCALA
        Escala quadraticamente com Força pura — Vigor não amplifica dano.
        Isso cria uma escolha real: Vigor = sobreviver, Força = bater mais forte.
        """
        from config import ESCALA_DANO
        forca_efetiva = self.forca + sum(
            h.bonus_atributo.get("forca", 0)
            for h in self.habilidades_passivas + self.habilidades_extras
        )
        return (self.dano_fisico_arma / 10) * (forca_efetiva ** 2) * 0.15 / ESCALA_DANO

    def dano_magico_base(self) -> float:
        """
        Dano mágico base depende da ARMA equipada:
          Arma mágica (cajado, varinha...): escala com conhecimento_tacito^2.5
          Arma física (espada, faca...):    escala com conhecimento_tacito^1.2 × 0.3
            → guerreiro pode usar magia mas ineficientemente
          Sem arma: usa conhecimento_tacito^1.5 × 0.5
        Isso garante que Kael (espada, tacito=8) não vira mago acidental.
        """
        from config import ESCALA_DANO
        item = self.item_equipado
        tipo_arma = getattr(item, "tipo_dano", None) if item else None

        if tipo_arma == "magico":
            # Mago com arma mágica — escala forte
            base = (self.conhecimento_tacito ** 2.5) * 1.2 / ESCALA_DANO
            base += (self.dano_magico_arma / 10) * (self.conhecimento_tacito ** 2) * 0.15 / ESCALA_DANO
        elif tipo_arma == "fisico":
            # Guerreiro com arma física — magia fraca (instintiva, não treinada)
            base = (self.conhecimento_tacito ** 1.2) * 0.3 / ESCALA_DANO
        else:
            # Sem arma / arma neutra
            base = (self.conhecimento_tacito ** 1.5) * 0.5 / ESCALA_DANO
        return base

    def pode_usar_habilidade(self, habilidade) -> bool:
        return self.psique_atual >= habilidade.custo_psique

    def usar_habilidade(self, habilidade) -> bool:
        if not self.pode_usar_habilidade(habilidade):
            print(f"  [Ψ insuficiente] {habilidade.nome} custa {habilidade.custo_psique:.1f} Ψ "
                  f"(você tem {self.psique_atual:.1f})")
            return False
        self.psique_atual -= habilidade.custo_psique
        return True

    def receber_dano(self, dano: float):
        dano_efetivo = dano - self.defesa_bonus_turno
        self.defesa_bonus_turno = 0.0  # consume a barreira
        # Redução flat por Vigor (resiliência): Vigor × 0.15
        # Kael(12) → -1.8/hit  Lyra(5) → -0.75/hit
        reducao_vigor = self.vigor * 0.15
        dano_efetivo = max(0, dano_efetivo - reducao_vigor)
        # Redução percentual por habilidades passivas (esquiva instintiva)
        for h in self.habilidades_passivas:
            reducao = h.bonus_atributo.get("reducao_dano_pct", 0)
            if reducao:
                dano_efetivo *= (1 - reducao)
        self.pv_atual = max(0, self.pv_atual - max(0, dano_efetivo))

    def esta_vivo(self) -> bool:
        return self.pv_atual > 0

    def regenerar_pos_batalha(self):
        """
        Regeneração automática pós-batalha:
          PV:     Vigor × 0.5  (Kael +6/batalha, Lyra +2.5)
          Psiquê: psique_max × regen_psique_pct  (10% base)
        """
        # PV regen por Vigor
        regen_pv = self.vigor * 0.5
        pv_antes = self.pv_atual
        self.pv_atual = min(self.pv_max, self.pv_atual + regen_pv)
        pv_ganho = self.pv_atual - pv_antes
        if pv_ganho > 0:
            pv_bar = int((self.pv_atual / self.pv_max) * 16)
            print(f"  [32m❤  +{pv_ganho:.0f} PV  "
                  f"[{'█'*pv_bar}{'░'*(16-pv_bar)}] "
                  f"{self.pv_atual:.0f}/{self.pv_max:.0f}[0m")

        # Psiquê regen
        regen_psi = self.psique_max * self.regen_psique_pct
        self.psique_atual = min(self.psique_max, self.psique_atual + regen_psi)
        print(f"  [35mΨ  +{regen_psi:.1f}  "
              f"{self.psique_atual:.1f}/{self.psique_max:.1f}[0m")

    def regenerar_psique_pos_batalha(self):
        """Legacy — chama regenerar_pos_batalha para compatibilidade."""
        self.regenerar_pos_batalha()

    def dormir(self):
        self.pv_atual = self.pv_max
        self.psique_atual = self.psique_max
        print(f"  [Descanso] PV e Psiquê totalmente restaurados.")

    # ── Inventário ────────────────────────────────────────────

    def inventario_cheio(self) -> bool:
        """Retorna True se os slots de inventário estão todos ocupados."""
        from config import SLOTS_INVENTARIO_BASE, SLOTS_INVENTARIO_MAX
        # Contar apenas itens que ocupam slot (armas/armaduras/acessórios)
        ocupados = len([i for i in self.inventario if i.tipo != "consumivel"])
        extras = sum(
            1 for h in self.habilidades_extras
            if h.nome in ("Mochila Extra", "Cinto de Utilidades")
        )
        slots = min(SLOTS_INVENTARIO_MAX, SLOTS_INVENTARIO_BASE + extras)
        return ocupados >= slots

    @property
    def slots_disponiveis(self) -> int:
        from config import SLOTS_INVENTARIO_BASE, SLOTS_INVENTARIO_MAX
        extras = sum(
            1 for h in self.habilidades_extras
            if h.nome in ("Mochila Extra", "Cinto de Utilidades")
        )
        return min(SLOTS_INVENTARIO_MAX, SLOTS_INVENTARIO_BASE + extras)

    def adicionar_item(self, item) -> bool:
        """
        Consumíveis vão para a bolsa (4 slots).
        Outros itens verificam slots do inventário principal.
        Returns False if no space in the appropriate container.
        """
        if item.tipo == "consumivel":
            if self.bolsa_cheia():
                return False   # caller handles full bolsa
            self.bolsa.append(item)
            return True
        if self.inventario_cheio():
            return False
        self.inventario.append(item)
        return True

    def remover_item(self, nome_item: str) -> Optional[object]:
        for i, it in enumerate(self.inventario):
            if it.nome.lower() == nome_item.lower():
                return self.inventario.pop(i)
        return None

    def bolsa_cheia(self) -> bool:
        """Retorna True se os slots da bolsa estão todos ocupados."""
        return len(self.bolsa) >= self.BOLSA_MAX

    def adicionar_bolsa(self, item) -> bool:
        """Add consumable to bolsa. Returns False if full."""
        if self.bolsa_cheia():
            return False
        self.bolsa.append(item)
        return True

    def remover_bolsa(self, idx: int):
        if 0 <= idx < len(self.bolsa):
            return self.bolsa.pop(idx)
        return None

    def verificar_requisito(self, item) -> tuple[bool, str]:
        """
        Verifica se o personagem atende ao requisito do item.
        Retorna (ok, mensagem_falha).

        Regras:
          arma física   → forca >= requisito["forca"]
          arma mágica   → conhecimento_tacito >= requisito["conhecimento_tacito"]
          armadura      → vigor >= requisito["vigor"]
          acessório     → conhecimento_explicito >= requisito["conhecimento_explicito"]
        """
        req = item.requisito if item.requisito else {}
        if not req:
            return True, ""

        attr_map = {
            "forca"                : self.forca,
            "vigor"                : self.vigor,
            "conhecimento_tacito"  : self.conhecimento_tacito,
            "conhecimento_explicito": self.conhecimento_explicito,
        }
        attr_labels = {
            "forca"                : "Força",
            "vigor"                : "Vigor",
            "conhecimento_tacito"  : "Conhecimento Tácito",
            "conhecimento_explicito": "Conhecimento Explícito",
        }
        for attr, minimo in req.items():
            valor_atual = attr_map.get(attr, 0)
            if valor_atual < minimo:
                label = attr_labels.get(attr, attr)
                return False, (
                    f"{label} insuficiente: você tem {valor_atual:.0f}, "
                    f"requerido {minimo:.0f} para usar {item.nome}."
                )
        return True, ""

    def equipar(self, item, silent: bool = False) -> bool:
        """
        Equipa o item se o requisito for atendido.
        Retorna True se equipou, False se requisito não atendido.
        """
        ok, msg = self.verificar_requisito(item)
        if not ok:
            if not silent:
                print(f"  [33m⚠  {msg}[0m")
            return False
        self.item_equipado = item
        if not silent:
            print(f"  [{self.nome} equipou: {iname(item)}]")
        return True

    # ── Consumíveis ──────────────────────────────────────────

    def usar_consumivel(self, idx: int) -> tuple[bool, str]:
        """
        Usa o consumível no índice idx da bolsa.
        Retorna (sucesso, mensagem).
        Aplica todos os efeitos: cura PV, cura Psiquê, remove status.
        """
        if not (0 <= idx < len(self.bolsa)):
            return False, "Índice inválido."
        item = self.bolsa.pop(idx)
        msgs = []

        # ── Cura de PV ───────────────────────────────────────
        cura_pv = item.bonus.get("cura", 0)
        if cura_pv:
            antes = self.pv_atual
            self.pv_atual = min(self.pv_max, self.pv_atual + cura_pv)
            ganho = self.pv_atual - antes
            msgs.append(f"+{ganho:.0f} PV ({self.pv_atual:.0f}/{self.pv_max:.0f})")

        # ── Cura de Psiquê ───────────────────────────────────
        cura_psi = item.bonus.get("cura_psique", 0)
        if cura_psi:
            antes = self.psique_atual
            self.psique_atual = min(self.psique_max, self.psique_atual + cura_psi)
            ganho = self.psique_atual - antes
            msgs.append(f"+{ganho:.1f} Ψ ({self.psique_atual:.1f}/{self.psique_max:.1f})")

        # ── Remove status effects ─────────────────────────────
        remove_status = item.bonus.get("remove_status", [])
        if remove_status == "todos":
            removidos = list(self.status_effects.keys())
            self.status_effects.clear()
            if removidos:
                msgs.append(f"Remove: {', '.join(removidos)}")
        elif isinstance(remove_status, list):
            for ef in remove_status:
                if ef in self.status_effects:
                    del self.status_effects[ef]
                    msgs.append(f"Remove {ef}")

        # ── Cura veneno (legado) ──────────────────────────────
        if item.bonus.get("cura_veneno") and "envenenar" in self.status_effects:
            del self.status_effects["envenenar"]
            msgs.append("Veneno curado")

        # ── Buff temporário ───────────────────────────────────
        buff_forca = item.bonus.get("buff_forca", 0)
        if buff_forca:
            self.forca = round(self.forca + buff_forca, 1)
            msgs.append(f"+{buff_forca:.0f} Força (temporário)")

        msg = item.nome + ": " + " | ".join(msgs) if msgs else item.nome + " usado."
        return True, msg

    # ── Progressão ───────────────────────────────────────────

    def ganhar_conhecimento_tacito(self, qtd: float, motivo: str = ""):
        self.conhecimento_tacito += qtd
        if motivo:
            print(f"  [+{qtd:.2f} Conh. Tácito] {motivo}")

    def ganhar_conhecimento_explicito(self, qtd: float, motivo: str = ""):
        self.conhecimento_explicito += qtd
        if motivo:
            print(f"  [+{qtd:.2f} Conh. Explícito] {motivo}")

    def treinar(self, forca: float = 0, vigor: float = 0):
        self.forca += forca
        self.vigor += vigor
        if forca: print(f"  [+{forca:.1f} Força]")
        if vigor: print(f"  [+{vigor:.1f} Vigor]")
        # Atualiza PV e Psiquê máximos após treino
        if self.pv_atual > self.pv_max:
            self.pv_atual = self.pv_max

    def adicionar_habilidade(self, habilidade, silent: bool = False) -> bool:
        if habilidade.tipo == "ativar":
            if len(self.habilidades_ativar) >= MAX_HABILIDADES_ATIVAR:
                print(f"  [LIMITE] Habilidades de ativar cheias ({MAX_HABILIDADES_ATIVAR}).")
                return False
            self.habilidades_ativar.append(habilidade)
        elif habilidade.tipo == "passiva":
            if len(self.habilidades_passivas) >= MAX_HABILIDADES_PASSIVAS:
                print(f"  [LIMITE] Habilidades passivas cheias ({MAX_HABILIDADES_PASSIVAS}).")
                return False
            self.habilidades_passivas.append(habilidade)
        else:
            self.habilidades_extras.append(habilidade)
        if not silent:
            print(f"  [Nova habilidade] {iname(habilidade)} ({habilidade.tipo})")
        return True

    # ── Serialização ─────────────────────────────────────────

    def ficha(self) -> str:
        W = 54
        pv_bar  = int((self.pv_atual     / max(self.pv_max,    1)) * 20)
        psi_bar = int((self.psique_atual / max(self.psique_max, 1)) * 20)
        n_itens   = len(self._itens_que_ocupam_slot())
        inv_info  = f"{n_itens}/{self.slots_disponiveis} {t('attr.slots')}"
        bolsa_info = f"{len(self.bolsa)}/{{self.BOLSA_MAX}}"

        def row(txt):
            return f"  {txt}"

        def bar(label, filled, empty, cur, mx, unit=""):
            b = "█" * filled + "░" * empty
            return f"  {label:<7} {b}  {cur:>5}{unit}/{mx}{unit}"

        lines = [
            f"  ╔{'═'*W}╗",
            f"  ║  {self.nome.upper() + ' — ' + t('attr.path') + ': ' + self.caminho.upper():<{W-2}}║",
            f"  ║  {self.descricao[:W-2]:<{W-2}}║",
            f"  ╠{'═'*W}╣",
            f"  ║  {t('attr.hp'):<7} {'█'*pv_bar}{'░'*(20-pv_bar)}  {self.pv_atual:>5.0f}/{self.pv_max:.0f}{'':<{W-37}}║",
            f"  ║  {t('attr.psique'):<7} {'█'*psi_bar}{'░'*(20-psi_bar)}  {self.psique_atual:>5.1f}/{self.psique_max:.1f}{'':<{W-39}}║",
            f"  ╠{'═'*W}╣",
            f"  ║  {t('attr.strength')} {self.forca:>4.1f}  {t('attr.vigor')} {self.vigor:>4.1f}  {t('attr.body')} {self.corpo_fisico:>5.1f}{'':<{W-41}}║",
            f"  ║  {t('attr.tac_know')} {self.conhecimento_tacito:>5.1f}   {t('attr.exp_know')} {self.conhecimento_explicito:>5.1f}{'':<{W-45}}║",
            f"  ║  {t('attr.knowledge')} {self.conhecimento:>5.2f}   {t('attr.psique_total')} {self.psique_max:>7.1f}{'':<{W-44}}║",
            f"  ║  {t('attr.damage')} {self.dano_personagem():>5.2f}   {t('attr.defense')}  {self.defesa_base:>7.1f}{'':<{W-44}}║",
            f"  ╠{'═'*W}╣",
            f"  ║  {t('attr.equipped')}: {(iname(self.item_equipado) if self.item_equipado else t('attr.none')):<{W-8}}║",
            f"  ║  Inv ({inv_info}): {str([i.nome for i in self.inventario])[:W-14]:<{W-14}}║",
            f"  ╠{'═'*W}╣",
            f"  ║  {t('attr.activate')}:  {str([(iname(h), f'P{h.custo_psique}') for h in self.habilidades_ativar])[:W-12]:<{W-12}}║",
            f"  ║  {t('attr.passive')}: {str([iname(h) for h in self.habilidades_passivas])[:W-12]:<{W-12}}║",
            f"  ║  {t('attr.extras')}:  {str([iname(h) for h in self.habilidades_extras])[:W-12]:<{W-12}}║",
            f"  ╚{'═'*W}╝",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "nome": self.nome, "caminho": self.caminho,
            "forca": self.forca, "vigor": self.vigor,
            "conhecimento_tacito": self.conhecimento_tacito,
            "conhecimento_explicito": self.conhecimento_explicito,
            "psique_base": self.psique_base,
            "pv_atual": self.pv_atual, "pv_max": self.pv_max,
            "psique_atual": self.psique_atual, "psique_max": self.psique_max,
            "corpo_fisico": self.corpo_fisico, "conhecimento": self.conhecimento,
            "item_equipado": self.item_equipado.nome if self.item_equipado else None,
            "inventario": [i.nome for i in self.inventario],
            "bolsa": [i.nome for i in self.bolsa],
            "slots_inventario": f"{len(self.inventario)}/{self.slots_disponiveis}",
            "habilidades_ativar": [(h.nome, h.custo_psique) for h in self.habilidades_ativar],
            "habilidades_passivas": [h.nome for h in self.habilidades_passivas],
            "habilidades_extras": [h.nome for h in self.habilidades_extras],
        }


# ══════════════════════════════════════════════════════════════
#  FÁBRICA DE PERSONAGENS
# ══════════════════════════════════════════════════════════════

def criar_kael(nome_jogador: str = 'Kael') -> Personagem:
    from itens import ESPADA_LONGA, ARMADURA_COURO
    from habilidades import HABILIDADE_RESISTENCIA, HABILIDADE_ACAMPAR

    kael = Personagem(
        nome=nome_jogador, caminho="luta",
        descricao="Guerreiro endurecido por anos de conflito.",
        forca=14.0, vigor=12.0,
        conhecimento_tacito=8.0, conhecimento_explicito=3.0,
        psique_base=6.0,
    )
    from habilidades import HABILIDADE_BLOQUEIO, HABILIDADE_ESQUIVA_INSTINTIVA
    kael.adicionar_habilidade(HABILIDADE_RESISTENCIA,        silent=True)
    kael.adicionar_habilidade(HABILIDADE_BLOQUEIO,           silent=True)
    kael.adicionar_habilidade(HABILIDADE_ESQUIVA_INSTINTIVA, silent=True)
    kael.adicionar_habilidade(HABILIDADE_ACAMPAR,            silent=True)
    kael.equipar(ESPADA_LONGA, silent=True)
    kael.inventario.append(ARMADURA_COURO)
    # Sync vitals to real max (skills may have changed psique_max/pv_max)
    kael.pv_atual     = kael.pv_max
    kael.psique_atual = kael.psique_max
    return kael


def criar_lyra(nome_jogador: str = 'Lyra') -> Personagem:
    from itens import CAJADO_ARCANO, CHAPEU_DO_MAGO
    from habilidades import (HABILIDADE_LEITURA_DINAMICA,
                              HABILIDADE_ANALISE_FRAQUEZA, HABILIDADE_CULINARIA)

    lyra = Personagem(
        nome=nome_jogador, caminho="sabedoria",
        descricao="Estudiosa de antigas tradições.",
        forca=4.0, vigor=5.0,
        conhecimento_tacito=4.0, conhecimento_explicito=18.0,
        psique_base=9.0,
    )
    from habilidades import HABILIDADE_CANAL_PSIQUICO, HABILIDADE_FOCO_MENTAL, HABILIDADE_MEMORIZAR_LECOES
    lyra.adicionar_habilidade(HABILIDADE_MEMORIZAR_LECOES,   silent=True)
    lyra.adicionar_habilidade(HABILIDADE_CANAL_PSIQUICO,     silent=True)
    lyra.adicionar_habilidade(HABILIDADE_FOCO_MENTAL,        silent=True)
    lyra.adicionar_habilidade(HABILIDADE_LEITURA_DINAMICA,   silent=True)
    lyra.adicionar_habilidade(HABILIDADE_ANALISE_FRAQUEZA,   silent=True)
    lyra.adicionar_habilidade(HABILIDADE_CULINARIA,          silent=True)
    lyra.equipar(CAJADO_ARCANO, silent=True)
    lyra.inventario.append(CHAPEU_DO_MAGO)
    # Sync vitals to real max (Foco Mental adds 20% to psique_max)
    lyra.pv_atual     = lyra.pv_max
    lyra.psique_atual = lyra.psique_max
    return lyra


if __name__ == "__main__":
    kael = criar_kael()
    lyra = criar_lyra()
    print(kael.ficha())
    print()
    print(lyra.ficha())
