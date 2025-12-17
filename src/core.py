# src/core.py
"""
Core do sistema: Classificação de documentos, pipeline de processamento e schema unificado.

Responsabilidades:
- Classificar documentos por tipo (Receita Federal, SEFAZ, FGTS)
- Orquestrar pipeline de extração e parsing
- Consolidar resultados em schema unificado
- Gerar relatório JSON final
"""

from __future__ import annotations

import re
import json
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

import pdfplumber

from src.parsers.base import ResultadoParsers
from src.parsers.receita_federal import interpretar_pdf_receita
from src.parsers.sefaz import interpretar_pdf_sefaz
from src.parsers.fgts import interpretar_pdf_fgts
from src.utils import converter_valor_br_para_float


# ==============================================================================
# CLASSIFICADOR DE DOCUMENTOS
# ==============================================================================

class DocumentClassifier:
    """
    Classificador baseado em palavras-chave (sem ML) que identifica o tipo de documento.
    """
    
    # Palavras-chave para cada tipo de documento
    KEYWORDS_RECEITA = [
        "receita federal",
        "e-cac",
        "integra contador",
        "situação fiscal",
        "sief",
        "cp-patronal",
        "cp-terceiros",
        "cp-segur",
        "pgfn",
        "procuradoria-geral da fazenda nacional"
    ]
    
    KEYWORDS_FGTS = [
        "certificado de regularidade do fgts",
        "crf",
        "fundo de garantia",
        "fgts",
        "caixa econômica federal"
    ]
    
    KEYWORDS_SEFAZ = [
        "certidão de regularidade fiscal",
        "sefaz",
        "secretaria da fazenda",
        "ipva",
        "icms",
        "fronteira"
    ]
    
    @staticmethod
    def classify(texto: str, debug_lines: int = 80) -> Dict[str, Any]:
        """
        Classifica o documento baseado em palavras-chave.
        
        Retorna:
        {
            "doc_type": "receita_federal" | "fgts" | "sefaz" | "desconhecido",
            "confidence_reason": "palavra-chave que bateu",
            "debug_text_head": "primeiras N linhas" (se desconhecido)
        }
        """
        texto_lower = texto.lower()
        linhas = texto.split('\n')[:debug_lines]
        debug_head = '\n'.join(linhas)
        
        # Receita Federal
        for keyword in DocumentClassifier.KEYWORDS_RECEITA:
            if keyword in texto_lower:
                return {
                    "doc_type": "receita_federal",
                    "confidence_reason": f"Palavra-chave encontrada: '{keyword}'",
                    "debug_text_head": None
                }
        
        # FGTS
        for keyword in DocumentClassifier.KEYWORDS_FGTS:
            if keyword in texto_lower:
                return {
                    "doc_type": "fgts",
                    "confidence_reason": f"Palavra-chave encontrada: '{keyword}'",
                    "debug_text_head": None
                }
        
        # SEFAZ
        for keyword in DocumentClassifier.KEYWORDS_SEFAZ:
            if keyword in texto_lower:
                return {
                    "doc_type": "sefaz",
                    "confidence_reason": f"Palavra-chave encontrada: '{keyword}'",
                    "debug_text_head": None
                }
        
        # Desconhecido
        return {
            "doc_type": "desconhecido",
            "confidence_reason": "Nenhuma palavra-chave conhecida encontrada",
            "debug_text_head": debug_head
        }


# ==============================================================================
# SCHEMA UNIFICADO
# ==============================================================================

def criar_schema_vazio() -> Dict[str, Any]:
    """
    Cria o schema unificado vazio do relatório.
    """
    return {
        "periodo": {
            "inicio": None,
            "fim": None
        },
        "receita_federal": {
            "contribuicoes": {
                "seguro_total": 0.0,
                "patronal_total": 0.0,
                "terceiros_total": 0.0,
                "total_geral": 0.0,
                "detalhes": []
            },
            "simples": {
                "tem_debito_em_aberto": False,
                "debitos": [],
                "tem_parcelamento": False,
                "parcelamento": {
                    "tipo": None,
                    "parcelas_em_atraso": None
                },
                "observacao": None
            },
            "tributos": {
                "irrf": [],
                "irls": [],
                "pis": [],
                "cofins": []
            },
            "pgfn_previdencia": {
                "existe": False,
                "receitas": [],
                "origem_secao": None,
                "informacoes_adicionais_usuario": ""
            },
            "previdencia": {
                "existe": False,
                "total_previdencia": None,
                "fonte": "Receita Federal"
            }
        },
        "pgfn": {
            "tem_debito": False,
            "inscricoes": [],
            "sispar": {
                "tem": False,
                "itens": [],
                "observacao": None
            },
            "parcelamento_unificado": {
                "tem": False,
                "situacao": None,
                "observacao": None
            }
        },
        "sefaz": {
            "situacao": None,
            "ipva": [],
            "fronteira": {
                "tem_em_aberto": False,
                "itens": []
            },
            "debitos_fiscais": {
                "tem": False,
                "itens": []
            },
            "observacao": None
        },
        "fgts": {
            "situacao": None,
            "debitos": [],
            "observacao": None
        },
        "resumo": {
            "previdencia_total": 0.0,
            "previdencia_itens": []
        },
        "observacoes_gerais": []
    }


# ==============================================================================
# PIPELINE DE PROCESSAMENTO
# ==============================================================================

def extrair_texto_pdf(caminho_pdf: Path | str) -> str:
    """
    Extrai texto completo do PDF.
    """
    caminho_pdf = Path(caminho_pdf)
    texto_completo = ""
    
    try:
        with pdfplumber.open(str(caminho_pdf)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if txt:
                    texto_completo += txt + "\n"
    except Exception as e:
        raise Exception(f"Erro ao extrair texto do PDF: {str(e)}")
    
    return texto_completo.strip()


def processar_documento(caminho_pdf: Path | str) -> Dict[str, Any]:
    """
    Pipeline completo de processamento de um documento:
    1. Extrair texto
    2. Classificar documento
    3. Chamar parser específico
    4. Retornar resultado com metadados
    """
    caminho_pdf = Path(caminho_pdf)
    
    # 1. Extrair texto
    texto = extrair_texto_pdf(caminho_pdf)
    
    if not texto:
        return {
            "doc_type": "desconhecido",
            "parser_used": None,
            "confidence_reason": "PDF sem texto extraível",
            "debug_text_head": None,
            "erro": "Não foi possível extrair texto do PDF"
        }
    
    # 2. Classificar
    classificacao = DocumentClassifier.classify(texto)
    doc_type = classificacao["doc_type"]
    
    # 3. Chamar parser específico
    resultado_parser = None
    parser_used = None
    
    try:
        if doc_type == "receita_federal":
            parser_used = "interpretar_pdf_receita"
            resultado_parser = interpretar_pdf_receita(caminho_pdf)
        elif doc_type == "fgts":
            parser_used = "interpretar_pdf_fgts"
            resultado_parser = interpretar_pdf_fgts(caminho_pdf)
        elif doc_type == "sefaz":
            parser_used = "interpretar_pdf_sefaz"
            resultado_parser = interpretar_pdf_sefaz(caminho_pdf)
        else:
            # Documento desconhecido - não chama parser
            return {
                "doc_type": doc_type,
                "parser_used": None,
                "confidence_reason": classificacao["confidence_reason"],
                "debug_text_head": classificacao["debug_text_head"],
                "erro": "Tipo de documento não suportado"
            }
    except Exception as e:
        return {
            "doc_type": doc_type,
            "parser_used": parser_used,
            "confidence_reason": classificacao["confidence_reason"],
            "debug_text_head": classificacao.get("debug_text_head"),
            "erro": f"Erro no parser: {str(e)}"
        }
    
    # 4. Retornar resultado
    return {
        "doc_type": doc_type,
        "parser_used": parser_used,
        "confidence_reason": classificacao["confidence_reason"],
        "debug_text_head": None,
        "resultado": resultado_parser
    }


# ==============================================================================
# CONSOLIDAÇÃO E GERAÇÃO DE RELATÓRIO
# ==============================================================================

def extrair_competencias_de_lista(itens: List[Dict[str, Any]]) -> List[str]:
    """
    Extrai todas as competências de uma lista de itens.
    Retorna lista de strings no formato "AAAA-MM" ou "MM/AAAA".
    """
    competencias = []
    
    for item in itens:
        competencia = item.get("competencia") or item.get("periodo") or item.get("ano")
        if competencia:
            competencias.append(str(competencia))
    
    return competencias


def normalizar_competencia(comp: str) -> Optional[str]:
    """
    Normaliza competência para formato "AAAA-MM".
    Aceita: "MM/AAAA", "AAAA-MM", "AAAA", "MM-AAAA"
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
        return f"{match.group(1)}-01"  # Assume janeiro se só ano
    
    return None


def determinar_periodo(resultados: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    """
    Determina período início/fim a partir das competências encontradas.
    """
    todas_competencias = []
    
    for resultado in resultados:
        if "erro" in resultado or not resultado.get("resultado"):
            continue
        
        res = resultado["resultado"]
        
        # Receita Federal
        if hasattr(res, 'receita_federal') and res.receita_federal:
            rf = res.receita_federal
            
            # Contribuições
            if rf.get('contribuicoes', {}).get('detalhes'):
                todas_competencias.extend(extrair_competencias_de_lista(rf['contribuicoes']['detalhes']))
            
            # Simples
            if rf.get('simples', {}).get('debitos'):
                todas_competencias.extend(extrair_competencias_de_lista(rf['simples']['debitos']))
            
            # Tributos
            for tributo in ['irrf', 'irls', 'pis', 'cofins']:
                if rf.get('tributos', {}).get(tributo):
                    todas_competencias.extend(extrair_competencias_de_lista(rf['tributos'][tributo]))
        
        # SEFAZ
        if hasattr(res, 'sefaz_estadual') and res.sefaz_estadual:
            sefaz = res.sefaz_estadual
            pendencias = sefaz.get('pendencias_identificadas', {})
            
            # IPVA (ano)
            for ipva in pendencias.get('ipva', []):
                if ipva.get('exercicio'):
                    todas_competencias.append(f"{ipva['exercicio']}-01")
            
            # Fronteira
            for item in pendencias.get('icms_fronteira_antecipado', []):
                if item.get('periodo_referencia'):
                    todas_competencias.append(item['periodo_referencia'])
            
            # Débitos fiscais
            for item in pendencias.get('debitos_fiscais_autuacoes', []):
                if item.get('periodo'):
                    todas_competencias.append(item['periodo'])
        
        # FGTS
        if hasattr(res, 'fgts') and res.fgts:
            fgts = res.fgts
            for debito in fgts.get('pendencias_financeiras', {}).get('lista_debitos', []):
                if debito.get('competencia'):
                    todas_competencias.append(debito['competencia'])
    
    # Normaliza e ordena
    competencias_normalizadas = []
    for comp in todas_competencias:
        comp_norm = normalizar_competencia(comp)
        if comp_norm:
            competencias_normalizadas.append(comp_norm)
    
    if not competencias_normalizadas:
        return {"inicio": None, "fim": None}
    
    competencias_normalizadas.sort()
    
    return {
        "inicio": competencias_normalizadas[0],
        "fim": competencias_normalizadas[-1]
    }


def consolidar_previdencia(resultados: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Consolida todos os itens previdenciários de diferentes documentos.
    Identifica tipo="previdenciaria" de Receita/PGFN/SISPAR.
    """
    previdencia_total = 0.0
    previdencia_itens = []
    
    for resultado in resultados:
        if "erro" in resultado or not resultado.get("resultado"):
            continue
        
        res = resultado["resultado"]
        doc_type = resultado.get("doc_type", "desconhecido")
        
        # Receita Federal - Contribuições Patronal e Seguro
        if hasattr(res, 'receita_federal') and res.receita_federal:
            rf = res.receita_federal
            contribuicoes = rf.get('contribuicoes', {})
            
            # Patronal (é previdenciário)
            for item in contribuicoes.get('detalhes', []):
                if item.get('categoria') == 'patronal':
                    valor = item.get('valor') or 0.0
                    if valor:
                        previdencia_total += valor
                    previdencia_itens.append({
                        "fonte": "receita_federal",
                        "tipo": "previdenciaria",
                        "subtipo": "patronal",
                        "competencia": item.get('competencia'),
                        "valor": valor,
                        "codigo": item.get('codigo')
                    })
            
            # Seguro (é previdenciário)
            for item in contribuicoes.get('detalhes', []):
                if item.get('categoria') == 'seguro':
                    valor = item.get('valor') or 0.0
                    if valor:
                        previdencia_total += valor
                    previdencia_itens.append({
                        "fonte": "receita_federal",
                        "tipo": "previdenciaria",
                        "subtipo": "seguro",
                        "competencia": item.get('competencia'),
                        "valor": valor,
                        "codigo": item.get('codigo')
                    })
            
            # PGFN - Inscrições previdenciárias
            pgfn = rf.get('pgfn', {})
            for inscricao in pgfn.get('previdenciario', []):
                previdencia_itens.append({
                    "fonte": "pgfn",
                    "tipo": "previdenciaria",
                    "inscricao": inscricao.get('inscricao'),
                    "situacao": inscricao.get('situacao'),
                    "valor": None  # PGFN geralmente não traz valor
                })
            
            # SISPAR
            sispar = rf.get('sispar', {})
            if sispar.get('tem_sispar'):
                for parc in sispar.get('parcelamentos', []):
                    # Só adiciona à previdência se for regime previdenciário e tiver valor
                    if parc.get('regime') == 'PREVIDENCIARIO':
                        valor_total = parc.get('valor_total_parcelado')
                        if valor_total:
                            try:
                                # Converte string "R$ 1.234,56" para float
                                valor_float = converter_valor_br_para_float(valor_total) if isinstance(valor_total, str) else float(valor_total or 0)
                                if valor_float > 0:
                                    previdencia_total += valor_float
                            except (ValueError, TypeError):
                                pass
                        previdencia_itens.append({
                            "fonte": "sispar",
                            "tipo": "previdenciaria",
                            "conta": parc.get('conta'),
                            "regime": parc.get('regime'),
                            "valor": valor_total
                        })
    
    return {
        "previdencia_total": previdencia_total,
        "previdencia_itens": previdencia_itens
    }


def gerar_relatorio_consolidado(caminhos_pdf: List[Path | str]) -> Dict[str, Any]:
    """
    Processa múltiplos PDFs e gera relatório consolidado no schema unificado.
    """
    # Inicializa schema vazio
    relatorio = criar_schema_vazio()
    
    # Processa cada documento
    resultados = []
    texto_completo_global = ""  # Para Parcelamento Unificado
    
    for caminho in caminhos_pdf:
        resultado = processar_documento(caminho)
        resultados.append(resultado)
        
        # Acumula texto para análise de Parcelamento Unificado
        if not resultado.get("erro"):
            try:
                texto_completo_global += extrair_texto_pdf(caminho) + "\n"
            except:
                pass
    
    # Determina período
    relatorio["periodo"] = determinar_periodo(resultados)
    
    # Consolida cada tipo de documento
    for resultado in resultados:
        if "erro" in resultado or not resultado.get("resultado"):
            relatorio["observacoes_gerais"].append(
                f"Documento {resultado.get('doc_type', 'desconhecido')}: {resultado.get('erro', 'Erro desconhecido')}"
            )
            continue
        
        res = resultado["resultado"]
        doc_type = resultado["doc_type"]
        
        # Receita Federal
        if doc_type == "receita_federal" and hasattr(res, 'receita_federal') and res.receita_federal:
            rf_data = res.receita_federal
            
            # Contribuições
            if rf_data.get('contribuicoes'):
                contrib = rf_data['contribuicoes']
                detalhes = contrib.get('detalhes', [])
                
                # Filtra detalhes por período se período estiver definido
                periodo = relatorio.get('periodo', {})
                if periodo.get('inicio') and periodo.get('fim'):
                    detalhes_filtrados = []
                    for item in detalhes:
                        comp = item.get('competencia')
                        if comp:
                            comp_norm = normalizar_competencia(comp)
                            if comp_norm and periodo['inicio'] <= comp_norm <= periodo['fim']:
                                detalhes_filtrados.append(item)
                        else:
                            # Se não tem competência, inclui mesmo assim
                            detalhes_filtrados.append(item)
                    detalhes = detalhes_filtrados
                    
                    # Recalcula totais após filtro
                    seguro_total = sum(item.get('valor', 0.0) or 0.0 for item in detalhes if item.get('categoria') == 'seguro')
                    patronal_total = sum(item.get('valor', 0.0) or 0.0 for item in detalhes if item.get('categoria') == 'patronal')
                    terceiros_total = sum(item.get('valor', 0.0) or 0.0 for item in detalhes if item.get('categoria') == 'terceiros')
                    
                    relatorio["receita_federal"]["contribuicoes"] = {
                        "seguro_total": seguro_total,
                        "patronal_total": patronal_total,
                        "terceiros_total": terceiros_total,
                        "total_geral": seguro_total + patronal_total + terceiros_total,
                        "detalhes": detalhes
                    }
                else:
                    relatorio["receita_federal"]["contribuicoes"] = {
                        "seguro_total": contrib.get('seguro_total', 0.0),
                        "patronal_total": contrib.get('patronal_total', 0.0),
                        "terceiros_total": contrib.get('terceiros_total', 0.0),
                        "total_geral": contrib.get('total_geral', 0.0),
                        "detalhes": detalhes
                    }
            
            # Simples
            if rf_data.get('simples_nacional'):
                simples = rf_data['simples_nacional']
                debitos = simples.get('debitos', [])
                
                # Filtra débitos por período se período estiver definido
                periodo = relatorio.get('periodo', {})
                if periodo.get('inicio') and periodo.get('fim'):
                    debitos_filtrados = []
                    for debito in debitos:
                        comp = debito.get('competencia')
                        if comp:
                            comp_norm = normalizar_competencia(comp)
                            if comp_norm and periodo['inicio'] <= comp_norm <= periodo['fim']:
                                debitos_filtrados.append(debito)
                        else:
                            # Se não tem competência, inclui mesmo assim
                            debitos_filtrados.append(debito)
                    debitos = debitos_filtrados
                
                relatorio["receita_federal"]["simples"] = {
                    "tem_debito_em_aberto": len(debitos) > 0 or simples.get('tem_pendencias', False),
                    "debitos": debitos,
                    "tem_parcelamento": simples.get('parcelamento', {}).get('tem_parcelamento', False),
                    "parcelamento": {
                        "tipo": simples.get('parcelamento', {}).get('tipo'),
                        "parcelas_em_atraso": simples.get('parcelamento', {}).get('parcelas_atraso')
                    },
                    "observacao": None
                }
            
            # Tributos
            if rf_data.get('debitos_gerais'):
                debitos = rf_data['debitos_gerais']
                
                # Filtra tributos por período
                periodo = relatorio.get('periodo', {})
                tributos_filtrados = {}
                
                for tributo_nome in ['IRRF', 'IRLS', 'PIS', 'COFINS']:
                    itens = debitos.get(tributo_nome, [])
                    if periodo.get('inicio') and periodo.get('fim'):
                        itens_filtrados = []
                        for item in itens:
                            comp = item.get('competencia')
                            if comp:
                                comp_norm = normalizar_competencia(comp)
                                if comp_norm and periodo['inicio'] <= comp_norm <= periodo['fim']:
                                    itens_filtrados.append(item)
                            else:
                                itens_filtrados.append(item)
                        tributos_filtrados[tributo_nome.lower()] = itens_filtrados
                    else:
                        tributos_filtrados[tributo_nome.lower()] = itens
                
                relatorio["receita_federal"]["tributos"] = tributos_filtrados
            
            # PGFN
            if rf_data.get('pgfn'):
                pgfn = rf_data['pgfn']
                inscricoes = []
                
                # Processa inscrições previdenciárias
                for insc in pgfn.get('previdenciario', []):
                    inscricoes.append({
                        "inscricao": insc.get('inscricao'),
                        "situacao": insc.get('situacao'),
                        "tipo": "previdenciaria"
                    })
                
                # Processa inscrições Simples Nacional
                for insc in pgfn.get('simples_nacional', []):
                    inscricoes.append({
                        "inscricao": insc.get('inscricao'),
                        "situacao": insc.get('situacao'),
                        "tipo": "simples_nacional"
                    })
                
                # SISPAR - Nova estrutura com parcelamentos
                sispar = rf_data.get('sispar', {})
                sispar_parcelamentos = []
                
                if sispar.get('tem_sispar'):
                    for parc in sispar.get('parcelamentos', []):
                        # Copia todos os campos do parcelamento
                        sispar_parcelamentos.append({
                            "conta": parc.get('conta'),
                            "tipo": parc.get('tipo'),
                            "modalidade": parc.get('modalidade'),
                            "regime": parc.get('regime'),
                            "limite_maximo_meses": parc.get('limite_maximo_meses'),
                            "negociado_no_sispar": parc.get('negociado_no_sispar'),
                            "exigibilidade_suspensa": parc.get('exigibilidade_suspensa'),
                            "quantidade_parcelas": parc.get('quantidade_parcelas'),
                            "valor_total_parcelado": parc.get('valor_total_parcelado'),
                            "valor_parcela": parc.get('valor_parcela'),
                            "competencias": parc.get('competencias', []),
                            "necessita_consulta_manual_pgfn": parc.get('necessita_consulta_manual_pgfn', True),
                            "observacao": parc.get('observacao'),
                            "conferido_pelo_usuario": parc.get('conferido_pelo_usuario', False)
                        })
                
                # Parcelamento Unificado
                parcelamento_unificado = {
                    "tem": False,
                    "situacao": None,
                    "observacao": None
                }
                
                # Detecta Parcelamento Unificado no texto global
                if "PARCELAMENTO UNIFICADO" in texto_completo_global.upper():
                    parcelamento_unificado["tem"] = True
                    
                    # Extrai situação
                    if "REGULAR" in texto_completo_global.upper():
                        parcelamento_unificado["situacao"] = "REGULAR"
                    elif "IRREGULAR" in texto_completo_global.upper():
                        parcelamento_unificado["situacao"] = "IRREGULAR"
                    elif "EM ATRASO" in texto_completo_global.upper():
                        parcelamento_unificado["situacao"] = "EM ATRASO"
                    
                    # Se houver previdência em outros documentos, relaciona
                    resumo_prev = relatorio.get("resumo", {})
                    if resumo_prev.get("previdencia_total", 0.0) > 0:
                        parcelamento_unificado["observacao"] = f"Valor previdenciário consolidado: R$ {resumo_prev['previdencia_total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                
                relatorio["pgfn"] = {
                    "tem_debito": len(inscricoes) > 0,
                    "inscricoes": inscricoes,
                    "sispar": {
                        "tem": sispar.get('tem_sispar', False),
                        "parcelamentos": sispar_parcelamentos
                    },
                    "parcelamento_unificado": parcelamento_unificado
                }
                
                # PGFN Previdência e Total de Previdência
                pgfn_previdencia = rf_data.get('pgfn_previdencia', {})
                previdencia = rf_data.get('previdencia', {})
                
                relatorio["receita_federal"]["pgfn_previdencia"] = {
                    "existe": pgfn_previdencia.get('existe', False),
                    "receitas": pgfn_previdencia.get('receitas', []),
                    "origem_secao": pgfn_previdencia.get('origem_secao'),
                    "informacoes_adicionais_usuario": pgfn_previdencia.get('informacoes_adicionais_usuario', '')
                }
                
                relatorio["receita_federal"]["previdencia"] = {
                    "existe": previdencia.get('existe', False),
                    "total_previdencia": previdencia.get('total_previdencia'),
                    "fonte": previdencia.get('fonte', 'Receita Federal')
                }
        
        # SEFAZ
        elif doc_type == "sefaz" and hasattr(res, 'sefaz_estadual') and res.sefaz_estadual:
            sefaz_data = res.sefaz_estadual
            cabecalho = sefaz_data.get('cabecalho_documento', {})
            pendencias = sefaz_data.get('pendencias_identificadas', {})
            
            relatorio["sefaz"]["situacao"] = cabecalho.get('situacao_geral')
            
            # IPVA
            for ipva in pendencias.get('ipva', []):
                ano = ipva.get('exercicio')
                valor = ipva.get('valor_total')
                relatorio["sefaz"]["ipva"].append({
                    "ano": int(ano) if ano and str(ano).isdigit() else None,
                    "valor": valor,
                    "situacao": ipva.get('status', 'DESCONHECIDA')
                })
            
            # Fronteira - só se não for certidão
            tipo_doc = sefaz_data.get('tipo_documento', 'extrato')
            if tipo_doc == "extrato":
                fronteira_items = pendencias.get('icms_fronteira_antecipado', [])
                if fronteira_items:
                    relatorio["sefaz"]["fronteira"]["tem_em_aberto"] = True
                    for item in fronteira_items:
                        relatorio["sefaz"]["fronteira"]["itens"].append({
                            "competencia": item.get('periodo_referencia'),
                            "valor": item.get('valor_total')
                        })
            
            # Débitos fiscais
            debitos_fiscais = pendencias.get('debitos_fiscais_autuacoes', [])
            if debitos_fiscais:
                relatorio["sefaz"]["debitos_fiscais"]["tem"] = True
                for item in debitos_fiscais:
                    relatorio["sefaz"]["debitos_fiscais"]["itens"].append({
                        "descricao": item.get('natureza_debito'),
                        "competencia": item.get('periodo'),
                        "valor": item.get('valor_consolidado')
                    })
            
            # Observação
            mensagens = sefaz_data.get('mensagens_sistema', {})
            if mensagens.get('observacao'):
                relatorio["sefaz"]["observacao"] = mensagens['observacao']
        
        # FGTS
        elif doc_type == "fgts" and hasattr(res, 'fgts') and res.fgts:
            fgts_data = res.fgts
            crf = fgts_data.get('crf_detalhes', {})
            pendencias = fgts_data.get('pendencias_financeiras', {})
            mensagens = fgts_data.get('mensagens_sistema', {})
            
            relatorio["fgts"]["situacao"] = crf.get('situacao_atual')
            
            for debito in pendencias.get('lista_debitos', []):
                relatorio["fgts"]["debitos"].append({
                    "competencia": debito.get('competencia'),
                    "valor": debito.get('valor_estimado'),
                    "situacao": "EM ABERTO" if pendencias.get('possui_debitos') else None
                })
            
            # Observação
            if mensagens.get('observacao'):
                relatorio["fgts"]["observacao"] = mensagens['observacao']
    
    # Aplica regra "não tem débito"
    aplicar_regra_sem_debito(relatorio)
    
    # Consolida previdência
    relatorio["resumo"] = consolidar_previdencia(resultados)
    
    return relatorio


def aplicar_regra_sem_debito(relatorio: Dict[str, Any]):
    """
    Aplica regra: se não houver débitos identificados, setar flags e observação.
    """
    # Receita Federal - Simples
    simples = relatorio["receita_federal"]["simples"]
    if not simples["tem_debito_em_aberto"] and not simples["debitos"]:
        simples["observacao"] = "Não há débitos identificados no período analisado."
    
    # SEFAZ - Fronteira
    fronteira = relatorio["sefaz"]["fronteira"]
    if not fronteira["tem_em_aberto"] and not fronteira["itens"]:
        relatorio["sefaz"]["observacao"] = "Não há débitos identificados no período analisado."
    
    # SEFAZ - Débitos Fiscais
    debitos_fiscais = relatorio["sefaz"]["debitos_fiscais"]
    if not debitos_fiscais["tem"] and not debitos_fiscais["itens"]:
        if not relatorio["sefaz"]["observacao"]:
            relatorio["sefaz"]["observacao"] = "Não há débitos identificados no período analisado."
    
    # FGTS
    if not relatorio["fgts"]["debitos"]:
        relatorio["fgts"]["observacao"] = "Não há débitos identificados no período analisado."
    
    # PGFN
    if not relatorio["pgfn"]["tem_debito"] and not relatorio["pgfn"]["inscricoes"]:
        # Não adiciona observação aqui, pois PGFN pode não ter débitos mesmo
        pass


# ==============================================================================
# FUNÇÕES LEGADAS (mantidas para compatibilidade)
# ==============================================================================

def slugify(texto: str) -> str:
    """Gera um slug seguro para nomes de arquivo."""
    texto = (texto or "").strip()
    texto = re.sub(r"[^A-Za-z0-9\-\s_]", "", texto)
    texto = re.sub(r"\s+", "_", texto)
    return texto or "relatorio"


def fmt_data(d: date | datetime | str | None) -> str:
    """Formata datas para o padrão brasileiro (DD/MM/AAAA)."""
    if not d:
        return ""
    if isinstance(d, (datetime, date)):
        return d.strftime("%d/%m/%Y")
    return str(d)


def montar_dados_relatorio(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Função legada mantida para compatibilidade com app.py.
    """
    # Implementação simplificada - pode ser expandida conforme necessário
    return form_data


def _converter_para_json_serializavel(obj: Any) -> Any:
    """
    Converte objetos não serializáveis (date, datetime) para strings.
    """
    if isinstance(obj, (date, datetime)):
        return obj.strftime("%d/%m/%Y")
    elif isinstance(obj, dict):
        return {k: _converter_para_json_serializavel(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_converter_para_json_serializavel(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(_converter_para_json_serializavel(item) for item in obj)
    else:
        return obj


def gerar_texto_relatorio(dados: Dict[str, Any]) -> str:
    """
    Função legada mantida para compatibilidade.
    Converte objetos date/datetime para strings antes de serializar.
    """
    dados_convertidos = _converter_para_json_serializavel(dados)
    return json.dumps(dados_convertidos, indent=2, ensure_ascii=False)
