# src/templates.py
"""
Modelos de texto (templates) usados pelo NOTA-EXPLICATIVA-BOT.

Aqui ficam apenas strings e textos padrão, sem lógica de negócio.
"""

from __future__ import annotations

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

DÉBITOS IDENTIFICADOS:
Abaixo, estão listados os débitos pendentes, e situação atual da empresa:

Eikon Soluções Ltda CNPJ: 09.502.539/0001-13

RECEITA FEDERAL
{bloco_receita_federal}
Data da consulta: {data_consulta_rf}

SEFAZ
Descrição do Débito     Período     Status
{tabela_sefaz}
Data da consulta: {data_consulta_sefaz}

DÉBITOS MUNICIPAIS
Descrição do Débito     Período     Valor     Status
{tabela_municipais}
Data da consulta: {data_consulta_municipal}

Eikon Soluções Ltda CNPJ: 09.502.539/0001-13

FGTS
{bloco_fgts}
Data da consulta: {data_consulta_fgts}

PARCELAMENTOS
PARCELAMENTO     VALOR APROXIMADO DAS PARCELAS     VENCIMENTO     QTD DE PARCELAS     PARCELA ATUAL
{tabela_parcelamentos}

CONCLUSÃO:
{bloco_conclusao}

Eikon Soluções Ltda CNPJ: 09.502.539/0001-13

Atenciosamente,
{responsavel_nome}
{responsavel_cargo}
e-mail: {responsavel_email}
"""

# -----------------------------------------------------------------------------
# TEXTOS PADRÃO (USADOS QUANDO O ANALISTA NÃO PREENCHER NADA)
# -----------------------------------------------------------------------------

DEFAULT_RECEITA_FEDERAL = (
    "- Não foi constatado débitos para o exercício fiscal em consulta."
)

DEFAULT_SEFAZ_TABELA = (
    "IPVA     RCG-7G42     Em atraso\n" "IPVA     RVJ-1A14     Em atraso"
)

DEFAULT_MUNICIPAIS_TABELA = "CIM     2025     R$ 1.493,85     Em atraso"

DEFAULT_FGTS = (
    "- Não foi constatado débitos para o exercício fiscal em consulta, "
    "regular com envio do FGTS."
)

DEFAULT_PARCELAMENTOS_TABELA = (
    "SIMPLES NACIONAL     R$ 2.100,00     Último dia útil do mês     60     28"
)

DEFAULT_CONCLUSAO = (
    "Listagem das principais ações adotadas até o momento para regularização dos débitos:\n"
    "Verificação de Irregularidades: Todos os débitos foram verificados junto aos órgãos "
    "competentes, sendo identificados tanto débitos fiscais quanto administrativos.\n"
    "Solicitação de Certidões: Certidões Negativas de Débito (CND) para comprovar a "
    "regularização fiscal, após pagamento do débito.\n"
    "Prazos: Importante observar os prazos para pagamento, pois débitos antigos pendentes, caso "
    "não sejam regularizados, poderão resultar na inclusão da empresa no Cadastro Informativo "
    "de Créditos não Quitados do Setor Público Federal (CADIN).\n"
    "Caso haja pendência na PGFN – Procuradoria Geral da Fazenda Nacional a não regularização "
    "poderá acarretar o envio do débito para ser protestado em cartório."
)
