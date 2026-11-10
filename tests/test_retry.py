import unittest
from unittest.mock import patch, MagicMock

from yfinance.data import YfData
from yfinance.exceptions import YFRateLimitError

URL = "https://query2.finance.yahoo.com/v8/finance/chart/AAPL"


def resposta_falsa(status):
    """Cria um objeto que finge ser uma resposta HTTP do Yahoo."""
    r = MagicMock()
    r.status_code = status
    r.url = URL
    return r


@patch("yfinance.data._time.sleep")          # não espera de verdade no teste
class TestRetryRateLimit(unittest.TestCase):

    def setUp(self):
        self.data = YfData()

    def test_sucesso_na_primeira_tentativa(self, mock_sleep):
        """Sem 429: faz 1 requisição e não espera nada."""
        with patch.object(YfData, "_make_request",
                          return_value=resposta_falsa(200)) as mock_req:
            r = self.data.get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mock_req.call_count, 1)
        mock_sleep.assert_not_called()

    def test_recupera_apos_429(self, mock_sleep):
        """429, 429, depois 200: deve tentar 3 vezes e retornar sucesso."""
        respostas = [resposta_falsa(429), resposta_falsa(429), resposta_falsa(200)]
        with patch.object(YfData, "_make_request",
                          side_effect=respostas) as mock_req:
            r = self.data.get(URL, max_retries=3)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mock_req.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_esgota_tentativas_e_lanca_erro(self, mock_sleep):
        """Sempre 429: deve tentar 3 vezes e então lançar YFRateLimitError."""
        with patch.object(YfData, "_make_request",
                          return_value=resposta_falsa(429)) as mock_req:
            with self.assertRaises(YFRateLimitError):
                self.data.get(URL, max_retries=3)
        self.assertEqual(mock_req.call_count, 3)

    def test_recupera_apos_429_no_crumb(self, mock_sleep):
        """429 na busca do crumb (exceção), depois 200: deve se recuperar."""
        with patch.object(YfData, "_make_request",
                          side_effect=[YFRateLimitError(), resposta_falsa(200)]) as mock_req:
            r = self.data.get(URL, max_retries=3)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mock_req.call_count, 2)

    def test_espera_cresce_exponencialmente(self, mock_sleep):
        """Os tempos de espera devem aumentar a cada tentativa."""
        with patch.object(YfData, "_make_request",
                          return_value=resposta_falsa(429)):
            with self.assertRaises(YFRateLimitError):
                self.data.get(URL, max_retries=4)
        esperas = [c.args[0] for c in mock_sleep.call_args_list]
        self.assertTrue(esperas[0] < esperas[1] < esperas[2])


if __name__ == "__main__":
    unittest.main()