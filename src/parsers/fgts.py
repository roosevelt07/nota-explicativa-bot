# src/parsers/fgts.py
"""
Parser robusto para PDFs do FGTS (Fundo de Garantia do Tempo de Serviço).

Implementa:
- Detecção de regular vs irregular
- Extração de competências pendentes (quando irregular)
- Tratamento de null + observações quando não há dados
"""

from __future__ import annotations

import re
import datetime
from pathlib import Path
from typing import Optional, Union, Dict, Any, List

import pdfplumber

from .base import ResultadoParsers
from src.utils import converter_valor_br_para_float


# ==============================================================================
# HELPERS BÁSICOS
# ==============================================================================

def _limpa(txt: str | None) -> str:
    """Remove espaços extras, quebras de linha e normaliza texto."""
    if not txt:
        return ""
    return " ".join(str(txt).replace('\n', ' ').split())


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


def _extrair_cnpj(texto: str) -> Optional[str]:
    """Busca o primeiro CNPJ válido no texto."""
    match = re.search(r'\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b', texto)
    if match:
        return match.group(1)
    return None


def _extrair_data(texto: str, padroes: list[str]) -> Optional[str]:
    """Tenta extrair uma data usando múltiplos padrões regex."""
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


# ==============================================================================
# PROCESSAMENTO FGTS
# ==============================================================================

def processar_fgts(texto: str) -> Dict[str, Any]:
    """
    Processa o texto do PDF do FGTS e extrai dados conforme especificação.
    Retorna estrutura conforme schema unificado.
    """
    resultado = {
        'situacao': None,
        'debitos': [],
        'observacao': None
    }
    
    texto_lower = texto.lower()
    
    # Verifica se é regular
    if "certificado de regularidade do fgts" in texto_lower or "crf" in texto_lower:
        if "encontra-se em situação regular" in texto_lower or "situação regular" in texto_lower:
            resultado['situacao'] = "REGULAR"
            resultado['debitos'] = []
            resultado['observacao'] = None
            return resultado
    
    # Se não for regular, tenta extrair débitos
    resultado['situacao'] = "IRREGULAR"
    
    # Procura competências pendentes
    padrao_competencia = r'(\d{2}/\d{4}|\d{4})'
    
    # Procura contexto de pendências
    secao_pendencias = ""
    match_secao = re.search(
        r'(pend[êe]ncias?|em\s+atraso|não\s+recolhido|débitos?|debitos?).*?(?=Validade|Certificação|$)',
        texto,
        re.IGNORECASE | re.DOTALL
    )
    if match_secao:
        secao_pendencias = match_secao.group(0)
    
    # Se não encontrou seção específica, busca no texto todo
    texto_busca = secao_pendencias if secao_pendencias else texto
    
    # Extrai competências
    matches_competencia = re.finditer(padrao_competencia, texto_busca)
    
    competencias_encontradas = set()
    for match in matches_competencia:
        competencia = match.group(1)
        # Valida se parece com competência
        if re.match(r'\d{2}/\d{4}', competencia) or (len(competencia) == 4 and competencia.isdigit()):
            competencias_encontradas.add(competencia)
    
    # Processa competências encontradas
    for comp in competencias_encontradas:
        comp_normalizada = _normalizar_competencia(comp)
        if comp_normalizada:
            resultado['debitos'].append({
                "competencia": comp_normalizada,
                "valor": None,  # FGTS geralmente não informa valor por competência
                "situacao": "EM ABERTO"
            })
    
    # Se não encontrou débitos, aplica regra "não há débitos"
    if not resultado['debitos']:
        resultado['observacao'] = "Não há débitos identificados no período analisado."
    
    return resultado


# ==============================================================================
# FUNÇÃO PRINCIPAL DO PARSER
# ==============================================================================

def interpretar_pdf_fgts(
    caminho_pdf: Path | str, resultado: ResultadoParsers | None = None
) -> ResultadoParsers:
    """
    Processa o PDF do FGTS, popula o novo schema 'fgts' e mantém campos legados.
    """
    if resultado is None:
        resultado = ResultadoParsers()

    # Inicializa a estrutura do schema NOVO se não existir
    if not hasattr(resultado, 'fgts') or not resultado.fgts:
        resultado.fgts = {
            "metadados": {
                "tipo_documento": "CRF - Certificado de Regularidade do FGTS",
                "data_processamento": datetime.datetime.now().strftime("%d/%m/%Y"),
                "arquivo_origem": str(caminho_pdf)
            },
            "empregador": {
                "identificacao": "",
                "tipo_identificacao": "CNPJ",
                "razao_social": "",
                "endereco_completo": ""
            },
            "crf_detalhes": {
                "numero_certificacao": "",
                "data_emissao": "",
                "validade_inicio": "",
                "validade_fim": "",
                "uf_emissao": "",
                "situacao_atual": None
            },
            "pendencias_financeiras": {
                "possui_debitos": False,
                "resumo": {"qtd_competencias": 0, "valor_total_estimado": 0.0},
                "lista_debitos": []
            },
            "mensagens_sistema": {}
        }

    try:
        texto_completo = _extrair_texto_completo(caminho_pdf)
        if not texto_completo:
            resultado.fgts['mensagens_sistema']['erro'] = "PDF sem texto extraível."
            return resultado

        # Processa dados estruturados
        dados_processados = processar_fgts(texto_completo)
        
        # Extrai metadados básicos
        cnpj = _extrair_cnpj(texto_completo)
        if cnpj:
            resultado.fgts['empregador']['identificacao'] = cnpj
            if not resultado.cnpj:
                resultado.cnpj = cnpj

        # Razão Social
        match_razao = re.search(
            r"Raz[ãa]o\s+Social[:\s]+(?P<nome>.+?)(?=Endereço|Inscriç[ãa]o|CNPJ)",
            texto_completo,
            re.IGNORECASE | re.DOTALL
        )
        if match_razao:
            razao_social = _limpa(match_razao.group('nome'))
            resultado.fgts['empregador']['razao_social'] = razao_social
            if not resultado.requerente:
                resultado.requerente = razao_social

        # Endereço
        match_endereco = re.search(
            r"(Endereço[:\s]+|LOT\s+|RUA\s+|AV\.\s+)(?P<end>.+?)(?=A\s+Caixa|O\s+presente|Validade)",
            texto_completo,
            re.IGNORECASE | re.DOTALL
        )
        if match_endereco:
            endereco = match_endereco.group('end')
            endereco = re.sub(r'Endereço[:\s]+', '', endereco, flags=re.IGNORECASE)
            resultado.fgts['empregador']['endereco_completo'] = _limpa(endereco)

        # Validade
        match_validade = re.search(
            r"Validade[:\s]+(?P<inicio>\d{2}/\d{2}/\d{4})\s+a\s+(?P<fim>\d{2}/\d{2}/\d{4})",
            texto_completo,
            re.IGNORECASE
        )
        if match_validade:
            resultado.fgts['crf_detalhes']['validade_inicio'] = match_validade.group('inicio')
            resultado.fgts['crf_detalhes']['validade_fim'] = match_validade.group('fim')
        else:
            # Tenta padrão "válida até"
            match_validade = re.search(
                r'válida\s+até[:\s]+(\d{2}/\d{2}/\d{4})',
                texto_completo,
                re.IGNORECASE
            )
            if match_validade:
                resultado.fgts['crf_detalhes']['validade_fim'] = match_validade.group(1)

        # Número da Certificação
        match_cert = re.search(r"Certificaç[ãa]o\s+N[úu]mero[:\s]+(\d+)", texto_completo, re.IGNORECASE)
        if match_cert:
            resultado.fgts['crf_detalhes']['numero_certificacao'] = match_cert.group(1)

        # Data da Consulta
        match_data = re.search(r"Informação\s+obtida\s+em\s+(?P<data>\d{2}/\d{2}/\d{4})", texto_completo, re.IGNORECASE)
        if match_data:
            data_consulta = match_data.group('data')
            resultado.fgts['crf_detalhes']['data_emissao'] = data_consulta
            if not resultado.data_consulta_fgts:
                resultado.data_consulta_fgts = data_consulta

        # Situação
        resultado.fgts['crf_detalhes']['situacao_atual'] = dados_processados['situacao']
        
        if dados_processados['situacao'] == "REGULAR":
            resultado.fgts['pendencias_financeiras']['possui_debitos'] = False
            resultado.fgts['pendencias_financeiras']['lista_debitos'] = []
        else:
            resultado.fgts['pendencias_financeiras']['possui_debitos'] = len(dados_processados['debitos']) > 0
            resultado.fgts['pendencias_financeiras']['resumo']['qtd_competencias'] = len(dados_processados['debitos'])
            
            # Lista competências pendentes
            for debito in dados_processados['debitos']:
                resultado.fgts['pendencias_financeiras']['lista_debitos'].append({
                    'competencia': debito.get('competencia'),
                    'valor_estimado': debito.get('valor'),
                    'descricao': 'Competência pendente'
                })

        # UF do endereço
        if resultado.fgts['empregador']['endereco_completo']:
            match_uf = re.search(r'/\s*([A-Z]{2})\s*/', resultado.fgts['empregador']['endereco_completo'])
            if match_uf:
                resultado.fgts['crf_detalhes']['uf_emissao'] = match_uf.group(1)

        # Observação
        if dados_processados.get('observacao'):
            resultado.fgts['mensagens_sistema']['observacao'] = dados_processados['observacao']

        # Gera bloco de texto legado
        partes_texto = []
        if dados_processados['situacao'] == "REGULAR":
            partes_texto.append(
                "De acordo com o Certificado de Regularidade do FGTS, a empresa "
                "encontra-se em situação regular perante o Fundo de Garantia do Tempo de Serviço."
            )
            if resultado.fgts['crf_detalhes'].get('validade_fim'):
                partes_texto.append(f"Validade: {resultado.fgts['crf_detalhes']['validade_fim']}.")
        else:
            partes_texto.append(
                "Foram identificadas pendências junto ao FGTS. "
                f"Situação atual: Irregular. Competências pendentes: {len(dados_processados['debitos'])}."
            )
            if dados_processados['debitos']:
                comps = [d.get('competencia', '') for d in dados_processados['debitos'][:5]]
                partes_texto.append(
                    f"Competências: {', '.join(comps)}"
                    + ("..." if len(dados_processados['debitos']) > 5 else "")
                )
        
        if resultado.fgts['crf_detalhes'].get('numero_certificacao'):
            partes_texto.append(f"Certificação: {resultado.fgts['crf_detalhes']['numero_certificacao']}.")

        resultado.bloco_fgts = " ".join(partes_texto)

    except Exception as e:
        erro_msg = f"Erro ao processar FGTS: {str(e)}"
        if hasattr(resultado, 'fgts'):
            resultado.fgts['mensagens_sistema']['erro_parser'] = erro_msg
        resultado.bloco_fgts = erro_msg
    
    return resultado
