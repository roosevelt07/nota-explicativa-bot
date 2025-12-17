# src/pdf_generator.py
"""
Geração de PDFs do relatório, com tabelas desenhadas.
Suporta dados manuais e estruturados (IPVA, FGTS detalhado, etc.).

Características:
- Usa papel timbrado (assets/nota_explicativa_em_branco.png)
- Centraliza valores e textos
- Processa objetos complexos (sefaz_estadual, fgts)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, Any, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.pdfgen import canvas as rl_canvas


# ==============================================================================
# HELPERS DE FORMATAÇÃO
# ==============================================================================
def _fmt_moeda(valor) -> str:
    """Formata float ou str numérico para R$ X.XXX,XX"""
    if not valor:
        return "-"
    try:
        val_float = float(valor)
        return f"R$ {val_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(valor)


class PDFTemplate(SimpleDocTemplate):
    """Classe customizada para adicionar papel timbrado como imagem de fundo."""

    def __init__(self, *args, template_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.template_path = template_path

    def build(
        self,
        flowables,
        onFirstPage=None,
        onLaterPages=None,
        canvasmaker=rl_canvas.Canvas,
    ):
        def on_first_page(canvas, doc):
            self._draw_letterhead(canvas, doc)
            if onFirstPage:
                onFirstPage(canvas, doc)

        def on_later_pages(canvas, doc):
            self._draw_letterhead(canvas, doc)
            if onLaterPages:
                onLaterPages(canvas, doc)

        if canvasmaker is None:
            canvasmaker = rl_canvas.Canvas

        super().build(
            flowables,
            onFirstPage=on_first_page,
            onLaterPages=on_later_pages,
            canvasmaker=canvasmaker,
        )

    def _draw_letterhead(self, canvas, doc):
        if self.template_path and Path(self.template_path).exists():
            try:
                img_reader = ImageReader(str(self.template_path))
                canvas.saveState()
                canvas.drawImage(
                    img_reader,
                    0,
                    0,
                    width=self.pagesize[0],
                    height=self.pagesize[1],
                    preserveAspectRatio=False,
                    mask=None,
                )
                canvas.restoreState()
            except Exception:
                pass


def _make_table(data, col_widths=None, header_align="CENTER", data_align="CENTER"):
    """Cria uma tabela formatada padrão."""
    t = Table(data, colWidths=col_widths)
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("LINEBELOW", (0, 0), (-1, 0), 2, colors.black),
                ("ALIGN", (0, 0), (-1, 0), header_align),
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                ("ALIGN", (0, 1), (-1, -1), data_align),
                ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]
        )
    )
    return t


def gerar_pdf_bytes(dados: Dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    
    # Caminho para o template
    base_dir = Path(__file__).resolve().parent.parent
    template_path = base_dir / "assets" / "nota_explicativa_em_branco.png"

    doc = PDFTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=60,
        bottomMargin=60,
        template_path=str(template_path) if template_path.exists() else None,
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.spaceAfter = 4

    heading = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        spaceBefore=10,
        spaceAfter=4,
    )
    
    heading3 = ParagraphStyle(
        "Heading3",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        spaceBefore=8,
        spaceAfter=4,
    )

    story: list[Any] = []

    # ------------------------ CABEÇALHO ------------------------
    story.append(Paragraph(f"Data do relatório: {dados['data_relatorio']}", normal))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Requerente: {dados['requerente']}", normal))
    story.append(Paragraph(f"CNPJ: {dados['cnpj']}", normal))
    story.append(Paragraph(f"Tributação: {dados['tributacao']}", normal))
    story.append(Paragraph(f"Certificado Digital: {dados['certificado_digital']}", normal))
    story.append(Spacer(1, 8))

    intro = (
        "Este relatório tem como objetivo acompanhar os débitos pendentes relacionados à entidade "
        "empresarial destacada acima, destacando os principais pontos sobre a situação fiscal, os "
        "valores devidos, datas de vencimento e providências necessárias para regularização."
    )
    story.append(Paragraph(intro, normal))
    story.append(Spacer(1, 8))

    story.append(Paragraph("DÉBITOS IDENTIFICADOS", heading))
    story.append(Spacer(1, 8))

    # ========================= RECEITA FEDERAL =========================
    story.append(Paragraph("RECEITA FEDERAL", heading))
    
    # Total de Previdência (OBJETIVO 3) - SOMENTE o total, sem tabela completa
    from src.utils import formatar_total_previdencia
    texto_total_previdencia = formatar_total_previdencia(dados)
    story.append(Paragraph(f"<b>{texto_total_previdencia}</b>", normal))
    story.append(Spacer(1, 8))
        
        # PGFN Previdência (OBJETIVO 1)
        pgfn_previdencia = receita.get("pgfn_previdencia", {})
        if pgfn_previdencia.get("existe"):
            receitas_list = pgfn_previdencia.get("receitas", [])
            receitas_str = "; ".join(receitas_list) if receitas_list else "Não identificado"
            
            story.append(Paragraph("<b>PGFN Previdência</b>", normal))
            story.append(Paragraph(f"Receita: {receitas_str}", normal))
            
            info_adicional = pgfn_previdencia.get("informacoes_adicionais_usuario", "")
            if info_adicional and info_adicional.strip():
                # Quebra o texto em linhas se for muito longo
                story.append(Paragraph("<b>Informações adicionais:</b>", normal))
                # Divide em parágrafos se houver quebras de linha
                for linha in info_adicional.split('\n'):
                    if linha.strip():
                        story.append(Paragraph(linha.strip(), normal))
            else:
                # Se não houver informações, mostra "(não informado)"
                story.append(Paragraph("<b>Informações adicionais:</b> (não informado)", normal))
            
            story.append(Spacer(1, 6))
    
    story.append(Paragraph(dados["bloco_receita_federal"], normal))
    story.append(Paragraph(f"Data da consulta: {dados['data_consulta_rf']}", normal))
    story.append(Spacer(1, 10))

    # ========================= SEFAZ (ESTADUAL) =========================
    story.append(Paragraph("SEFAZ (Estadual)", heading))

    # 1. Consolida linhas manuais com linhas extraídas automaticamente
    tabela_sefaz_data = [["Descrição do Débito / Pendência", "Período / Placa", "Valor / Situação"]]
    
    linhas_finais = []
    
    # A) Adiciona linhas manuais (se houver)
    if dados.get("sefaz_rows"):
        linhas_finais.extend(dados["sefaz_rows"])

    # B) Adiciona dados estruturados do Parser SEFAZ (Schema Novo)
    if "sefaz_estadual" in dados and dados["sefaz_estadual"]:
        sefaz = dados["sefaz_estadual"]
        pendencias = sefaz.get("pendencias_identificadas", {})

        # IPVA
        for item in pendencias.get("ipva", []):
            desc = f"IPVA {item.get('exercicio', '')}"
            ref = item.get('placa', '')
            val = _fmt_moeda(item.get('valor_total', 0))
            linhas_finais.append([desc, ref, val])
            
        # Fronteira/Antecipado
        for item in pendencias.get("icms_fronteira_antecipado", []):
            desc = item.get('descricao', 'ICMS Antecipado')
            ref = item.get('periodo_referencia', '')
            val = _fmt_moeda(item.get('valor_total', 0))
            linhas_finais.append([desc, ref, val])

        # Competências em Aberto
        for item in pendencias.get("icms_competencias_aberto", []):
            desc = f"ICMS Omissão ({item.get('tipo_omissao', '')})"
            ref = item.get('periodo', '')
            val = _fmt_moeda(item.get('valor_estimado', 0))
            linhas_finais.append([desc, ref, val])

        # Autuações
        for item in pendencias.get("debitos_fiscais_autuacoes", []):
            desc = f"Autuação {item.get('natureza_debito', '')} - Proc: {item.get('numero_processo','')}"
            ref = "Exigível"
            val = _fmt_moeda(item.get('valor_consolidado', 0))
            linhas_finais.append([desc, ref, val])

    # Renderiza Tabela ou Mensagem "Sem Débitos"
    if linhas_finais:
        tabela_sefaz_data.extend(linhas_finais)
        story.append(
            _make_table(
                tabela_sefaz_data,
                col_widths=[220, 100, 100],
                data_align="CENTER",
            )
        )
    else:
        # Verifica se o parser identificou explicitamente como Regular
        status_geral = dados.get("sefaz_estadual", {}).get("cabecalho_documento", {}).get("situacao_geral", "")
        if "REGULAR" in status_geral.upper():
            story.append(Paragraph("✅ Situação REGULAR (Certidão Negativa Emitida).", normal))
        else:
            story.append(Paragraph("Sem débitos informados ou identificados.", normal))

    story.append(Paragraph(f"Data da consulta: {dados['data_consulta_sefaz']}", normal))
    story.append(Spacer(1, 10))

    # ==================== DÉBITOS MUNICIPAIS =================
    story.append(Paragraph("DÉBITOS MUNICIPAIS", heading))
    if dados.get("municipais_rows") and len(dados["municipais_rows"]) > 0:
        tabela_mun = [["Descrição do Débito", "Período", "Valor", "Status"]] + dados["municipais_rows"]
        story.append(
            _make_table(
                tabela_mun,
                col_widths=[180, 70, 90, 90],
                data_align="CENTER",
            )
        )
    else:
        story.append(Paragraph("Sem débitos informados.", normal))
    story.append(Paragraph(f"Data da consulta: {dados['data_consulta_municipal']}", normal))
    story.append(Spacer(1, 10))

    # ============================ FGTS ================================
    story.append(Paragraph("FGTS", heading))
    
    # Lógica Híbrida: Usa dados estruturados se disponíveis, senão usa texto bloco
    usou_estrutura_fgts = False
    if "fgts" in dados and dados["fgts"]:
        fgts_data = dados["fgts"]
        crf = fgts_data.get("crf_detalhes", {})
        pendencias = fgts_data.get("pendencias_financeiras", {})
        
        # Mostra detalhes estruturados se houver CRF
        if crf.get("numero_certificacao"):
            usou_estrutura_fgts = True
            
            # Monta uma tabelinha de resumo do Certificado
            status_cor = "REGULAR" if crf.get("situacao_atual") == "REGULAR" else "IRREGULAR"
            resumo_data = [
                ["Situação", "Validade", "Certificação"],
                [
                    status_cor,
                    f"{crf.get('validade_inicio','')} a {crf.get('validade_fim','')}",
                    crf.get("numero_certificacao", "-")
                ]
            ]
            story.append(_make_table(resumo_data, col_widths=[100, 160, 160]))
            story.append(Spacer(1, 6))
        
        # Tabela de Débitos do FGTS
        lista_debitos = pendencias.get("lista_debitos", [])
        if lista_debitos:
            tabela_fgts_data = [["Competência", "Valor", "Situação"]]
            for debito in lista_debitos:
                tabela_fgts_data.append([
                    debito.get("competencia", "-"),
                    _fmt_moeda(debito.get("valor_estimado", 0)),
                    debito.get("situacao", "EM ABERTO")
                ])
            story.append(_make_table(tabela_fgts_data, col_widths=[120, 120, 100], data_align="CENTER"))
            story.append(Spacer(1, 6))
        elif crf.get("situacao_atual") == "REGULAR":
            story.append(Paragraph("✅ Situação REGULAR - Não há débitos pendentes.", normal))
            story.append(Spacer(1, 6))

    # Adiciona o bloco de texto (que serve como fallback ou complemento explicativo)
    story.append(Paragraph(dados["bloco_fgts"], normal))
    story.append(Paragraph(f"Data da consulta: {dados['data_consulta_fgts']}", normal))
    story.append(Spacer(1, 12))

    # 👉 NOVA PÁGINA
    story.append(PageBreak())
    story.append(Spacer(1, 120)) # Espaço para o cabeçalho do timbrado na pag 2

    # ========================= PARCELAMENTOS =================
    story.append(Paragraph("PARCELAMENTOS", heading))
    
    # SISPAR - Nova estrutura com parcelamentos
    if "receita_federal" in dados and dados["receita_federal"]:
        receita = dados["receita_federal"]
        sispar = receita.get("sispar", {})
        
        if sispar.get("tem_sispar"):
            parcelamentos = sispar.get("parcelamentos", [])
            
            for idx, parc in enumerate(parcelamentos):
                story.append(Paragraph(f"Parcelamento SISPAR {idx + 1 if len(parcelamentos) > 1 else ''}", heading3))
                
                # Informações básicas extraídas do PDF
                linhas_info = []
                
                conta = parc.get("conta")
                tipo = parc.get("tipo")
                if conta:
                    if tipo:
                        linhas_info.append(Paragraph(f"<b>Conta:</b> {conta} {tipo}", normal))
                    else:
                        linhas_info.append(Paragraph(f"<b>Conta:</b> {conta}", normal))
                
                modalidade = parc.get("modalidade")
                if modalidade:
                    linhas_info.append(Paragraph(f"<b>Modalidade:</b> {modalidade}", normal))
                
                regime = parc.get("regime")
                if regime:
                    linhas_info.append(Paragraph(f"<b>Regime:</b> {regime}", normal))
                
                limite = parc.get("limite_maximo_meses")
                if limite:
                    linhas_info.append(Paragraph(f"<b>Limite máximo:</b> ATÉ {limite} MESES", normal))
                
                negociado = parc.get("negociado_no_sispar")
                if negociado is not None:
                    linhas_info.append(Paragraph(f"<b>Negociado no SISPAR:</b> {'SIM' if negociado else 'NÃO'}", normal))
                
                exigibilidade = parc.get("exigibilidade_suspensa")
                if exigibilidade is not None:
                    linhas_info.append(Paragraph(f"<b>Exigibilidade suspensa:</b> {'SIM' if exigibilidade else 'NÃO'}", normal))
                
                for linha in linhas_info:
                    story.append(linha)
                
                story.append(Spacer(1, 6))
                
                # Informações preenchidas manualmente (se houver)
                qtd_parcelas = parc.get("quantidade_parcelas")
                valor_total = parc.get("valor_total_parcelado")
                valor_parcela = parc.get("valor_parcela")
                competencias = parc.get("competencias", [])
                
                if qtd_parcelas or valor_total or valor_parcela or competencias:
                    story.append(Paragraph("<b>Informações preenchidas manualmente:</b>", normal))
                    linhas_manual = []
                    
                    if qtd_parcelas:
                        linhas_manual.append(Paragraph(f"<b>Quantidade de parcelas:</b> {qtd_parcelas}", normal))
                    if valor_total:
                        linhas_manual.append(Paragraph(f"<b>Valor total parcelado:</b> {valor_total}", normal))
                    if valor_parcela:
                        linhas_manual.append(Paragraph(f"<b>Valor da parcela:</b> {valor_parcela}", normal))
                    if competencias:
                        comps_str = ", ".join(competencias)
                        linhas_manual.append(Paragraph(f"<b>Competências:</b> {comps_str}", normal))
                    
                    linhas_manual.append(Paragraph("<b>Status:</b> INFORMADO PELO USUÁRIO", normal))
                    
                    for linha in linhas_manual:
                        story.append(linha)
                else:
                    # Observação de necessidade de consulta manual
                    observacao = parc.get("observacao", "O relatório da Receita Federal não informa quantidade de parcelas, valores ou competências; é necessária consulta manual ao PGFN/SISPAR.")
                    story.append(Paragraph(f"<b>Observação:</b> {observacao}", normal))
                    story.append(Paragraph("<b>Status:</b> NECESSITA CONSULTA MANUAL", normal))
                
                story.append(Spacer(1, 10))
    
    # Parcelamentos manuais
    parcelamentos_rows = dados.get("parcelamentos_rows") or []
    if parcelamentos_rows:
        story.append(Paragraph("Outros Parcelamentos", heading3))
        tabela_parc = [
            [
                "Parcelamento",
                "Valor Parcela",
                "Vencimento",
                "Qtd",
                "Atual",
            ]
        ] + parcelamentos_rows
        story.append(
            _make_table(
                tabela_parc,
                col_widths=[110, 100, 90, 60, 60],
                data_align="CENTER",
            )
        )
    elif not ("receita_federal" in dados and dados["receita_federal"] and dados["receita_federal"].get("sispar", {}).get("tem_sispar")):
        story.append(Paragraph("Não há parcelamentos informados.", normal))
    story.append(Spacer(1, 12))

    # ============================ CONCLUSÃO ===========================
    story.append(Paragraph("CONCLUSÃO", heading))
    for linha in dados["bloco_conclusao"].split("\n"):
        if linha.strip():
            story.append(Paragraph(linha.strip(), normal))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Eikon Soluções Ltda CNPJ: 09.502.539/0001-13", normal))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Atenciosamente,", normal))
    story.append(Spacer(1, 8))
    story.append(Paragraph(dados["responsavel_nome"], normal))
    story.append(Paragraph(dados["responsavel_cargo"], normal))
    story.append(Paragraph(f"e-mail: {dados['responsavel_email']}", normal))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()