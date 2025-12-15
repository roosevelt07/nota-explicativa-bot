# src/utils.py
"""
Utilitários compartilhados para conversão de valores e formatação.
"""

import re
from typing import Optional


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

