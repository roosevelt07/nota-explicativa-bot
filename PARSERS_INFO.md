# Informações sobre os Interpretadores de PDF

## Como Funcionam os Parsers

Os interpretadores de PDF foram desenvolvidos para serem **robustos e flexíveis**, mas têm algumas limitações importantes:

### ✅ O que os parsers conseguem fazer:

1. **Extrair texto de PDFs** usando `pdfplumber`
   - Funciona com PDFs baseados em texto (não apenas imagens)
   - Tenta extrair de tabelas quando o texto direto não está disponível

2. **Buscar informações usando múltiplos padrões regex**
   - CNPJ: reconhece vários formatos (com/sem espaços, com/sem formatação)
   - Datas: múltiplos formatos e padrões de busca
   - Nomes/Razão Social: diferentes variações de campos
   - Situação fiscal: identifica regularidade ou débitos

3. **Tolerância a variações**
   - Espaços extras no CNPJ (ex: `27.363 .271 / 0001-68`)
   - Diferentes formatos de data
   - Variações de nomenclatura (ex: "Inscrição" vs "CNPJ")

### ⚠️ Limitações:

1. **PDFs baseados em imagem (escaneados)**
   - ❌ Não funcionam diretamente - precisariam de OCR (Optical Character Recognition)
   - ✅ Solução: usar ferramentas como Tesseract OCR antes do parser

2. **PDFs com layout muito diferente**
   - Se o formato do PDF mudar completamente, os padrões regex podem não funcionar
   - ✅ Solução: adicionar novos padrões ao parser

3. **PDFs protegidos ou criptografados**
   - ❌ Não conseguem extrair texto de PDFs protegidos por senha
   - ✅ Solução: remover proteção antes de processar

4. **PDFs com texto em colunas complexas**
   - Pode ter dificuldade se o texto estiver em múltiplas colunas não estruturadas
   - ✅ Solução: melhorar a lógica de extração de tabelas

## Exemplos de PDFs que funcionam bem:

✅ **CND FGTS** (como o exemplo fornecido)
- Extrai: CNPJ, Razão Social, Validade, Data da consulta

✅ **CND SEFAZ** (como o exemplo fornecido)
- Extrai: CNPJ, Data de Emissão, Situação

✅ **Certidões da Receita Federal**
- Extrai: CNPJ, Nome da empresa, Data, Situação fiscal

## Como melhorar ainda mais:

Se você encontrar PDFs que não estão sendo lidos corretamente:

1. **Adicione novos padrões regex** nos arquivos de parser
2. **Teste com diferentes formatos** e ajuste conforme necessário
3. **Use OCR** para PDFs escaneados (requer biblioteca adicional)

## Estrutura dos Parsers:

```
src/parsers/
├── base.py              # Classe ResultadoParsers (armazena dados extraídos)
├── receita_federal.py   # Parser para RFB
├── fgts.py              # Parser para FGTS
└── sefaz.py             # Parser para SEFAZ
```

Cada parser:
- Tenta extrair informações usando múltiplos padrões
- Não quebra o app se houver erro
- Retorna dados parciais mesmo se não conseguir extrair tudo

