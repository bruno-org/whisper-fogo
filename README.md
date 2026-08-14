<div align="center">

<img src="docs/img/banner.png" alt="Whisper Fogo" width="820">

**Ditado por voz que roda inteiro na sua máquina, feito para o português do Brasil.**

Você fala, o texto aparece onde o cursor estiver. Em qualquer programa.
Sem nuvem, sem mensalidade, sem enviar suas informações para servidor nenhum.

<br>

<a href="https://github.com/bruno-org/whisper-fogo/raw/main/instalador/Instalar-Whisper-Fogo.bat">
<img src="https://img.shields.io/badge/Baixar%20para-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Baixar para Windows">
</a>
&nbsp;&nbsp;
<a href="https://github.com/bruno-org/whisper-fogo/raw/main/instalador/Instalar-Whisper-Fogo.command">
<img src="https://img.shields.io/badge/Baixar%20para-macOS%20(beta)-999999?style=for-the-badge&logo=apple&logoColor=white" alt="Baixar para macOS">
</a>

<br><br>

![Licença MIT](https://img.shields.io/badge/licença-MIT-brasa?color=f75a4c)
![Roda offline](https://img.shields.io/badge/nuvem-nenhuma-2ea043)
![Português do Brasil](https://img.shields.io/badge/idioma-português%20do%20Brasil-f7c948)
![Testes](https://img.shields.io/badge/testes-45%20asserts-2ea043)

</div>

---

## Por que este existe

Ditado por voz bom sempre foi coisa de quem fala inglês. As ferramentas que valem
a pena cobram mensalidade, mandam a sua voz para a nuvem e tratam o português como
idioma secundário: transcrevem "Claude" como "cloud", trocam o nome da sua empresa,
não entendem a gíria e ainda escrevem "voce" sem acento.

O Whisper Fogo nasceu de uma decisão simples: **o português do Brasil é o idioma
principal, não um item da lista de suportados.** Tudo aqui foi escolhido pensando
em quem fala português: o modelo, o dicionário que aprende as suas palavras e até
as regras de pontuação, que proíbem travessão porque quase ninguém usa em texto
de trabalho.

E ele roda **inteiro na sua máquina**. Nenhum áudio, nenhuma transcrição e nenhuma
palavra do seu dicionário saem do seu computador. Não existe conta para criar, não
existe servidor para cair, não existe limite de minutos por mês.

---

## Como funciona na prática

| Você faz | O que acontece |
|---|---|
| Segura `Ctrl` + `Shift` e fala | Grava enquanto segurar, cola o texto ao soltar |
| `Ctrl` + `Shift` + `Espaço` | Mãos livres: fala à vontade, a mesma tecla encerra |
| Soma `Alt` enquanto fala | Revisa o texto antes de colar: tira "né", "tipo", "aí", pontua e quebra em parágrafos |
| Clica no ícone da bandeja | Abre o histórico de tudo que você já ditou |
| Corrige uma palavra no campo | O programa aprende a sua grafia e nunca mais erra aquela palavra |

O texto vai para onde o cursor estiver: editor de código, campo de chat, e-mail,
terminal, formulário no navegador. Se o programa aceita texto, ele aceita a sua voz.

---

## Nada do que você fala se perde

<div align="center">
<img src="docs/img/historico.png" alt="Janela de histórico do Whisper Fogo" width="820">
</div>

Toda transcrição é salva **antes** de ir para a área de transferência. Se você
ditou e não tinha campo de texto em foco, a colagem cai no vazio, mas o texto
continua aqui. Abre o histórico, clica em **Copiar transcrição** e segue a vida.

Se a transcrição falhar por qualquer motivo, o áudio é guardado em disco em vez
de evaporar. O que você falou é seu.

---

## Ele aprende as suas palavras sozinho

<div align="center">
<img src="docs/img/aviso.png" alt="Aviso de palavra aprendida">
</div>

Ditou, o texto colou, e você corrigiu uma palavra ali mesmo no campo? O Whisper
Fogo percebe, aprende a grafia certa e passa a acertar sempre. Aparece um aviso
no canto da tela mostrando o que foi aprendido, com um botão de **Desfazer** para
o caso de você não querer.

Não é keylogger: o programa pergunta ao sistema operacional o conteúdo do campo,
pelo mesmo caminho que um leitor de tela usa, e só durante 60 segundos depois de
colar. Campo de senha nunca é lido, e nada disso vai para log nenhum.

**O que vira regra, e o que não vira.** Nome próprio, marca, sigla e termo técnico
entram na primeira correção. Palavra comum do português só entra se você corrigir
duas vezes, senão uma escolha circunstancial viraria regra permanente. Reformatação,
troca de número e correção que não parece erro de transcrição são descartadas.

Você também pode ensinar à mão, editando `dicionario.json`:

```json
{
  "trocas":     { "Cloud Code": "Claude Code", "Verso": "Vercel" },
  "maiusculas": [ "GitHub", "PostgreSQL" ],
  "hotwords":   [ "Kubernetes", "endpoint", "deploy" ],
  "expansoes":  false
}
```

`hotwords` é o vocabulário que o reconhecedor deve esperar ouvir. `expansoes` liga
a troca de "pra" por "para" e "tá" por "está" no texto final.

---

## Instalação

### Para quem só quer usar

Baixe o instalador do seu sistema e dê dois cliques. Ele confere se a sua máquina
aguenta, instala tudo numa pasta isolada, baixa os modelos, cria o atalho e abre o
programa. Não mexe em nada fora da pasta dele.

<div align="center">

[**Baixar para Windows**](https://github.com/bruno-org/whisper-fogo/raw/main/instalador/Instalar-Whisper-Fogo.bat) &nbsp;•&nbsp; [**Baixar para macOS (beta)**](https://github.com/bruno-org/whisper-fogo/raw/main/instalador/Instalar-Whisper-Fogo.command)

</div>

### Para quem quer mexer no código

```bash
git clone https://github.com/bruno-org/whisper-fogo.git
cd whisper-fogo

# Windows
powershell -ExecutionPolicy Bypass -File instalador/instalar.ps1

# macOS
bash instalador/instalar.sh
```

O instalador detecta que você está dentro do repositório e usa os seus arquivos
locais em vez de baixar de novo. Editou o código? Rode o instalador outra vez ou
copie os `.py` por cima da pasta de instalação.

### O que a sua máquina precisa ter

|  | Mínimo | Recomendado |
|---|---|---|
| Sistema | Windows 10 (64 bits) | Windows 11 |
| Placa de vídeo | qualquer (roda na CPU, bem mais lento) | NVIDIA com 6 GB de VRAM |
| Memória | 8 GB | 16 GB |
| Disco | 4 GB (só transcrição) | 8 GB (com revisão de texto) |

Sem placa NVIDIA o programa funciona, mas transcrever 1 minuto de fala pode levar
mais de 1 minuto. Com uma GPU modesta, o mesmo minuto sai em poucos segundos. O
instalador mede a sua máquina e avisa antes de baixar qualquer coisa.

---

## O que é instalado

| Componente | Tamanho | Para quê |
|---|---|---|
| Whisper `large-v3-turbo` | 1,6 GB | Transcrever a fala |
| Gemma 3 4B (`Q4_K_M`) | 2,4 GB | Revisar o texto quando você segura `Alt` |
| llama.cpp com CUDA | 1,1 GB | Rodar o modelo de revisão na GPU |
| Python isolado e bibliotecas | ~2 GB | O programa em si |

A revisão de texto é opcional e o instalador pergunta. Sem ela, o ditado funciona
igual, só não tem o `Alt`.

**Velocidade medida** numa RTX 4050 para notebook: 42 minutos de áudio transcritos
em 86 segundos, ou 29 vezes mais rápido que o tempo real. Ditados curtos do dia a
dia saem em 2 a 6 segundos.

---

## Desempenho e privacidade, em números

- **0 bytes** enviados para a internet durante o uso. O download acontece uma vez, na instalação.
- **0 conta** para criar. Não existe login, não existe telemetria, não existe servidor.
- **60 segundos** é a janela em que o programa observa o campo para aprender a sua grafia. Fora dela, ele não olha nada.
- **1 hora** de fala contínua por ditado, o teto de segurança contra microfone esquecido aberto.
- **10 minutos** sem uso e o modelo sai da memória da placa de vídeo sozinho, devolvendo a VRAM para os seus outros programas.

---

## Como o programa é feito

Python puro, sem framework, sem servidor local, sem Electron. Cada arquivo faz uma
coisa:

| Arquivo | Responsabilidade |
|---|---|
| `voz.py` | O programa: bandeja, gravação, transcrição, colagem |
| `teclado.py` | O atalho global, com a máquina de estados de segurar e travar |
| `clip.py` | Área de transferência e colagem, por sistema operacional |
| `corrigir.py` | Aplica o dicionário na transcrição |
| `aprendizado.py` | Decide o que vira regra de grafia a partir das suas correções |
| `observador.py` | Lê o campo por API de acessibilidade e observa por 60 segundos |
| `historico.py` | Registro em disco e a janela de histórico |
| `aviso.py` | O aviso de palavra aprendida, com desfazer |
| `limpar.py` | A revisão de texto pelo modelo local |

**Testes.** 45 asserts, todos rodando sem microfone e sem placa de vídeo:

```bash
cd whisper_fogo
python corrigir.py      # 10 asserts: dicionário e expansões
python aprendizado.py   # 21 asserts: o que vira regra e o que é descartado
python observador.py    #  8 asserts: âncora e janela de observação
python teste_corte.py   #  3 asserts: gravação longa e corte de segurança
python clip.py          #  3 asserts: área de transferência com acento
```

---

## Estado de cada plataforma

| Recurso | Windows | macOS |
|---|---|---|
| Ditado com atalho global | testado | escrito, **não testado** |
| Colagem no cursor | testado | escrito, **não testado** |
| Histórico e cópia | testado | deve funcionar (Tk) |
| Revisão de texto pelo `Alt` | testado | exige `brew install llama.cpp` |
| Aprender pela sua correção | testado | **ainda não**, depende da API de acessibilidade da Apple |
| Ícone na bandeja | testado | deve funcionar |

Sendo franco: **o Whisper Fogo foi construído e usado no Windows.** O caminho do
macOS existe, foi escrito com as APIs corretas e está no código, mas nunca rodou
numa máquina Apple, porque não havia uma para testar. Se você tem um Mac e topa
ser cobaia, [abra uma issue](https://github.com/bruno-org/whisper-fogo/issues)
contando o que aconteceu. É a contribuição mais útil possível agora.

No macOS o sistema vai pedir duas permissões na primeira execução, em Ajustes,
Privacidade e Segurança: **Microfone** e **Acessibilidade**. Sem a segunda, o
atalho global não funciona.

---

## Perguntas que todo mundo faz

**Minha voz vai para algum servidor?**
Não. O modelo roda na sua máquina. Você pode desligar a internet depois de instalar
e o programa continua funcionando igual.

**Funciona em qualquer programa?**
Em qualquer campo de texto que aceite colar. Editor de código, navegador, chat,
terminal, e-mail, planilha.

**Precisa de placa de vídeo cara?**
Não. Foi construído numa RTX 4050 de notebook, que é placa de entrada. Sem placa
nenhuma ele roda na CPU, só que devagar.

**Por que o primeiro ditado do dia demora mais?**
O modelo carrega na primeira vez que você fala, e isso leva alguns segundos. Depois
fica na memória até você ficar 10 minutos sem ditar.

**Ele funciona em inglês?**
O reconhecedor entende dezenas de idiomas, mas tudo aqui está afinado para
português: o dicionário, a revisão, a lista de palavras comuns. Para inglês existem
boas opções. Para português, esta é a proposta.

**Posso usar no trabalho, em empresa?**
Pode. A licença é MIT, e como nada sai da máquina, não há dado de cliente
trafegando para fora.

---

## Contribuir

Issue e pull request são bem-vindos. O que mais ajuda agora, em ordem:

1. **Testar no macOS** e relatar o que quebrou.
2. **Casos em que a transcrição erra feio** em português, com o áudio se possível.
3. **Palavras que o aprendizado deveria ou não deveria ter pegado.**

O código é comentado em português e explica o porquê das decisões, não só o quê.
Se for mexer, mantenha esse padrão.

---

## Créditos

Construído sobre [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[CTranslate2](https://github.com/OpenNMT/CTranslate2),
[llama.cpp](https://github.com/ggml-org/llama.cpp) e os modelos
[Whisper](https://github.com/openai/whisper) e
[Gemma](https://ai.google.dev/gemma). A lista de palavras comuns do português vem
do [FrequencyWords](https://github.com/hermitdave/FrequencyWords).

O comportamento de aprender pela correção foi inspirado no Wispr Flow.

---

<div align="center">

Feito por **Bruno Henrique Leal da Cunha**
Licença [MIT](LICENSE)

</div>
