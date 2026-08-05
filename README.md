# RPG LLM — Mestre Autônomo com llama3.1:8b

Sistema de RPG de mesa mediado por texto com Mestre de Jogo autônomo
baseado em Large Language Model local via **Ollama**.

---

## Estrutura de Arquivos

```
rpg_llm/
├── config.py        # Configurações do LLM, URLs, constantes do sistema
├── personagens.py   # Definição de Kael (Luta) e Lyra (Sabedoria) + dataclasses
├── itens.py         # Catálogo de itens com maestria e progressão
├── habilidades.py   # Catálogo de habilidades (ativar / passiva / extra)
├── inimigos.py      # Catálogo de inimigos + gerador procedural
├── combate.py       # Motor de combate com avaliação via LLM
├── jornada.py       # Persistência — log.json e estado.json (anti-alucinação)
├── historias.py     # NPCs, cenários pré-definidos e motor narrativo
└── main.py          # Ponto de entrada — loop principal do jogo
```

---

## Requisitos

```bash
pip install requests
```

**Ollama instalado e rodando:**
```bash
ollama serve
ollama pull llama3.1:8b
```

---

## Como Jogar

```bash
python main.py
```

1. Escolha o personagem:
   - **Kael** — Caminho da Luta (Força 14, Vigor 12)
   - **Lyra** — Caminho da Sabedoria (Conhecimento Explícito 18, Psiquê 9)

2. Escolha o cenário:
   - **A** — A Fortaleza Sitiada (foco em combate)
   - **B** — O Mistério da Biblioteca (foco em investigação)
   - **C** — O Mundo Esquecido (mundo aberto)

3. Comandos disponíveis:
   ```
   ação <texto>       Realizar uma ação narrada pela LLM
   falar <npc> <msg>  Dialogar com um NPC
   ficha              Ver sua ficha de personagem
   inimigos           Listar inimigos disponíveis
   combater <id>      Iniciar combate (ex: combater goblin_batedeiro)
   contexto           Ver contexto atual da jornada
   sair               Encerrar a sessão
   ```

---

## Sistema de Combate

```
Dano Final = ((Criatividade + Eficiência) + Dano do Personagem) − Defesa do Alvo

Dano do Personagem = (Dano da Arma / 10) × (Corpo Físico / 4) × (Conhecimento × 4)

Criatividade : avaliada pela LLM com base no texto da ação  [0.5 – 1.0]
Eficiência   : efetividade do ataque vs. defesa do alvo     [0.5 – 1.5]
```

**Atributos:**
| Atributo | Composição |
|---|---|
| Corpo Físico | Força + Vigor |
| Conhecimento | (Tácito/2) + (Explícito/3) |
| Psiquê | Base (criação) + (Conhecimento + Corpo Físico)/4 |
| PV Máx | Corpo Físico × 5 |

---

## Persistência (Anti-Alucinação)

Toda chamada à LLM inclui automaticamente o contexto de `jornada/estado.json`,
que contém: localização, atributos do personagem, NPCs conhecidos, segredos
descobertos e os N eventos mais recentes do `jornada/log.json`.

---

## Personagens

### Kael — Caminho da Luta
- Força: 14 | Vigor: 12 | Corpo Físico: **26**
- Conhecimento Tácito: 8 | Explícito: 3 | Conhecimento: **5.0**
- Psiquê base: 6
- Item: Espada Longa (dano 15, def 5)
- Habilidade passiva: Resistência (+3 Vigor)

### Lyra — Caminho da Sabedoria
- Força: 4 | Vigor: 5 | Corpo Físico: **9**
- Conhecimento Tácito: 4 | Explícito: 18 | Conhecimento: **8.0**
- Psiquê base: 9
- Item: Chapéu do Mago (def 5, dobra conhecimento obtido)
- Habilidades extras: Leitura Dinâmica, Análise de Fraqueza, Culinária
