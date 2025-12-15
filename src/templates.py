from __future__ import annotations
# src/templates.py
"""
Modelos de texto (templates) usados pelo NOTA-EXPLICATIVA-BOT.

Aqui ficam apenas strings e textos padrão, sem lógica de negócio.
"""


# -----------------------------------------------------------------------------
# TEMPLATE PRINCIPAL DO RELATÓRIO
# -----------------------------------------------------------------------------
# Este template é usado apenas para pré-visualização de texto no app.
# O PDF é gerado diretamente do dicionário de dados usando src/pdf_generator.py

TEXTO_RELATORIO = """Data do relatório: {data_relatorio}

Requerente: {requerente}
CNPJ: {cnpj}
Tributação: {tributacao}
Certificado Digital: {certificado_digital}

Este relatório tem como objetivo acompanhar os débitos pendentes relacionados à entidade
empresarial destacada acima, destacando os principais pontos sobre a situação fiscal, os
valores devidos, datas de vencimento e providências necessárias para regularização. Nos
casos em que haja desacordo com os débitos e irregularidades apresentadas ou já tenha sido
efetuado o pagamento, favor entrar em contato conosco para a resolução da pendência.

================================================================
DÉBITOS IDENTIFICADOS
================================================================

--- RECEITA FEDERAL ---
{bloco_receita_federal}
Data da consulta: {data_consulta_rf}


--- SEFAZ (ESTADUAL) ---
DESCRIÇÃO | PERÍODO/REF | STATUS/VALOR
{tabela_sefaz}
Data da consulta: {data_consulta_sefaz}


--- DÉBITOS MUNICIPAIS ---
DESCRIÇÃO | PERÍODO | VALOR | STATUS
{tabela_municipais}
Data da consulta: {data_consulta_municipal}


--- FGTS ---
{bloco_fgts}
Data da consulta: {data_consulta_fgts}


================================================================
PARCELAMENTOS ATIVOS
================================================================
PARCELAMENTO | VALOR PARCELA | VENCIMENTO | QTD TOTAL | PARCELA ATUAL
{tabela_parcelamentos}


================================================================
CONCLUSÃO
================================================================
{bloco_conclusao}


----------------------------------------------------------------
Atenciosamente,
{responsavel_nome}
{responsavel_cargo}
e-mail: {responsavel_email}
"""

# -----------------------------------------------------------------------------
# TEXTOS PADRÃO (USADOS QUANDO O ANALISTA NÃO PREENCHER NADA)
# -----------------------------------------------------------------------------

DEFAULT_RECEITA_FEDERAL = (
    "- Não foram constatados débitos para o exercício fiscal em consulta."
)

# Dica: Use | para separar colunas com precisão
DEFAULT_SEFAZ_TABELA = (
    "IPVA 2024 | PLACA KKK-0000 | R$ 1.500,00 (Em atraso)\n"
    "ICMS Fronteira | 01/2025 | R$ 350,00"
)

DEFAULT_MUNICIPAIS_TABELA = (
    "Taxa de Licença (TLF) | 2025 | R$ 1.493,85 | Em atraso"
)

DEFAULT_FGTS = (
    "- Não foram constatados débitos para o exercício fiscal em consulta. "
    "Situação regular perante o FGTS."
)

DEFAULT_PARCELAMENTOS_TABELA = (
    "SIMPLES NACIONAL | R$ 2.100,00 | Dia 20 | 60 | 28"
)

DEFAULT_CONCLUSAO = (
    "Ações recomendadas:\n"
    "1. Regularização Imediata: Proceder com o pagamento das guias de IPVA e Taxas Municipais listadas acima.\n"
    "2. Monitoramento: Acompanhar o processamento do pagamento para garantir a baixa nos sistemas da SEFAZ e Prefeitura.\n"
    "3. Parcelamento: O parcelamento do Simples Nacional encontra-se em dia. Manter o pagamento pontual para evitar rescisão."
)