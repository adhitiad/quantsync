REQUIRED_CRYPTO_SYMBOLS = [
    "BTC/USDT",
    "BTC/USDC",
    "ETH/USDT",
    "ETH/USDC",
    "SOL/USDT",
    "SOL/USDC",
    "BNB/USDT",
    "BNB/USDC",
]

REQUIRED_FOREX_ASSETS = [
    {"name": "EUR/USD", "inst": "EUR/USD"},
    {"name": "GBP/USD", "inst": "GBP/USD"},
    {"name": "XAU/USD", "inst": "XAU/USD"},
]

REQUIRED_FOREX_SYMBOLS = [asset["name"] for asset in REQUIRED_FOREX_ASSETS]


def get_required_runtime_assets():
    return REQUIRED_CRYPTO_SYMBOLS + REQUIRED_FOREX_SYMBOLS
