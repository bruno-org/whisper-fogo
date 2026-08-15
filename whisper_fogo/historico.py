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
PREVIA = 160          # teto grosseiro da prévia: quem corta de verdade é a medida em pixel
RESPIRO = 12          # px que o título nunca invade, para não encostar na barra de rolagem
INTERVALO = 1000      # ms entre uma olhada e outra no arquivo, para o ditado novo entrar sozinho


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


def ler_novos(posicao):
    """Lê só o que foi acrescentado desde a última leitura.

    Devolve (ditados novos, nova posição, se o arquivo recomeçou). A posição é
    em bytes e não em linha porque só ela é barata de retomar, e acentuação
    ocupa mais de um byte. Linha ainda sem quebra fica para a rodada seguinte:
    é escrita em andamento, não linha corrompida.
    """
    if not ARQUIVO.exists():
        return [], 0, posicao > 0
    tamanho = ARQUIVO.stat().st_size
    recomecou = tamanho < posicao         # histórico limpo ou arquivo trocado
    inicio = 0 if recomecou else posicao
    if tamanho == inicio:
        return [], inicio, recomecou
    with open(ARQUIVO, "rb") as f:
        f.seek(inicio)
        bruto = f.read()
    if b"\n" not in bruto:
        return [], inicio, recomecou
    completo = bruto.rsplit(b"\n", 1)[0] + b"\n"
    novos = []
    for linha in completo.decode("utf-8", "replace").splitlines():
        try:
            novos.append(json.loads(linha))
        except ValueError:
            pass
    return novos, inicio + len(completo), recomecou


def rotular(item):
    """Uma linha da lista: marca de revisado pelo Gemma, quando, e o começo do
    que foi dito. Quem corta no tamanho da coluna é tema.encurtar."""
    marca = "*" if item.get("revisado") else " "
    return f"{marca} {item['quando']}  {' '.join(item['texto'].split())[:PREVIA]}"


def main():
    import tkinter as tk
    from tkinter import font as tkfont
    sys.path.insert(0, str(BASE))
    from clip import escrever
    import tema

    itens = carregar()
    posicao = [ARQUIVO.stat().st_size if ARQUIVO.exists() else 0]
    raiz = tk.Tk()
    raiz.title("Whisper Fogo: histórico de ditados")
    raiz.geometry("980x600")
    raiz.minsize(720, 420)
    icone = BASE / "fogo.ico"
    if icone.exists():
        raiz.iconbitmap(default=str(icone))   # default: vale para a janela e a barra
    tema.aplicar(raiz)                        # fundo e barra de título na cor da marca

    corpo = tkfont.Font(family="Segoe UI", size=11)
    miudo = tkfont.Font(family="Segoe UI", size=9)
    botao_fonte = tkfont.Font(family="Segoe UI", size=10, weight="bold")

    topo = tk.Frame(raiz, bg=tema.FUNDO)
    topo.pack(fill="x", padx=14, pady=(12, 6))
    contador = tk.Label(topo, text=f"{len(itens)} ditados", bg=tema.FUNDO, fg=tema.TEXTO,
                        font=corpo)
    contador.pack(side="left")
    tk.Label(topo, text="Enter ou duplo clique também copia. Esc fecha.",
             bg=tema.FUNDO, fg=tema.APAGADO, font=miudo).pack(side="right")

    meio = tk.Frame(raiz, bg=tema.FUNDO)
    meio.pack(fill="both", expand=True, padx=14, pady=6)

    # A lista e a barra moram no mesmo painel, e não lado a lado soltos: assim a
    # barra fica dentro da caixa escura, como no site, em vez de boiar no fundo.
    esquerda = tk.Frame(meio, bg=tema.PAINEL)
    esquerda.pack(side="left", fill="y", padx=(0, 10))
    barra_lista = tema.BarraDeRolagem(esquerda)
    barra_lista.pack(side="right", fill="y", padx=(0, 3), pady=3)
    lista = tk.Listbox(esquerda, width=44, font=miudo, bg=tema.PAINEL, fg=tema.TEXTO,
                       selectbackground=tema.VERDE, selectforeground=tema.BRANCO,
                       highlightthickness=0, borderwidth=0, activestyle="none")
    lista.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=3)
    barra_lista.ligar(lista)

    # Painel da transcrição aberta: cabeçalho com a data e o botão de copiar,
    # texto embaixo. O botão mora aqui, e não no rodapé, porque é a ação daquela
    # transcrição que está na tela.
    direita = tk.Frame(meio, bg=tema.FUNDO)
    direita.pack(side="left", fill="both", expand=True)

    cabecalho = tk.Frame(direita, bg=tema.FUNDO)
    cabecalho.pack(fill="x", pady=(0, 6))
    carimbo = tk.Label(cabecalho, text="", bg=tema.FUNDO, fg=tema.APAGADO, font=miudo)
    carimbo.pack(side="left")
    copiar_btn = tk.Button(cabecalho, text="Copiar transcrição", font=botao_fonte,
                           bg=tema.VERDE, fg=tema.BRANCO, activebackground=tema.VERDE_CLARO,
                           activeforeground=tema.BRANCO, relief="flat", borderwidth=0,
                           padx=16, pady=6, cursor="hand2",
                           command=lambda: copiar())
    copiar_btn.pack(side="right")

    painel = tk.Frame(direita, bg=tema.PAINEL)
    painel.pack(fill="both", expand=True)
    barra_texto = tema.BarraDeRolagem(painel)
    barra_texto.pack(side="right", fill="y", padx=(0, 3), pady=3)
    texto = tk.Text(painel, wrap="word", font=corpo, bg=tema.PAINEL, fg=tema.TEXTO,
                    insertbackground=tema.TEXTO, highlightthickness=0, borderwidth=0,
                    padx=12, pady=10)
    texto.pack(side="left", fill="both", expand=True)
    barra_texto.ligar(texto)

    rodape = tk.Label(raiz, text="", bg=tema.FUNDO, fg="#6fbf7f", font=miudo, anchor="w")
    rodape.pack(fill="x", padx=14, pady=(0, 12))

    rotulos = [rotular(it) for it in itens]
    largura_usada = [0]

    def preencher(*_):
        """Reescreve os títulos no tamanho que cabe de verdade.

        Roda a cada mudança de largura porque a medida em pixel só existe depois
        de o Tk desenhar a lista.
        """
        cabe = lista.winfo_width() - RESPIRO
        if cabe == largura_usada[0] or cabe < 60:
            return
        largura_usada[0] = cabe
        selecao, altura_rolada = lista.curselection(), lista.yview()[0]
        lista.delete(0, "end")
        for rotulo in rotulos:
            lista.insert("end", tema.encurtar(miudo, rotulo, cabe))
        if selecao:
            lista.selection_set(selecao[0])
        lista.yview_moveto(altura_rolada)

    lista.bind("<Configure>", preencher)

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

    def observar():
        """Ditado novo entra sozinho, sem fechar e abrir a janela.

        Quem grava é o processo do ditado, então aqui a janela vigia o arquivo.
        Um stat por segundo não custa nada e não depende de aviso entre
        processos, que se perderia justamente quando um dos dois caísse.
        """
        novos, posicao[0], recomecou = ler_novos(posicao[0])
        if recomecou:                       # histórico limpo: começa a lista de novo
            itens[:] = carregar()
            rotulos[:] = [rotular(it) for it in itens]
            lista.delete(0, "end")
            largura_usada[0] = 0
            preencher()
            texto.delete("1.0", "end")
            carimbo.config(text="")
        elif novos:
            selecionado = lista.curselection()
            acompanhando = selecionado in ((), (0,))
            for it in reversed(novos):      # do mais antigo para o mais novo
                itens.insert(0, it)
                rotulos.insert(0, rotular(it))
                lista.insert(0, tema.encurtar(miudo, rotulos[0], largura_usada[0]))
            # Quem está no ditado mais recente segue nele, que é a razão de a
            # janela estar aberta. Quem foi ler algo antigo não perde o lugar.
            alvo = 0 if acompanhando else selecionado[0] + len(novos)
            lista.selection_clear(0, "end")
            lista.selection_set(alvo)
            lista.see(alvo)
            if acompanhando:
                mostrar()
        if novos or recomecou:
            contador.config(text=f"{len(itens)} ditados")
        raiz.after(INTERVALO, observar)

    lista.bind("<<ListboxSelect>>", mostrar)
    lista.bind("<Double-Button-1>", copiar)
    raiz.bind("<Return>", copiar)
    raiz.bind("<Escape>", lambda *_: raiz.destroy())

    raiz.update_idletasks()
    preencher()
    if itens:
        lista.selection_set(0)
        mostrar()
    lista.focus_set()
    raiz.after(INTERVALO, observar)
    raiz.mainloop()


def _demo():
    """Autoteste da leitura incremental, em arquivo temporário: o histórico de
    verdade nunca é tocado por teste."""
    import tempfile
    global ARQUIVO
    verdadeiro = ARQUIVO
    with tempfile.TemporaryDirectory() as pasta:
        ARQUIVO = Path(pasta) / "historico.jsonl"

        novos, posicao, recomecou = ler_novos(0)
        assert (novos, posicao, recomecou) == ([], 0, False)   # arquivo nem existe

        registrar("Primeiro ditado, com acentuação.")
        novos, posicao, recomecou = ler_novos(0)
        assert len(novos) == 1 and novos[0]["texto"].endswith("acentuação.")
        assert posicao == ARQUIVO.stat().st_size and not recomecou

        novos, posicao2, _ = ler_novos(posicao)                # nada mudou
        assert novos == [] and posicao2 == posicao

        registrar("Segundo ditado.", revisado=True)
        novos, posicao, _ = ler_novos(posicao)                 # só o que chegou depois
        assert len(novos) == 1 and novos[0]["revisado"] is True

        with open(ARQUIVO, "a", encoding="utf-8") as f:        # escrita pela metade
            f.write('{"quando": "14/08/2026 22:00", "texto": "cortad')
        novos, parcial, _ = ler_novos(posicao)
        assert novos == [] and parcial == posicao, "linha sem quebra não pode ser consumida"

        with open(ARQUIVO, "a", encoding="utf-8") as f:        # o resto chega depois
            f.write('o no meio"}\n')
        novos, posicao, _ = ler_novos(parcial)
        assert len(novos) == 1 and novos[0]["texto"] == "cortado no meio"

        ARQUIVO.write_text("", encoding="utf-8")               # histórico limpo
        novos, posicao, recomecou = ler_novos(posicao)
        assert recomecou and novos == [] and posicao == 0

        assert rotular({"quando": "14/08/2026 22:00", "texto": "a  b\n c"}) == "  14/08/2026 22:00  a b c"
        assert rotular({"quando": "x", "texto": "y", "revisado": True}).startswith("*")
    ARQUIVO = verdadeiro
    print("historico.py: autoteste ok")


if __name__ == "__main__":
    _demo() if "--teste" in sys.argv else main()
