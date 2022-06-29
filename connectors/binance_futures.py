import json

import requests
import websocket
import threading
from keys import *
import logging
import typing

logger = logging.getLogger()


class BinanceFuturesClient:
    def __init__(self, public_key: str, secret_key: str, testnet: bool):
        if testnet:
            self._base_url = "https://testnet.binancefuture.com"
            self._wss_url = "wss://testnet.binancefuture.com/ws"
            self.connection_type = "Testnet"
        else:
            self._base_url = "https://fapi.binance.com"
            self._wss_url = "wss://fsrteam.binance.com/ws"
            self.connection_type = "Real Account"

        self._public_key = public_key
        self._secret_key = secret_key

        self.connection_trials = 0

    def make_get_request(self, endpoint: str, params: dict):
        """
        :param endpoint: depending on request type, will be copied from documentation.
        :param params: will be sent as a query string
        :return:
        """
        complete_url = self._base_url + endpoint

        response = requests.get(complete_url, params)
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
        print(f"Binance Futures Client | API is connected. Current server time: {get_server_time['serverTime']}")

    def get_current_contracts(self):
        exchange_info = self.make_get_request("/fapi/v1/exchangeInfo", dict())
        assets = [asset['asset'] for asset in exchange_info['assets']]
        print(assets)
        viable_symbols = []
        for contract in exchange_info['symbols']:
            if contract['contractType'] == "PERPETUAL" and contract['status'] == "TRADING" and contract['quoteAsset'] in assets:
                print(contract['symbol'])
                viable_symbols.append(contract['symbol'])
        print(len(viable_symbols))


if __name__ == '__main__':
    binance = BinanceFuturesClient(BINANCE_TESTNET_API_PUBLIC, BINANCE_TESTNET_API_SECRET, testnet=True)
    binance.get_current_contracts()
    