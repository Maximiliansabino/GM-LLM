"""
launch.py
─────────────────────────────────────────────────────────────
Launcher do RPG LLM.

Detecta o sistema operacional e abre o jogo em uma janela
de terminal separada, mantendo a janela aberta ao terminar.

Uso:
  python launch.py        → abre nova janela e inicia o jogo
  python launch.py --here → roda direto no terminal atual
─────────────────────────────────────────────────────────────
"""

import os
import sys
import subprocess
import platform


# Caminho absoluto deste arquivo e do main.py
HERE    = os.path.dirname(os.path.abspath(__file__))
MAIN    = os.path.join(HERE, "main.py")
PYTHON  = sys.executable
SISTEMA = platform.system()   # "Windows" | "Darwin" | "Linux"


def _titulo_janela() -> str:
    return "RPG LLM — Mestre Autônomo"


def abrir_janela() -> None:
    """Abre o jogo em uma nova janela de terminal."""

    if SISTEMA == "Windows":
        _abrir_windows()
    elif SISTEMA == "Darwin":
        _abrir_macos()
    else:
        _abrir_linux()


# ── Windows ───────────────────────────────────────────────────
def _abrir_windows() -> None:
    """
    Abre o jogo em nova janela CMD usando CREATE_NEW_CONSOLE.
    Passa python e main.py como lista de argumentos para evitar
    qualquer problema com aspas ou espaços no caminho.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"   # force UTF-8 in child process
    subprocess.Popen(
        [PYTHON, MAIN],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        cwd=HERE,
        close_fds=True,
        env=env,
    )


# ── macOS ─────────────────────────────────────────────────────
def _abrir_macos() -> None:
    """
    Usa osascript para abrir o Terminal.app com o comando.
    A janela permanece aberta após o script terminar.
    """
    titulo = _titulo_janela()
    script = (
        f'tell application "Terminal"\n'
        f'    do script "echo -ne \'\\\\033]0;{titulo}\\\\007\'; '
        f'cd \\"{HERE}\\" && \\"{PYTHON}\\" \\"{MAIN}\\"; '
        f'echo \\"\\nPressione Enter para fechar...\\"; read"\n'
        f'    activate\n'
        f'end tell'
    )
    subprocess.Popen(["osascript", "-e", script])


# ── Linux ─────────────────────────────────────────────────────
def _abrir_linux() -> None:
    """
    Tenta os emuladores de terminal mais comuns em ordem.
    Cada um tem sintaxe diferente para título e para manter aberto.
    """
    titulo = _titulo_janela()

    # Comando a executar dentro do terminal
    cmd_jogo = (
        f'cd "{HERE}" && "{PYTHON}" "{MAIN}"; '
        f'echo ""; echo "Pressione Enter para fechar..."; read'
    )

    terminais = [
        # gnome-terminal (Ubuntu, Fedora GNOME)
        ["gnome-terminal", f"--title={titulo}", "--",
         "bash", "-c", cmd_jogo],

        # konsole (KDE)
        ["konsole", f"--title={titulo}", "-e",
         "bash", "-c", cmd_jogo],

        # xfce4-terminal
        ["xfce4-terminal", f"--title={titulo}", "-e",
         f'bash -c "{cmd_jogo}"'],

        # xterm (fallback universal)
        ["xterm", "-title", titulo, "-e",
         "bash", "-c", cmd_jogo],

        # tilix
        ["tilix", f"--title={titulo}", "-e",
         "bash", "-c", cmd_jogo],

        # alacritty
        ["alacritty", "--title", titulo, "-e",
         "bash", "-c", cmd_jogo],
    ]

    for args in terminais:
        try:
            subprocess.Popen(args,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            print(f"  Terminal aberto: {args[0]}")
            return
        except FileNotFoundError:
            continue

    # Nenhum terminal encontrado — roda no terminal atual
    print("  Nenhum emulador de terminal encontrado.")
    print("  Iniciando no terminal atual...\n")
    _rodar_aqui()


# ── Fallback: rodar no terminal atual ─────────────────────────
def _rodar_aqui() -> None:
    os.chdir(HERE)
    import runpy
    runpy.run_path(MAIN, run_name="__main__")


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--here" in sys.argv:
        _rodar_aqui()
    else:
        print(f"  Abrindo RPG LLM em nova janela ({SISTEMA})...")
        abrir_janela()