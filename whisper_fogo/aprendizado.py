"""Aprende grafia a partir da correção que você faz no campo, depois de colar.

Espelha o Auto-add to Dictionary do Wispr Flow, estudado em 14/08/2026 no banco,
nos logs e no pacote do app dele. O que foi copiado de lá, e por quê:

- alinhamento palavra a palavra entre o texto colado e o texto final, com a
  pontuação tratada em canal separado (é assim que "cloud.md." ensina "cloud.md");
- filtro por lista de palavras comuns, para não virar regra a partir de correção
  circunstancial. No Wispr são 15.504 stopwords; aqui, as 15.000 mais frequentes
  do português brasileiro;
- só a substituição de uma palavra por outra ensina. Inserção e remoção, não.

Onde este vai além do Wispr: ele compara sempre em minúsculas, então filtraria
"Vivo" e "Claude", que são palavras comuns do português e marcas de quem dita ao
mesmo tempo. Aqui a caixa e a pontuação interna entram na decisão, e por isso
"Vivo" entra na primeira, enquanto "sessão" precisa se repetir.
"""
import json
import re
import time
import unicodedata
from pathlib import Path

BASE = Path(__file__).parent
ARQUIVO = BASE / "aprendido.json"
STOPWORDS = BASE / "stopwords_pt.txt"

# Palavra comum só vira regra na repetição, nome
# próprio e sigla entram de primeira.
REPETICOES_PARA_COMUM = 2
# Abaixo disso o texto foi reescrito, não corrigido, e nada ali é grafia.
SIMILARIDADE_MINIMA = 0.80
# Uma correção real mexe em poucas palavras. Acima disso é reescrita.
MAX_PARES_POR_DITADO = 4
# Só o miolo da palavra interessa; o que gruda na borda é pontuação.
BORDAS = " \t\n\r.,;:!?()[]{}\"'`«»…"
# Erro de transcrição troca uma palavra por outra parecida, porque o som é o
# mesmo: "simpla" por "Kubernetes", "playwrite" por "PlayWright". Quando as duas não
# se parecem em nada, não foi o ouvido que errou, foi você reescrevendo.
# Calibrado contra os 365 ditados editados do Wispr: 0,5 mantém os acertos e
# derruba "muito" -> "botou", que ele mesmo já tinha classificado como ruim.
PARECENCA_MINIMA = 0.5
# Token que carrega marcação não é palavra: veio de reformatar lista ou HTML.
# A barra fica de fora de propósito: "verde/vermelho" e "páginas/steps" são junção
# de duas ideias, não grafia de uma palavra.
MARCACAO = re.compile(r"[^\wÀ-ɏ.'\-]")
# Palavra de uma ou duas letras erra por qualquer motivo e estraga texto demais
# quando vira regra: na calibração apareceram "a" -> "iA" e "s" -> "SEO".
TAMANHO_MINIMO = 3

_stopwords = None


def _carregar_stopwords():
    global _stopwords
    if _stopwords is None:
        try:
            _stopwords = set(STOPWORDS.read_text(encoding="utf-8").split())
        except Exception:
            _stopwords = set()      # sem a lista, todo mundo vira "incomum"
    return _stopwords


def _sem_acento(p):
    return "".join(c for c in unicodedata.normalize("NFD", p)
                   if unicodedata.category(c) != "Mn")


def e_nome_proprio(palavra, apos_ponto=False):
    """Sinais de que a palavra é nome, marca, sigla ou termo técnico, e não
    palavra corrente. Estes entram no dicionário na primeira correção."""
    nu = palavra.strip(BORDAS)
    if not nu:
        return False
    if any(c.isupper() for c in nu[1:]):        # PostgreSQL, HTML, PlayWright
        return True
    if any(c.isdigit() for c in nu):            # GPT-4, Q4_K_M
        return True
    if any(c in nu[1:-1] for c in "._-"):       # claude.md, RAG-Ready
        return True
    if nu[0].isupper() and not apos_ponto:      # Vivo, Ipiranga, no meio da frase
        return True
    return False


def e_palavra_comum(palavra):
    nu = palavra.strip(BORDAS).lower()
    if not nu:
        return True
    s = _carregar_stopwords()
    return nu in s or _sem_acento(nu) in s


def similaridade(a, b):
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


def e_palavra(token):
    """Palavra de verdade, não pedaço de marcação nem número solto."""
    if not token or len(token) < TAMANHO_MINIMO or MARCACAO.search(token):
        return False
    return any(c.isalpha() for c in token)


def extrair_pares(colado, editado):
    """Devolve [(o que o ASR escreveu, o que você deixou)] das trocas de
    palavra. Ignora inserção, remoção e diferença que é só de pontuação."""
    import difflib
    # A quebra de linha vira token próprio: sem ela, "Das" no começo de uma linha
    # parece nome próprio, quando é só a primeira palavra da frase.
    a, b = re.findall(r"\S+|\n", colado), re.findall(r"\S+|\n", editado)
    if not a or not b:
        return []
    if similaridade(colado, editado) < SIMILARIDADE_MINIMA:
        return []                                # reescreveu, não corrigiu

    pares = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag != "replace" or (i2 - i1) != (j2 - j1):
            continue                             # só troca 1 para 1 ensina grafia
        for k in range(i2 - i1):
            velho, novo = a[i1 + k].strip(BORDAS), b[j1 + k].strip(BORDAS)
            # Maiúscula depois de ponto é gramática, não marca. É o que separa
            # "das" -> "Das" (início de frase, lixo) de "vivo" -> "Vivo"
            # (marca dele no meio da frase).
            pos = j1 + k
            anterior = b[pos - 1] if pos else ""
            apos_ponto = (pos == 0 or anterior == "\n"
                          or anterior.endswith((".", "!", "?", ":", ";")))
            if not velho or not novo or velho == novo:
                continue                         # mudou só a pontuação da borda
            if not e_palavra(velho) or not e_palavra(novo):
                continue                         # marcação de lista ou HTML
            if velho.lower() == novo.lower() and (apos_ponto
                                                  or not e_nome_proprio(novo, apos_ponto)):
                continue                         # só a caixa mudou, e por gramática
            if any(c.isdigit() for c in velho) and any(c.isdigit() for c in novo):
                continue                         # 30% -> 20% é dado, não grafia
            if similaridade(velho.lower(), novo.lower()) < PARECENCA_MINIMA:
                continue                         # trocou de palavra, não corrigiu o som
            pares.append((velho, novo, apos_ponto))
    return pares[:MAX_PARES_POR_DITADO] if len(pares) <= MAX_PARES_POR_DITADO else []


def carregar():
    """{o que o ASR escreve: grafia certa}, só o que já foi promovido a regra.

    A chave guarda a caixa exata que o ASR produziu, e a aplicação é sensível a
    ela. Sem isso, corrigir "DAS," para "Das," viraria a regra "todo das vira
    Das", que estragaria o texto inteiro. O Wispr guarda igual, no observedSource.
    """
    dados = _ler()
    return {k: v["certo"] for k, v in dados.items() if v.get("ativo")}


def _ler():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _gravar(dados):
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def registrar(pares):
    """Aplica a regra de promoção e devolve só o que virou regra agora, que é o
    que o aviso na tela mostra."""
    dados = _ler()
    novos = []
    agora = time.strftime("%d/%m/%Y %H:%M")
    for velho, novo, apos_ponto in pares:
        chave = velho                            # caixa preservada, ver carregar()
        item = dados.get(chave) or {"certo": novo, "vezes": 0, "ativo": False,
                                    "criado": agora}
        item["certo"] = novo
        item["vezes"] += 1
        item["visto"] = agora
        # Só sinal forte de nome, marca ou sigla entra de primeira. Palavra
        # estrangeira e termo inventado ("buyer", "dolar") passam batido pela
        # lista de português e enchiam o dicionário de lixo na primeira correção.
        proprio = e_nome_proprio(novo, apos_ponto)
        preciso = 1 if proprio else REPETICOES_PARA_COMUM
        item["origem"] = "nome próprio" if proprio else (
            "termo incomum" if not e_palavra_comum(novo) else "palavra comum")
        if not item["ativo"] and item["vezes"] >= preciso:
            item["ativo"] = True
            item["promovido"] = agora
            novos.append((velho, novo))
        dados[chave] = item
    if pares:
        _gravar(dados)
    return novos


def desfazer(pares):
    """O botão do aviso: tira a regra e zera a contagem, para não voltar sozinha
    no ditado seguinte."""
    dados = _ler()
    for velho, _novo in pares:
        dados.pop(velho, None)
    _gravar(dados)


def _autoteste():
    global _stopwords
    _stopwords = {"para", "sessao", "sessão", "seção", "secao", "reunião", "reuniao",
                  "isso", "muito", "vivo", "claude", "casa", "ali", "aqui",
                  "quando", "disse", "usei", "fiz", "eu", "o", "a", "no", "mes"}

    # nome próprio, marca e termo técnico entram na primeira correção
    for velho, novo in (("Kubernets", "Kubernetes"), ("PlayWrite", "PlayWright"),
                        ("cloud.md", "claude.md"), ("iOS", "IOPS")):
        ARQUIVO.unlink(missing_ok=True)
        pares = extrair_pares(f"eu usei o {velho} ali", f"eu usei o {novo} ali")
        assert pares, f"nao detectou {velho} -> {novo}"
        assert registrar(pares) == [(velho, novo)], f"nao aprendeu {velho} de primeira"

    # a marca que também é palavra comum: a maiúscula no meio da frase decide
    ARQUIVO.unlink(missing_ok=True)
    p = extrair_pares("eu usei o vivo ali", "eu usei o Vivo ali")
    assert registrar(p) == [("vivo", "Vivo")], "Vivo deveria entrar de primeira"

    # palavra comum só vira regra na segunda vez
    ARQUIVO.unlink(missing_ok=True)
    p = extrair_pares("abri a sessão ali", "abri a seção ali")
    assert registrar(p) == [], "palavra comum nao pode virar regra de primeira"
    assert carregar() == {}, "nao pode aplicar antes de virar regra"
    assert registrar(extrair_pares("abri a sessão ali", "abri a seção ali")) == \
        [("sessão", "seção")], "na segunda vez tinha que aprender"
    assert carregar() == {"sessão": "seção"}

    # desfazer tira a regra e zera, nao volta na proxima
    desfazer([("sessão", "seção")])
    assert carregar() == {}, "desfazer nao limpou"
    assert registrar(extrair_pares("abri a sessão ali", "abri a seção ali")) == [], \
        "depois de desfazer, tem que recomecar a contagem"

    # o que NAO pode virar regra
    ARQUIVO.unlink(missing_ok=True)
    assert extrair_pares("subiu 30% no mes", "subiu 20% no mes") == [], "numero nao e grafia"
    assert extrair_pares("eu fiz isso.", "eu fiz isso") == [], "pontuacao nao e grafia"
    assert extrair_pares("eu fiz isso", "eu fiz isso ali") == [], "insercao nao ensina"
    assert extrair_pares("eu fiz isso ali", "eu fiz isso") == [], "remocao nao ensina"
    assert extrair_pares("eu falei uma coisa aqui", "texto completamente diferente") == [], \
        "reescrita nao ensina"
    # trocou meia frase: e reescrita, mesmo com similaridade alta
    assert extrair_pares("a b c d e f g h", "z y x w v u t s") == []
    # marcacao de lista e HTML nao e palavra (95 regras de lixo vieram daqui,
    # na calibracao contra o historico real do Wispr)
    assert extrair_pares("- boas praticas aqui", "<ul> boas praticas aqui") == []
    assert extrair_pares("<li>atualizar isso aqui", "atualizar isso aqui") == []
    # palavra trocada por outra sem parecenca nenhuma nao e erro de ouvido
    assert extrair_pares("ele falou muito disso", "ele falou botou disso") == [], \
        "troca sem parecenca fonetica nao pode ensinar"
    # mas a troca parecida continua ensinando
    assert extrair_pares("subiu na Verso ontem", "subiu na Vercel ontem"), \
        "Verso -> Vercel tem que passar"

    ARQUIVO.unlink(missing_ok=True)
    print("aprendizado: 21/21 ok")


if __name__ == "__main__":
    _autoteste()
