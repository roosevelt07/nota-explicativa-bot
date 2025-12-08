# src/pdf_generator.py
"""
Geração de PDFs do relatório, com tabelas desenhadas (SEFAZ, Débitos Municipais,
Parcelamentos).

Características:
- Usa papel timbrado (imagem de fundo) da pasta assets/
- Centraliza valores e textos em todas as tabelas
- Mantém dimensões A4 padrão
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, Any

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
    PageBreak,  # <-- para forçar quebra de página
)
from reportlab.pdfgen import canvas as rl_canvas


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
        """Sobrescreve build para adicionar papel timbrado como fundo em todas as páginas."""

        # Define funções que serão chamadas ao criar cada página
        def on_first_page(canvas, doc):
            # Desenha o papel timbrado como fundo
            self._draw_letterhead(canvas, doc)
            # Chama callback customizado se fornecido
            if onFirstPage:
                onFirstPage(canvas, doc)

        def on_later_pages(canvas, doc):
            # Desenha o papel timbrado como fundo em páginas subsequentes
            self._draw_letterhead(canvas, doc)
            # Chama callback customizado se fornecido
            if onLaterPages:
                onLaterPages(canvas, doc)

        # Garantia extra: se alguém chamar com canvasmaker=None, corrige aqui
        if canvasmaker is None:
            canvasmaker = rl_canvas.Canvas

        # Chama o build da classe pai com os callbacks customizados
        super().build(
            flowables,
            onFirstPage=on_first_page,
            onLaterPages=on_later_pages,
            canvasmaker=canvasmaker,
        )

    def _draw_letterhead(self, canvas, doc):
        """Desenha o papel timbrado como imagem de fundo."""
        if self.template_path and Path(self.template_path).exists():
            try:
                # Carrega a imagem do papel timbrado
                img_reader = ImageReader(str(self.template_path))

                # Salva o estado do canvas
                canvas.saveState()

                # Desenha a imagem cobrindo toda a página
                # No ReportLab, esta imagem será renderizada como fundo
                canvas.drawImage(
                    img_reader,
                    0,  # Coordenada X (canto esquerdo)
                    0,  # Coordenada Y (canto inferior)
                    width=self.pagesize[0],  # Largura da página
                    height=self.pagesize[1],  # Altura da página
                    preserveAspectRatio=False,
                    mask=None,
                )

                # Restaura o estado do canvas
                canvas.restoreState()
            except Exception:
                # Se houver erro, continua sem o papel timbrado
                # mas não interrompe a geração do PDF
                pass


def _make_table(data, col_widths=None, header_align="CENTER", data_align="CENTER"):
    """
    Cria uma tabela formatada com bordas e estilos apropriados.
    Valores e textos centralizados por padrão.

    Args:
        data: Lista de listas com os dados da tabela (primeira linha é o cabeçalho)
        col_widths: Lista com larguras das colunas
        header_align: Alinhamento do cabeçalho ("LEFT", "CENTER", "RIGHT")
        data_align: Alinhamento dos dados ("LEFT", "CENTER", "RIGHT")
    """
    t = Table(data, colWidths=col_widths)
    t.setStyle(
        TableStyle(
            [
                # Bordas
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("LINEBELOW", (0, 0), (-1, 0), 2, colors.black),
                # Alinhamento do cabeçalho - centralizado
                ("ALIGN", (0, 0), (-1, 0), header_align),
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                # Alinhamento dos dados - centralizado
                ("ALIGN", (0, 1), (-1, -1), data_align),
                ("VALIGN", (0, 1), (-1, -1), "MIDDLE"),
                # Fontes
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                # Espaçamento do cabeçalho
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                # Espaçamento dos dados
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                # Cor de fundo do cabeçalho
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]
        )
    )
    return t


def gerar_pdf_bytes(dados: Dict[str, Any]) -> bytes:
    """
    Gera o PDF em memória a partir do dicionário 'dados' montado em core.montar_dados_relatorio.

    Características:
    - Usa papel timbrado (nota_explicativa_em_branco.png) como imagem de fundo
    - Centraliza valores e textos em todas as tabelas
    - Formato A4 com margens adequadas
    """
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

    story: list[Any] = []

    # ------------------------ CABEÇALHO ------------------------
    story.append(Paragraph(f"Data do relatório: {dados['data_relatorio']}", normal))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Requerente: {dados['requerente']}", normal))
    story.append(Paragraph(f"CNPJ: {dados['cnpj']}", normal))
    story.append(Paragraph(f"Tributação: {dados['tributacao']}", normal))
    story.append(
        Paragraph(f"Certificado Digital: {dados['certificado_digital']}", normal)
    )
    story.append(Spacer(1, 8))

    intro = (
        "Este relatório tem como objetivo acompanhar os débitos pendentes relacionados à entidade "
        "empresarial destacada acima, destacando os principais pontos sobre a situação fiscal, os "
        "valores devidos, datas de vencimento e providências necessárias para regularização. Nos "
        "casos em que haja desacordo com os débitos e irregularidades apresentadas ou já tenha sido "
        "efetuado o pagamento, favor entrar em contato conosco para a resolução da pendência."
    )
    story.append(Paragraph(intro, normal))
    story.append(Spacer(1, 8))

    story.append(Paragraph("DÉBITOS IDENTIFICADOS", heading))
    story.append(
        Paragraph(
            "Abaixo, estão listados os débitos pendentes e a situação atual da empresa:",
            normal,
        )
    )
    story.append(Spacer(1, 8))

    # ========================= RECEITA FEDERAL =========================
    story.append(Paragraph("RECEITA FEDERAL", heading))
    story.append(Paragraph(dados["bloco_receita_federal"], normal))
    story.append(Paragraph(f"Data da consulta: {dados['data_consulta_rf']}", normal))
    story.append(Spacer(1, 10))

    # ========================= SEFAZ (TABELA) ==========================
    story.append(Paragraph("SEFAZ", heading))
    if dados.get("sefaz_rows") and len(dados["sefaz_rows"]) > 0:
        tabela_sefaz = [["Descrição do Débito", "Período", "Status"]] + dados[
            "sefaz_rows"
        ]
        story.append(
            _make_table(
                tabela_sefaz,
                col_widths=[220, 100, 100],
                data_align="CENTER",
            )
        )
    else:
        story.append(Paragraph("Sem débitos informados.", normal))
    story.append(Paragraph(f"Data da consulta: {dados['data_consulta_sefaz']}", normal))
    story.append(Spacer(1, 10))

    # ==================== DÉBITOS MUNICIPAIS (TABELA) =================
    story.append(Paragraph("DÉBITOS MUNICIPAIS", heading))
    if dados.get("municipais_rows") and len(dados["municipais_rows"]) > 0:
        tabela_mun = [["Descrição do Débito", "Período", "Valor", "Status"]] + dados[
            "municipais_rows"
        ]
        story.append(
            _make_table(
                tabela_mun,
                col_widths=[180, 70, 90, 90],
                data_align="CENTER",
            )
        )
    else:
        story.append(Paragraph("Sem débitos informados.", normal))
    story.append(
        Paragraph(f"Data da consulta: {dados['data_consulta_municipal']}", normal)
    )
    story.append(Spacer(1, 10))

    # ============================ FGTS ================================
    # ============================ FGTS ================================
    story.append(Paragraph("FGTS", heading))
    story.append(Paragraph(dados["bloco_fgts"], normal))
    story.append(Paragraph(f"Data da consulta: {dados['data_consulta_fgts']}", normal))
    story.append(Spacer(1, 12))

    # 👉 NOVA PÁGINA PARA PARCELAMENTOS + CONCLUSÃO
    story.append(PageBreak())

    # 👉 EMPURRA O CONTEÚDO PRA BAIXO PRA NÃO “BRIGAR” COM O TIMBRADO
    #    ajuste o 120 se quiser mais ou menos espaço (medida em pontos)
    story.append(Spacer(1, 120))

    # ========================= PARCELAMENTOS (TABELA) =================
    story.append(Paragraph("PARCELAMENTOS", heading))
    parcelamentos_rows = dados.get("parcelamentos_rows") or []
    if parcelamentos_rows:
        tabela_parc = [
            [
                "Parcelamento",
                "Valor aproximado das parcelas",
                "Vencimento",
                "Qtd de parcelas",
                "Parcela atual",
            ]
        ] + parcelamentos_rows
        story.append(
            _make_table(
                tabela_parc,
                col_widths=[100, 120, 90, 80, 80],
                data_align="CENTER",
            )
        )
    else:
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
