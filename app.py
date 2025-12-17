# app.py
"""
Aplicativo Streamlit para geração de Relatórios de Acompanhamento de Débitos.

Integração:
- Parsers (Receita, SEFAZ, FGTS) -> Extraem dados e estruturas JSON.
- Core -> Monta o dicionário de dados final.
- PDF Generator -> Renderiza tabelas complexas e papel timbrado.
- Word Generator -> Gera documento editável.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any
import tempfile
import os
import copy

import streamlit as st
import pandas as pd

# Importações dos módulos internos
from src.core import montar_dados_relatorio, gerar_texto_relatorio, slugify
from src.pdf_generator import gerar_pdf_bytes
from src.word_generator import gerar_docx_bytes  # Generator de Word (opcional)
from src.parsers import interpretar_todos      # Fachada dos parsers

# ============================================================================
# CONFIGURAÇÕES BÁSICAS DO PROJETO
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output" / "notas"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def _date_from_string(br_date: str | None) -> date:
    """Converte 'DD/MM/AAAA' para date; se falhar ou for None, retorna hoje."""
    if not br_date:
        return date.today()
    try:
        return datetime.strptime(br_date, "%d/%m/%Y").date()
    except ValueError:
        return date.today()


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
        "Faça upload dos PDFs oficiais (Receita, SEFAZ, FGTS) para pré-preencher "
        "os campos e gerar o relatório final com tabelas detalhadas."
    )

    with st.sidebar:
        st.header("Instruções")
        st.info(
            "1. Faça upload dos PDFs nos campos abaixo.\n"
            "2. Clique em 'Ler PDFs'.\n"
            "3. Revise os campos pré-preenchidos.\n"
            "4. Gere o relatório em PDF ou Word."
        )
        st.markdown("---")
        st.markdown("### Módulos Ativos")
        st.markdown("- ✅ Receita Federal (SIEF)")
        st.markdown("- ✅ SEFAZ (IPVA/ICMS)")
        st.markdown("- ✅ FGTS (CRF)")

    # -------------------------------------------------------------------------
    # 1. UPLOAD DE ARQUIVOS
    # -------------------------------------------------------------------------

    st.subheader("1. Upload de Documentos")

    col_pdf1, col_pdf2, col_pdf3 = st.columns(3)
    with col_pdf1:
        pdf_receita_upload = st.file_uploader("Relatório Receita (PDF)", type=["pdf"], key="pdf_receita")
    with col_pdf2:
        pdf_fgts_upload = st.file_uploader("CND FGTS (PDF)", type=["pdf"], key="pdf_fgts")
    with col_pdf3:
        pdf_sefaz_upload = st.file_uploader("CND SEFAZ (PDF)", type=["pdf"], key="pdf_sefaz")

    # Botão de processamento dos parsers
    if st.button("📥 Ler PDFs e Extrair Dados", type="primary"):
        tmp_paths: Dict[str, str] = {}

        # Salva arquivos temporários para os parsers lerem
        for nome, up in [
            ("receita", pdf_receita_upload),
            ("fgts", pdf_fgts_upload),
            ("sefaz", pdf_sefaz_upload),
        ]:
            if up is not None:
                # Cria arquivo temporário seguro
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(up.getbuffer())
                    tmp_paths[nome] = tmp.name

        # Chama a inteligência dos parsers
        with st.spinner("Analisando documentos..."):
            resultado = interpretar_todos(
                receita_pdf=tmp_paths.get("receita"),
                fgts_pdf=tmp_paths.get("fgts"),
                sefaz_pdf=tmp_paths.get("sefaz"),
            )
        
        # Salva o resultado na sessão para persistir após o rerun do Streamlit
        st.session_state["resultado_parsers"] = resultado
        
        # Limpeza de arquivos temporários
        for path in tmp_paths.values():
            try:
                os.remove(path)
            except:
                pass

        st.success("Leitura concluída! Verifique os dados abaixo.")

    # Recupera os dados extraídos da sessão
    resultado = st.session_state.get("resultado_parsers")

    # -------------------------------------------------------------------------
    # 1.5. DASHBOARD DE DADOS EXTRAÍDOS
    # -------------------------------------------------------------------------
    
    if resultado and resultado.tem_algum_dado():
        st.markdown("---")
        st.subheader("📊 Dashboard - Resumo dos Dados Extraídos")
        
        # Cards de Totais
        col1, col2, col3, col4, col5 = st.columns(5)
        
        # Receita Federal - Total de Previdência (OBJETIVO 3)
        from src.utils import formatar_total_previdencia
        # Cria um dict temporário para usar a função utilitária
        dados_temp = {"receita_federal": resultado.receita_federal if hasattr(resultado, 'receita_federal') and resultado.receita_federal else {}}
        texto_total_previdencia = formatar_total_previdencia(dados_temp)
        # Extrai apenas o valor após "Total de Previdência: "
        valor_exibido = texto_total_previdencia.replace("Total de Previdência: ", "")
        
        with col1:
            st.metric("Total de Previdência", valor_exibido)
        
        # SEFAZ - Situação e Total
        situacao_sefaz = "N/A"
        total_sefaz = 0.0
        if hasattr(resultado, 'sefaz_estadual') and resultado.sefaz_estadual:
            cabecalho = resultado.sefaz_estadual.get('cabecalho_documento', {})
            situacao_sefaz = cabecalho.get('situacao_geral', 'N/A')
            resumo = resultado.sefaz_estadual.get('resumo_financeiro', {})
            total_sefaz = resumo.get('total_geral_consolidado', 0.0) or resumo.get('total_debitos', 0.0)
        
        # SEFAZ e FGTS em nova linha
        col_sefaz, col_fgts = st.columns(2)
        
        with col_sefaz:
            if situacao_sefaz == 'REGULAR':
                st.metric("SEFAZ", "✅ Regular", delta=None)
            elif situacao_sefaz == 'EM ATRASO':
                st.metric("SEFAZ", "⚠️ Em Atraso", 
                         delta=f"R$ {total_sefaz:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            else:
                st.metric("SEFAZ", situacao_sefaz, 
                         delta=f"R$ {total_sefaz:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if total_sefaz > 0 else None)
        
        # FGTS - Situação
        situacao_fgts = "N/A"
        if hasattr(resultado, 'fgts') and resultado.fgts:
            situacao_fgts = resultado.fgts.get('crf_detalhes', {}).get('situacao_atual', 'N/A')
        
        with col_fgts:
            st.metric("FGTS (Situação)", situacao_fgts)
        
        # Expanders com Tabelas Detalhadas
        st.markdown("### 📋 Detalhamento")
        
        # Receita Federal
        if hasattr(resultado, 'receita_federal') and resultado.receita_federal:
            with st.expander("🏛️ Receita Federal - Detalhes", expanded=False):
                receita = resultado.receita_federal
                
                # Total de Previdência (OBJETIVO 3)
                from src.utils import formatar_total_previdencia
                dados_temp = {"receita_federal": receita}
                texto_total_previdencia = formatar_total_previdencia(dados_temp)
                st.markdown(f"#### 💰 {texto_total_previdencia}")
                
                # CP Seguro (renomeado de CP Segurados)
                cp_seguro = receita.get('cp_seguro', {})
                if cp_seguro.get('detalhes'):
                    st.markdown("#### 🛡️ CP Seguro (CP-SEGUR.)")
                    st.markdown(f"**Total: R$ {cp_seguro.get('total', 0.0):,.2f}**".replace(",", "X").replace(".", ",").replace("X", "."))
                    df_seguro = pd.DataFrame(cp_seguro['detalhes'])
                    st.dataframe(df_seguro, use_container_width=True)
                
                # CP Patronal
                if receita.get('cp_patronal', {}).get('detalhes'):
                    st.markdown("#### CP Patronal (1138-01, 1646-01)")
                    st.markdown(f"**Total Consolidado: R$ {receita['cp_patronal']['total']:,.2f}**".replace(",", "X").replace(".", ",").replace("X", "."))
                    df_patronal = pd.DataFrame(receita['cp_patronal']['detalhes'])
                    st.dataframe(df_patronal, use_container_width=True)
                
                # CP Terceiros
                if receita.get('cp_terceiros', {}).get('detalhes'):
                    st.markdown("#### CP Terceiros (1170-01, 1176-01, 1191-01, 1196-01, 1200-01)")
                    st.markdown(f"**Total Consolidado: R$ {receita['cp_terceiros']['total']:,.2f}**".replace(",", "X").replace(".", ",").replace("X", "."))
                    df_terceiros = pd.DataFrame(receita['cp_terceiros']['detalhes'])
                    st.dataframe(df_terceiros, use_container_width=True)
                
                # Débitos Gerais
                debitos_gerais = receita.get('debitos_gerais', {})
                if any(debitos_gerais.values()):
                    st.markdown("#### Débitos Gerais")
                    for nome, lista in debitos_gerais.items():
                        if lista:
                            st.markdown(f"**{nome}**")
                            df = pd.DataFrame(lista)
                            st.dataframe(df, use_container_width=True)
                
                # Simples Nacional
                simples = receita.get('simples_nacional', {})
                if simples.get('tem_pendencias'):
                    st.markdown("#### Simples Nacional")
                    st.warning("⚠️ Há pendências de Simples Nacional")
                    if simples.get('parcelamento', {}).get('tem_parcelamento'):
                        parc = simples['parcelamento']
                        st.info(f"Parcelamento ativo. Parcelas em atraso: {parc.get('parcelas_atraso', 0)}")
                        if parc.get('data_validade'):
                            st.info(f"Data de Validade: {parc['data_validade']}")
                
                # PGFN
                pgfn = receita.get('pgfn', {})
                if pgfn.get('previdenciario') or pgfn.get('simples_nacional'):
                    st.markdown("#### PGFN - Dívida Ativa")
                    if pgfn.get('previdenciario'):
                        st.markdown("**Previdenciário:**")
                        df_prev = pd.DataFrame(pgfn['previdenciario'])
                        st.dataframe(df_prev, use_container_width=True)
                    if pgfn.get('simples_nacional'):
                        st.markdown("**Simples Nacional:**")
                        df_sn = pd.DataFrame(pgfn['simples_nacional'])
                        st.dataframe(df_sn, use_container_width=True)
                
                # PGFN Previdência (OBJETIVO 1)
                pgfn_previdencia = receita.get('pgfn_previdencia', {})
                if pgfn_previdencia.get('existe'):
                    st.markdown("#### PGFN Previdência")
                    receitas_list = pgfn_previdencia.get('receitas', [])
                    receitas_str = '; '.join(receitas_list) if receitas_list else "Não identificado"
                    
                    # Tabelinha
                    df_pgfn_prev = pd.DataFrame({
                        "Campo": ["Receita", "Informações adicionais"],
                        "Valor": [receitas_str, pgfn_previdencia.get('informacoes_adicionais_usuario', '')]
                    })
                    st.table(df_pgfn_prev)
                    st.info("💡 Use a seção 'Ajustes Manuais - PGFN Previdência' no formulário abaixo para editar as informações adicionais.")
                elif pgfn_previdencia:
                    # Se existe mas não tem receitas, mostra "Não identificado"
                    st.markdown("#### PGFN Previdência")
                    st.info("Não identificado")
                
                # SISPAR
                sispar = receita.get('sispar', {})
                if sispar.get('tem_sispar'):
                    st.markdown("#### SISPAR")
                    st.info("✅ Parcelamento SISPAR identificado")
                    parcelamentos = sispar.get('parcelamentos', [])
                    if parcelamentos:
                        for idx, parc in enumerate(parcelamentos):
                            with st.expander(f"Parcelamento {idx + 1} - Conta: {parc.get('conta', 'N/A')}", expanded=True):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**Conta:** {parc.get('conta', '-')}")
                                    st.write(f"**Tipo:** {parc.get('tipo', '-')}")
                                    st.write(f"**Modalidade:** {parc.get('modalidade', '-')}")
                                with col2:
                                    st.write(f"**Regime:** {parc.get('regime', '-')}")
                                    if parc.get('limite_maximo_meses'):
                                        st.write(f"**Limite máximo:** ATÉ {parc.get('limite_maximo_meses')} MESES")
                                    if parc.get('exigibilidade_suspensa') is not None:
                                        st.write(f"**Exigibilidade suspensa:** {'SIM' if parc.get('exigibilidade_suspensa') else 'NÃO'}")
                                    if parc.get('negociado_no_sispar') is not None:
                                        st.write(f"**Negociado no SISPAR:** {'SIM' if parc.get('negociado_no_sispar') else 'NÃO'}")
                                
                                if parc.get('observacao'):
                                    st.warning(parc.get('observacao'))
        
        # SEFAZ
        if hasattr(resultado, 'sefaz_estadual') and resultado.sefaz_estadual:
            with st.expander("🏛️ SEFAZ - Detalhes", expanded=False):
                sefaz = resultado.sefaz_estadual
                situacao = sefaz.get('cabecalho_documento', {}).get('situacao_geral', 'N/A')
                
                # Exibe situação com destaque
                if situacao == 'REGULAR':
                    st.success(f"✅ **Situação: {situacao}** - Nada consta")
                elif situacao == 'EM ATRASO':
                    st.error(f"⚠️ **Situação: {situacao}**")
                else:
                    st.warning(f"⚠️ **Situação: {situacao}**")
                
                # Resumo Financeiro (sempre mostra, mesmo se regular)
                resumo = sefaz.get('resumo_financeiro', {})
                total_geral = resumo.get('total_geral_consolidado', 0.0) or resumo.get('total_debitos', 0.0)
                
                if total_geral > 0:
                    st.markdown("#### 💰 Resumo Financeiro")
                    st.markdown(f"**Total de Débitos: R$ {total_geral:,.2f}**".replace(",", "X").replace(".", ",").replace("X", "."))
                
                # Se tem débitos, mostra detalhes
                if situacao in ['IRREGULAR', 'EM ATRASO', 'IRREGULAR / COM PENDÊNCIAS'] or total_geral > 0:
                    pendencias = sefaz.get('pendencias_identificadas', {})
                    
                    # IPVA
                    if pendencias.get('ipva'):
                        st.markdown("#### 🚗 IPVA")
                        df_ipva = pd.DataFrame(pendencias['ipva'])
                        st.dataframe(df_ipva, use_container_width=True)
                    
                    # ICMS Fronteira/Antecipado
                    if pendencias.get('icms_fronteira_antecipado'):
                        st.markdown("#### 📋 ICMS Fronteira/Antecipado")
                        df_icms = pd.DataFrame(pendencias['icms_fronteira_antecipado'])
                        st.dataframe(df_icms, use_container_width=True)
                    
                    # Débitos Fiscais
                    if pendencias.get('debitos_fiscais_autuacoes'):
                        st.markdown("#### 💸 Débitos Fiscais")
                        df_debitos = pd.DataFrame(pendencias['debitos_fiscais_autuacoes'])
                        st.dataframe(df_debitos, use_container_width=True)
                    
                    # Detalhamento do resumo
                    if resumo and (resumo.get('total_ipva', 0.0) > 0 or resumo.get('total_icms_fronteira', 0.0) > 0 or resumo.get('total_divida_ativa', 0.0) > 0):
                        st.markdown("#### 📊 Detalhamento")
                        if resumo.get('total_ipva', 0.0) > 0:
                            st.markdown(f"- Total IPVA: R$ {resumo.get('total_ipva', 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        if resumo.get('total_icms_fronteira', 0.0) > 0:
                            st.markdown(f"- Total ICMS Fronteira: R$ {resumo.get('total_icms_fronteira', 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                        if resumo.get('total_divida_ativa', 0.0) > 0:
                            st.markdown(f"- Total Dívida Ativa: R$ {resumo.get('total_divida_ativa', 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        # FGTS
        if hasattr(resultado, 'fgts') and resultado.fgts:
            with st.expander("🏦 FGTS - Detalhes", expanded=False):
                fgts = resultado.fgts
                situacao = fgts.get('crf_detalhes', {}).get('situacao_atual', 'N/A')
                st.markdown(f"**Situação: {situacao}**")
                
                if situacao == 'REGULAR':
                    validade = fgts.get('crf_detalhes', {}).get('validade_fim', '')
                    if validade:
                        st.success(f"✅ Regular no FGTS. Validade: {validade}")
                else:
                    pendencias = fgts.get('pendencias_financeiras', {})
                    if pendencias.get('lista_debitos'):
                        st.warning(f"⚠️ {pendencias.get('resumo', {}).get('qtd_competencias', 0)} competências pendentes")
                        df_comp = pd.DataFrame(pendencias['lista_debitos'])
                        st.dataframe(df_comp, use_container_width=True)
        
        st.markdown("---")

    # -------------------------------------------------------------------------
    # 2. FORMULÁRIO DE EDIÇÃO
    # -------------------------------------------------------------------------

    with st.form("form_relatorio"):
        st.subheader("2. Dados Principais")

        col_a, col_b = st.columns(2)
        with col_a:
            data_relatorio = st.date_input("Data do relatório", value=date.today())
        with col_b:
            periodo_referencia = st.text_input("Período de referência *", placeholder="Ex.: Novembro/2025")

        st.markdown("#### Identificação do Contribuinte")
        
        # Defaults inteligentes
        def_req = resultado.requerente if resultado and resultado.requerente else ""
        def_cnpj = resultado.cnpj if resultado and resultado.cnpj else ""

        requerente = st.text_input("Requerente / Razão Social *", value=def_req)
        cnpj = st.text_input("CNPJ *", value=def_cnpj, placeholder="00.000.000/0001-00")

        col_c, col_d = st.columns(2)
        with col_c:
            tributacao = st.selectbox("Tributação", ["", "Simples Nacional", "Lucro Presumido", "Lucro Real", "Outro"])
        with col_d:
            certificado_digital = st.text_input("Certificado Digital (Validade)", placeholder="Ex.: 24/03/2026")

        # --------------------- SEÇÃO DE DATAS ---------------------
        st.markdown("#### Datas das Consultas")
        
        # Extração de datas dos parsers
        d_rf = _date_from_string(resultado.data_consulta_rf) if resultado else date.today()
        d_sefaz = _date_from_string(resultado.data_consulta_sefaz) if resultado else date.today()
        d_fgts = _date_from_string(resultado.data_consulta_fgts) if resultado else date.today()
        d_mun = date.today()

        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        with col_d1:
            data_consulta_rf = st.date_input("Receita Federal", value=d_rf)
        with col_d2:
            data_consulta_sefaz = st.date_input("SEFAZ", value=d_sefaz)
        with col_d3:
            data_consulta_fgts = st.date_input("FGTS", value=d_fgts)
        with col_d4:
            data_consulta_municipal = st.date_input("Municipal", value=d_mun)

        # --------------------- SEÇÃO DE CONTEÚDO ---------------------
        st.subheader("3. Detalhamento dos Débitos")
        
        # --- Receita Federal ---
        def_rec = resultado.bloco_receita_federal if resultado and resultado.bloco_receita_federal else ""
        bloco_receita_federal = st.text_area(
            "Receita Federal (Resumo/Texto)", 
            value=def_rec, 
            height=100, 
            placeholder="Cole o texto ou deixe o parser preencher."
        )

        # --- SEFAZ (Híbrido: Texto Manual + Dados Estruturados) ---
        st.markdown("---")
        st.markdown("**SEFAZ (Estadual)**")
        if resultado and getattr(resultado, "sefaz_estadual", None):
            st.info("✅ Dados estruturados de IPVA/ICMS foram carregados e serão incluídos na tabela do PDF.")
        
        # Tratamento para tabela manual (Legado)
        def_sefaz_manual = ""
        if resultado and resultado.sefaz_rows:
            # Converte lista de listas em texto para o textarea
            lines = []
            for row in resultado.sefaz_rows:
                lines.append(" | ".join(str(x) for x in row))
            def_sefaz_manual = "\n".join(lines)

        tabela_sefaz = st.text_area(
            "Itens Adicionais SEFAZ (Opcional - Formato: Descrição | Período | Status)", 
            value=def_sefaz_manual,
            height=80,
            help="Use barra vertical | para separar as colunas se digitar manualmente."
        )

        # --- Municipais ---
        st.markdown("---")
        tabela_municipais = st.text_area(
            "Débitos Municipais (Manual)",
            placeholder="Taxa TFF | 2025 | R$ 500,00 | Em aberto",
            height=80
        )

        # --- FGTS ---
        st.markdown("---")
        st.markdown("**FGTS**")
        if resultado and getattr(resultado, "fgts", None):
            st.info("✅ Dados detalhados do CRF/FGTS carregados.")
            
        def_fgts = resultado.bloco_fgts if resultado and resultado.bloco_fgts else ""
        bloco_fgts = st.text_area("Texto FGTS (Complementar)", value=def_fgts, height=80)

        # --- Parcelamentos ---
        st.markdown("---")
        tabela_parcelamentos = st.text_area(
            "Parcelamentos Ativos (Manual)",
            placeholder="SIMPLES | R$ 1000 | Dia 20 | 60 | 10",
            height=80
        )

        # --- Ajustes Manuais PGFN Previdência ---
        if resultado and getattr(resultado, "receita_federal", None):
            receita = resultado.receita_federal
            pgfn_previdencia = receita.get('pgfn_previdencia', {})
            if pgfn_previdencia.get('existe'):
                st.markdown("---")
                st.subheader("Ajustes Manuais - PGFN Previdência")
                
                receitas_list = pgfn_previdencia.get('receitas', [])
                receitas_str = '; '.join(receitas_list) if receitas_list else "Não identificado"
                st.info(f"Receita detectada automaticamente: {receitas_str}")
                
                # Usa key= para persistência automática - não precisa salvar manualmente no session_state
                valor_inicial = st.session_state.get('pgfn_prev_info_adicional', pgfn_previdencia.get('informacoes_adicionais_usuario', ''))
                
                info_adicional = st.text_area(
                    "Informações adicionais",
                    value=valor_inicial,
                    key="pgfn_prev_info_adicional",
                    height=100,
                    help="Preencha informações adicionais sobre o PGFN Previdência"
                )
                
                # NÃO salva no session_state aqui - será feito apenas quando o form for submetido
        
        # --- Ajustes Manuais SISPAR ---
        if resultado and getattr(resultado, "receita_federal", None):
            receita = resultado.receita_federal
            sispar = receita.get('sispar', {})
            if sispar.get('tem_sispar'):
                st.markdown("---")
                st.subheader("Ajustes Manuais - SISPAR")
                st.info("Preencha manualmente as informações que não constam no PDF (quantidade de parcelas, valores, competências)")
                
                parcelamentos = sispar.get('parcelamentos', [])
                for idx, parc in enumerate(parcelamentos):
                    with st.expander(f"Parcelamento SISPAR {idx + 1} - Conta: {parc.get('conta', 'N/A')}", expanded=False):
                        col_qtd, col_valor_total, col_valor_parcela = st.columns(3)
                        
                        with col_qtd:
                            qtd_parcelas = st.number_input(
                                "Quantidade de Parcelas",
                                min_value=1,
                                max_value=240,
                                value=parc.get('quantidade_parcelas') if parc.get('quantidade_parcelas') else None,
                                key=f"sispar_qtd_{idx}"
                            )
                        
                        with col_valor_total:
                            valor_total_str = st.text_input(
                                "Valor Total Parcelado (R$)",
                                value=parc.get('valor_total_parcelado') if parc.get('valor_total_parcelado') else "",
                                placeholder="R$ 1.234,56",
                                key=f"sispar_valor_total_{idx}"
                            )
                        
                        with col_valor_parcela:
                            valor_parcela_str = st.text_input(
                                "Valor da Parcela (R$)",
                                value=parc.get('valor_parcela') if parc.get('valor_parcela') else "",
                                placeholder="R$ 123,45",
                                key=f"sispar_valor_parcela_{idx}"
                            )
                        
                        competencias_str = st.text_area(
                            "Competências (1 por linha: MM/AAAA ou AAAA-MM)",
                            value="\n".join(parc.get('competencias', [])) if parc.get('competencias') else "",
                            placeholder="01/2025\n02/2025\n03/2025",
                            height=100,
                            key=f"sispar_competencias_{idx}"
                        )
                        
                        conferido = st.checkbox(
                            "Marcar como conferido pelo usuário",
                            value=parc.get('conferido_pelo_usuario', False),
                            key=f"sispar_conferido_{idx}"
                        )
                        
                        # NÃO atualiza o objeto aqui - será feito apenas quando o form for submetido
                        # Os valores são salvos automaticamente no session_state pelos inputs com key=

        # --- Conclusão e Responsável ---
        st.subheader("4. Finalização")
        bloco_conclusao = st.text_area(
            "Conclusão e Recomendações",
            value=(
                "Recomendamos a regularização imediata dos débitos listados para evitar inscrição em Dívida Ativa.\n"
                "Os parcelamentos ativos devem ser mantidos em dia."
            ),
            height=120
        )

        c_r1, c_r2, c_r3 = st.columns(3)
        with c_r1:
            responsavel_nome = st.text_input("Responsável Técnico", placeholder="Nome Completo")
        with c_r2:
            responsavel_cargo = st.text_input("Cargo", placeholder="Contador / Analista")
        with c_r3:
            responsavel_email = st.text_input("E-mail", placeholder="contato@empresa.com")

        # BOTÃO DE AÇÃO
        gerar = st.form_submit_button("🔨 Gerar Relatório Oficial", type="primary")

    # -------------------------------------------------------------------------
    # 3. PROCESSAMENTO E GERAÇÃO
    # -------------------------------------------------------------------------

    if gerar:
        # Validação simples
        erros = []
        if not periodo_referencia: erros.append("Período de Referência")
        if not requerente: erros.append("Requerente")
        if not cnpj: erros.append("CNPJ")
        
        if erros:
            st.error(f"Campos obrigatórios faltando: {', '.join(erros)}")
            return

        # Montagem do Dicionário Base
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

        # [CRÍTICO] INJEÇÃO DE DADOS ESTRUTURADOS (JSON SCHEMAS)
        # Se os parsers extraíram objetos complexos, passamos eles para o core/pdf_generator
        if resultado:
            if getattr(resultado, "sefaz_estadual", None):
                form_data["sefaz_estadual"] = resultado.sefaz_estadual
            
            if getattr(resultado, "fgts", None):
                form_data["fgts"] = resultado.fgts
            
            if getattr(resultado, "receita_federal", None):
                # Cria uma cópia profunda do receita_federal para não modificar o objeto original
                receita_federal_copy = copy.deepcopy(resultado.receita_federal) if isinstance(resultado.receita_federal, dict) else dict(resultado.receita_federal) if hasattr(resultado.receita_federal, '__dict__') else resultado.receita_federal
                
                # Garante que a estrutura pgfn_previdencia existe
                if not receita_federal_copy.get('pgfn_previdencia'):
                    receita_federal_copy['pgfn_previdencia'] = {}
                
                # Atualiza informações adicionais do PGFN Previdência do session_state (preenchido no form)
                # O valor foi salvo automaticamente no session_state pelo st.text_area com key=
                info_adicional = st.session_state.get('pgfn_prev_info_adicional', '')
                receita_federal_copy['pgfn_previdencia']['informacoes_adicionais_usuario'] = info_adicional if info_adicional else ''
                
                # Atualiza também os dados do SISPAR se foram preenchidos
                sispar = receita_federal_copy.get('sispar', {})
                if sispar.get('tem_sispar'):
                    parcelamentos = sispar.get('parcelamentos', [])
                    for idx, parc in enumerate(parcelamentos):
                        # Captura valores do session_state
                        qtd_key = f"sispar_qtd_{idx}"
                        valor_total_key = f"sispar_valor_total_{idx}"
                        valor_parcela_key = f"sispar_valor_parcela_{idx}"
                        competencias_key = f"sispar_competencias_{idx}"
                        conferido_key = f"sispar_conferido_{idx}"
                        
                        if qtd_key in st.session_state:
                            parc['quantidade_parcelas'] = st.session_state[qtd_key]
                        if valor_total_key in st.session_state:
                            parc['valor_total_parcelado'] = st.session_state[valor_total_key]
                        if valor_parcela_key in st.session_state:
                            parc['valor_parcela'] = st.session_state[valor_parcela_key]
                        if competencias_key in st.session_state:
                            comps = [c.strip() for c in st.session_state[competencias_key].split('\n') if c.strip()]
                            parc['competencias'] = comps
                        if conferido_key in st.session_state:
                            parc['conferido_pelo_usuario'] = st.session_state[conferido_key]
                            if st.session_state[conferido_key]:
                                parc['necessita_consulta_manual_pgfn'] = False
                                parc['observacao'] = "Informações preenchidas manualmente pelo usuário."
                
                # Garante que o objeto receita_federal tenha a estrutura completa atualizada
                form_data["receita_federal"] = receita_federal_copy

        # Processamento Final (Core)
        dados_finais = montar_dados_relatorio(form_data)
        
        # Geração dos Arquivos em Memória
        pdf_bytes = gerar_pdf_bytes(dados_finais)
        try:
            docx_bytes = gerar_docx_bytes(dados_finais)
        except Exception:
            docx_bytes = None # Fallback caso word_generator não esteja 100%

        # Feedback Visual
        st.balloons()
        st.success("Relatório gerado com sucesso!")

        # Área de Download
        st.subheader("📥 Downloads")
        
        col_down1, col_down2 = st.columns(2)
        
        nome_arquivo = f"Relatorio_Fiscal_{slugify(requerente)}_{slugify(periodo_referencia)}"
        
        with col_down1:
            st.download_button(
                label="📄 Baixar PDF (Com Tabelas)",
                data=pdf_bytes,
                file_name=f"{nome_arquivo}.pdf",
                mime="application/pdf"
            )
        
        with col_down2:
            if docx_bytes:
                st.download_button(
                    label="📝 Baixar Word (Editável)",
                    data=docx_bytes,
                    file_name=f"{nome_arquivo}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                st.warning("Geração de Word indisponível no momento.")

        # Pré-visualização rápida do texto
        with st.expander("Ver texto do relatório (Raw)"):
            st.text(gerar_texto_relatorio(dados_finais))

if __name__ == "__main__":
    main()