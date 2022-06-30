import datetime
import typing
import datetime as dt
import pandas as pd


class Contract:
    def __init__(self, platform, contract_data):
        self.platform = platform
        self.symbol = str()
        self.base_asset = str()
        self.quote_asset = str()
        self.margin_asset = str()
        self.margin_percent = float()
        self.price_precision = int()
        self.quantity_precision = int()
        self.tick_size = float()
        self.lot_size = float()
        self.max_order_limit = int()
        self.order_types = list()
        self.time_in_forces = list()

        if self.platform == "binance_futures":
            self.get_binance_futures_contracts(contract_data)

    def get_binance_futures_contracts(self, contract_data):
        self.symbol = contract_data['symbol']
        self.base_asset = contract_data['baseAsset']
        self.quote_asset = contract_data['quoteAsset']
        self.margin_asset = contract_data['marginAsset']
        self.margin_percent = float(contract_data['requiredMarginPercent'])
        self.price_precision = int(contract_data['pricePrecision'])
        self.quantity_precision = int(contract_data['quantityPrecision'])
        self.tick_size = float(contract_data['filters'][0]['tickSize'])
        self.lot_size = float(contract_data['filters'][1]['minQty'])
        self.max_order_limit = int(contract_data['filters'][4]['limit'])
        self.order_types = contract_data['orderTypes']
        self.time_in_forces = contract_data['timeInForce']


class Candle:
    def __init__(self, candle_data: dict):
        self.timestamp = int()
        self.date_time = datetime.date
        self.time_frame = int() # timeframe in terms of minutes (i.e 60 for 1h timeframe)
        self.open = float()
        self.high = float()
        self.low = float()
        self.close = float()
        self.volume = float()


class TechnicalAnalysis:
    def __init__(self, contract: Contract, candle_list: typing.List[Candle]):
        self.contract = contract

    def calculate_ema(self, look_back):
        pass

    def calculate_sma(self, look_back):
        pass

    def calculate_rsi(self, look_back):
        pass

    def calculate_kdj(self, look_back):
        pass

    def calculate_atr(self, look_back):
        pass


class GraphCandles:
    def __init__(self, candle_list: typing.List[Candle]):
        self.df_candles = pd.DataFrame(candle_list,  # index??
                                       columns=["timestamp", "datetime", "timeframe", "open", "high", "low", "close"])

    def draw_graph(self, interval):
        pass

    def draw_ema(self, interval):
        pass

    def draw_rsi(self, interval):
        pass

    def draw_kdj(self, interval):
        pass

    def remove_from_graph(self, parameter):
        pass
    