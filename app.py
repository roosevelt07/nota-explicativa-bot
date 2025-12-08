# app.py
"""
Aplicativo Streamlit para geração de Relatórios de Acompanhamento de Débitos
em PDF, a partir de dados informados manualmente pelo analista.

- Não depende de planilhas.
- Usa um modelo de texto seguindo o exemplo fornecido.
- Gera PDF com tabelas formatadas usando ReportLab.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, Any

import streamlit as st

from src.core import montar_dados_relatorio, gerar_texto_relatorio, slugify
from src.pdf_generator import gerar_pdf_bytes
from src.word_generator import gerar_docx_bytes  # <-- NOVO IMPORT

# ============================================================================
# CONFIGURAÇÕES BÁSICAS DO PROJETO
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output" / "notas"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# INTERFACE STREAMLIT
# ============================================================================


def main() -> None:
    st.set_page_config(
        page_title="Relatório de Acompanhamento de Débitos",
        page_icon="🧾",
        layout="centered",
    )

    st.title("🧾 Relatório de Acompanhamento de Débitos")
    st.caption(
        "Preencha os dados coletados nos entes federais, estaduais e municipais "
        "e gere o relatório em PDF no padrão da Eikon."
    )

    with st.sidebar:
        st.markdown("### Sobre o aplicativo")
        st.markdown(
            "- Gera relatório padrão com tabelas formatadas;\n"
            "- Não depende de planilhas;\n"
            "- Ideal para consultas manuais em RFB, SEFAZ, Prefeituras e FGTS."
        )

    # ------------------------- FORMULÁRIO PRINCIPAL -------------------------

    with st.form("form_relatorio"):
        st.subheader("Dados principais")

        col_a, col_b = st.columns(2)
        with col_a:
            data_relatorio = st.date_input(
                "Data do relatório",
                value=date.today(),
            )
        with col_b:
            periodo_referencia = st.text_input(
                "Período de referência *",
                placeholder="Ex.: Setembro/2025",
            )

        st.subheader("Dados da empresa / requerente")
        requerente = st.text_input("Requerente / Nome da empresa *")
        cnpj = st.text_input("CNPJ *", placeholder="00.000.000/0001-00")

        col_c, col_d = st.columns(2)
        with col_c:
            tributacao = st.selectbox(
                "Tributação",
                options=[
                    "",
                    "Simples Nacional",
                    "Lucro Presumido",
                    "Lucro Real",
                    "Outro",
                ],
                index=0,
            )
        with col_d:
            certificado_digital = st.text_input(
                "Certificado Digital",
                placeholder="Ex.: 24/03/2026",
            )

        st.subheader("Consultas realizadas")

        col_rf, col_sefaz = st.columns(2)
        with col_rf:
            data_consulta_rf = st.date_input(
                "Data da consulta à Receita Federal",
                value=date.today(),
            )
        with col_sefaz:
            data_consulta_sefaz = st.date_input(
                "Data da consulta à SEFAZ",
                value=date.today(),
            )

        col_mun, col_fgts = st.columns(2)
        with col_mun:
            data_consulta_municipal = st.date_input(
                "Data da consulta ao ente municipal",
                value=date.today(),
            )
        with col_fgts:
            data_consulta_fgts = st.date_input(
                "Data da consulta ao FGTS",
                value=date.today(),
            )

        st.subheader("Seções do relatório")

        # Receita Federal – texto direto
        bloco_receita_federal = st.text_area(
            "Receita Federal (texto)",
            placeholder="- Não foi constatado débitos para o exercício fiscal em consulta.",
            height=80,
        )

        # SEFAZ – mini tabela: uma linha por débito
        tabela_sefaz = st.text_area(
            "SEFAZ – linhas da tabela (uma por linha)",
            value="IPVA     RCG-7G42     Em atraso\nIPVA     RVJ-1A14     Em atraso",
            height=90,
        )

        # Municipais – mini tabela
        tabela_municipais = st.text_area(
            "Débitos Municipais – linhas da tabela (uma por linha)",
            value="CIM     2025     R$ 1.493,85     Em atraso",
            height=80,
        )

        # FGTS – texto direto
        bloco_fgts = st.text_area(
            "FGTS (texto)",
            value="- Não foi constatado débitos para o exercício fiscal em consulta, regular com envio do FGTS.",
            height=80,
        )

        # Parcelamentos – mini tabela
        tabela_parcelamentos = st.text_area(
            "Parcelamentos – linhas da tabela (uma por linha)",
            value="SIMPLES NACIONAL     R$ 2.100,00     Último dia útil do mês     60     28",
            height=80,
        )

        st.subheader("Conclusão e responsável técnico")

        bloco_conclusao = st.text_area(
            "Conclusão",
            value=(
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
            ),
            height=200,
        )

        col_resp1, col_resp2 = st.columns(2)
        with col_resp1:
            responsavel_nome = st.text_input(
                "Responsável pelo relatório",
                placeholder="Ex.: Caio César",
            )
            responsavel_cargo = st.text_input(
                "Cargo",
                placeholder="Ex.: Gerente de Contas",
            )
        with col_resp2:
            responsavel_email = st.text_input(
                "E-mail do responsável",
                placeholder="cesar.tributario@eikonsolucoes.com.br",
            )

        # BOTÃO (agora mais genérico, já que teremos PDF e Word)
        gerar = st.form_submit_button("Gerar relatório")

    # ------------------------- PROCESSAMENTO -------------------------

    if gerar:
        erros = []
        if not periodo_referencia.strip():
            erros.append("Período de referência")
        if not requerente.strip():
            erros.append("Requerente / Nome da empresa")
        if not cnpj.strip():
            erros.append("CNPJ")

        if erros:
            st.error("Por favor, preencha os campos obrigatórios: " + ", ".join(erros))
            return

        form_data = {
            "data_relatorio": data_relatorio,
            "periodo_referencia": periodo_referencia,
            "requerente": requerente,
            "cnpj": cnpj,
            "tributacao": tributacao,
            "certificado_digital": certificado_digital,
            "bloco_receita_federal": bloco_receita_federal,
            "tabela_sefaz": tabela_sefaz,
            "tabela_municipais": tabela_municipais,
            "bloco_fgts": bloco_fgts,
            "tabela_parcelamentos": tabela_parcelamentos,
            "bloco_conclusao": bloco_conclusao,
            "data_consulta_rf": data_consulta_rf,
            "data_consulta_sefaz": data_consulta_sefaz,
            "data_consulta_municipal": data_consulta_municipal,
            "data_consulta_fgts": data_consulta_fgts,
            "responsavel_nome": responsavel_nome,
            "responsavel_cargo": responsavel_cargo,
            "responsavel_email": responsavel_email,
        }

        dados = montar_dados_relatorio(form_data)
        texto_relatorio = gerar_texto_relatorio(dados)

        st.success(
            "Relatório gerado com sucesso! Veja o texto abaixo e baixe o arquivo."
        )

        st.subheader("Pré-visualização do texto")
        st.text_area(
            "Texto do relatório",
            value=texto_relatorio,
            height=350,
        )

        # ------------------------- GERAÇÃO DOS ARQUIVOS -------------------------

        # Nome base para ambos os formatos
        nome_base = (
            f"relatorio_debitos_"
            f"{slugify(dados['requerente'])}_"
            f"{slugify(dados['periodo_referencia'])}"
        )
        nome_arquivo_pdf = f"{nome_base}.pdf"
        nome_arquivo_docx = f"{nome_base}.docx"

        # Gera bytes dos arquivos
        pdf_bytes = gerar_pdf_bytes(dados)
        docx_bytes = gerar_docx_bytes(dados)

        # Salva uma cópia do PDF no disco (histórico interno)
        try:
            caminho_saida = OUTPUT_DIR / nome_arquivo_pdf
            with open(caminho_saida, "wb") as f:
                f.write(pdf_bytes)
            st.info(f"Cópia em PDF salva em: {caminho_saida}")
        except OSError as e:
            st.warning(f"Não foi possível salvar a cópia em disco: {e}")

        # ------------------------- ABAS DE DOWNLOAD -------------------------

        tab_pdf, tab_word = st.tabs(["📄 Baixar PDF", "📝 Baixar Word"])

        with tab_pdf:
            st.download_button(
                label="📥 Baixar PDF do relatório",
                data=pdf_bytes,
                file_name=nome_arquivo_pdf,
                mime="application/pdf",
            )

        with tab_word:
            st.download_button(
                label="📥 Baixar Word do relatório",
                data=docx_bytes,
                file_name=nome_arquivo_docx,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )


if __name__ == "__main__":
    main()
