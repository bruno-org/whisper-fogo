"""Histórico de ditados: nada do que foi falado se perde.

Toda transcrição entra no jsonl ANTES de ir para a área de transferência. Se o
Windows estiver sem campo de texto focado, a colagem cai no vazio, mas o texto
continua aqui para ser copiado depois. É o que o Wispr Flow faz e é o motivo de
muita gente confiar nele.

A janela abre em processo separado de propósito: o pystray ocupa a thread
principal do ditado, e um Tk lá dentro derruba o app inteiro se travar. Aqui, o
pior caso é a janela morrer sozinha, com o ditado intacto.
"""
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent
ARQUIVO = BASE / "historico.jsonl"
LIMITE = 500          # quantos ditados a janela mostra, do mais novo para o mais velho
PREVIA = 64           # caracteres da prévia na lista da esquerda


def registrar(texto, revisado=False):
    """Append puro: não lê, não reescreve, não trava o ditado se o disco engasgar."""
    linha = json.dumps({"quando": time.strftime("%d/%m/%Y %H:%M"),
                        "revisado": revisado, "texto": texto}, ensure_ascii=False)
    with open(ARQUIVO, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def carregar():
    if not ARQUIVO.exists():
        return []
    itens = []
    for linha in ARQUIVO.read_text(encoding="utf-8").splitlines():
        try:
            itens.append(json.loads(linha))
        except ValueError:
            pass      # linha truncada por queda no meio da escrita: ignora e segue
    return itens[-LIMITE:][::-1]


def main():
    import tkinter as tk
    from tkinter import font as tkfont
    sys.path.insert(0, str(BASE))
    from clip import escrever

    itens = carregar()
    raiz = tk.Tk()
    raiz.title("Whisper Fogo: histórico de ditados")
    raiz.geometry("1060x640")
    raiz.configure(bg="#1e1f22")
    icone = BASE / "fogo.ico"
    if icone.exists():
        raiz.iconbitmap(default=str(icone))   # default: vale para a janela e a barra

    corpo = tkfont.Font(family="Segoe UI", size=11)
    miudo = tkfont.Font(family="Segoe UI", size=9)
    botao_fonte = tkfont.Font(family="Segoe UI", size=10, weight="bold")

    topo = tk.Frame(raiz, bg="#1e1f22")
    topo.pack(fill="x", padx=14, pady=(12, 6))
    tk.Label(topo, text=f"{len(itens)} ditados", bg="#1e1f22", fg="#e6e6e6",
             font=corpo).pack(side="left")
    tk.Label(topo, text="Enter ou duplo clique também copia. Esc fecha.",
             bg="#1e1f22", fg="#8a8d93", font=miudo).pack(side="right")

    meio = tk.Frame(raiz, bg="#1e1f22")
    meio.pack(fill="both", expand=True, padx=14, pady=6)

    barra = tk.Scrollbar(meio)
    lista = tk.Listbox(meio, width=48, font=miudo, bg="#26282c", fg="#e6e6e6",
                       selectbackground="#3d6b46", selectforeground="#ffffff",
                       highlightthickness=0, borderwidth=0, activestyle="none",
                       yscrollcommand=barra.set)
    barra.config(command=lista.yview)
    lista.pack(side="left", fill="y")
    barra.pack(side="left", fill="y", padx=(0, 10))

    # Painel da transcrição aberta: cabeçalho com a data e o botão de copiar,
    # texto embaixo. O botão mora aqui, e não no rodapé, porque é a ação daquela
    # transcrição que está na tela.
    direita = tk.Frame(meio, bg="#1e1f22")
    direita.pack(side="left", fill="both", expand=True)

    cabecalho = tk.Frame(direita, bg="#1e1f22")
    cabecalho.pack(fill="x", pady=(0, 6))
    carimbo = tk.Label(cabecalho, text="", bg="#1e1f22", fg="#8a8d93", font=miudo)
    carimbo.pack(side="left")
    copiar_btn = tk.Button(cabecalho, text="Copiar transcrição", font=botao_fonte,
                           bg="#3d6b46", fg="#ffffff", activebackground="#4d8759",
                           activeforeground="#ffffff", relief="flat", borderwidth=0,
                           padx=16, pady=6, cursor="hand2",
                           command=lambda: copiar())
    copiar_btn.pack(side="right")

    texto = tk.Text(direita, wrap="word", font=corpo, bg="#26282c", fg="#e6e6e6",
                    insertbackground="#e6e6e6", highlightthickness=0, borderwidth=0,
                    padx=12, pady=10)
    texto.pack(fill="both", expand=True)

    rodape = tk.Label(raiz, text="", bg="#1e1f22", fg="#6fbf7f", font=miudo, anchor="w")
    rodape.pack(fill="x", padx=14, pady=(0, 12))

    for it in itens:
        limpo = " ".join(it["texto"].split())
        marca = "*" if it.get("revisado") else " "   # revisado pelo Gemma
        lista.insert("end", f"{marca} {it['quando']}  {limpo[:PREVIA]}")

    def mostrar(*_):
        sel = lista.curselection()
        if not sel:
            return
        it = itens[sel[0]]
        carimbo.config(text=f"{it['quando']}  ·  {len(it['texto'])} caracteres")
        texto.delete("1.0", "end")
        texto.insert("1.0", it["texto"])

    def copiar(*_):
        sel = lista.curselection()
        if not sel:
            return
        escrever(itens[sel[0]]["texto"])
        copiar_btn.config(text="Copiado")
        rodape.config(text="Copiado. Cole com Ctrl+V onde quiser.")
        raiz.after(2500, lambda: (copiar_btn.config(text="Copiar transcrição"),
                                  rodape.config(text="")))

    lista.bind("<<ListboxSelect>>", mostrar)
    lista.bind("<Double-Button-1>", copiar)
    raiz.bind("<Return>", copiar)
    raiz.bind("<Escape>", lambda *_: raiz.destroy())

    if itens:
        lista.selection_set(0)
        mostrar()
    lista.focus_set()
    raiz.mainloop()


if __name__ == "__main__":
    main()
