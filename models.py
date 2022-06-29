class Contracts:
    def __init__(self, platform, data):
        if platform == "binance_futures":
            self.get_binance_futures_contracts(data)

    def get_binance_futures_contracts(self, data):
        self.symbol = data['symbol']
        self.base_asset = data['baseAsset']
        self.quote_asset = data['quoteAsset']
        self.margin_asset = data['marginAsset']

