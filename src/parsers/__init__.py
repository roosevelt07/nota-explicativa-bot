# src/parsers/__init__.py
"""
Módulo principal para interpretação de PDFs oficiais (Fachada).
Consolida as chamadas para Receita Federal, FGTS e SEFAZ.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

# Importa a classe base de resultados
from src.parsers.base import ResultadoParsers

# Importa as funções específicas de cada parser
# Certifique-se de que os nomes dos arquivos .py estão corretos (receita_federal.py ou receita.py?)
# Ajuste o import abaixo conforme o nome real do seu arquivo da receita.
try:
    from .receita_federal import interpretar_pdf_receita
except ImportError:
    # Fallback caso o arquivo se chame apenas 'receita.py'
    from .receita_federal import interpretar_pdf_receita

from .fgts import interpretar_pdf_fgts
from .sefaz import interpretar_pdf_sefaz

# Configuração básica de log para ajudar no debug do Streamlit
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _validar_caminho(caminho: Union[Path, str]) -> bool:
    """Helper para verificar se o arquivo existe, aceitando str ou Path."""
    if not caminho:
        return False
    p = Path(caminho)
    return p.exists() and p.is_file()


def interpretar_todos(
    receita_pdf: Optional[Union[Path, str]] = None,
    fgts_pdf: Optional[Union[Path, str]] = None,
    sefaz_pdf: Optional[Union[Path, str]] = None,
) -> ResultadoParsers:
    """
    Orquestrador: Chama todos os parsers disponíveis e consolida em um único objeto.

    Parâmetros:
      Recebe os caminhos (Path ou str) para os arquivos PDF temporários.
    
    Retorno:
      Objeto ResultadoParsers preenchido com a soma das informações extraídas.
    """
    
    # 1. Cria o objeto acumulador vazio
    resultado = ResultadoParsers()

    # 2. Processa Receita Federal (SIEF / PGFN)
    if _validar_caminho(receita_pdf):
        logger.info(f"Iniciando parser Receita Federal: {receita_pdf}")
        try:
            resultado = interpretar_pdf_receita(receita_pdf, resultado)
        except Exception as e:
            logger.error(f"❌ Erro no parser Receita Federal: {e}")
            # Não lança o erro (raise) para permitir que os outros parsers rodem
    
    # 3. Processa FGTS (CRF)
    if _validar_caminho(fgts_pdf):
        logger.info(f"Iniciando parser FGTS: {fgts_pdf}")
        try:
            resultado = interpretar_pdf_fgts(fgts_pdf, resultado)
        except Exception as e:
            logger.error(f"❌ Erro no parser FGTS: {e}")

    # 4. Processa SEFAZ (Estadual)
    if _validar_caminho(sefaz_pdf):
        logger.info(f"Iniciando parser SEFAZ: {sefaz_pdf}")
        try:
            resultado = interpretar_pdf_sefaz(sefaz_pdf, resultado)
        except Exception as e:
            logger.error(f"❌ Erro no parser SEFAZ: {e}")

    return resultado