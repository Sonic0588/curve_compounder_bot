import logging
import time

import requests
from web3 import Web3

import abis
from addresses import CRV_ADDRESS, CRVUSD_ADDRESS, ONEINCH_ROUTER_ADDRESS
from config import ARBITRUM_RPC, ONEINCH_API_KEY, ONEINCH_API_URL, PRIVATE_KEY, WALLET_ADDRESS
from utils import build_approve_tx, get_allowance, get_gas_fees, send_tx


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Настройки


# Инициализация Web3
web3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))
assert web3.is_connected(), "Не удалось подключиться к сети Arbitrum"


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


def build_swap_tx(wallet_address, from_token, to_token, amount, slippage=0.1):
    """Построение транзакции для обмена"""
    url = f"{ONEINCH_API_URL}/swap"
    headers = {
        "authorization": f"Bearer {ONEINCH_API_KEY}",
    }
    params = {
        "src": from_token,
        "dst": to_token,
        "amount": amount,
        "from": wallet_address,
        "origin": wallet_address,
        "slippage": slippage,
    }

    response = requests.get(url, headers=headers, params=params)
    swap_data = response.json()
    logger.info(swap_data)

    tx = swap_data["tx"]
    del tx["gasPrice"]

    tx.update(
        {
            "from": wallet_address,
            "to": ONEINCH_ROUTER_ADDRESS,
            "nonce": web3.eth.get_transaction_count(wallet_address),
            "chainId": 42161,
            "value": int(tx["value"]),
            **get_gas_fees(web3),
        }
    )

    return tx


# Основная логика
if __name__ == "__main__":
    amount = int(float(input("Введите количество CRV для обмена: ")) * 10**18)

    # Проверяем баланс
    crv_contract = web3.eth.contract(address=Web3.to_checksum_address(CRV_ADDRESS), abi=abis.ERC20)
    balance = crv_contract.functions.balanceOf(WALLET_ADDRESS).call()
    assert balance >= amount, "Недостаточно CRV токенов"

    # Получаем котировку
    quote = get_quote(CRV_ADDRESS, CRVUSD_ADDRESS, amount)
    logger.info(f"Получим примерно: {int(quote['dstAmount']) / 10**18} crvUSD")

    # Проверяем разрешение
    allowance = get_allowance(
        web3=web3,
        wallet_address=WALLET_ADDRESS,
        token_address=CRV_ADDRESS,
        spender=ONEINCH_ROUTER_ADDRESS,
    )

    if allowance < amount:
        logger.info("Выдаем разрешение...")
        approve_tx = build_approve_tx(
            web3=web3,
            wallet_address=WALLET_ADDRESS,
            token_address=CRV_ADDRESS,
            spender=ONEINCH_ROUTER_ADDRESS,
            amount=amount,
        )

        tx_hash = send_tx(web3, approve_tx, PRIVATE_KEY)

        logger.info(f"Транзакция разрешения: {tx_hash}")
        time.sleep(30)  # Ждем подтверждения

    # Совершаем обмен
    swap_tx = build_swap_tx(
        wallet_address=WALLET_ADDRESS,
        from_token=CRV_ADDRESS,
        to_token=CRVUSD_ADDRESS,
        amount=amount,
    )

    swap_tx_hash = send_tx(web3, swap_tx, PRIVATE_KEY)
    logger.info(f"Транзакция обмена: {swap_tx_hash}")
