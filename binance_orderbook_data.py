from connectors.binance_futures import BinanceFuturesClient
from keys import *

DATA_TYPE = "T_DEPTH"
# tick-by-tick order book (level 2). Directly fetched from our api, will have gapes.


if __name__ == '__main__':
    binance_real = BinanceFuturesClient(BINANCE_REAL_API_PUBLIC, BINANCE_REAL_API_SECRET, testnet=False)
