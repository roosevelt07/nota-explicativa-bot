# src/core.py
"""
Regras de negócio para o NOTA-EXPLICATIVA-BOT.

- Monta o dicionário de dados a partir do formulário do Streamlit;
- Converte os campos de "tabela" (SEFAZ, Municipais, Parcelamentos)
  em listas de linhas;
- Gera o texto completo para pré-visualização no app.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Dict, Any

from .templates import (
    TEXTO_RELATORIO,
    DEFAULT_RECEITA_FEDERAL,
    DEFAULT_SEFAZ_TABELA,
    DEFAULT_MUNICIPAIS_TABELA,
    DEFAULT_FGTS,
    DEFAULT_PARCELAMENTOS_TABELA,
    DEFAULT_CONCLUSAO,
)


def slugify(texto: str) -> str:
    texto = texto.strip()
    texto = re.sub(r"[^A-Za-z0-9\-\s_]", "", texto)
    texto = re.sub(r"\s+", "_", texto)
    return texto or "relatorio"


def fmt_data(d: date | datetime | str) -> str:
    if isinstance(d, (datetime, date)):
        return d.strftime("%d/%m/%Y")
    return str(d)


def _parse_tabela_linhas(texto_tabela: str, padrao_default: str, num_colunas: int):
    """
    Converte o texto digitado (uma linha por débito) em lista de listas:

    Exemplo de entrada (textarea):
        IPVA     RCG-7G42     Em atraso
        IPVA     RVJ-1A14     Em atraso

    Saída:
        [
            ["IPVA", "RCG-7G42", "Em atraso"],
            ["IPVA", "RVJ-1A14", "Em atraso"],
        ]
    
    Aceita separação por múltiplos espaços (2+), tabs ou pipe (|).
    """
    texto = (texto_tabela or "").strip()
    # Se o texto estiver vazio, usa o padrão
    if not texto:
        texto = padrao_default
    
    linhas = []
    for raw in texto.splitlines():
        linha = raw.strip()
        if not linha:
            continue
        
        # Tenta separar por pipe primeiro (mais preciso)
        if "|" in linha:
            partes = [p.strip() for p in linha.split("|")]
        # Depois tenta por tabs
        elif "\t" in linha:
            partes = [p.strip() for p in linha.split("\t")]
        # Por último, separa por múltiplos espaços (2 ou mais)
        else:
            partes = re.split(r"\s{2,}", linha)
            partes = [p.strip() for p in partes if p.strip()]
        
        # Garante que tenha o número correto de colunas
        if len(partes) < num_colunas:
            partes += [""] * (num_colunas - len(partes))
        elif len(partes) > num_colunas:
            partes = partes[:num_colunas]
        
        linhas.append(partes)
    return linhas


def montar_dados_relatorio(form_data: Dict[str, Any]) -> Dict[str, Any]:
    hoje_str = fmt_data(date.today())

    dados: Dict[str, Any] = {
        "data_relatorio": fmt_data(form_data.get("data_relatorio") or date.today()),
        "periodo_referencia": form_data.get("periodo_referencia", "").strip()
        or "Período não informado",
        "requerente": form_data.get("requerente", "").strip(),
        "cnpj": form_data.get("cnpj", "").strip(),
        "tributacao": form_data.get("tributacao", "").strip() or "Não informado",
        "certificado_digital": form_data.get("certificado_digital", "").strip()
        or "Informação não disponível",
        "bloco_receita_federal": form_data.get("bloco_receita_federal", "").strip()
        or DEFAULT_RECEITA_FEDERAL,
        "bloco_fgts": form_data.get("bloco_fgts", "").strip() or DEFAULT_FGTS,
        "bloco_conclusao": form_data.get("bloco_conclusao", "").strip()
        or DEFAULT_CONCLUSAO,
        "data_consulta_rf": fmt_data(form_data.get("data_consulta_rf") or hoje_str),
        "data_consulta_sefaz": fmt_data(
            form_data.get("data_consulta_sefaz") or hoje_str
        ),
        "data_consulta_municipal": fmt_data(
            form_data.get("data_consulta_municipal") or hoje_str
        ),
        "data_consulta_fgts": fmt_data(form_data.get("data_consulta_fgts") or hoje_str),
        "responsavel_nome": form_data.get("responsavel_nome", "").strip()
        or "Responsável não informado",
        "responsavel_cargo": form_data.get("responsavel_cargo", "").strip()
        or "Gerente de Contas",
        "responsavel_email": form_data.get("responsavel_email", "").strip()
        or "contato@eikonsolucoes.com.br",
    }

    # Linhas das tabelas
    dados["sefaz_rows"] = _parse_tabela_linhas(
        form_data.get("tabela_sefaz", ""),
        DEFAULT_SEFAZ_TABELA,
        num_colunas=3,
    )

    dados["municipais_rows"] = _parse_tabela_linhas(
        form_data.get("tabela_municipais", ""),
        DEFAULT_MUNICIPAIS_TABELA,
        num_colunas=4,
    )

    dados["parcelamentos_rows"] = _parse_tabela_linhas(
        form_data.get("tabela_parcelamentos", ""),
        DEFAULT_PARCELAMENTOS_TABELA,
        num_colunas=5,
    )

    # Converter listas em strings para o template de texto
    def _formatar_tabela_linhas(rows: list, separador: str = "     ") -> str:
        """Converte lista de linhas em string formatada."""
        if not rows:
            return ""
        linhas_str = []
        for row in rows:
            linhas_str.append(separador.join(str(cell) for cell in row))
        return "\n".join(linhas_str)

    # Adicionar versões em string para o template de texto
    dados["tabela_sefaz"] = _formatar_tabela_linhas(dados["sefaz_rows"])
    dados["tabela_municipais"] = _formatar_tabela_linhas(dados["municipais_rows"])
    dados["tabela_parcelamentos"] = _formatar_tabela_linhas(dados["parcelamentos_rows"])

    return dados


def gerar_texto_relatorio(dados: Dict[str, Any]) -> str:
    """
    Só pra pré-visualizar no app (texto corrido).
    O PDF usa o dicionário 'dados', não esse texto.
    """
    return TEXTO_RELATORIO.format(**dados)
