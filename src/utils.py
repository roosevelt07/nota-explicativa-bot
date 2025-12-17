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


def formatar_total_previdencia(dados: dict) -> str:
    """
    Formata o total de previdência para exibição.
    
    Retorna:
    - "Total de Previdência: Regular" se o valor estiver ausente (None, "", 0 inválido, ou chave inexistente)
    - "Total de Previdência: R$ X" se o valor estiver presente
    
    Args:
        dados: Dicionário com estrutura de dados do relatório
        
    Returns:
        String formatada com o total de previdência
    """
    # Acessa a estrutura: dados["receita_federal"]["previdencia"]["total_previdencia"]
    receita_federal = dados.get("receita_federal", {})
    previdencia = receita_federal.get("previdencia", {})
    total_previdencia = previdencia.get("total_previdencia")
    
    # Verifica se o valor está ausente (None, string vazia, ou 0 inválido)
    if not total_previdencia or (isinstance(total_previdencia, str) and not total_previdencia.strip()):
        return "Total de Previdência: Regular"
    
    # Se o valor já está formatado como "R$ X.XXX,XX", usa diretamente
    if isinstance(total_previdencia, str) and total_previdencia.strip():
        # Garante que começa com "R$" se não começar
        valor_formatado = total_previdencia.strip()
        if not valor_formatado.startswith("R$"):
            valor_formatado = f"R$ {valor_formatado}"
        return f"Total de Previdência: {valor_formatado}"
    
    # Se for número, formata
    try:
        valor_float = float(total_previdencia)
        if valor_float > 0:
            return f"Total de Previdência: {formatar_moeda_br(valor_float)}"
        else:
            return "Total de Previdência: Regular"
    except (ValueError, TypeError):
        return "Total de Previdência: Regular"

