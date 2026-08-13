import unittest
from unittest.mock import MagicMock
from app.scrapers.co import ColoradoScraper

class TestColoradoScraper(unittest.TestCase):
    def test_click_best_result_direct_redirect(self):
        """Prueba que el scraper detecta redireccion directa por ID."""
        scraper = ColoradoScraper()
        mock_page = MagicMock()
        mock_page.url = "https://www.sos.state.co.us/biz/BusinessEntityDetail.do?quit=true"
        mock_page.inner_text.return_value = "algun contenido"
        
        result = scraper._click_best_result(mock_page, "20141242416")
        
        self.assertTrue(result)
        mock_page.query_selector_all.assert_not_called()

    def test_click_best_result_table(self):
        """Prueba que el scraper hace click en la tabla si se busca por nombre."""
        scraper = ColoradoScraper()
        mock_page = MagicMock()
        mock_page.url = "https://www.sos.state.co.us/biz/BusinessEntityCriteriaExt.do"
        mock_page.inner_text.return_value = "algun contenido"
        
        mock_link = MagicMock()
        mock_link.inner_text.return_value = "VOICES PARTNERS LLC"
        mock_page.query_selector_all.return_value = [mock_link]
        
        result = scraper._click_best_result(mock_page, "Voices Partners LLC")
        
        self.assertTrue(result)
        mock_link.click.assert_called_once()

if __name__ == "__main__":
    unittest.main()
