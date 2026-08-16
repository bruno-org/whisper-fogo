"""Onde ficam o código e onde ficam os dados, em cada sistema.

No Windows os dois moram na mesma pasta, que é onde o programa é instalado.

No macOS o programa é um aplicativo assinado, e aplicativo assinado não se
altera depois de instalado: qualquer arquivo escrito lá dentro invalidaria a
assinatura e o sistema passaria a tratar o programa como adulterado. Por isso o
que nasce durante o uso, como o histórico de ditados e o dicionário que você
ensina, mora na pasta de dados que o próprio macOS reserva para cada programa.
"""
import sys
from pathlib import Path

MAC = sys.platform == "darwin"

CODIGO = Path(__file__).parent

if MAC:
    DADOS = Path.home() / "Library" / "Application Support" / "WhisperFogo"
    DADOS.mkdir(parents=True, exist_ok=True)
else:
    DADOS = CODIGO
