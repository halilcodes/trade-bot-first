import requests
import websocket
import threading


class BinanceSpotClient:
    def __init__(self, public_key: str, private_key: str, testnet: bool):
        if testnet:
            self._base_url = "https://testnet.binance.vision/api"
            self._ws_url = "wss://testnet.binance.vision/ws"
            self._stream_url = "wss://testnet.binance.vision/stream"
            self.connection_type = "Testnet"
        else:
            self._base_url = "https://api.binance.com/api"
            self._ws_url = "wss://stream.binance.com:9443/ws"
            self._stream_url = "wss://stream.binance.com:9443/stream"
            self.connection_type = "Real Account"
