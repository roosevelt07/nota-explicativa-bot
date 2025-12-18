# src/utils.py
"""
Utilitários compartilhados para conversão de valores e formatação.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def safe_str(x: any) -> str:
    """
    Converte qualquer valor para string de forma segura.
    Retorna string vazia se None.
    """
    if x is None:
        return ""
    try:
        return str(x)
    except (ValueError, TypeError):
        return ""


def normalize_text(s: str) -> str:
    """
    Normaliza texto: colapsa espaços, remove quebras excessivas, converte para maiúsculas.
    """
    if not s:
        return ""
    # Remove quebras de linha excessivas
    texto = re.sub(r'\n{3,}', '\n\n', str(s))
    # Colapsa espaços múltiplos
    texto = re.sub(r' +', ' ', texto)
    # Remove espaços no início/fim
    texto = texto.strip()
    return texto


def converter_valor_br_para_float(valor_str: str) -> float:
    """
    Converte string monetária brasileira (ex: '1.000,00' ou '99.249,14') para float.
    
    Trata:
    - Pontos como separadores de milhar
    - Vírgula como separador decimal
    - Remove caracteres não numéricos (R$, espaços, etc.)
    
    Exemplos:
        '1.000,00' -> 1000.0
        '99.249,14' -> 99249.14
        'R$ 1.000,00' -> 1000.0
        '1.000' -> 1000.0
    """
    if not valor_str:
        return 0.0
    
    try:
        # Remove tudo que não for dígito, ponto ou vírgula
        limpo = re.sub(r'[^\d.,]', '', str(valor_str).strip())
        
        if not limpo:
            return 0.0
        
        # Se tem vírgula, assume formato BR (ponto = milhar, vírgula = decimal)
        if ',' in limpo:
            # Remove pontos de milhar e troca vírgula por ponto
            limpo = limpo.replace('.', '').replace(',', '.')
        # Se só tem ponto, pode ser formato internacional ou BR sem decimais
        elif '.' in limpo:
            # Se tem mais de um ponto, assume que são milhares BR
            if limpo.count('.') > 1:
                limpo = limpo.replace('.', '')
            # Caso contrário, mantém como está (pode ser decimal internacional)
        
        return float(limpo)
    except (ValueError, AttributeError):
        return 0.0


def to_float_ptbr(value: any) -> float:
    """
    Converte valor para float de forma segura, tratando formato pt-BR.
    
    Args:
        value: Valor a converter (str, float, int, None)
        
    Returns:
        float: Valor convertido ou 0.0 se inválido
    """
    if value is None:
        return 0.0
    
    # Se já é float ou int, retorna direto
    if isinstance(value, (float, int)):
        return float(value)
    
    # Se é string, tenta converter usando converter_valor_br_para_float
    if isinstance(value, str):
        return converter_valor_br_para_float(value)
    
    # Para outros tipos, tenta converter para string primeiro
    try:
        return converter_valor_br_para_float(str(value))
    except (ValueError, TypeError, AttributeError):
        return 0.0


def formatar_moeda_br(valor: float) -> str:
    """
    Formata float para string monetária brasileira (R$ X.XXX,XX).
    """
    if valor == 0.0:
        return "R$ 0,00"
    
    try:
        valor_str = f"{valor:,.2f}"
        # Troca vírgula por X temporariamente, depois troca ponto por vírgula e X por ponto
        valor_str = valor_str.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {valor_str}"
    except (ValueError, TypeError):
        return "R$ 0,00"


def formatar_total_previdencia(dados: dict) -> str:
    """
    Formata o total de previdência para exibição.
    
    Retorna:
    - "Regular" se o valor estiver ausente (None, "", "-", "não identificado", 0 inválido, ou chave inexistente)
    - "R$ X.XXX,XX" se o valor estiver presente
    
    Args:
        dados: Dicionário com estrutura de dados do relatório
        
    Returns:
        String formatada: "Regular" ou "R$ X.XXX,XX"
    """
    # Acessa a estrutura: dados["receita_federal"]["previdencia"]["total_previdencia"]
    receita_federal = dados.get("receita_federal", {})
    previdencia = receita_federal.get("previdencia", {})
    total_previdencia = previdencia.get("total_previdencia")
    
    # Valores que indicam ausência de débito (Regular)
    valores_ausentes = [None, "", "-", "não identificado", "nao identificado", "não informado", "nao informado"]
    
    # Verifica se o valor está ausente
    if total_previdencia is None:
        return "Regular"
    
    # Se for string, verifica se está vazia ou é um valor ausente
    if isinstance(total_previdencia, str):
        valor_limpo = total_previdencia.strip().lower()
        if not valor_limpo or valor_limpo in valores_ausentes:
            return "Regular"
        
        # Se já está formatado como "R$ X.XXX,XX", retorna apenas o valor (sem "Total de Previdência:")
        if valor_limpo.startswith("r$"):
            return total_previdencia.strip()
        # Se não começa com R$, tenta formatar como moeda
        try:
            # Tenta converter string BR para float
            valor_float = converter_valor_br_para_float(total_previdencia)
            if valor_float > 0:
                return formatar_moeda_br(valor_float)
            else:
                return "Regular"
        except (ValueError, TypeError):
            return "Regular"
    
    # Se for número, formata
    try:
        valor_float = float(total_previdencia)
        if valor_float > 0:
            return formatar_moeda_br(valor_float)
        else:
            return "Regular"
    except (ValueError, TypeError):
        return "Regular"

