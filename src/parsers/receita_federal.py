# src/parsers/receita_federal.py
"""
Parser robusto para PDFs da Receita Federal (Situação Fiscal / PGFN).

Implementa:
- Contribuições: Seguro, Patronal, Terceiros (somatórios obrigatórios)
- Simples Nacional: débitos em aberto + parcelamento
- Tributos: IRRF, IRLS, PIS, COFINS
- PGFN: inscrições e SISPAR
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union, Dict, List, Any
import pdfplumber

from src.parsers.base import ResultadoParsers
from src.utils import converter_valor_br_para_float


# ==============================================================================
# CONFIGURAÇÃO DE CÓDIGOS E PADRÕES
# ==============================================================================

CODIGOS_CP_SEGURO = ["1082-01", "1099-01"]
CODIGOS_CP_PATRONAL = ["1138-01", "1646-01"]
CODIGOS_CP_TERCEIROS = ["1170-01", "1176-01", "1191-01", "1196-01", "1200-01"]

CODIGOS_TRIBUTOS = {
    "IRRF": ["0561-07"],
    "PIS": ["8109-02", "0810"],  # 0810-PIS
    "COFINS": ["2172-01", "4493"],  # 4493-COFINS
    "IRLS": []  # Apenas por palavra-chave
}

SITUACOES_PGFN = [
    "ATIVA AJUIZADA",
    "ATIVA EM COBRANCA",
    "ATIVA A SER AJUIZADA",
    "ATIVA A SER COBRADA"
]


# ==============================================================================
# HELPERS BÁSICOS
# ==============================================================================

def _limpa(txt: str | None) -> str:
    """Remove espaços extras e normaliza texto."""
    if not txt:
        return ""
    return " ".join(str(txt).strip().split())


def _extrair_texto_completo(caminho_pdf: Union[Path, str]) -> str:
    """Extrai texto completo do PDF."""
    caminho_pdf = Path(caminho_pdf)
    texto_completo = ""
    
    with pdfplumber.open(str(caminho_pdf)) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if txt:
                texto_completo += txt + "\n"
    
    return texto_completo.strip()


def _extrair_tabelas_estruturadas(caminho_pdf: Union[Path, str]) -> List[List[List[str]]]:
    """Extrai tabelas do PDF de forma estruturada."""
    caminho_pdf = Path(caminho_pdf)
    todas_tabelas = []
    
    with pdfplumber.open(str(caminho_pdf)) as pdf:
        for page in pdf.pages:
            tabelas = page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "snap_tolerance": 3,
                "join_tolerance": 3,
            })
            
            if tabelas:
                for tabela in tabelas:
                    if tabela:
                        todas_tabelas.append(tabela)
    
    return todas_tabelas


def _normalizar_competencia(comp: str) -> Optional[str]:
    """
    Normaliza competência para formato AAAA-MM.
    Aceita: "MM/AAAA", "AAAA-MM", "AAAA"
    """
    if not comp:
        return None
    
    comp = comp.strip()
    
    # Formato MM/AAAA
    match = re.match(r'(\d{2})/(\d{4})', comp)
    if match:
        mes, ano = match.groups()
        return f"{ano}-{mes}"
    
    # Formato AAAA-MM
    match = re.match(r'(\d{4})-(\d{2})', comp)
    if match:
        return comp
    
    # Formato AAAA
    match = re.match(r'(\d{4})', comp)
    if match:
        return f"{match.group(1)}-01"  # Assume janeiro
    
    return None


def _extrair_valor_de_celula(celula: str) -> float:
    """Extrai valor monetário de uma célula."""
    if not celula:
        return 0.0
    
    celula_limpa = _limpa(celula)
    
    padroes_valor = [
        r'([\d\.]+,\d{2})',
        r'([\d\.]+,\d{1,2})',
        r'R\$\s*([\d\.]+,\d{2})',
        r'([\d]+,\d{2})',
    ]
    
    for padrao in padroes_valor:
        match = re.search(padrao, celula_limpa)
        if match:
            valor_str = match.group(1)
            return converter_valor_br_para_float(valor_str)
    
    return 0.0


def _identificar_colunas_tabela(cabeçalho: List[str]) -> Dict[str, int]:
    """Identifica as posições das colunas importantes na tabela."""
    indices = {
        'saldo_devedor': -1,
        'saldo_consolidado': -1,
        'valor_original': -1
    }
    
    if not cabeçalho:
        return indices
    
    for i, cell in enumerate(cabeçalho):
        if not cell:
            continue
        
        cell_upper = _limpa(cell).upper()
        
        # Saldo Devedor Consolidado (prioridade)
        if any(termo in cell_upper for termo in [
            "SDO.DEV.CONS", "SDO DEV CONS", "SALDO DEVEDOR CONSOLIDADO",
            "SALDO CONSOLIDADO", "CONSOLIDADO", "SDO.DEV.CONS."
        ]):
            indices['saldo_consolidado'] = i
        
        # Saldo Devedor
        elif any(termo in cell_upper for termo in [
            "SDO.DEVEDOR", "SDO DEVEDOR", "SALDO DEVEDOR"
        ]):
            indices['saldo_devedor'] = i
        
        # Valor Original
        elif any(termo in cell_upper for termo in [
            "VL.ORIGINAL", "VALOR ORIGINAL", "ORIGINAL"
        ]):
            indices['valor_original'] = i
    
    return indices


def _extrair_valor_da_linha(linha: List[str], indices_colunas: Dict[str, int]) -> Optional[float]:
    """
    Extrai o valor correto da linha.
    Prioriza Saldo Devedor Consolidado, senão usa Saldo Devedor.
    Retorna None se não encontrar valor válido.
    """
    # Prioridade 1: Saldo Devedor Consolidado
    if indices_colunas['saldo_consolidado'] >= 0:
        idx = indices_colunas['saldo_consolidado']
        if idx < len(linha) and linha[idx]:
            valor = _extrair_valor_de_celula(linha[idx])
            if valor > 0:
                return valor
    
    # Prioridade 2: Saldo Devedor
    if indices_colunas['saldo_devedor'] >= 0:
        idx = indices_colunas['saldo_devedor']
        if idx < len(linha) and linha[idx]:
            valor = _extrair_valor_de_celula(linha[idx])
            if valor > 0:
                return valor
    
    # Fallback: procura o maior valor monetário na linha
    valor_max = 0.0
    for cell in linha:
        if cell:
            valor_cell = _extrair_valor_de_celula(cell)
            if valor_cell > valor_max:
                valor_max = valor_cell
    
    return valor_max if valor_max > 0 else None


def _classificar_categoria(linha_completa_upper: str, codigo: str) -> Optional[str]:
    """
    Classifica a categoria da contribuição baseado em palavras-chave e código.
    Retorna: 'seguro', 'patronal', 'terceiros' ou None
    """
    # Seguro: CP-SEGUR., CP SEGURADOS, CONTR. SEGURADOS, SEGURADOS
    if any(termo in linha_completa_upper for termo in [
        "CP-SEGUR", "CP SEGUR", "CP SEGURADOS", "CONTR. SEGURADOS", "SEGURADOS"
    ]) or codigo in CODIGOS_CP_SEGURO:
        return "seguro"
    
    # Patronal: CP-PATRONAL, PATRONAL
    if "CP-PATRONAL" in linha_completa_upper or "CP PATRONAL" in linha_completa_upper or codigo in CODIGOS_CP_PATRONAL:
        return "patronal"
    
    # Terceiros: CP-TERCEIROS, TERCEIROS
    if "CP-TERCEIROS" in linha_completa_upper or "CP TERCEIROS" in linha_completa_upper or codigo in CODIGOS_CP_TERCEIROS:
        return "terceiros"
    
    return None


def _classificar_tributo(linha_completa_upper: str, codigo: str) -> Optional[str]:
    """
    Classifica o tipo de tributo.
    Retorna: 'irrf', 'irls', 'pis', 'cofins' ou None
    """
    # IRRF
    if codigo in CODIGOS_TRIBUTOS["IRRF"] or "IRRF" in linha_completa_upper:
        return "irrf"
    
    # IRLS (apenas por palavra-chave)
    if "IRLS" in linha_completa_upper:
        return "irls"
    
    # PIS
    if any(c in codigo for c in CODIGOS_TRIBUTOS["PIS"]) or "PIS" in linha_completa_upper:
        return "pis"
    
    # COFINS
    if any(c in codigo for c in CODIGOS_TRIBUTOS["COFINS"]) or "COFINS" in linha_completa_upper:
        return "cofins"
    
    return None


def _processar_linha_tabela(linha: List[str], indices_colunas: Dict[str, int] = None) -> Optional[Dict[str, Any]]:
    """
    Processa uma linha de tabela e extrai dados.
    Retorna None se a linha não contiver dados válidos.
    """
    if not linha or len(linha) < 2:
        return None
    
    linha_completa = " ".join([_limpa(cell) for cell in linha if cell])
    linha_completa_upper = linha_completa.upper()
    
    # Procura código
    match_codigo = re.search(r'(\d{4}-\d{2}|\d{4})', linha_completa)
    if not match_codigo:
        return None
    
    codigo = match_codigo.group(1)
    
    # Procura competência
    match_competencia = re.search(r'(\d{2}/\d{4})', linha_completa)
    competencia_raw = match_competencia.group(1) if match_competencia else None
    competencia = _normalizar_competencia(competencia_raw) if competencia_raw else None
    
    # Extrai valor
    if indices_colunas:
        valor = _extrair_valor_da_linha(linha, indices_colunas)
    else:
        valor = None
        for cell in linha:
            if cell:
                valor_cell = _extrair_valor_de_celula(cell)
                if valor_cell > 0:
                    valor = valor_cell
                    break
    
    # Verifica se é débito válido
    tem_devedor = "DEVEDOR" in linha_completa_upper or "ATIVA" in linha_completa_upper
    
    # Classifica categoria
    categoria = _classificar_categoria(linha_completa_upper, codigo)
    tributo = _classificar_tributo(linha_completa_upper, codigo)
    
    # Extrai descrição (primeiros 100 chars)
    descricao = linha_completa[:100] if linha_completa else None
    
    # Se tem valor ou é débito válido ou tem categoria/tributo, processa
    if valor is not None or tem_devedor or categoria or tributo:
        return {
            'codigo': codigo,
            'competencia': competencia,
            'valor': valor,
            'categoria': categoria,
            'tributo': tributo,
            'descricao': descricao,
            'linha_completa_upper': linha_completa_upper,
            'tem_devedor': tem_devedor
        }
    
    return None


# ==============================================================================
# PROCESSAMENTO POR CATEGORIA
# ==============================================================================

def processar_receita(texto: str, tabelas: List[List[List[str]]]) -> Dict[str, Any]:
    """
    Processa o texto e tabelas do PDF da Receita Federal.
    Retorna estrutura conforme schema unificado.
    """
    resultado = {
        'contribuicoes': {
            'seguro_total': 0.0,
            'patronal_total': 0.0,
            'terceiros_total': 0.0,
            'total_geral': 0.0,
            'detalhes': []
        },
        'simples_nacional': {
            'tem_pendencias': False,
            'debitos': [],
            'parcelamento': {
                'tem_parcelamento': False,
                'tipo': None,
                'parcelas_atraso': None
            }
        },
        'debitos_gerais': {
            'IRRF': [],
            'IRLS': [],
            'PIS': [],
            'COFINS': []
        },
        'pgfn': {
            'previdenciario': [],
            'simples_nacional': [],
            'geral': []
        },
        'sispar': {
            'tem_sispar': False,
            'detalhes': []
        }
    }
    
    # Processa tabelas
    todos_debitos = []
    for tabela in tabelas:
        if not tabela:
            continue
        
        # Identifica colunas do cabeçalho
        indices_colunas = {}
        if len(tabela) > 0:
            indices_colunas = _identificar_colunas_tabela(tabela[0])
        
        # Processa linhas
        for i, linha in enumerate(tabela):
            if i == 0:
                continue  # Pula cabeçalho
            
            debito = _processar_linha_tabela(linha, indices_colunas)
            if debito:
                todos_debitos.append(debito)
    
    # Se não encontrou nas tabelas, tenta no texto
    if not todos_debitos:
        padrao_geral = r'(\d{4}-\d{2}|\d{4}).*?(\d{2}/\d{4})?.*?([\d\.]+,\d{2}).*?DEVEDOR'
        matches = re.finditer(padrao_geral, texto, re.IGNORECASE)
        
        for match in matches:
            codigo = match.group(1)
            competencia_raw = match.group(2)
            valor_str = match.group(3)
            valor = converter_valor_br_para_float(valor_str) if valor_str else None
            linha_completa = match.group(0)
            
            todos_debitos.append({
                'codigo': codigo,
                'competencia': _normalizar_competencia(competencia_raw) if competencia_raw else None,
                'valor': valor,
                'categoria': _classificar_categoria(linha_completa.upper(), codigo),
                'tributo': _classificar_tributo(linha_completa.upper(), codigo),
                'descricao': linha_completa[:100],
                'linha_completa_upper': linha_completa.upper(),
                'tem_devedor': True
            })
    
    # Processa cada débito
    for debito in todos_debitos:
        codigo = debito.get('codigo')
        competencia = debito.get('competencia')
        valor = debito.get('valor')
        categoria = debito.get('categoria')
        tributo = debito.get('tributo')
        descricao = debito.get('descricao')
        
        # Contribuições (Seguro, Patronal, Terceiros)
        if categoria:
            item_detalhe = {
                "competencia": competencia,
                "codigo": codigo,
                "descricao": descricao,
                "categoria": categoria,
                "valor": valor,
                "fonte": "receita_federal"
            }
            
            resultado['contribuicoes']['detalhes'].append(item_detalhe)
            
            # Atualiza totais
            if categoria == 'seguro' and valor:
                resultado['contribuicoes']['seguro_total'] += valor
            elif categoria == 'patronal' and valor:
                resultado['contribuicoes']['patronal_total'] += valor
            elif categoria == 'terceiros' and valor:
                resultado['contribuicoes']['terceiros_total'] += valor
        
        # Tributos (IRRF, IRLS, PIS, COFINS)
        if tributo:
            item_tributo = {
                "competencia": competencia,
                "codigo": codigo,
                "descricao": descricao,
                "valor": valor,
                "situacao": "DEVEDOR" if debito.get('tem_devedor') else None
            }
            
            resultado['debitos_gerais'][tributo.upper()].append(item_tributo)
        
        # Simples Nacional
        linha_upper = debito.get('linha_completa_upper', '')
        if "SIMPLES NAC" in linha_upper and debito.get('tem_devedor'):
            resultado['simples_nacional']['tem_pendencias'] = True
            resultado['simples_nacional']['debitos'].append({
                "competencia": competencia,
                "codigo": codigo,
                "descricao": descricao,
                "valor": valor
            })
    
    # Calcula total geral de contribuições
    resultado['contribuicoes']['total_geral'] = (
        resultado['contribuicoes']['seguro_total'] +
        resultado['contribuicoes']['patronal_total'] +
        resultado['contribuicoes']['terceiros_total']
    )
    
    # Simples Nacional - Parcelamento
    texto_lower = texto.lower()
    if any(termo in texto_lower for termo in [
        "parcsn", "parcmei", "simples nacional - em parcelamento",
        "pendência - parcelamento", "pendencia - parcelamento"
    ]):
        resultado['simples_nacional']['parcelamento']['tem_parcelamento'] = True
        
        # Extrai parcelas em atraso
        match_atraso = re.search(r'parcelas\s+em\s+atraso.*?(\d+)', texto, re.IGNORECASE)
        if match_atraso:
            resultado['simples_nacional']['parcelamento']['parcelas_atraso'] = int(match_atraso.group(1))
        
        # Identifica tipo
        if "parcsn" in texto_lower:
            resultado['simples_nacional']['parcelamento']['tipo'] = "PARCSN"
        elif "parcmei" in texto_lower:
            resultado['simples_nacional']['parcelamento']['tipo'] = "PARCMEI"
    
    # PGFN
    padrao_inscricao = r'(\d{2}\.\d\.\d{2}\.\d{6}-\d{2})'
    padrao_situacao = '|'.join(SITUACOES_PGFN)
    
    matches_pgfn = re.finditer(
        rf'{padrao_inscricao}.*?({padrao_situacao})',
        texto,
        re.IGNORECASE
    )
    
    for match in matches_pgfn:
        inscricao = match.group(1)
        situacao = match.group(2)
        
        contexto = texto[max(0, match.start()-100):min(len(texto), match.end()+100)]
        tipo = "simples_nacional" if "1507" in contexto or "simples" in contexto.lower() else "previdenciario"
        
        if tipo == "simples_nacional":
            resultado['pgfn']['simples_nacional'].append({
                'inscricao': inscricao,
                'situacao': situacao
            })
        else:
            resultado['pgfn']['previdenciario'].append({
                'inscricao': inscricao,
                'situacao': situacao
            })
    
    # SISPAR - Extração melhorada de valor total, quantidade de parcelas e valor da parcela
    texto_normalizado = re.sub(r'\s+', ' ', texto)
    
    # Padrões para detectar SISPAR
    padroes_sispar = [
        r'Parcelamento\s*\(?\s*SISPAR\s*\)?',
        r'NEGOCIADA\s+NO\s+SISPAR',
        r'SISPAR',
        r'Parcelamento\s+com\s+Exigibilidade\s+Suspensa\s*\(?\s*SISPAR\s*\)?'
    ]
    
    tem_sispar = False
    for padrao in padroes_sispar:
        if re.search(padrao, texto_normalizado, re.IGNORECASE):
            tem_sispar = True
            break
    
    if tem_sispar:
        resultado['sispar']['tem_sispar'] = True
        
        # Extrai contexto ao redor de SISPAR (até 500 caracteres antes e depois)
        contexto_sispar = ""
        for padrao in padroes_sispar:
            match = re.search(padrao, texto_normalizado, re.IGNORECASE)
            if match:
                inicio = max(0, match.start() - 250)
                fim = min(len(texto_normalizado), match.end() + 500)
                contexto_sispar = texto_normalizado[inicio:fim]
                break
        
        if contexto_sispar:
            # 1. Extrai valor total (procura por "R$", "valor", "total" seguido de número)
            valor_total = None
            padroes_valor = [
                r'(?:valor\s+total|total|valor\s+consolidado|valor\s+do\s+parcelamento)[:\s]*R?\$?\s*(?P<valor>[\d\.]+,\d{2})',
                r'R\$\s*(?P<valor>[\d\.]+,\d{2})(?:\s+.*?SISPAR|.*?parcelamento)',
                r'SISPAR.*?R\$\s*(?P<valor>[\d\.]+,\d{2})',
                r'(?P<valor>[\d\.]+,\d{2})(?:\s+.*?SISPAR|.*?parcelamento)'
            ]
            
            for padrao_valor in padroes_valor:
                match_valor = re.search(padrao_valor, contexto_sispar, re.IGNORECASE)
                if match_valor:
                    valor_str = match_valor.group('valor')
                    if valor_str:
                        valor_total = converter_valor_br_para_float(valor_str)
                        if valor_total and valor_total > 0:
                            break
            
            # 2. Extrai quantidade de parcelas
            quantidade_parcelas = None
            padroes_qtd = [
                r'(?:quantidade|qtd|qtde|n[úu]mero|n\.?\s*de)\s*(?:de\s*)?parcelas?[:\s]*(?P<qtd>\d+)',
                r'(?P<qtd>\d+)\s*(?:parcelas?|presta[çc][õo]es?)',
                r'parcela\s+(?P<qtd>\d+)\s+de\s+\d+',
                r'(?P<qtd>\d+)\s+vezes',
                r'em\s+(?P<qtd>\d+)\s+parcelas?'
            ]
            
            for padrao_qtd in padroes_qtd:
                match_qtd = re.search(padrao_qtd, contexto_sispar, re.IGNORECASE)
                if match_qtd:
                    qtd_str = match_qtd.group('qtd')
                    if qtd_str:
                        try:
                            quantidade_parcelas = int(qtd_str)
                            if quantidade_parcelas > 0:
                                break
                        except ValueError:
                            pass
            
            # 3. Extrai valor da parcela (se disponível)
            valor_parcela = None
            if quantidade_parcelas and valor_total:
                # Calcula valor da parcela se tiver quantidade
                valor_parcela = valor_total / quantidade_parcelas
            else:
                # Tenta extrair valor da parcela diretamente
                padroes_parcela = [
                    r'(?:valor\s+da\s+parcela|parcela\s+de|valor\s+parcela)[:\s]*R?\$?\s*(?P<valor>[\d\.]+,\d{2})',
                    r'R\$\s*(?P<valor>[\d\.]+,\d{2})\s+por\s+parcela'
                ]
                for padrao_parcela in padroes_parcela:
                    match_parcela = re.search(padrao_parcela, contexto_sispar, re.IGNORECASE)
                    if match_parcela:
                        valor_str = match_parcela.group('valor')
                        if valor_str:
                            valor_parcela = converter_valor_br_para_float(valor_str)
                            if valor_parcela and valor_parcela > 0:
                                break
            
            # 4. Extrai competência
            competencia = None
            match_comp = re.search(r'(\d{2}/\d{4})', contexto_sispar)
            if match_comp:
                competencia_raw = match_comp.group(1)
                competencia = _normalizar_competencia(competencia_raw)
            
            # Adiciona detalhes do SISPAR
            detalhe_sispar = {
                'valor_total': valor_total,
                'quantidade_parcelas': quantidade_parcelas,
                'valor_parcela': valor_parcela,
                'competencia': competencia
            }
            
            resultado['sispar']['detalhes'].append(detalhe_sispar)
    
    return resultado


# ==============================================================================
# FUNÇÃO PRINCIPAL DO PARSER
# ==============================================================================

def interpretar_pdf_receita(
    caminho_pdf: Path | str, resultado: ResultadoParsers | None = None
) -> ResultadoParsers:
    """
    Processa PDF da Receita Federal e preenche ResultadoParsers com dados estruturados.
    """
    if resultado is None:
        resultado = ResultadoParsers()
    
    try:
        texto_completo = _extrair_texto_completo(caminho_pdf)
        tabelas = _extrair_tabelas_estruturadas(caminho_pdf)
        
        if not texto_completo and not tabelas:
            resultado.bloco_receita_federal = "Erro de leitura do PDF."
            return resultado
        
        # Extrai metadados básicos
        if not resultado.cnpj:
            match_cnpj = re.search(r'\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b', texto_completo)
            if match_cnpj:
                resultado.cnpj = match_cnpj.group(1)
        
        if not resultado.requerente:
            match_razao = re.search(r"Raz[ãa]o\s+Social[:\s]+(.+?)(?:\n|CNPJ)", texto_completo, re.IGNORECASE)
            if match_razao:
                resultado.requerente = _limpa(match_razao.group(1))
        
        padroes_data = [
            r"Data\s+da\s+Consulta[:\s]+([\d/]+)",
            r"Emitido\s+em[:\s]+([\d/]+)"
        ]
        if not resultado.data_consulta_rf:
            for padrao in padroes_data:
                match = re.search(padrao, texto_completo, re.IGNORECASE)
                if match:
                    data_str = re.sub(r"[^\d/]", "", match.group(1))
                    if re.match(r"\d{2}/\d{2}/\d{4}", data_str):
                        resultado.data_consulta_rf = data_str
                        break
        
        # Identifica situação fiscal
        texto_lower = texto_completo.lower()
        tem_debitos = "consta débito" in texto_lower or "possui débito" in texto_lower or "devador" in texto_lower
        situacao_label = "COM DÉBITOS / PENDÊNCIAS" if tem_debitos else "REGULAR"
        
        resultado.bloco_receita_federal = f"Situação fiscal: {situacao_label}."
        
        # Processa dados detalhados
        dados_processados = processar_receita(texto_completo, tabelas)
        
        if not hasattr(resultado, 'receita_federal') or not resultado.receita_federal:
            resultado.receita_federal = {}
        
        resultado.receita_federal = dados_processados
    
    except Exception as e:
        resultado.bloco_receita_federal = f"Erro no parser: {str(e)}"
        import traceback
        print(f"Erro detalhado: {traceback.format_exc()}")
    
    return resultado
