import unittest
from unittest.mock import patch, AsyncMock
from app import (
    get_income_statements,
    get_balance_sheets,
    get_cash_flow_statements,
    get_current_stock_price,
    get_historical_stock_prices,
    get_company_news,
    get_stocks_from_search,
    get_intraday_historical_data,
)

class TestFinancialAPIFunctions(unittest.IsolatedAsyncioTestCase):

    @patch('app.make_request', new_callable=AsyncMock)
    async def test_get_income_statements(self, mock_make_request):
        mock_make_request.return_value = {
            "Financials": {
                "Income_Statement": {
                    "annual": {"2023": {"Revenue": 100}, "2022": {"Revenue": 90}}
                }
            }
        }
        result = await get_income_statements("AAPL")
        self.assertIn('"Revenue": 100', result)

    @patch('app.make_request', new_callable=AsyncMock)
    async def test_get_balance_sheets(self, mock_make_request):
        mock_make_request.return_value = {
            "Financials": {
                "Balance_Sheet": {
                    "annual": {"2023": {"Assets": 200}, "2022": {"Assets": 180}}
                }
            }
        }
        result = await get_balance_sheets("AAPL")
        self.assertIn('"Assets": 200', result)

    @patch('app.make_request', new_callable=AsyncMock)
    async def test_get_cash_flow_statements(self, mock_make_request):
        mock_make_request.return_value = {
            "Financials": {
                "Cash_Flow": {
                    "annual": {"2023": {"Operating_Cash_Flow": 120}, "2022": {"Operating_Cash_Flow": 110}}
                }
            }
        }
        result = await get_cash_flow_statements("AAPL")
        self.assertIn('"Operating_Cash_Flow": 120', result)

    @patch('app.make_request', new_callable=AsyncMock)
    async def test_get_current_stock_price(self, mock_make_request):
        mock_make_request.return_value = {"close": 150}
        result = await get_current_stock_price("AAPL")
        self.assertIn('"close": 150', result)

    @patch('app.make_request', new_callable=AsyncMock)
    async def test_get_historical_stock_prices(self, mock_make_request):
        mock_make_request.return_value = [{"date": "2023-06-14", "close": 150}]
        result = await get_historical_stock_prices("AAPL", "2023-06-01", "2023-06-14")
        self.assertIn('"date": "2023-06-14"', result)

    @patch('app.make_request', new_callable=AsyncMock)
    async def test_get_company_news(self, mock_make_request):
        mock_make_request.return_value = [{"title": "Apple launches new product"}]
        result = await get_company_news("AAPL")
        self.assertIn('"title": "Apple launches new product"', result)

    @patch('app.make_request', new_callable=AsyncMock)
    async def test_get_stocks_from_search(self, mock_make_request):
        mock_make_request.return_value = [{"symbol": "AAPL"}]
        result = await get_stocks_from_search("Apple")
        self.assertIn('"symbol": "AAPL"', result)

    @patch('app.make_request', new_callable=AsyncMock)
    async def test_get_intraday_historical_data(self, mock_make_request):
        mock_make_request.return_value = [{"datetime": "2023-06-14 15:30", "close": 150}]
        result = await get_intraday_historical_data("AAPL", interval="1m")
        self.assertIn('"datetime": "2023-06-14 15:30"', result)

if __name__ == '__main__':
    unittest.main()
