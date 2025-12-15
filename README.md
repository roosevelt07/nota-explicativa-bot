# Nota Explicativa Bot

Aplicativo Streamlit para geração de Relatórios de Acompanhamento de Débitos em PDF.

## Funcionalidades

- ✅ Geração de relatórios em PDF e Word com tabelas formatadas
- ✅ Formulário interativo para preenchimento de dados
- ✅ Suporte para débitos da Receita Federal, SEFAZ, Municípios e FGTS
- ✅ **Interpretadores robustos de PDF** para pré-preencher campos automaticamente:
  - Receita Federal: extrai CNPJ, nome da empresa, data de consulta e situação fiscal
  - FGTS: extrai data de consulta, período de validade e situação
  - SEFAZ: extrai CNPJ, data de consulta e débitos identificados (IPVA, ICMS, etc.)
- ✅ Gerenciamento de parcelamentos
- ✅ Pré-visualização do texto antes de gerar o PDF

## Instalação

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Como usar

1. Execute o aplicativo:
```bash
streamlit run app.py
```

2. **(Opcional)** Carregue PDFs oficiais para pré-preencher campos automaticamente:
   - Faça upload dos PDFs da Receita Federal, FGTS e/ou SEFAZ
   - Clique em "📥 Ler PDFs e pré-preencher campos"
   - Os campos serão preenchidos automaticamente quando possível

3. Preencha o formulário com os dados necessários:
   - **Dados principais**: Data do relatório, período de referência
   - **Dados da empresa**: Requerente, CNPJ, Tributação, Certificado Digital
   - **Consultas realizadas**: Datas das consultas aos órgãos
   - **Seções do relatório**: 
     - Receita Federal (texto)
     - SEFAZ (tabela - uma linha por débito)
     - Débitos Municipais (tabela - uma linha por débito)
     - FGTS (texto)
     - Parcelamentos (tabela - uma linha por parcelamento)
   - **Conclusão e responsável técnico**

4. Clique em "Gerar relatório"

5. Baixe o PDF ou Word gerado

## Formato das tabelas

As tabelas podem ser preenchidas separando as colunas por:
- Múltiplos espaços (2 ou mais): `IPVA     RCG-7G42     Em atraso`
- Tabs: `IPVA	RCG-7G42	Em atraso`
- Pipe (|): `IPVA | RCG-7G42 | Em atraso`

### Exemplos:

**SEFAZ** (3 colunas: Descrição, Período, Status):
```
IPVA     RCG-7G42     Em atraso
IPVA     RVJ-1A14     Em atraso
```

**Débitos Municipais** (4 colunas: Descrição, Período, Valor, Status):
```
CIM     2025     R$ 1.493,85     Em atraso
ISS     2024     R$ 2.500,00     Em atraso
```

**Parcelamentos** (5 colunas: Parcelamento, Valor, Vencimento, Qtd parcelas, Parcela atual):
```
SIMPLES NACIONAL     R$ 2.100,00     Último dia útil do mês     60     28
```

## Estrutura do projeto

```
.
├── app.py                 # Aplicativo principal Streamlit
├── requirements.txt       # Dependências do projeto
├── src/
│   ├── core.py           # Lógica de negócio e processamento de dados
│   ├── pdf_generator.py  # Geração de PDFs com tabelas formatadas
│   ├── word_generator.py # Geração de documentos Word (.docx)
│   ├── templates.py      # Templates de texto
│   └── parsers/          # Interpretadores robustos de PDF
│       ├── base.py       # Classe base ResultadoParsers
│       ├── receita_federal.py  # Parser para PDFs da Receita Federal
│       ├── fgts.py       # Parser para PDFs do FGTS
│       └── sefaz.py      # Parser para PDFs da SEFAZ
└── output/
    └── notas/            # PDFs gerados são salvos aqui
```

## Dependências

- `streamlit>=1.28.0` - Framework web para a interface
- `reportlab>=4.0.0` - Geração de PDFs
- `pdfplumber>=0.10.0` - Extração de texto e tabelas de PDFs
- `python-docx>=1.1.0` - Geração de documentos Word
- `Pillow>=10.0.0` - Processamento de imagens (papel timbrado)

## Notas

- Os PDFs gerados são salvos automaticamente em `output/notas/`
- Campos marcados com * são obrigatórios
- As tabelas no PDF são formatadas automaticamente com bordas e cabeçalhos destacados

