# src/word_generator.py
"""
Geração de arquivo Word (.docx) do relatório, usando o mesmo dicionário 'dados'
do PDF (montado em core.montar_dados_relatorio).

Objetivo:
- Replicar o conteúdo do PDF (seções, textos e tabelas);
- Gerar um arquivo de 1–2 páginas, sem exagero de quebras;
- Incluir o papel timbrado como imagem no topo do documento.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, Any

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH


def _configurar_estilo_normal(doc: Document) -> None:
    """Configura o estilo padrão do documento."""
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)


def _add_heading(doc: Document, text: str) -> None:
    """Adiciona um título de seção, equivalente aos headings do PDF."""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(12)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT


def _add_paragrafo(doc: Document, text: str) -> None:
    """Parágrafo padrão."""
    if not text:
        return
    p = doc.add_paragraph(text)
    for run in p.runs:
        run.font.size = Pt(11)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT


def _add_table(doc: Document, headers, rows):
    """Tabela simples com cabeçalho em negrito."""
    if not rows:
        return

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"

    # Cabeçalho
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h

    for cell in hdr_cells:
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
                run.font.size = Pt(10)

    # Linhas de dados
    for row in rows:
        row_cells = table.add_row().cells
        for i, value in enumerate(row):
            row_cells[i].text = str(value)
        for cell in row_cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(10)

    # Espaço após a tabela
    doc.add_paragraph("")


def _add_papel_timbrado_topo(doc: Document) -> None:
    """
    Adiciona o papel timbrado como imagem no topo do documento (antes do texto).
    Usa o mesmo arquivo do PDF: assets/nota_explicativa_em_branco.png
    """
    base_dir = Path(__file__).resolve().parent.parent
    template_path = base_dir / "assets" / "nota_explicativa_em_branco.png"

    if not template_path.exists():
        return

    # Usa a largura útil da página (largura menos margens) para a imagem
    section = doc.sections[0]
    largura_util = section.page_width - section.left_margin - section.right_margin

    # add_picture aceita o valor em EMU (page_width já está em EMU)
    doc.add_picture(str(template_path), width=largura_util)
    # Pequeno espaço depois da imagem
    doc.add_paragraph("")


def gerar_docx_bytes(dados: Dict[str, Any]) -> bytes:
    """
    Gera o arquivo .docx em memória a partir do dicionário 'dados'.
    Retorna os bytes do arquivo para uso no st.download_button.
    """
    doc = Document()
    _configurar_estilo_normal(doc)

    # Papel timbrado no topo
    _add_papel_timbrado_topo(doc)

    # ======================= CABEÇALHO / DADOS BÁSICOS =======================

    _add_paragrafo(doc, f"Data do relatório: {dados['data_relatorio']}")
    _add_paragrafo(doc, f"Requerente: {dados['requerente']}")
    _add_paragrafo(doc, f"CNPJ: {dados['cnpj']}")
    _add_paragrafo(doc, f"Tributação: {dados['tributacao']}")
    _add_paragrafo(doc, f"Certificado Digital: {dados['certificado_digital']}")
    doc.add_paragraph("")

    intro = (
        "Este relatório tem como objetivo acompanhar os débitos pendentes relacionados à entidade "
        "empresarial destacada acima, destacando os principais pontos sobre a situação fiscal, os "
        "valores devidos, datas de vencimento e providências necessárias para regularização. Nos "
        "casos em que haja desacordo com os débitos e irregularidades apresentadas ou já tenha sido "
        "efetuado o pagamento, favor entrar em contato conosco para a resolução da pendência."
    )
    _add_paragrafo(doc, intro)
    doc.add_paragraph("")

    _add_heading(doc, "DÉBITOS IDENTIFICADOS")
    _add_paragrafo(
        doc,
        "Abaixo, estão listados os débitos pendentes e a situação atual da empresa:",
    )
    doc.add_paragraph("")

    # ========================= RECEITA FEDERAL =========================

    _add_heading(doc, "RECEITA FEDERAL")
    _add_paragrafo(doc, dados.get("bloco_receita_federal", ""))
    _add_paragrafo(doc, f"Data da consulta: {dados['data_consulta_rf']}")
    doc.add_paragraph("")

    # ============================= SEFAZ ==============================

    _add_heading(doc, "SEFAZ")
    sefaz_rows = dados.get("sefaz_rows") or []
    if sefaz_rows:
        _add_table(
            doc,
            ["Descrição do Débito", "Período", "Status"],
            sefaz_rows,
        )
    else:
        _add_paragrafo(doc, "Sem débitos informados.")
    _add_paragrafo(doc, f"Data da consulta: {dados['data_consulta_sefaz']}")
    doc.add_paragraph("")

    # ======================= DÉBITOS MUNICIPAIS =======================

    _add_heading(doc, "DÉBITOS MUNICIPAIS")
    municipais_rows = dados.get("municipais_rows") or []
    if municipais_rows:
        _add_table(
            doc,
            ["Descrição do Débito", "Período", "Valor", "Status"],
            municipais_rows,
        )
    else:
        _add_paragrafo(doc, "Sem débitos informados.")
    _add_paragrafo(doc, f"Data da consulta: {dados['data_consulta_municipal']}")
    doc.add_paragraph("")

    # =============================== FGTS =============================

    _add_heading(doc, "FGTS")
    _add_paragrafo(doc, dados.get("bloco_fgts", ""))
    _add_paragrafo(doc, f"Data da consulta: {dados['data_consulta_fgts']}")
    doc.add_paragraph("")

    # =========================== PARCELAMENTOS ========================

    _add_heading(doc, "PARCELAMENTOS")
    parcelamentos_rows = dados.get("parcelamentos_rows") or []
    if parcelamentos_rows:
        _add_table(
            doc,
            [
                "Parcelamento",
                "Valor aproximado das parcelas",
                "Vencimento",
                "Qtd de parcelas",
                "Parcela atual",
            ],
            parcelamentos_rows,
        )
    else:
        _add_paragrafo(doc, "Não há parcelamentos informados.")
    doc.add_paragraph("")

    # ============================= CONCLUSÃO ==========================

    _add_heading(doc, "CONCLUSÃO")
    for linha in dados.get("bloco_conclusao", "").split("\n"):
        if linha.strip():
            _add_paragrafo(doc, linha.strip())
    doc.add_paragraph("")

    _add_paragrafo(doc, "Eikon Soluções Ltda CNPJ: 09.502.539/0001-13")
    doc.add_paragraph("")
    _add_paragrafo(doc, "Atenciosamente,")
    doc.add_paragraph("")
    _add_paragrafo(doc, dados.get("responsavel_nome", ""))
    _add_paragrafo(doc, dados.get("responsavel_cargo", ""))
    _add_paragrafo(doc, f"e-mail: {dados.get('responsavel_email', '')}")

    # ========================= SAÍDA EM MEMÓRIA =======================

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()
