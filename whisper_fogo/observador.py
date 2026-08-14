"""Observa o campo onde o texto foi colado, para ver como você corrigiu.

Copiado do EditTextManager do Wispr Flow, medido nos logs dele em 14/08/2026:
lê o campo pelo UI Automation do Windows (o mesmo IUIAutomationElement, com
ValuePattern, TextPattern e o IAccessible antigo como último recurso) e observa
por 60 segundos, encerrando antes pelos mesmos motivos que ele registra.

Não é keylogger: pergunta ao Windows o conteúdo do campo focado, não o que foi
digitado. Se o campo não expuser o conteúdo, a observação simplesmente não
acontece e o ditado segue igual.
"""
import difflib
import re
import sys
import threading
import time

JANELA_S = 60.0        # medido: 180 janelas do Wispr, todas de 60,0 s exatos
INTERVALO_S = 1.0      # de quanto em quanto tempo relê o campo
CAMPO_LONGO = 20000    # acima disso o Wispr desiste ("textbox_too_long")
COBERTURA_MINIMA = 0.5  # quanto do texto colado ainda precisa estar no campo

VALUE, TEXT, LEGACY = 10002, 10014, 10018
E_SENHA = 30052        # UIA_IsPasswordPropertyId


def _tokens(t):
    return re.findall(r"\S+|\n", t)


def recortar(conteudo, colado):
    """Acha, dentro do campo, o pedaço que corresponde ao que foi colado.

    É a âncora do Wispr: sem ela, o texto que você já tinha no campo entraria
    na comparação e toda edição pareceria uma reescrita gigante.
    """
    c, p = _tokens(conteudo), _tokens(colado)
    if not c or not p:
        return None
    blocos = [b for b in difflib.SequenceMatcher(None, c, p).get_matching_blocks() if b.size]
    if not blocos:
        return None
    if sum(b.size for b in blocos) / len(p) < COBERTURA_MINIMA:
        return None                              # âncora perdida
    ini = max(0, blocos[0].a - blocos[0].b)
    ultimo = blocos[-1]
    fim = min(len(c), ultimo.a + ultimo.size + (len(p) - ultimo.b - ultimo.size))
    return " ".join(c[ini:fim]).replace(" \n ", "\n")


class Campo:
    """Envelope fino sobre o UI Automation, para o resto do código não precisar
    saber de COM."""

    def __init__(self):
        import comtypes.client
        self._m = comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import CUIAutomation, IUIAutomation
        self.auto = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)

    def ler_focado(self):
        """Conteúdo do campo com foco agora, ou None se não der para ler.

        🔴 Campo de senha nunca é lido. O foco pode mudar durante os 60 s de
        observação, e sem esta guarda o app leria a senha que você digitasse
        logo depois de colar um ditado.
        """
        try:
            el = self.auto.GetFocusedElement()
            if el.GetCurrentPropertyValue(E_SENHA):
                return None
        except Exception:
            return None
        for pid, iface in ((VALUE, "IUIAutomationValuePattern"),
                           (TEXT, "IUIAutomationTextPattern"),
                           (LEGACY, "IUIAutomationLegacyIAccessiblePattern")):
            try:
                pat = el.GetCurrentPattern(pid)
                if not pat:
                    continue
                pat = pat.QueryInterface(getattr(self._m, iface))
                v = pat.DocumentRange.GetText(-1) if pid == TEXT else pat.CurrentValue
                if v:
                    return v
            except Exception:
                continue
        return None


def observar(colado, ao_terminar, parar_agora, leitor=None):
    """Roda em thread própria. Chama ao_terminar(texto_final, motivo) uma vez.

    parar_agora é um threading.Event: o ditado seguinte o dispara, que é o
    "next_dictation_started" do Wispr. leitor existe para o teste injetar uma
    leitura determinística no lugar do UI Automation.

    🔴 O conteúdo lido nunca é impresso no log. Durante os 60 s o foco pode ir
    para qualquer campo da máquina, e o que não casar com a âncora do ditado é
    descartado na hora, sem passar por lugar nenhum.
    """
    if leitor is None:
        try:
            leitor = Campo().ler_focado
        except Exception as e:
            print(f"[observador não subiu] {e}", file=sys.stderr)
            return
    inicio = time.time()
    ultimo = None
    motivo = "janela_de_60s"
    while time.time() - inicio < JANELA_S:
        if parar_agora.wait(INTERVALO_S):
            motivo = "novo_ditado"
            break
        atual = leitor()
        if atual is None:
            continue                             # campo sem conteúdo legível agora
        if len(atual) > CAMPO_LONGO:
            motivo = "campo_muito_longo"
            break
        trecho = recortar(atual, colado)
        if trecho is None:
            motivo = "ancora_perdida"
            break
        ultimo = trecho
    if ultimo is not None and ultimo.strip() != colado.strip():
        ao_terminar(ultimo, motivo)


def observar_em_thread(colado, ao_terminar, parar_agora, leitor=None):
    t = threading.Thread(target=observar, args=(colado, ao_terminar, parar_agora, leitor),
                         daemon=True)
    t.start()
    return t


def _autoteste():
    # o campo tem texto que já estava lá antes e depois; a âncora tem que achar só o ditado
    campo = "anotação antiga aqui\nabri o Kubernets ontem\nrodapé que ja existia"
    colado = "abri o Kubernetes ontem"
    trecho = recortar(campo, "abri o Kubernets ontem")
    assert trecho == "abri o Kubernets ontem", trecho

    # a correção fica dentro do recorte
    campo2 = "lixo antes\neu usei o claude.md hoje\nlixo depois"
    assert recortar(campo2, "eu usei o cloud.md hoje") == "eu usei o claude.md hoje"

    # campo esvaziado: âncora perdida, não inventa comparação
    assert recortar("nada a ver com isso", "eu usei o cloud.md hoje") is None

    # campo idêntico ao colado
    assert recortar("um dois tres", "um dois tres") == "um dois tres"

    # o recorte não pode arrastar o texto que você já tinha
    campo3 = "primeiro paragrafo dele\n" + "a b c d e f" + "\nassinatura dele"
    assert recortar(campo3, "a b c d e f") == "a b c d e f"

    # ---- a janela de observação, com leitura injetada ----
    colado = "eu subi o site na Verso ontem"
    leituras = iter([colado, colado, colado.replace("Verso", "Vercel")])
    pego = {}
    parar = threading.Event()
    t = observar_em_thread(colado, lambda f, m: pego.update(final=f, motivo=m), parar,
                           leitor=lambda: next(leituras, colado.replace("Verso", "Vercel")))
    time.sleep(3.5)
    parar.set()
    t.join(timeout=5)
    assert pego.get("final", "").strip() == "eu subi o site na Vercel ontem", pego
    assert pego["motivo"] == "novo_ditado", pego

    # campo trocado no meio: âncora perdida, não entrega nada
    pego2, parar2 = {}, threading.Event()
    t2 = observar_em_thread(colado, lambda f, m: pego2.update(final=f), parar2,
                            leitor=lambda: "outro assunto totalmente diferente aqui")
    t2.join(timeout=5)
    assert pego2 == {}, pego2

    # sem edição nenhuma, não chama ninguém
    pego3, parar3 = {}, threading.Event()
    t3 = observar_em_thread(colado, lambda f, m: pego3.update(final=f), parar3,
                            leitor=lambda: colado)
    time.sleep(2.0)
    parar3.set()
    t3.join(timeout=5)
    assert pego3 == {}, pego3
    print("observador: 8/8 ok")


if __name__ == "__main__":
    _autoteste()
