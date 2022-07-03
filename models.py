import datetime
import typing
import datetime as dt
import pandas as pd

TIME_CONVERSION = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240, "6h": 360,
                   "8h": 480, "12h": 720, "1d": 1440, "3d": 4320, "1w": 10080, "1M": 40320}


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
        self.max_leverage = int()

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
        self.max_leverage = contract_data['leverage']


class Candle:
    def __init__(self, platform: str, candle_list: list, time_frame: str):
        self.platform = platform
        self.start_timestamp = int()
        self.end_timestamp = int()
        self.start_date_time = datetime.date
        self.end_date_time = datetime.date
        self.time_frame = TIME_CONVERSION[time_frame]  # timeframe in terms of minutes (i.e 60 for 1h timeframe)
        self.open = float()
        self.high = float()
        self.low = float()
        self.close = float()
        self.volume_base = float()  # in BTC
        self.volume_quote = float()  # in USDT
        self.num_of_trades = int()
        if self.platform == "binance_futures":
            self.get_binance_futures_klines(candle_list)

    def get_binance_futures_klines(self, candle_list):
        self.start_timestamp = candle_list[0]
        self.start_date_time = dt.datetime.fromtimestamp(int(self.start_timestamp / 1000)).strftime('%Y/%m/%d %H:%M:%S')
        self.end_timestamp = candle_list[6]
        self.end_date_time = dt.datetime.fromtimestamp(int(self.end_timestamp / 1000)).strftime('%Y/%m/%d %H:%M:%S')
        self.open = candle_list[1]
        self.high = candle_list[2]
        self.low = candle_list[3]
        self.close = candle_list[4]
        self.volume_base = candle_list[5]
        self.volume_quote = candle_list[7]
        self.num_of_trades = candle_list[8]


class Order:
    def __init__(self, platform, order_data):
        self.platform = platform
        self.order_data = order_data


class Wallet:
    def __init__(self, platform: str, wallet_data: dict):
        self.platform = platform
        # self.update_timestamp = int()
        # self.update_dt = dt.datetime.utcnow()
        self.wallet_info = dict()
        self.position_info = dict()

        self.available_balance = float()
        self.can_deposit = bool()
        self.can_trade = bool()
        self.can_withdraw = bool()
        self.total_balance = float()
        self.fee_tier = int()
        self.total_required_margin = float()
        self.total_unrealised_pnl = float()
        if self.platform == "binance_futures":
            self.get_binance_wallet_info(wallet_data)

    def get_binance_wallet_info(self, data):
        # TODO: entries need revision.
        self.wallet_info = dict()
        self.position_info = dict()
        for asset in data['assets'][0]:
            symbol = asset['asset']
            self.wallet_info[symbol] = {'available_balance': float(asset['availableBalance']),
                                        'wallet_balance': float(asset['walletBalance']),
                                        'unrealised_pnl': float(asset['unrealizedProfit']),
                                        'required_margin': float(asset['initialMargin'])}
        self.available_balance = float(data['availableBalance'])
        self.total_balance = float(data['maxWithdrawAmount'])
        self.can_deposit = bool(data['canDeposit'])
        self.can_trade = bool(data['canTrade'])
        self.can_withdraw = bool(data['canWithdraw'])
        self.fee_tier = int(data['feeTier'])
        self.total_required_margin = float(data['totalPositionInitialMargin'])
        self.total_unrealised_pnl = float(data['totalUnrealizedProfit'])
        for position in data['positions'][0]:
            if position['positionAmt'] != '0':
                symbol = position['symbol']
                self.position_info[symbol] = {'entry_price': float(position['entryPrice']),
                                              'required_margin': float(position['initialMargin']),
                                              'is_isolated': bool(position['isolated']),
                                              'leverage': int(position['leverage']),
                                              'position_amount': float(position['positionAmt']),
                                              'unrealised_pnl': float(position['unrealizedProfit'])}


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
    # maybe it is better to pass dataframe as it would be easier to store them in sqlite3.
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
