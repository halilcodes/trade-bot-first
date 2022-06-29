import json
import pprint

import requests
import websocket
import threading
from keys import *
import logging
import typing
from models import Contract

logger = logging.getLogger()


class BinanceFuturesClient:
    def __init__(self, public_key: str, secret_key: str, testnet: bool):
        if testnet:
            self._base_url = "https://testnet.binancefuture.com"
            self._wss_url = "wss://testnet.binancefuture.com/ws"
            self.connection_type = "Testnet"
        else:
            self._base_url = "https://fapi.binance.com"
            self._wss_url = "wss://fstream.binance.com/ws"
            self.connection_type = "Real Account"

        self.platform = "binance_futures"
        self._public_key = public_key
        self._secret_key = secret_key
        self._header = {"X-MBX-APIKEY": self._secret_key}
        self.connection_trials = 0

        self.maker_commission: float
        self.taker_commission: float

        self.contracts = dict()

    def make_get_request(self, endpoint: str, params: dict) -> typing.Union[dict, None]:
        """
        :param endpoint: depending on request type, will be copied from documentation.
        :param params: will be sent as a query string, pass dict() if not required.
        :return:
        """
        complete_url = self._base_url + endpoint

        response = requests.get(complete_url, params, headers=self._header)
        code = response.status_code
        if code // 100 == 5:
            while self.connection_trials < 5:
                print("Binance Futures Client | Internal error... sending new request.")
                self.make_get_request(endpoint, params)
                self.connection_trials += 1
            print("Binance Futures Client | 5 requests in a row returned 5xx error code."
                  " Check server integrity.")

        if self.is_request_good(response):
            self.connection_trials = 0
            return response.json()
        else:
            return None

    def is_request_good(self, response) -> bool:
        code = response.status_code
        if code == 200:
            print("Binance Futures Client | Request sent successfully. ")
            self.connection_trials = 0
            return True
        elif code == 429:
            print("Binance Futures Client | Request limit has broken. ")
        elif code == 418:
            print("Binance Futures Client | IP has been auto-banned for continuing to send requests"
                  " after receiving 429 codes. ")
        elif code // 100 == 4:
            print("Binance Futures Client | 4xx code error, malformed request. ")
        return False

    def check_api_connection(self):
        _ = self.make_get_request("/fapi/v1/ping", dict())
        get_server_time = self.make_get_request("/fapi/v1/time", dict())
        if get_server_time:
            print(f"Binance Futures Client | API is connected. Current server time: {get_server_time['serverTime']}")
        else:
            print("Binance Futures Client | API Connection Failure. ")

    def get_current_commissions(self):
        return

    def get_base_assets(self) -> list:
        exchange_info = self.make_get_request("/fapi/v1/exchangeInfo", dict())
        assets = [asset['asset'] for asset in exchange_info['assets']]
        return assets

    def get_current_contracts(self) -> typing.Dict[str, Contract]:
        exchange_info = self.make_get_request("/fapi/v1/exchangeInfo", dict())
        assets = self.get_base_assets()
        contract_dict = dict()
        for contract in exchange_info['symbols']:
            if contract['contractType'] == "PERPETUAL" and contract['status'] == "TRADING" \
                    and contract['quoteAsset'] in assets:
                symbol = contract['symbol']
                contract_dict[symbol] = Contract("binance_futures", contract)
        if contract_dict is not None:
            return contract_dict

    def get_last_trade_info(self, contract: Contract, count=1) -> dict:
        symbol = contract.symbol
        endpoint = "/fapi/v1/trades"
        params = {'symbol': symbol, 'limit': count}
        response = self.make_get_request(endpoint, params)
        response = response[0]
        last_trade = {"price": float(response['price']),
                      "quantity": float(response['qty']),
                      "time": int(response['time']),
                      "buyer_filled": bool(response['isBuyerMaker'])}
        return last_trade


if __name__ == '__main__':
    binance = BinanceFuturesClient(BINANCE_TESTNET_API_PUBLIC, BINANCE_TESTNET_API_SECRET, testnet=True)
    contracts = binance.get_current_contracts()
    # print(f"platform: {contracts['BTCUSDT'].platform} | type: {type(contracts['BTCUSDT'].platform)}")
    # print(f"symbol: {contracts['BTCUSDT'].symbol} | type: {type(contracts['BTCUSDT'].symbol)}")
    # print(f"base_asset: {contracts['BTCUSDT'].base_asset} | type: {type(contracts['BTCUSDT'].base_asset)}")
    # print(f"quote_asset: {contracts['BTCUSDT'].quote_asset} | type: {type(contracts['BTCUSDT'].quote_asset)}")
    # print(f"margin_asset: {contracts['BTCUSDT'].margin_asset} | type: {type(contracts['BTCUSDT'].margin_asset)}")
    # print(f"margin_percent: {contracts['BTCUSDT'].margin_percent} | type: {type(contracts['BTCUSDT'].margin_percent)}")
    # print(f"price_precision: {contracts['BTCUSDT'].price_precision} | type: {type(contracts['BTCUSDT'].price_precision)}")
    # print(f"quantity_precision: {contracts['BTCUSDT'].quantity_precision} | type: {type(contracts['BTCUSDT'].quantity_precision)}")
    # print(f"tick_size: {contracts['BTCUSDT'].tick_size} | type: {type(contracts['BTCUSDT'].tick_size)}")
    # print(f"lot_size: {contracts['BTCUSDT'].lot_size} | type: {type(contracts['BTCUSDT'].lot_size)}")
    # print(f"max_order_limit: {contracts['BTCUSDT'].max_order_limit} | type: {type(contracts['BTCUSDT'].max_order_limit)}")
    # print(f"order_types: {contracts['BTCUSDT'].order_types} | type: {type(contracts['BTCUSDT'].order_types)}")
    # print(f"time_in_forces: {contracts['BTCUSDT'].time_in_forces} | type: {type(contracts['BTCUSDT'].time_in_forces)}")
    pprint.pprint(binance.get_last_trade_info(contracts['BTCUSDT'], 10))
    print("*" * 20)
    pprint.pprint(binance.get_last_trade_info(contracts['BTCUSDT']))
