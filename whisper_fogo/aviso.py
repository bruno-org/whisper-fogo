"""Aviso no canto da tela quando o Whisper Fogo aprende uma palavra.

Espelha o toast LearnedDictionaryWords do Wispr Flow: compacto, sem som, com uma
única ação, desfazer, e fechando sozinho. Aqui ganha contagem regressiva visível,
porque saber quanto tempo resta para desfazer vale mais que a surpresa.

Roda em processo separado, chamado assim:
    pythonw aviso.py "errado>certo" "errado2>certo2"
Ao clicar em desfazer, ele mesmo tira a regra do aprendido.json e sai.
"""
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent
SEGUNDOS = 8            # o Wispr usa entre 5 e 8,7 s nos toasts dele
LARGURA, ALTURA = 330, 96


def mostrar(pares):
    import tkinter as tk
    from tkinter import font as tkfont
    sys.path.insert(0, str(BASE))

    raiz = tk.Tk()
    raiz.overrideredirect(True)          # sem barra de título, é um aviso
    raiz.attributes("-topmost", True)
    raiz.configure(bg="#1e1f22")
    try:
        raiz.attributes("-alpha", 0.97)
    except Exception:
        pass

    altura = ALTURA + 18 * (len(pares) - 1)
    x = raiz.winfo_screenwidth() - LARGURA - 24
    y = raiz.winfo_screenheight() - altura - 64      # acima da barra de tarefas
    raiz.geometry(f"{LARGURA}x{altura}+{x}+{y}")

    borda = tk.Frame(raiz, bg="#3d6b46")             # fiapo verde da marca
    borda.pack(fill="both", expand=True, padx=1, pady=1)
    corpo = tk.Frame(borda, bg="#1e1f22")
    corpo.pack(fill="both", expand=True, padx=2, pady=2)

    titulo = tkfont.Font(family="Segoe UI", size=10, weight="bold")
    normal = tkfont.Font(family="Segoe UI", size=10)
    miudo = tkfont.Font(family="Segoe UI", size=8)

    tk.Label(corpo, text="Aprendi a sua grafia", bg="#1e1f22", fg="#e6e6e6",
             font=titulo).pack(anchor="w", padx=12, pady=(10, 2))
    for velho, novo in pares:
        linha = tk.Frame(corpo, bg="#1e1f22")
        linha.pack(anchor="w", fill="x", padx=12)
        tk.Label(linha, text=velho, bg="#1e1f22", fg="#8a8d93", font=normal).pack(side="left")
        tk.Label(linha, text="  vira  ", bg="#1e1f22", fg="#8a8d93", font=miudo).pack(side="left")
        tk.Label(linha, text=novo, bg="#1e1f22", fg="#6fbf7f", font=titulo).pack(side="left")

    rodape = tk.Frame(corpo, bg="#1e1f22")
    rodape.pack(fill="x", padx=12, pady=(6, 10))
    restante = tk.Label(rodape, text="", bg="#1e1f22", fg="#8a8d93", font=miudo)
    restante.pack(side="left")

    def desfazer():
        import aprendizado
        aprendizado.desfazer(pares)
        raiz.destroy()

    tk.Button(rodape, text="Desfazer", command=desfazer, font=miudo, bg="#2f3136",
              fg="#e6e6e6", activebackground="#3d4046", activeforeground="#ffffff",
              relief="flat", borderwidth=0, padx=12, pady=3,
              cursor="hand2").pack(side="right")

    # clicar no aviso fecha antes da hora, sem desfazer nada
    for w in (corpo, raiz):
        w.bind("<Button-1>", lambda *_: raiz.destroy())
    raiz.bind("<Escape>", lambda *_: raiz.destroy())

    fim = time.time() + SEGUNDOS

    def tique():
        falta = fim - time.time()
        if falta <= 0:
            raiz.destroy()
            return
        restante.config(text=f"fecha em {int(falta) + 1}s, clique para fechar agora")
        raiz.after(200, tique)

    tique()
    raiz.mainloop()


if __name__ == "__main__":
    pares = [tuple(a.split(">", 1)) for a in sys.argv[1:] if ">" in a]
    if pares:
        mostrar(pares)
