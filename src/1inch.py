import logging
import os
import random
import time

import requests
from dotenv import load_dotenv
from web3 import Web3

import abis


load_dotenv()

logger = logging.getLogger(__name__)

# Настройки
ARBITRUM_RPC = os.getenv("ARBITRUM_RPC", "https://arb1.arbitrum.io/rpc")
ARBITRUM_CHAIN_ID = 42161
ONEINCH_API_URL = f"https://api.1inch.com/swap/v6.1/{ARBITRUM_CHAIN_ID}"
ONEINCH_API_KEY = os.getenv("ONEINCH_API_KEY", "")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")  # Никогда не храните в коде!
WALLET_ADDRESS = Web3.to_checksum_address(os.getenv("WALLET_ADDRESS", ""))

# Адреса контрактов (Arbitrum)
CRV_ADDRESS = Web3.to_checksum_address("0x11cDb42B0EB46D95f990BeDD4695A6e3fA034978")
CRVUSD_ADDRESS = Web3.to_checksum_address("0x498Bf2B1e120FeD3ad3D42EA2165E9b73f99C1e5")
ONEINCH_ROUTER_ADDRESS = Web3.to_checksum_address("0x111111125421ca6dc452d289314280a0f8842a65")

# Инициализация Web3
web3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))
assert web3.is_connected(), "Не подключено к Arbitrum"


def get_allowance(token_address, wallet_address, spender):
    """Проверка разрешенного количества токенов"""
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=abis.ERC20,
    )

    return contract.functions.allowance(
        Web3.to_checksum_address(wallet_address),
        spender,
    ).call()


def get_gas_fees():
    fee_history = web3.eth.fee_history(5, "latest", [50])
    base_fee = fee_history["baseFeePerGas"][-1]
    priority = int(base_fee * 0.1)

    rewards = sorted(r[0] for r in fee_history["reward"] if r)
    if rewards:
        mid = len(rewards) // 2
        priority = rewards[mid] if len(rewards) % 2 else (rewards[mid - 1] + rewards[mid]) // 2
        priority = int(priority * random.uniform(1.03, 1.1))

    return {
        "maxPriorityFeePerGas": priority,
        "maxFeePerGas": max(base_fee + priority, int(base_fee * 1.15)),
    }


def approve_token(token_address, spender, amount):
    """Выдача разрешения на использование токенов"""
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=abis.ERC20,
    )

    tx = contract.functions.approve(
        Web3.to_checksum_address(spender),
        amount,
    ).build_transaction(
        {
            "from": WALLET_ADDRESS,
            "nonce": web3.eth.get_transaction_count(WALLET_ADDRESS),
            "chainId": 42161,
            **get_gas_fees(),
        }
    )

    signed_tx = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return web3.to_hex(tx_hash)


def get_quote(from_token, to_token, amount):
    """Получение котировки от 1inch"""
    url = f"{ONEINCH_API_URL}/quote"
    headers = {
        "authorization": f"Bearer {ONEINCH_API_KEY}",
    }
    params = {
        "src": from_token,
        "dst": to_token,
        "amount": amount,
    }

    response = requests.get(url, headers=headers, params=params)
    return response.json()


def build_swap_tx(from_token, to_token, amount, slippage=0.1):
    """Построение транзакции для обмена"""
    url = f"{ONEINCH_API_URL}/swap"
    headers = {
        "authorization": f"Bearer {ONEINCH_API_KEY}",
    }
    params = {
        "src": from_token,
        "dst": to_token,
        "amount": amount,
        "from": WALLET_ADDRESS,
        "origin": WALLET_ADDRESS,
        "slippage": slippage,
    }

    response = requests.get(url, headers=headers, params=params)
    return response.json()


def execute_swap(swap_data):
    """Выполнение обмена"""
    tx = swap_data["tx"]
    del tx["gasPrice"]

    tx.update(
        {
            "from": WALLET_ADDRESS,
            "to": ONEINCH_ROUTER_ADDRESS,
            "nonce": web3.eth.get_transaction_count(WALLET_ADDRESS),
            "chainId": 42161,
            "value": int(tx["value"]),
            **get_gas_fees(),
        }
    )

    signed_tx = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    return web3.to_hex(tx_hash)


# Основная логика
if __name__ == "__main__":
    amount = int(input("Введите количество CRV для обмена: ")) * 10**18

    # Проверяем баланс
    crv_contract = web3.eth.contract(
        address=Web3.to_checksum_address(CRV_ADDRESS),
        abi=abis.ERC20,
    )
    balance = crv_contract.functions.balanceOf(WALLET_ADDRESS).call()
    assert balance >= amount, "Недостаточно CRV токенов"

    # Получаем котировку
    quote = get_quote(CRV_ADDRESS, CRVUSD_ADDRESS, amount)
    logger.info(f"Получим примерно: {int(quote['dstAmount']) / 10**18} crvUSD")

    # Проверяем разрешение
    allowance = get_allowance(
        CRV_ADDRESS,
        WALLET_ADDRESS,
        ONEINCH_ROUTER_ADDRESS,
    )

    if allowance < amount:
        logger.info("Выдаем разрешение...")
        approve_tx = approve_token(
            CRV_ADDRESS,
            ONEINCH_ROUTER_ADDRESS,
            amount,
        )
        logger.info(f"Транзакция разрешения: {approve_tx}")
        time.sleep(30)  # Ждем подтверждения

    # Совершаем обмен
    swap_data = build_swap_tx(CRV_ADDRESS, CRVUSD_ADDRESS, amount)
    logger.info(swap_data)
    swap_tx_hash = execute_swap(swap_data)
    logger.info(f"Транзакция обмена: {swap_tx_hash}")
