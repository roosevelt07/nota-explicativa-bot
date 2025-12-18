# src/parsers/sefaz.py
"""
Parser robusto para PDFs da SEFAZ (Secretaria da Fazenda Estadual).

Implementa:
- Identificação de CND/Certidão vs Extrato de Débitos
- IPVA (quando houver evidência)
- Fronteira/ICMS Antecipado (quando não for certidão)
- Débitos Fiscais (quando houver tabela/listagem)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union, List, Dict, Any

import pdfplumber

from src.parsers.base import ResultadoParsers
from src.utils import converter_valor_br_para_float, safe_str, normalize_text
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


# ==============================================================================
# HELPERS BÁSICOS
# ==============================================================================

def _limpa(txt: str | None) -> str:
    """Remove espaços extras e normaliza texto."""
    if not txt:
        return ""
    return " ".join(str(txt).strip().split())


def _extrair_texto_completo(caminho_pdf: Union[Path, str]) -> str:
    """Extrai texto de todas as páginas do PDF."""
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


def _extrair_data(texto: str, padroes: list[str]) -> Optional[str]:
    """Retorna a primeira data encontrada no formato DD/MM/YYYY."""
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if not match:
            continue
        data_str = match.group(1)
        data_str = re.sub(r"[^\d/]", "", data_str)

        if re.match(r"\d{2}/\d{2}/\d{4}", data_str):
            return data_str
        if re.match(r"\d{2}/\d{2}/\d{2}", data_str):
            dia, mes, ano2 = data_str.split("/")
            return f"{dia}/{mes}/20{ano2}"
    return None


def _extrair_cnpj(texto: str) -> Optional[str]:
    """Extrai CNPJ formatado."""
    padroes = [
        r"CNPJ[:\s]+([\d.\s/-]+)",
        r"Inscriç[ãa]o[:\s]+([\d.\s/-]+)",
        r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b",
    ]
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            cnpj = match.group(1)
            cnpj_limpo = re.sub(r"[^\d]", "", cnpj)
            if len(cnpj_limpo) == 14:
                return f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"
    return None


def _identificar_tipo_documento(texto: str, tabelas: List[List[List[str]]]) -> str:
    """
    Identifica se o documento é certidão (CND/CRF) ou extrato de débitos.
    Retorna: "certidao" ou "extrato"
    """
    texto_upper = texto.upper()
    
    # Verifica se é certidão
    if "CERTIDÃO DE REGULARIDADE FISCAL" in texto_upper or "CERTIDAO DE REGULARIDADE FISCAL" in texto_upper:
        # Se não tiver tabelas de débito, é certidão
        tem_tabela_debitos = False
        for tabela in tabelas:
            if not tabela:
                continue
            # Verifica se tem colunas de débito/valor
            primeira_linha = " ".join([_limpa(cell).upper() for cell in tabela[0] if cell])
            if any(termo in primeira_linha for termo in ["DÉBITO", "DEBITO", "VALOR", "COMPETÊNCIA", "COMPETENCIA"]):
                tem_tabela_debitos = True
                break
        
        if not tem_tabela_debitos:
            return "certidao"
    
    # Se tem palavras-chave de listagem de débitos, é extrato
    if any(termo in texto_upper for termo in ["DÉBITOS", "DEBITOS", "VALOR", "COMPETÊNCIA", "COMPETENCIA", "LISTAGEM"]):
        return "extrato"
    
    # Default: assume extrato se tiver tabelas
    return "extrato" if tabelas else "certidao"


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


def _extrair_debitos_fiscais(texto: str) -> List[Dict[str, Any]]:
    """
    Extrai bloco DÉBITOS FISCAIS do texto do PDF.
    Retorna lista de dicts com processo, situacao, saldo.
    """
    debitos = []
    
    # Normaliza texto: colapsa espaços múltiplos, preserva quebras de linha
    texto_normalizado = normalize_text(texto)
    linhas = texto_normalizado.split('\n')
    
    # Encontra início do bloco DÉBITOS FISCAIS
    inicio_bloco = None
    for i, linha in enumerate(linhas):
        if re.search(r'DÉBITOS\s+FISCAIS|DEBITOS\s+FISCAIS', linha, re.IGNORECASE):
            inicio_bloco = i
            break
    
    if inicio_bloco is None:
        return debitos
    
    # Encontra fim do bloco (próxima seção ou fim)
    fim_bloco = len(linhas)
    marcadores_fim = ['FRONTEIRAS', 'FRONTEIRA', 'IPVA', 'CONCLUSÃO', 'OBSERVAÇÃO']
    for i in range(inicio_bloco + 1, len(linhas)):
        linha_upper = linhas[i].upper()
        if any(marcador in linha_upper for marcador in marcadores_fim):
            fim_bloco = i
            break
    
    # Extrai linhas do bloco
    linhas_bloco = linhas[inicio_bloco:fim_bloco]
    
    # Padrões regex para parsear linhas (mais flexível)
    # Exemplo: 2024.000010816644-80 ATIVO 36.491,20
    # Também aceita: 2024.000010816644-80 ATIVO 36.491,20 ou 2024000010816644-80 ATIVO 36.491,20
    padrao_linha = re.compile(
        r'(?P<processo>\d{4}[\.-]?\d{8,}-?\d{2,})'  # Processo: 2024.000010816644-80 ou variações
        r'\s+'
        r'(?P<situacao>[A-ZÁÉÍÓÚÇ\s]{2,20}?)'  # Situação: ATIVO, SUSPENSO, etc. (2-20 chars)
        r'\s+'
        r'(?P<saldo>[\d\.]+,\d{2})'  # Saldo: 36.491,20
    )
    
    for linha in linhas_bloco:
        linha_limpa = _limpa(linha)
        
        # Ignora cabeçalhos
        if any(termo in linha_limpa.upper() for termo in ['PROCESSO', 'SITUAÇÃO', 'SITUACAO', 'SALDO', 'VALOR']):
            continue
        
        # Tenta fazer match
        match = padrao_linha.search(linha_limpa)
        if match:
            processo = safe_str(match.group('processo')).strip()
            situacao = safe_str(match.group('situacao')).strip()
            saldo_str = safe_str(match.group('saldo')).strip()
            
            # Converte saldo pt-BR para float
            saldo = converter_valor_br_para_float(saldo_str) if saldo_str else 0.0
            
            if processo or saldo > 0:
                debitos.append({
                    "processo": processo,
                    "situacao": situacao,
                    "saldo": saldo
                })
    
    return debitos


def _extrair_fronteiras(texto: str) -> List[Dict[str, Any]]:
    """
    Extrai bloco FRONTEIRAS do texto do PDF.
    Retorna lista de dicts com dae, vencimento, valor_original.
    """
    fronteiras = []
    
    # Normaliza texto
    texto_normalizado = normalize_text(texto)
    linhas = texto_normalizado.split('\n')
    
    # Encontra início do bloco FRONTEIRAS
    inicio_bloco = None
    for i, linha in enumerate(linhas):
        if re.search(r'FRONTEIRAS|FRONTEIRA', linha, re.IGNORECASE):
            inicio_bloco = i
            break
    
    if inicio_bloco is None:
        return fronteiras
    
    # Encontra fim do bloco
    fim_bloco = len(linhas)
    marcadores_fim = ['DÉBITOS FISCAIS', 'DEBITOS FISCAIS', 'IPVA', 'CONCLUSÃO']
    for i in range(inicio_bloco + 1, len(linhas)):
        linha_upper = linhas[i].upper()
        if any(marcador in linha_upper for marcador in marcadores_fim):
            fim_bloco = i
            break
    
    # Extrai linhas do bloco
    linhas_bloco = linhas[inicio_bloco:fim_bloco]
    
    # Padrão regex para parsear linhas
    # Exemplo: 9693489 28/01/2025 899,93
    padrao_linha = re.compile(
        r'(?P<dae>\d{6,})'  # Num. DAE: 9693489
        r'\s+'
        r'(?P<vencimento>\d{2}/\d{2}/\d{4})'  # Data: 28/01/2025
        r'\s+'
        r'(?P<valor>[\d\.]+,\d{2})'  # Valor: 899,93
    )
    
    for linha in linhas_bloco:
        linha_limpa = _limpa(linha)
        
        # Ignora cabeçalhos
        if any(termo in linha_limpa.upper() for termo in ['NUM', 'DAE', 'DT', 'VENC', 'VALOR', 'ORIGINAL']):
            continue
        
        # Tenta fazer match
        match = padrao_linha.search(linha_limpa)
        if match:
            dae = safe_str(match.group('dae')).strip()
            vencimento = safe_str(match.group('vencimento')).strip()
            valor_str = safe_str(match.group('valor')).strip()
            
            # Converte valor pt-BR para float
            valor = converter_valor_br_para_float(valor_str) if valor_str else 0.0
            
            if dae or valor > 0:
                fronteiras.append({
                    "dae": dae,
                    "vencimento": vencimento,
                    "valor_original": valor
                })
    
    return fronteiras


# ==============================================================================
# PROCESSAMENTO ESPECÍFICO
# ==============================================================================

def processar_sefaz(texto: str, tabelas: List[List[List[str]]]) -> Dict[str, Any]:
    """
    Processa o texto e tabelas do PDF da SEFAZ.
    Retorna estrutura padronizada com situacao, motivos, detalhes.
    """
    resultado = {
        'tipo_documento': 'extrato',  # certidao ou extrato
        'situacao': 'INDETERMINADO',  # REGULAR, IRREGULAR, ou INDETERMINADO
        'motivos': [],
        'detalhes': {
            'ipva': [],
            'fronteira': {
                'tem_em_aberto': False,
                'itens': []
            },
            'debitos_fiscais': {
                'tem': False,
                'itens': []
            }
        },
        'observacao': None
    }
    
    # Normaliza texto para análise
    texto_normalizado = normalize_text(texto)
    texto_upper = texto_normalizado.upper()
    texto_lower = texto_normalizado.lower()
    
    # Identifica tipo de documento
    tipo_doc = _identificar_tipo_documento(texto, tabelas)
    resultado['tipo_documento'] = tipo_doc
    
    # DETECÇÃO ROBUSTA DE SITUAÇÃO
    # Prioridade: IRREGULARIDADES > REGULARIDADE > INDETERMINADO
    
    # Verifica IRREGULARIDADES primeiro
    termos_irregular = [
        'irregularidades', 'irregularidade', 'irregular',
        'débitos pendentes', 'debitos pendentes', 'débito pendente', 'debito pendente',
        'consta débito', 'consta debito', 'há débito', 'ha debito',
        'em atraso', 'atraso', 'pendências', 'pendencias'
    ]
    
    tem_irregular = any(termo in texto_lower for termo in termos_irregular)
    
    if tem_irregular:
        resultado['situacao'] = 'IRREGULAR'
        resultado['motivos'].append('Documento contém irregularidades ou débitos pendentes')
        logger.debug("SEFAZ: Situação detectada como IRREGULAR (termos encontrados)")
    else:
        # Verifica REGULARIDADE
        termos_regular = [
            'situação regular', 'situacao regular', 'regularidade',
            'nada consta', 'sem pendências', 'sem pendencias',
            'certidão negativa', 'certidao negativa'
        ]
        
        tem_regular = any(termo in texto_lower for termo in termos_regular)
        
        if tem_regular and tipo_doc == "certidao":
            resultado['situacao'] = 'REGULAR'
            resultado['motivos'].append('Certidão de regularidade fiscal emitida')
            resultado['observacao'] = "Documento é certidão; não contém detalhamento de IPVA/fronteira/débitos fiscais."
            logger.debug("SEFAZ: Situação detectada como REGULAR (certidão)")
            return resultado
        elif tem_regular:
            resultado['situacao'] = 'REGULAR'
            resultado['motivos'].append('Documento indica situação regular')
            logger.debug("SEFAZ: Situação detectada como REGULAR")
        else:
            # Não conseguiu detectar
            resultado['situacao'] = 'INDETERMINADO'
            resultado['motivos'].append('Texto não corresponde ao padrão esperado')
            logger.debug(f"SEFAZ: Situação INDETERMINADO (texto com {len(texto)} caracteres)")
    
    # IPVA - só extrai se houver evidência textual
    texto_normalizado = re.sub(r'\s+', ' ', texto)
    
    # Procura IPVA no texto
    if any(termo in texto.upper() for termo in ["IPVA", "ANO", "EXERCÍCIO", "EXERCICIO"]):
        padrao_ipva = r'IPVA.*?(?P<ano>\d{4}).*?R\$?\s*(?P<valor>[\d\.]+,\d{2})'
        matches_ipva = re.finditer(padrao_ipva, texto_normalizado, re.IGNORECASE)
        
        for match in matches_ipva:
            ano = match.group('ano')
            valor_str = match.group('valor')
            valor = converter_valor_br_para_float(valor_str) if valor_str else None
            
            if valor:
                resultado['detalhes']['ipva'].append({
                    "ano": int(ano) if ano.isdigit() else None,
                    "valor": valor,
                    "situacao": "EM ABERTO"  # Default, pode ser ajustado se houver informação
                })
    
    # EXTRAÇÃO ROBUSTA DE DÉBITOS FISCAIS E FRONTEIRAS (quando IRREGULAR)
    if resultado['situacao'] == 'IRREGULAR':
        # Extrai débitos fiscais do texto
        debitos_fiscais = _extrair_debitos_fiscais(texto)
        if debitos_fiscais:
            resultado['detalhes']['debitos_fiscais']['tem'] = True
            resultado['detalhes']['debitos_fiscais']['itens'] = debitos_fiscais
            logger.debug(f"SEFAZ: Extraídos {len(debitos_fiscais)} débitos fiscais do texto")
        
        # Extrai fronteiras do texto
        fronteiras = _extrair_fronteiras(texto)
        if fronteiras:
            resultado['detalhes']['fronteira']['tem_em_aberto'] = True
            resultado['detalhes']['fronteira']['itens'] = fronteiras
            logger.debug(f"SEFAZ: Extraídas {len(fronteiras)} fronteiras do texto")
    
    # Fallback: Fronteira - só se não for certidão e houver evidência (método antigo)
    if tipo_doc == "extrato" and not resultado['detalhes']['fronteira']['itens']:
        # Procura explicitamente por "FRONTEIRA"
        if "FRONTEIRA" in texto.upper() or "ICMS ANTECIPADO" in texto.upper():
            padrao_fronteira = r'(FRONTEIRA|ICMS\s+ANTECIPADO).*?(?P<competencia>\d{2}/\d{4}).*?R\$?\s*(?P<valor>[\d\.]+,\d{2})'
            matches_fronteira = re.finditer(texto_normalizado, re.IGNORECASE)
            
            for match in matches_fronteira:
                competencia = match.group('competencia')
                valor_str = match.group('valor')
                valor = converter_valor_br_para_float(valor_str) if valor_str else None
                
                if valor:
                    resultado['detalhes']['fronteira']['tem_em_aberto'] = True
                    resultado['detalhes']['fronteira']['itens'].append({
                        "competencia": competencia,
                        "valor": valor
                    })
    
    # Fallback: Débitos Fiscais de tabelas (se não extraiu do texto)
    if not resultado['detalhes']['debitos_fiscais']['itens']:
        tem_tabela_debitos = False
        for tabela in tabelas:
            if not tabela:
                continue
            
            primeira_linha = " ".join([_limpa(cell).upper() for cell in tabela[0] if cell])
            if any(termo in primeira_linha for termo in ["DÉBITO", "DEBITO", "VALOR", "COMPETÊNCIA", "COMPETENCIA"]):
                tem_tabela_debitos = True
                
                # Processa linhas da tabela
                for i, linha in enumerate(tabela):
                    if i == 0:
                        continue  # Pula cabeçalho
                    
                    linha_completa = " ".join([_limpa(cell) for cell in linha if cell])
                    
                    # Procura valores monetários
                    valor = None
                    for cell in linha:
                        if cell:
                            valor_cell = _extrair_valor_de_celula(cell)
                            if valor_cell > 0:
                                valor = valor_cell
                                break
                    
                    # Procura competência
                    match_comp = re.search(r'(\d{2}/\d{4})', linha_completa)
                    competencia = match_comp.group(1) if match_comp else None
                    
                    # Procura descrição
                    descricao = linha_completa[:100] if linha_completa else None
                    
                    if valor or competencia or descricao:
                        resultado['detalhes']['debitos_fiscais']['tem'] = True
                        resultado['detalhes']['debitos_fiscais']['itens'].append({
                            "processo": descricao or "",
                            "situacao": "",
                            "saldo": valor or 0.0
                        })
    
    # Se não encontrou débitos, aplica regra "não há débitos"
    if not resultado['detalhes']['ipva'] and not resultado['detalhes']['fronteira']['itens'] and not resultado['detalhes']['debitos_fiscais']['itens']:
        if not resultado['observacao']:
            resultado['observacao'] = "Não há débitos identificados no período analisado."
    
    return resultado


# ==============================================================================
# FUNÇÃO PRINCIPAL DO PARSER
# ==============================================================================

def interpretar_pdf_sefaz(
    caminho_pdf: Path | str, resultado: ResultadoParsers | None = None
) -> ResultadoParsers:
    """
    Lê o PDF da SEFAZ e preenche o objeto ResultadoParsers.
    """
    if resultado is None:
        resultado = ResultadoParsers()

    if not hasattr(resultado, 'sefaz_estadual') or not resultado.sefaz_estadual:
        resultado.sefaz_estadual = {
            "cabecalho_documento": {},
            "contribuinte": {},
            "pendencias_identificadas": {
                "ipva": [],
                "icms_fronteira_antecipado": [],
                "icms_competencias_aberto": [],
                "debitos_fiscais_autuacoes": [],
                "divida_ativa_estadual": []
            },
            "resumo_financeiro": {},
            "mensagens_sistema": {}
        }

    try:
        texto_completo = _extrair_texto_completo(caminho_pdf)
        tabelas = _extrair_tabelas_estruturadas(caminho_pdf)
        
        if not texto_completo and not tabelas:
            resultado.sefaz_estadual['mensagens_sistema']['erro'] = "Não foi possível extrair texto do PDF."
            return resultado

        # Metadados Gerais
        if not resultado.cnpj:
            resultado.cnpj = _extrair_cnpj(texto_completo)
        
        resultado.sefaz_estadual['contribuinte']['cnpj_cpf'] = resultado.cnpj
        
        # Datas
        padroes_data = [
            r"Data\s+de\s+Emiss[aã]o[:\s]+([\d/]+)",
            r"Data\s+da\s+Consulta[:\s]+([\d/]+)",
            r"Emitido\s+em[:\s]+([\d/]+)",
            r"Válida\s+até[:\s]+([\d/]+)"
        ]
        data_encontrada = _extrair_data(texto_completo, padroes_data)
        if not resultado.data_consulta_sefaz:
            resultado.data_consulta_sefaz = data_encontrada
        
        resultado.sefaz_estadual['cabecalho_documento']['data_emissao'] = data_encontrada

        # Validade específica
        match_validade = re.search(r'(Válida\s+até|Validade)[:\s]+([\d/]+)', texto_completo, re.IGNORECASE)
        if match_validade:
            resultado.sefaz_estadual['cabecalho_documento']['validade'] = match_validade.group(2)

        # Processa dados estruturados
        dados_processados = processar_sefaz(texto_completo, tabelas)
        
        # Situação padronizada (REGULAR/IRREGULAR/INDETERMINADO)
        situacao = dados_processados.get('situacao', 'INDETERMINADO')
        resultado.sefaz_estadual['cabecalho_documento']['situacao_geral'] = situacao
        resultado.sefaz_estadual['cabecalho_documento']['motivos'] = dados_processados.get('motivos', [])
        
        # IPVA
        pendencias = resultado.sefaz_estadual['pendencias_identificadas']
        detalhes = dados_processados.get('detalhes', {})
        for item in detalhes.get('ipva', []):
            pendencias['ipva'].append({
                "exercicio": str(item['ano']) if item.get('ano') else "",
                "placa": "",
                "renavam": "",
                "valor_original": 0.0,
                "valor_total": item.get('valor', 0.0),
                "status": item.get('situacao', 'DESCONHECIDA')
            })
        
        # Fronteira
        if detalhes.get('fronteira', {}).get('itens'):
            for item in detalhes['fronteira']['itens']:
                pendencias['icms_fronteira_antecipado'].append({
                    "periodo_referencia": item.get('competencia'),
                    "codigo_receita": "",
                    "descricao": "ICMS Antecipado/Fronteira",
                    "data_vencimento": "",
                    "valor_total": item.get('valor', 0.0)
                })
        
        # Débitos Fiscais (estrutura padronizada)
        if detalhes.get('debitos_fiscais', {}).get('itens'):
            for item in detalhes['debitos_fiscais']['itens']:
                pendencias['debitos_fiscais_autuacoes'].append({
                    "numero_processo": safe_str(item.get('processo', '')),
                    "natureza_debito": safe_str(item.get('situacao', 'DÉBITO FISCAL')),
                    "periodo": "",
                    "fase_processual": "Cobrança Administrativa",
                    "valor_consolidado": float(item.get('saldo', 0.0))
                })
        
        # Armazena dados processados para acesso no app.py e PDF
        resultado.sefaz_estadual['dados_processados'] = dados_processados
        
        # Cálculo de Totais
        resumo = resultado.sefaz_estadual['resumo_financeiro']
        
        resumo['total_ipva'] = sum(d.get('valor_total', 0.0) for d in pendencias['ipva'])
        resumo['total_icms_fronteira'] = sum(d.get('valor_total', 0.0) for d in pendencias['icms_fronteira_antecipado'])
        resumo['total_icms_normal'] = sum(d.get('valor_estimado', 0.0) for d in pendencias['icms_competencias_aberto'])
        resumo['total_divida_ativa'] = sum(d.get('valor_consolidado', 0.0) for d in pendencias['debitos_fiscais_autuacoes'])
        
        resumo['total_geral_consolidado'] = (
            resumo['total_ipva'] + 
            resumo['total_icms_fronteira'] + 
            resumo['total_icms_normal'] + 
            resumo['total_divida_ativa']
        )
        
        # Observação
        if dados_processados.get('observacao'):
            resultado.sefaz_estadual['mensagens_sistema']['observacao'] = dados_processados['observacao']
        
        # Armazena tipo de documento para uso na consolidação
        resultado.sefaz_estadual['tipo_documento'] = dados_processados.get('tipo_documento', 'extrato')

    except Exception as e:
        if hasattr(resultado, 'sefaz_estadual'):
            resultado.sefaz_estadual['mensagens_sistema']['erro_parser'] = str(e)
        return resultado

    return resultado
