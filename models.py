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

