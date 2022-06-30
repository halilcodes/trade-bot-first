import json
import pprint
import time
import requests
import websocket
import threading
from keys import *
import logging
import typing
from models import Contract, Candle
import hmac
import hashlib
from urllib.parse import urlencode
import datetime as dt

# TODO: All print statements will be converted to logging entries.
logger = logging.getLogger()


def timestamp():
    return int(time.time() * 1000) - 500


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
        self._header = {"X-MBX-APIKEY": self._public_key}
        self.connection_trials = 0

        self.maker_commission = 0.02 / 100
        self.taker_commission = 0.04 / 100

        self.contracts = dict()
        self.candles = dict()

    def _get_signature(self, data: dict):
        """ HMAC SHA 256 signature provider"""
        key = self._secret_key.encode()
        payload = urlencode(data).encode()
        return hmac.new(key, payload, hashlib.sha256).hexdigest()

    def make_request(self, method: str, endpoint: str, params: dict) -> typing.Union[dict, None]:
        """
        :param method: get/post/put/delete depending on documentation
        :param endpoint: depending on request type, will be copied from documentation.
        :param params: will be sent as a query string, pass dict() if not required.
        :return:
        """
        method = method.strip().upper()
        params['recvWindow'] = 5000
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._get_signature(params)
        complete_url = self._base_url + endpoint
        if method == "GET":
            response = requests.get(complete_url, params, headers=self._header)
        elif method == "POST":
            response = requests.post(complete_url, params, headers=self._header)
        else:
            response = requests.put(complete_url, params, headers=self._header)
        code = response.status_code

        if code // 100 == 5:
            while self.connection_trials < 5:
                print(f"Binance Futures Client | Internal error... sending new request. {self.connection_trials}/5")
                self.make_request(method, endpoint, params)
                self.connection_trials += 1
            print(f"Binance Futures Client | 5 requests in a row returned {code} error code."
                  " Check server integrity.")

        if self.is_request_good(response):
            self.connection_trials = 0
            return response.json()
        else:
            return None

    def is_request_good(self, response) -> bool:
        """
        Helper function for make_xx_request() functions. determines reason should there be an error.
        :param response: direct response after the request module.
        :return: True if no error, False otherwise.
        """
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
            print(f"Binance Futures Client | {code} code error, malformed request. {response.json()['msg']}")
        return False

    def check_api_connection(self):
        _ = self.make_request("GET", "/fapi/v1/ping", dict())
        get_server_time = self.make_request("GET", "/fapi/v1/time", dict())
        if get_server_time:
            print(f"Binance Futures Client | API is connected. Current server time: {get_server_time['serverTime']}")
        else:
            print("Binance Futures Client | API Connection Failure. ")

    def get_current_commissions(self):
        """Not available in Binance Futures API. Still here for organisation purposes."""
        pass

    def get_base_assets(self) -> list:
        exchange_info = self.make_request("GET", "/fapi/v1/exchangeInfo", dict())
        assets = [asset['asset'] for asset in exchange_info['assets']]
        return assets

    def get_current_contracts(self) -> typing.Dict[str, Contract]:
        exchange_info = self.make_request("GET", "/fapi/v1/exchangeInfo", dict())
        assets = self.get_base_assets()
        contract_dict = dict()
        for contract in exchange_info['symbols']:
            if contract['contractType'] == "PERPETUAL" and contract['status'] == "TRADING" \
                    and contract['quoteAsset'] in assets:
                symbol = contract['symbol']
                contract_dict[symbol] = Contract("binance_futures", contract)
        if contract_dict is not None:
            return contract_dict

    def get_price_update(self, contract: Contract, count=1) -> dict:
        endpoint = "/fapi/v1/trades"
        params = {'symbol': contract.symbol, 'limit': count}
        response = self.make_request("GET", endpoint, params)
        response = response[0]
        last_trade = {"price": float(response['price']),
                      "quantity": float(response['qty']),
                      "time": int(response['time']),
                      "buyer_filled": bool(response['isBuyerMaker'])}
        return last_trade

    def adjust_leverage(self, contract: Contract, leverage: int):
        endpoint = "/fapi/v1/leverage"
        method = "POST"
        params = dict()
        params['symbol'] = contract.symbol
        params['leverage'] = leverage
        set_leverage = self.make_request(method, endpoint, params)
        if set_leverage is not None:
            return set_leverage

    def place_market_order(self, contract: Contract, quantity: float, side: str):
        endpoint = "/fapi/v1/order"
        params = dict()
        params['type'] = "MARKET"
        params['symbol'] = contract.symbol
        params['side'] = side.strip().upper()
        params['quantity'] = quantity
        params['timestamp'] = int(time.time() * 1000)
        response = self.make_request("POST", endpoint, params)
        return response

    def place_limit_order(self, contract: Contract, quantity: float, side: str, price: float, tif="GTC"):
        endpoint = "/fapi/v1/order"
        params = dict()
        params['symbol'] = contract.symbol
        params['side'] = side.strip().upper()
        params['type'] = "LIMIT"
        params['timeInForce'] = tif
        params['quantity'] = quantity
        params['price'] = price
        params['timestamp'] = int(time.time() * 1000)
        response = self.make_request("POST", endpoint, params)
        return response

    def place_stop_order(self, contract: Contract, quantity: float, side: str, price: float, stop_price: float,
                         tif="GTC"):
        """
        General place order function. Able to send all kinds of orders including LIMIT,MARKET and STOP.
        :param contract: Contract object to be traded
        :param quantity: base asset amount. ie 0.01 = 0.01 of BTC in BTCUSDT contract
        :param side: buy or sell in string format
        :param price: required in stop or limit orders
        :param order_type:
        :param tif:
                    GTC (Good-Till-Cancel): the order will last until it is completed or you cancel it.
                    IOC (Immediate-Or-Cancel): the order will attempt to execute all or part of it immediately at the
                     price and quantity available, then cancel any remaining, unfilled part of the order.
                     If no quantity is available at the chosen price when you place the order, it will be canceled
                     immediately. Please note that Iceberg orders are not supported.
                    FOK (Fill-Or-Kill): the order is instructed to execute in full immediately (filled),
                     otherwise it will be canceled (killed). Please note that Iceberg orders are not supported.
        :param stop_price:
        :return: Order object
        """
        endpoint = "/fapi/v1/order"
        method = "POST"
        params = dict()
        params['symbol'] = contract.symbol
        params['side'] = side
        params['type'] = "STOP"
        params['timeInForce'] = tif
        params['quantity'] = quantity
        params['price'] = price
        params['stopPrice'] = stop_price
        response = self.make_request(method, endpoint, params)
        return response

    def get_all_standing_orders(self, contract: Contract):
        endpoint = "/fapi/v1/allOrders"
        params = dict()
        params['symbol'] = contract.symbol
        standing_orders = dict()
        orders = self.make_request("GET", endpoint, params)
        for order in orders:
            symbol = order['symbol']
            if order['status'] not in ["FILLED", "CANCELED"]:
                standing_orders[symbol] = order
        if len(standing_orders) > 0:
            return standing_orders
        else:
            return None

    def get_historical_data(self, contract: Contract, interval: str, limit=500, start_time=None,
                            end_time=None):
        # TODO: there might be a better way to store klines that enables me to access them later on easily.
        """
        Get historical candles as Candle object list.
        :param contract:
        :param interval:
        :param limit: Default 500; max 1500.
        :param start_time:
        :param end_time:
        :return:
        """
        if limit > 1500:
            limit = 1500
        candle_dict = dict()
        endpoint = "/fapi/v1/klines"
        method = "GET"
        params = dict()
        params['symbol'] = contract.symbol
        params['interval'] = interval
        if start_time and end_time:
            params['startTime'] = start_time
            params['endTime'] = end_time
        params['limit'] = limit
        klines = self.make_request(method, endpoint, params)
        if klines is not None:
            candle_dict[contract.symbol] = dict()
            if start_time is None and end_time is None:
                start_time = float(klines[-1][0])
                end_time = float(klines[0][6])

            start_in_dt = dt.datetime.fromtimestamp(int(start_time / 1000)).strftime('%Y/%m/%d %H:%M:%S')
            end_in_dt = dt.datetime.fromtimestamp(int(end_time / 1000)).strftime('%Y/%m/%d %H:%M:%S')
            date_label = f"{start_in_dt}-{end_in_dt}-{interval}"
            candle_dict[contract.symbol][date_label] = list()
            for candle in klines:
                candle_dict[contract.symbol][date_label].append(Candle("binance_futures", candle, interval))
            return candle_dict
        else:
            return None


if __name__ == '__main__':
    binance = BinanceFuturesClient(BINANCE_TESTNET_API_PUBLIC, BINANCE_TESTNET_API_SECRET, testnet=True)
    contracts = binance.get_current_contracts()
    btcusdt = contracts['BTCUSDT']
    linkusdt = contracts['LINKUSDT']
    # print(f"platform: {contracts['BTCUSDT'].platform} | type: {type(contracts['BTCUSDT'].platform)}")
    # print(f"symbol: {contracts['BTCUSDT'].symbol} | type: {type(contracts['BTCUSDT'].symbol)}")
    # print(f"base_asset: {contracts['BTCUSDT'].base_asset} | type: {type(contracts['BTCUSDT'].base_asset)}")
    # print(f"quote_asset: {contracts['BTCUSDT'].quote_asset} | type: {type(contracts['BTCUSDT'].quote_asset)}")
    # print(f"margin_asset: {contracts['BTCUSDT'].margin_asset} | type: {type(contracts['BTCUSDT'].margin_asset)}")
    # print(f"margin_percent: {contracts['BTCUSDT'].margin_percent} |"
    #       f" type: {type(contracts['BTCUSDT'].margin_percent)}")
    # print(f"price_precision: {contracts['BTCUSDT'].price_precision} |"
    #       f" type: {type(contracts['BTCUSDT'].price_precision)}")
    # print(f"quantity_precision: {contracts['BTCUSDT'].quantity_precision} |"
    #       f" type: {type(contracts['BTCUSDT'].quantity_precision)}")
    # print(f"tick_size: {contracts['BTCUSDT'].tick_size} | type: {type(contracts['BTCUSDT'].tick_size)}")
    # print(f"lot_size: {contracts['BTCUSDT'].lot_size} | type: {type(contracts['BTCUSDT'].lot_size)}")
    # print(f"max_order_limit: {contracts['BTCUSDT'].max_order_limit} |"
    #       f" type: {type(contracts['BTCUSDT'].max_order_limit)}")
    # print(f"order_types: {contracts['BTCUSDT'].order_types} | type: {type(contracts['BTCUSDT'].order_types)}")
    # print(f"time_in_forces: {contracts['BTCUSDT'].time_in_forces} |"
    #       f" type: {type(contracts['BTCUSDT'].time_in_forces)}")
    link_1h = binance.get_historical_data(linkusdt, "15m")
    # pprint.pprint(link_1h)
    for symbol, value_1 in link_1h.items():
        for _, value in value_1.items():
            print(len(value))



