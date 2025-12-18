# tests/test_parsers.py
"""
Testes unitários para os parsers (SEFAZ, Receita/PGFN).
Garante que nunca retornem situacao=None e que detectem corretamente REGULAR/IRREGULAR/INDETERMINADO.
"""

import unittest
from src.parsers.sefaz import processar_sefaz
from src.parsers.receita_federal import processar_receita
from src.utils import safe_str, normalize_text


class TestSEFAZParser(unittest.TestCase):
    """Testes para o parser SEFAZ."""
    
    def test_sefaz_irregularidades(self):
        """Testa detecção de IRREGULARIDADES."""
        texto = "O documento contém IRREGULARIDADES fiscais. Há débitos pendentes."
        tabelas = []
        resultado = processar_sefaz(texto, tabelas)
        
        self.assertEqual(resultado['situacao'], 'IRREGULAR')
        self.assertIsNotNone(resultado['situacao'])
        self.assertIn('irregularidades', resultado['motivos'][0].lower())
    
    def test_sefaz_regularidade(self):
        """Testa detecção de REGULARIDADE."""
        texto = "CERTIDÃO DE REGULARIDADE FISCAL. Situação REGULAR. Nada consta."
        tabelas = []
        resultado = processar_sefaz(texto, tabelas)
        
        self.assertEqual(resultado['situacao'], 'REGULAR')
        self.assertIsNotNone(resultado['situacao'])
    
    def test_sefaz_indeterminado(self):
        """Testa retorno INDETERMINADO quando não há match."""
        texto = "Documento genérico sem informações claras sobre situação fiscal."
        tabelas = []
        resultado = processar_sefaz(texto, tabelas)
        
        self.assertEqual(resultado['situacao'], 'INDETERMINADO')
        self.assertIsNotNone(resultado['situacao'])
        self.assertIn('não corresponde', resultado['motivos'][0].lower())


class TestReceitaParser(unittest.TestCase):
    """Testes para o parser Receita/PGFN."""
    
    def test_receita_siefpar_atraso(self):
        """Testa detecção de SIEFPAR com parcelas em atraso."""
        texto = """
        Pendência - Parcelamento (SIEFPAR)
        Parcelas em Atraso: 1
        Valor em Atraso: 571,90
        """
        resultado = processar_receita(texto, [])
        
        # Verifica que detectou parcelamento
        self.assertTrue(resultado['simples_nacional']['parcelamento']['tem_parcelamento'])
        self.assertEqual(resultado['simples_nacional']['parcelamento']['parcelas_atraso'], 1)
        self.assertAlmostEqual(resultado['simples_nacional']['parcelamento'].get('valor_atraso', 0), 571.90, places=2)
        self.assertTrue(resultado['simples_nacional']['tem_debito_em_aberto'])
    
    def test_receita_sem_atraso(self):
        """Testa caso sem atraso (REGULAR)."""
        texto = "Não foram detectadas pendências. Situação regular."
        resultado = processar_receita(texto, [])
        
        # Não deve ter débitos em aberto
        self.assertFalse(resultado['simples_nacional']['tem_debito_em_aberto'])


class TestUtils(unittest.TestCase):
    """Testes para funções utilitárias."""
    
    def test_safe_str_none(self):
        """Testa safe_str com None."""
        self.assertEqual(safe_str(None), "")
        self.assertEqual(safe_str(""), "")
    
    def test_safe_str_valor(self):
        """Testa safe_str com valores."""
        self.assertEqual(safe_str("teste"), "teste")
        self.assertEqual(safe_str(123), "123")
    
    def test_normalize_text(self):
        """Testa normalize_text."""
        texto = "  Teste   com   espaços  \n\n\n múltiplos  "
        resultado = normalize_text(texto)
        self.assertNotIn("   ", resultado)  # Não deve ter espaços triplos
        self.assertIn("Teste", resultado)


if __name__ == '__main__':
    unittest.main()

