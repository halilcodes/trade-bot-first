import json
import pprint
import time
import requests
import websocket
import threading
from keys import *
import logging
import typing
from models import Contract, Candle, Order, Wallet
import hmac
import hashlib
from urllib.parse import urlencode
import datetime as dt
from dateutil.relativedelta import relativedelta

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
            # self._base_url = "https://fapi.binance.com"
            self._base_url = "https://api.binance.com/sapi/v1"
            self._wss_url = "wss://fstream.binance.com/ws"
            self.connection_type = "Real Account"

        self.platform = "binance_futures"
        self._public_key = public_key
        self._secret_key = secret_key
        self._header = {"X-MBX-APIKEY": self._public_key}
        self.connection_trials = 0
        # self.wallet_info = self.get_balances()

        self.maker_commission = 0.02 / 100
        self.taker_commission = 0.04 / 100

        self.contracts = dict()
        self.candles = dict()
        self.standing_orders = dict()
        self.orders_history = dict()
        self.failed_orders = dict()

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

    def get_balances(self):
        endpoint = "/fapi/v1/account"
        method = "GET"
        balance = self.make_request(method, endpoint, dict())
        if balance is not None:
            return Wallet("binance_futures", balance)

    def get_current_commissions(self, contract: Contract):
        endpoint = "/fapi/v1/commissionRate"
        method = "GET"
        params = dict()
        params['symbol'] = contract.symbol
        commissions = self.make_request(method, endpoint, params)
        if commissions is not None:
            self.maker_commission = float(commissions["makerCommissionRate"])
            self.taker_commission = float(commissions["takerCommissionRate"])

    def get_base_assets(self) -> list:
        exchange_info = self.make_request("GET", "/fapi/v1/exchangeInfo", dict())
        assets = [asset['asset'] for asset in exchange_info['assets']]
        return assets

    def get_current_contracts(self) -> typing.Dict[str, Contract]:
        exchange_info = self.make_request("GET", "/fapi/v1/exchangeInfo", dict())
        leverage_finder = self.make_request("GET", "/fapi/v1/leverageBracket", dict())
        assets = self.get_base_assets()
        contract_dict = dict()
        for contract in exchange_info['symbols']:
            if contract['contractType'] == "PERPETUAL" and contract['status'] == "TRADING" \
                    and contract['quoteAsset'] in assets:
                symbol = contract['symbol']
                for each in leverage_finder:
                    if each['symbol'] == symbol:
                        contract['leverage'] = each["brackets"][0]['initialLeverage']
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
        else:
            return None

    def change_margin_type(self, contract: Contract, margin: str):
        """Margin type can be ISOLATED, CROSSED"""
        margin = margin.strip().upper()
        if margin not in ["ISOLATED", "CROSSED"]:
            return None
        endpoint = "fapi/v1/marginType"
        method = "POST"
        params = dict()
        params['symbol'] = contract.symbol
        params['marginType'] = margin
        change_margin = self.make_request(method, endpoint, params)
        if change_margin is not None:
            return change_margin
        else:
            return None

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
        while quantity * price < 10:
            quantity += contract.lot_size
        quantity = round(quantity, contract.quantity_precision)
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
        :param tif:
                    GTC (Good-Till-Cancel): the order will last until it is completed, or you cancel it.
                    IOC (Immediate-Or-Cancel): the order will attempt to execute all or part of it immediately at the
                     price and quantity available, then cancel any remaining, unfilled part of the order.
                     If no quantity is available at the chosen price when you place the order, it will be canceled
                     immediately. Please note that Iceberg orders are not supported.
                    FOK (Fill-Or-Kill): the order is instructed to execute in full immediately (filled),
                     otherwise it will be canceled (killed). Please note that Iceberg orders are not supported.
        :param stop_price:
        :return: Order object
        """
        while quantity * price < 10:
            quantity += contract.lot_size
        quantity = round(quantity, contract.quantity_precision)

        endpoint = "/fapi/v1/order"
        method = "POST"
        params = dict()
        params['symbol'] = contract.symbol
        params['side'] = side.strip().upper()
        params['type'] = "STOP"
        params['timeInForce'] = tif
        params['quantity'] = quantity
        params['price'] = price
        params['stopPrice'] = stop_price
        response = self.make_request(method, endpoint, params)
        return response

    def get_orders_for_symbol(self, contract: Contract):
        """Order Types:
        NEW, PARTIALLY_FILLED, FILLED, CANCELED, REPLACED, STOPPED, REJECTED, EXPIRED,
        NEW_INSURANCE - Liquidation with Insurance Fund, NEW_ADL - Counterparty Liquidation
        Caution!! This function only updates orders dictionaries for the object.
        `"""
        endpoint = "/fapi/v1/allOrders"
        params = dict()
        params['symbol'] = contract.symbol

        orders = self.make_request("GET", endpoint, params)
        if orders is not None:
            self.standing_orders[contract.symbol], self.orders_history[contract.symbol], self.failed_orders[
                contract.symbol] = list(), list(), list()
            for order in orders:
                symbol = order['symbol']
                if order['status'] in ["NEW", "PARTIALLY_FILLED"]:
                    self.standing_orders[symbol].append(order)
                elif order['status'] == "FILLED":
                    self.orders_history[symbol].append(order)
                else:
                    self.failed_orders[symbol].append(order)

            if len(self.standing_orders) > 0:
                return self.standing_orders
        else:
            return None

    def get_all_open_orders(self, contract=None) -> typing.Union[None, typing.List[Order]]:
        endpoint = "/fapi/v1/openOrders"
        method = "GET"
        params = dict()
        order_result = list()
        if contract is not None:
            params['symbol'] = contract.symbol

        open_orders = self.make_request(method, endpoint, params)
        # open orders returns list of dictionaries
        if open_orders is not None:
            for order in open_orders:
                new = Order("binance_futures", order)
                order_result.append(new)
            return order_result
        else:
            return None

    def get_historical_data(self, contract: Contract, interval: str, limit=500, start_time=None, end_time=None,
                            is_timestamp=True) -> typing.Union[None, typing.Dict[str, typing.List[Candle]]]:
        """
        Get historical candles as Candle object list.
        :param contract: Contract object of interested contract.
        :param interval: m -> minutes; h -> hours; d -> days; w -> weeks; M -> months
                        1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
        :param limit: Default 500; max 1500.
        :param start_time: in timestamp format OR '%Y/%m/%d %H:%M:%S' string format.
        :param end_time: im timestamp format '%Y/%m/%d %H:%M:%S' string format.
        :param is_timestamp: True if start_time and end_time are in timestamp format, false if string format.
        :return: Dictionary with a key of start time - end time - interval and value of a list of candles as Candle
                 objects.
        """
        if not is_timestamp:
            if start_time is not None:
                start_time = time.mktime(dt.datetime.strptime(start_time, '%Y/%m/%d %H:%M:%S').timetuple()) * 1000
            if end_time is not None:
                end_time = time.mktime(dt.datetime.strptime(end_time, '%Y/%m/%d %H:%M:%S').timetuple()) * 1000

        if limit > 1500:
            limit = 1500
        candle_dict = dict()
        endpoint = "/fapi/v1/klines"
        method = "GET"
        params = dict()
        params['symbol'] = contract.symbol
        params['interval'] = interval
        if start_time is not None:
            params['startTime'] = int(start_time)
        if end_time is not None:
            params['endTime'] = int(end_time)
        params['limit'] = limit
        klines = self.make_request(method, endpoint, params)
        if klines is not None:

            first_candle_ts = Candle("binance_futures", klines[0], "15m").start_timestamp
            last_candle_ts = Candle("binance_futures", klines[-1], "15m").end_timestamp

            start_in_dt = dt.datetime.fromtimestamp(int(first_candle_ts / 1000)).strftime('%Y/%m/%d %H:%M:%S')
            end_in_dt = dt.datetime.fromtimestamp(int(last_candle_ts / 1000)).strftime('%Y/%m/%d %H:%M:%S')

            date_label = f"{start_in_dt}**{end_in_dt}**{interval}"
            candle_dict[date_label] = list()
            for candle in klines:
                candle_dict[date_label].append(Candle("binance_futures", candle, interval))
            return candle_dict
        else:
            return None

    def get_lvl2_data(self, symbol: str, start_time, end_time, is_timestamp=False, data_type="T_DEPTH"):
        desired_symbols = ["BTCUSDT", "ADAUSDT", "LINKUSDT", "MANAUSDT", "ETHUSDT", "LTCUSDT", "1000SHIBUSDT",
                           "SOLUSDT", "AVAXUSDT", "DYDXUSDT", "BCHUSDT", "XRPUSDT", "EOSUSDT", "TRXUSDT", "ETCUSDT",
                           "BNBUSDT", "DOGEUSDT", "MKRUSDT", "BATUSDT", "ANKRUSDT"]

        initial_time = "2020/07/01 00:00:01"
        """
        It is recommended that you request within 1-3 months length each time,
         especially for tick-level order book data.
        :param contract:
        :param start_time:
        :param end_time:
        :param data_type:
        :param is_timestamp:
        :return:
        """

        if not is_timestamp:
            if start_time is not None:
                start_time = time.mktime(dt.datetime.strptime(start_time, '%Y/%m/%d %H:%M:%S').timetuple()) * 1000
            if end_time is not None:
                end_time = time.mktime(dt.datetime.strptime(end_time, '%Y/%m/%d %H:%M:%S').timetuple()) * 1000

        endpoint = "/futuresHistDataId"
        method = "POST"
        params = dict()
        params['symbol'] = symbol.upper().strip()
        params['startTime'] = int(start_time)
        params['endTime'] = int(end_time)
        params["dataType"] = data_type

        id_info = self.make_request(method, endpoint, params)
        if id_info is not None:
            print(id_info)
            print("*"*20)
            download_id = id_info['id']
            print(download_id)
            print(f"download id: {download_id},"
                  f" start time={dt.datetime.fromtimestamp(start_time/1000).strftime('%Y/%m/%d %H:%M:%S')},"
                  f"end time: = {dt.datetime.fromtimestamp(end_time/1000).strftime('%Y/%m/%d %H:%M:%S')}")
            return id_info
        else:
            return "ID Request gone wrong"

    def id_to_link(self, download_id):
        params = dict()
        params['downloadId'] = download_id
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._get_signature(params)
        endpoint = "/downloadLink"
        full_url = self._base_url + endpoint
        link = requests.get(full_url, params, headers=self._header)
        print(link.status_code)
        print(link.json())
        if link is not None:
            with open(f"../depth_datas/LINKUSDT_link_list.json", "a") as file:
                json.dump(link.json(), file)
                file.write('\n')
            return link.json()
        else:
            return "LINK Request gone wrong"

    def foo(self, first_start_time, daily_interval=7, repetition=1):
        # TODO: I wrote this to get download id's in a bulk but its half-done.
        start_time = dt.datetime.strptime(first_start_time, '%Y/%m/%d %H:%M:%S')
        symbol = "LINKUSDT"
        for i in range(repetition):
            end_time = start_time + relativedelta(days=daily_interval)
            start_in_str = dt.datetime.strftime(start_time, '%Y/%m/%d %H:%M:%S')
            end_in_str = dt.datetime.strftime(end_time, '%Y/%m/%d %H:%M:%S')
            btc_lv2 = self.get_lvl2_data(symbol, start_time=start_in_str, end_time=end_in_str)

            with open(f"../depth_datas/{symbol}_id_list.txt", "a") as file:
                file.write("*" * 50)
                file.write("\n")
                file.write(f"start_time: {start_in_str} end_time: {end_in_str} id: {btc_lv2}")
                file.write('\n')
            start_time = end_time

        # initial_start_time = "2021/06/01 00:00:01"
        # binance.foo(initial_start_time, 2, 2)
        # print(binance.id_to_link(615764))


if __name__ == '__main__':
    bin_real = BinanceFuturesClient(BINANCE_REAL_API_PUBLIC, BINANCE_REAL_API_SECRET, testnet=False)
    bin_real.id_to_link("626606")
    # binance = BinanceFuturesClient(BINANCE_TESTNET_API_PUBLIC, BINANCE_TESTNET_API_SECRET, testnet=True)
    
    # contracts = binance.get_current_contracts()
    # btcusdt = contracts['BTCUSDT']
    # linkusdt = contracts['LINKUSDT']
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


