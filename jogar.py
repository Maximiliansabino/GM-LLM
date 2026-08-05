"""
jogar.py
─────────────────────────────────────────────────────────────
Atalho para iniciar o RPG LLM em nova janela.
Equivalente ao jogar.bat — basta executar:

  python jogar.py
─────────────────────────────────────────────────────────────
"""
import os
import sys

# Garante que o diretório do jogo está no path
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import launch
launch.abrir_janela()