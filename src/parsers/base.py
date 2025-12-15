# src/parsers/base.py
"""
Estruturas básicas para armazenar e mesclar resultados dos parsers de PDF.

A ideia é:
- Cada parser (Receita, FGTS, SEFAZ, etc.) preenche alguns campos deste dataclass.
- No final, usamos `ResultadoParsers.mesclar_no_dados(dados)` para jogar
  automaticamente esses valores dentro do dicionário `dados` usado na
  geração do relatório (PDF/Word).

Todos os campos são opcionais. Se um parser não conseguir extrair algo,
simplesmente deixa como None ou lista/dicionário vazio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class ResultadoParsers:
    """
    Armazena os dados extraídos dos PDFs pelos parsers.

    Campos principais:
    - Dados da empresa (requerente, cnpj)
    - Datas de consulta (RF, SEFAZ, FGTS)
    - Blocos de texto (Receita Federal, FGTS) - LEGADO
    - Linhas de tabelas (SEFAZ, Municipais, Parcelamentos) - LEGADO
    - NOVAS ESTRUTURAS (fgts, sefaz_estadual) - OTIMIZADO
    """

    # ------------------------------------------------------------------
    # DADOS BÁSICOS DA EMPRESA (LEGADO)
    # ------------------------------------------------------------------
    requerente: Optional[str] = None
    cnpj: Optional[str] = None

    # ------------------------------------------------------------------
    # DATAS DE CONSULTA (STRING NO FORMATO DD/MM/AAAA) (LEGADO)
    # ------------------------------------------------------------------
    data_consulta_rf: Optional[str] = None
    data_consulta_sefaz: Optional[str] = None
    data_consulta_fgts: Optional[str] = None

    # ------------------------------------------------------------------
    # BLOCOS DE TEXTO PARA O RELATÓRIO (LEGADO)
    # ------------------------------------------------------------------
    bloco_receita_federal: Optional[str] = None
    bloco_fgts: Optional[str] = None

    # ------------------------------------------------------------------
    # LINHAS DE TABELAS (LISTA DE LISTAS DE STRINGS) (LEGADO)
    # ------------------------------------------------------------------
    sefaz_rows: List[List[str]] = field(default_factory=list)
    municipais_rows: List[List[str]] = field(default_factory=list)
    parcelamentos_rows: List[List[str]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # NOVAS ESTRUTURAS HIERÁRQUICAS (SCHEMA OTIMIZADO)
    # ------------------------------------------------------------------
    sefaz_estadual: Dict[str, Any] = field(default_factory=dict)
    fgts: Dict[str, Any] = field(default_factory=dict)
    receita_federal: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # MÉTODOS AUXILIARES
    # ------------------------------------------------------------------
    def _tem_lista(self, nome_campo: str) -> bool:
        """
        Retorna True se o campo de lista existir e não estiver vazio.
        """
        valor = getattr(self, nome_campo, None)
        return isinstance(valor, list) and len(valor) > 0

    def tem_algum_dado(self) -> bool:
        """
        Indica se pelo menos um dos campos foi preenchido por algum parser.
        Útil para saber se a leitura dos PDFs realmente extraiu algo.
        """
        # Verifica campos simples
        campos_simples = [
            "requerente",
            "cnpj",
            "data_consulta_rf",
            "data_consulta_sefaz",
            "data_consulta_fgts",
            "bloco_receita_federal",
            "bloco_fgts",
        ]
        if any(getattr(self, campo, None) for campo in campos_simples):
            return True

        # Verifica listas (LEGADO)
        listas = ["sefaz_rows", "municipais_rows", "parcelamentos_rows"]
        if any(self._tem_lista(nome) for nome in listas):
            return True
            
        # Verifica novas estruturas (OTIMIZADO)
        if self.sefaz_estadual or self.fgts:
            return True

        return False

    # ------------------------------------------------------------------
    # MESCLAGEM COM O DICIONÁRIO PRINCIPAL DO RELATÓRIO
    # ------------------------------------------------------------------
    def mesclar_no_dados(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mescla os dados extraídos nos campos do dicionário 'dados'.
        
        Regra:
        - Campos simples (str): só sobrescrevem se não forem None ou string vazia.
        - Listas (tabelas): só sobrescrevem se tiverem pelo menos 1 linha.
        - Dicionários (schemas): só sobrescrevem se não estiverem vazios.
        """

        def aplica_simples(campo_pdf: str, campo_dados: Optional[str] = None) -> None:
            chave = campo_dados or campo_pdf
            valor = getattr(self, campo_pdf, None)
            if isinstance(valor, str):
                if valor.strip():
                    dados[chave] = valor
            elif valor is not None:
                # Permite outros tipos simples
                dados[chave] = valor

        def aplica_lista(campo_pdf: str, campo_dados: Optional[str] = None) -> None:
            chave = campo_dados or campo_pdf
            valor = getattr(self, campo_pdf, None)
            if isinstance(valor, list) and len(valor) > 0:
                dados[chave] = valor
        
        # --- EXECUÇÃO DA MESCLAGEM ---

        # 1. Campos simples (LEGADO)
        aplica_simples("requerente")
        aplica_simples("cnpj")
        aplica_simples("data_consulta_rf")
        aplica_simples("data_consulta_sefaz")
        aplica_simples("data_consulta_fgts")
        aplica_simples("bloco_receita_federal")
        aplica_simples("bloco_fgts")

        # 2. Listas / tabelas (LEGADO)
        aplica_lista("sefaz_rows")
        aplica_lista("municipais_rows")
        aplica_lista("parcelamentos_rows")
        
        # 3. NOVAS ESTRUTURAS HIERÁRQUICAS (OTIMIZADO)
        if self.sefaz_estadual:
            # Mescla o objeto SEFAZ no dicionário principal
            dados["sefaz_estadual"] = self.sefaz_estadual
            
        if self.fgts:
            # Mescla o objeto FGTS no dicionário principal
            dados["fgts"] = self.fgts
        
        if self.receita_federal:
            # Mescla o objeto Receita Federal no dicionário principal
            dados["receita_federal"] = self.receita_federal

        return dados