"""Aparência das janelas do Whisper Fogo: cor de marca, barra de título e barra
de rolagem.

Mora fora do historico.py porque o Tk não entrega nada disso pronto no Windows:
a barra de título nativa só muda de cor pelo DWM, o Scrollbar clássico não faz
canto arredondado e o ttk simplesmente ignora cor no tema nativo. As duas coisas
são desenhadas aqui e reaproveitadas por qualquer janela do programa.

A referência visual é a barra de rolagem fina de site: trilho na cor do painel,
polegar arredondado e um respiro entre os dois, que em CSS sai de um
`border: 2px solid` na cor do trilho.
"""
import sys
import tkinter as tk

MAC = sys.platform == "darwin"

VERDE = "#3d6b46"          # o mesmo do botão "Copiar transcrição"
VERDE_CLARO = "#4d8759"    # o mesmo do hover daquele botão
FUNDO = "#1e1f22"
PAINEL = "#26282c"
TEXTO = "#e6e6e6"
APAGADO = "#8a8d93"
BRANCO = "#ffffff"


def pintar_titulo(janela, fundo=VERDE, texto=BRANCO, borda=VERDE):
    """Pinta a barra de título nativa na cor da marca.

    Windows 11 (build 22000 ou mais novo). Em versão antiga, no macOS ou no
    Linux o DWM não existe e a janela fica com a barra padrão do sistema, que é
    exatamente o que se quer como degradação.
    """
    import ctypes

    janela.update_idletasks()
    hwnd = ctypes.windll.user32.GetParent(janela.winfo_id()) or janela.winfo_id()

    def colorref(hexa):
        r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
        return ctypes.c_int(b << 16 | g << 8 | r)   # o COLORREF do Windows é 0x00BBGGRR

    # 20 = modo escuro (deixa os ícones de minimizar, maximizar e fechar claros
    # sobre o verde), 34 = borda, 35 = fundo da barra, 36 = cor do título.
    for atributo, valor in ((20, 1), (34, borda), (35, fundo), (36, texto)):
        v = ctypes.c_int(valor) if isinstance(valor, int) else colorref(valor)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, atributo, ctypes.byref(v), 4)


def aplicar(janela):
    """Cor de marca na janela inteira. Silencioso quando o sistema não suporta,
    porque aparência quebrada nunca pode derrubar o histórico de ditados."""
    janela.configure(bg=FUNDO)
    try:
        pintar_titulo(janela)
    except Exception:
        pass


def barra_de_titulo(raiz, titulo):
    """Barra de título na cor da marca, desenhada pelo programa.

    A barra que o macOS desenha tem cor fixa e não acompanha o tema da janela,
    então no macOS ela é substituída por esta, com os mesmos controles no mesmo
    lugar: fechar e minimizar à esquerda, arrastar pela faixa.
    """
    if not MAC:
        return None

    raiz.overrideredirect(True)
    barra = tk.Frame(raiz, bg=VERDE, height=28)
    barra.pack(side="top", fill="x")
    barra.pack_propagate(False)

    controles = tk.Frame(barra, bg=VERDE)
    controles.pack(side="left", padx=(10, 0))

    def botao_redondo(cor, acao):
        alvo = tk.Canvas(controles, width=14, height=14, bg=VERDE,
                         highlightthickness=0, cursor="hand2")
        alvo.create_oval(2, 2, 12, 12, fill=cor, outline="")
        alvo.pack(side="left", padx=3)
        alvo.bind("<Button-1>", lambda _: acao())
        return alvo

    botao_redondo("#ff5f57", raiz.destroy)
    botao_redondo("#febc2e", lambda: raiz.wm_iconify())

    tk.Label(barra, text=titulo, bg=VERDE, fg=BRANCO,
             font=("Helvetica", 12)).pack(side="left", expand=True)

    # arrastar a janela pela faixa, que é o que a barra do sistema faria
    posicao = {}

    def pegar(evento):
        posicao["x"], posicao["y"] = evento.x_root, evento.y_root
        posicao["jx"], posicao["jy"] = raiz.winfo_x(), raiz.winfo_y()

    def mover(evento):
        if not posicao:
            return
        raiz.geometry(f"+{posicao['jx'] + evento.x_root - posicao['x']}"
                      f"+{posicao['jy'] + evento.y_root - posicao['y']}")

    for alvo in (barra, barra.winfo_children()[-1]):
        alvo.bind("<Button-1>", pegar)
        alvo.bind("<B1-Motion>", mover)
    return barra


def botao(pai, texto, comando, fonte):
    """Botão na cor da marca, com o mesmo desenho nos dois sistemas.

    O botão do Tk no macOS é desenhado pelo próprio sistema e não aceita cor de
    fundo, então lá ele é montado sobre um rótulo, que aceita a cor e responde
    a clique e à passagem do mouse do mesmo jeito.
    """
    comum = dict(text=texto, font=fonte, bg=VERDE, fg=BRANCO,
                 padx=16, pady=6, cursor="hand2", relief="flat", borderwidth=0)
    if not MAC:
        return tk.Button(pai, activebackground=VERDE_CLARO, activeforeground=BRANCO,
                         command=comando, **comum)
    alvo = tk.Label(pai, **comum)
    alvo.bind("<Button-1>", lambda _: comando())
    alvo.bind("<Enter>", lambda _: alvo.config(bg=VERDE_CLARO))
    alvo.bind("<Leave>", lambda _: alvo.config(bg=VERDE))
    return alvo


class BarraDeRolagem(tk.Canvas):
    """Barra de rolagem fina e arredondada, desenhada à mão.

    Fala o mesmo protocolo do Scrollbar do Tk: recebe `set(primeiro, último)` do
    widget rolado e devolve `("moveto", fração)` ou `("scroll", n, "units")`, o
    que a deixa intercambiável com a barra nativa.
    """

    LARGURA = 14        # os 10px do CSS mais o respiro dos dois lados
    RESPIRO = 3         # o `border: 2px solid` de lá: descola o polegar do trilho
    ALTURA_MINIMA = 34  # numa lista longa o polegar encolheria até sumir

    def __init__(self, pai, trilho=PAINEL, polegar=VERDE, aceso=VERDE_CLARO, **kw):
        super().__init__(pai, width=self.LARGURA, highlightthickness=0,
                         borderwidth=0, bg=trilho, takefocus=0, **kw)
        self.cor_polegar, self.cor_acesa = polegar, aceso
        self.comando = None
        self.primeiro, self.ultimo = 0.0, 1.0
        self.sob_o_mouse = False
        self.agarre = None
        self.bind("<Configure>", lambda *_: self._desenhar())
        self.bind("<Button-1>", self._clicar)
        self.bind("<B1-Motion>", self._arrastar)
        self.bind("<ButtonRelease-1>", lambda *_: setattr(self, "agarre", None))
        self.bind("<Enter>", lambda *_: self._realce(True))
        self.bind("<Leave>", lambda *_: self._realce(False))
        self.bind("<MouseWheel>", self._roda)

    def ligar(self, alvo):
        """Liga a barra ao widget nos dois sentidos, de uma vez só."""
        self.comando = alvo.yview
        alvo.configure(yscrollcommand=self.set)
        return alvo

    # ------------------------------------------------------------- protocolo
    def set(self, primeiro, ultimo):
        self.primeiro, self.ultimo = float(primeiro), float(ultimo)
        self._desenhar()

    def get(self):
        return self.primeiro, self.ultimo

    # ---------------------------------------------------------------- desenho
    def _altura(self):
        """Altura real, com a pedida como reserva enquanto o Tk não calculou a
        geometria (acontece antes da janela aparecer, e no autoteste)."""
        altura = self.winfo_height()
        return altura if altura > 1 else self.winfo_reqheight()

    def _faixa(self):
        """Topo e base do polegar em pixel, já com o mínimo aplicado."""
        altura = self._altura()
        y0, y1 = self.primeiro * altura, self.ultimo * altura
        if y1 - y0 < self.ALTURA_MINIMA:
            meio = self.ALTURA_MINIMA / 2
            centro = min(max((y0 + y1) / 2, meio), max(altura - meio, meio))
            y0, y1 = centro - meio, centro + meio
        return y0, y1

    def _desenhar(self):
        self.delete("all")
        if self.ultimo - self.primeiro >= 1.0:
            return      # nada a rolar: some o polegar, o trilho segue reservado
        y0, y1 = self._faixa()
        x0, x1 = self.RESPIRO, self.LARGURA - self.RESPIRO
        cor = self.cor_acesa if self.sob_o_mouse else self.cor_polegar
        raio = (x1 - x0) / 2
        self.create_oval(x0, y0, x1, y0 + 2 * raio, fill=cor, outline=cor)
        self.create_oval(x0, y1 - 2 * raio, x1, y1, fill=cor, outline=cor)
        self.create_rectangle(x0, y0 + raio, x1, y1 - raio, fill=cor, outline=cor)

    def _realce(self, ligado):
        self.sob_o_mouse = ligado
        self._desenhar()

    # ------------------------------------------------------------- interação
    def _clicar(self, evento):
        y0, y1 = self._faixa()
        if y0 <= evento.y <= y1:
            self.agarre = evento.y - y0        # pegou o polegar onde clicou
        else:
            self.agarre = (y1 - y0) / 2        # clicou no trilho: pula para lá
            self._mover(evento.y)

    def _arrastar(self, evento):
        if self.agarre is not None:
            self._mover(evento.y)

    def _mover(self, y):
        if not self.comando:
            return
        altura = max(self._altura(), 1)
        janela = self.ultimo - self.primeiro
        fracao = (y - self.agarre) / altura
        self.comando("moveto", min(max(fracao, 0.0), max(1.0 - janela, 0.0)))

    def _roda(self, evento):
        if self.comando:
            self.comando("scroll", -int(evento.delta / 40) or (-1 if evento.delta > 0 else 1),
                         "units")


def encurtar(fonte, texto, limite):
    """Corta o texto e assina com reticências, medindo em pixel.

    Contar caractere não serve: no Segoe UI um "i" e um "M" não têm a mesma
    largura, então a mesma quantidade de letras dá textos de larguras diferentes.
    """
    if limite <= 0 or fonte.measure(texto) <= limite:
        return texto
    baixo, alto = 0, len(texto)
    while baixo < alto:
        meio = (baixo + alto + 1) // 2
        if fonte.measure(texto[:meio].rstrip() + "…") <= limite:
            baixo = meio
        else:
            alto = meio - 1
    return texto[:baixo].rstrip() + "…"


def _demo():
    from tkinter import font as tkfont
    raiz = tk.Tk()
    raiz.withdraw()
    f = tkfont.Font(family="Segoe UI", size=9)

    largo = f.measure("Whisper Fogo histórico")
    assert encurtar(f, "Whisper Fogo histórico", largo + 50) == "Whisper Fogo histórico"
    curto = encurtar(f, "Whisper Fogo histórico de ditados", largo)
    assert curto.endswith("…") and f.measure(curto) <= largo, curto
    assert encurtar(f, "qualquer coisa", 0) == "qualquer coisa"   # sem largura ainda
    assert encurtar(f, "", 100) == ""

    barra = BarraDeRolagem(raiz)
    barra.set(0.0, 0.25)
    assert barra.get() == (0.0, 0.25)
    barra.configure(height=400)
    raiz.update_idletasks()
    y0, y1 = barra._faixa()
    assert y0 == 0 and abs((y1 - y0) - 100) < 1, (y0, y1)

    barra.set(0.0, 0.01)           # lista enorme: 4px de polegar viraria o mínimo
    y0, y1 = barra._faixa()
    assert y1 - y0 == BarraDeRolagem.ALTURA_MINIMA, (y0, y1)

    barra.set(0.99, 1.0)           # esticado no fim: fica dentro do trilho
    y0, y1 = barra._faixa()
    assert y1 <= 400 and y0 >= 0, (y0, y1)

    barra.set(0.0, 1.0)            # nada a rolar: só o trilho
    barra._desenhar()
    assert not barra.find_all()

    movidos = []
    barra.comando = lambda *a: movidos.append(a)
    barra.set(0.0, 0.25)
    barra.agarre = 0
    barra._mover(400)              # arrastou até o fim: para no limite
    assert movidos == [("moveto", 0.75)], movidos

    raiz.destroy()
    print("tema.py: autoteste ok")


if __name__ == "__main__":
    _demo()
