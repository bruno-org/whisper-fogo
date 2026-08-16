"""Ponto de entrada do aplicativo do macOS.

O executável do pacote é o próprio interpretador, e é isso que faz o sistema
tratar tudo como um programa só: ao pedir microfone e acessibilidade, aparece
uma linha, escrita "Whisper Fogo", com o ícone do aplicativo.

Lançado pelo Finder, o interpretador sobe sem argumento nenhum. Este módulo é
carregado pelo Python na inicialização e entrega o controle ao programa.
"""
import os
import sys

# O aplicativo é assinado, e a assinatura vale enquanto nada muda lá dentro.
# Sem esta linha, a primeira importação gravaria arquivos de cache no pacote e
# o sistema passaria a tratar o programa como adulterado.
sys.dont_write_bytecode = True

if (os.path.basename(sys.executable) == "whisper-fogo"
        and sys.argv[:1] == [""]):          # sem argumento: veio do Finder
    conteudo = os.path.dirname(os.path.dirname(os.path.realpath(sys.executable)))
    voz = os.path.join(conteudo, "Resources", "app", "voz.py")
    sys.argv = [voz]
    with open(voz, encoding="utf-8") as arquivo:
        codigo = compile(arquivo.read(), voz, "exec")
    exec(codigo, {"__name__": "__main__", "__file__": voz})
    raise SystemExit(0)
