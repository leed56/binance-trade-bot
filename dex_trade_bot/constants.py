"""BSC chain constants: well-known addresses and the minimal ABIs the bot needs.

Addresses are mainnet (chain id 56). Only the ABI fragments actually called are
included to keep things lean.
"""

CHAIN_ID = 56

# --- Core tokens -----------------------------------------------------------
WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDT = "0x55d398326f99059fF775485246999027B3197955"
USDC = "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"
BUSD = "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"

STABLES = {
    "USDT": USDT,
    "USDC": USDC,
    "BUSD": BUSD,
}

# --- PancakeSwap V2 --------------------------------------------------------
PANCAKE_V2_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
PANCAKE_V2_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"

# A second BSC DEX used for DEX-DEX arbitrage comparison (Biswap V2 router/factory).
BISWAP_ROUTER = "0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8"
BISWAP_FACTORY = "0x858E3312ed3A876947EA49d572A7C42DE08af7EE"

MAX_UINT256 = 2**256 - 1

# --- Common liquid BSC tokens (symbol -> address) for cross-venue comparison ---
COMMON_TOKENS = {
    "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
    "ETH": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
    "BTCB": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",
    "XRP": "0x1D2F0da169ceB9fC7B3144628dB156f3F6c60dBE",
    "ADA": "0x3EE2200Efb3400fAbB9AacF31297cBdD1d435D47",
    "LINK": "0xF8A0BF9cF54Bb92F17374d9e9A321E6a111a51bD",
    "DOT": "0x7083609fCE4d1d8Dc0C979AAb8c869Ea2C873402",
}

# --- Venus Protocol (BSC) comptroller for liquidation monitoring ---
VENUS_COMPTROLLER = "0xfD36E2c2a6789Db23113685031d7F16329158384"

VENUS_COMPTROLLER_ABI = [
    {"constant": True, "inputs": [{"name": "account", "type": "address"}],
     "name": "getAccountLiquidity",
     "outputs": [{"name": "error", "type": "uint256"}, {"name": "liquidity", "type": "uint256"},
                 {"name": "shortfall", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
    {"constant": True, "inputs": [], "name": "closeFactorMantissa",
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
]

# --- Minimal ABIs ----------------------------------------------------------
ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}],
     "type": "function"},
]

ROUTER_ABI = [
    {"inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "path", "type": "address[]"}],
     "name": "getAmountsOut", "outputs": [{"name": "amounts", "type": "uint256[]"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "amountOutMin", "type": "uint256"},
                {"name": "path", "type": "address[]"}, {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"}],
     "name": "swapExactTokensForTokens", "outputs": [{"name": "amounts", "type": "uint256[]"}],
     "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "amountOutMin", "type": "uint256"},
                {"name": "path", "type": "address[]"}, {"name": "to", "type": "address"},
                {"name": "deadline", "type": "uint256"}],
     "name": "swapExactTokensForTokensSupportingFeeOnTransferTokens", "outputs": [],
     "stateMutability": "nonpayable", "type": "function"},
]

FACTORY_ABI = [
    {"inputs": [{"name": "tokenA", "type": "address"}, {"name": "tokenB", "type": "address"}],
     "name": "getPair", "outputs": [{"name": "pair", "type": "address"}],
     "stateMutability": "view", "type": "function"},
    {"anonymous": False, "inputs": [
        {"indexed": True, "name": "token0", "type": "address"},
        {"indexed": True, "name": "token1", "type": "address"},
        {"indexed": False, "name": "pair", "type": "address"},
        {"indexed": False, "name": "", "type": "uint256"}],
     "name": "PairCreated", "type": "event"},
]

PAIR_ABI = [
    {"constant": True, "inputs": [], "name": "getReserves",
     "outputs": [{"name": "_reserve0", "type": "uint112"}, {"name": "_reserve1", "type": "uint112"},
                 {"name": "_blockTimestampLast", "type": "uint32"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "token0", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "token1", "outputs": [{"name": "", "type": "address"}], "type": "function"},
]
