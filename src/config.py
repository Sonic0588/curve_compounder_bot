import os

from dotenv import load_dotenv
from web3 import Web3


load_dotenv()

ARBITRUM_RPC = os.getenv("ARBITRUM_RPC", "https://arb1.arbitrum.io/rpc")
ARBITRUM_CHAIN_ID = 42161
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")  # Никогда не храните в коде!
WALLET_ADDRESS = Web3.to_checksum_address(os.getenv("WALLET_ADDRESS", ""))
WEEK = 7 * 24 * 60 * 60  # 7 days in seconds
POLL_INTERVAL = 60 * 60  # Check every hour

ONEINCH_API_URL = f"https://api.1inch.com/swap/v6.1/{ARBITRUM_CHAIN_ID}"
ONEINCH_API_KEY = os.getenv("ONEINCH_API_KEY", "")
