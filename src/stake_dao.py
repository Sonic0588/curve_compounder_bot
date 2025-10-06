import logging

from web3 import Web3

import abis
from addresses import (
    GMAC_CRVUSD_ETH_GAUGE_ADDRESS,
    GMAC_CRVUSD_ETH_POOL_ADDRESS,
    GMAC_CRVUSD_ETH_STAKE_DAO_VAULT_ADDRESS,
    STAKE_DAO_HARVESTER_ADDRESS,
    ZERO_ADDRESS,
)
from config import ARBITRUM_RPC, PRIVATE_KEY, WALLET_ADDRESS
from utils import build_approve_tx, get_allowance, get_gas_fees, send_tx


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def build_deposit_tx(web3: Web3, wallet_address, vault_address, amount):
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(vault_address),
        abi=abis.STAKE_DAO_VAULT,
    )

    tx = contract.functions.deposit(amount, ZERO_ADDRESS).build_transaction(
        {
            "from": wallet_address,
            "nonce": web3.eth.get_transaction_count(wallet_address),
            **get_gas_fees(web3),
        }
    )

    return tx


def build_claim_tx(web3: Web3, wallet_address, gauges_addresses):
    contract = web3.eth.contract(
        address=STAKE_DAO_HARVESTER_ADDRESS,
        abi=abis.STAKE_DAO_HARVERSTER,
    )

    tx = contract.functions.claim(gauges_addresses, [b"0x"]).build_transaction(
        {
            "from": wallet_address,
            "nonce": web3.eth.get_transaction_count(wallet_address),
            **get_gas_fees(web3),
        }
    )

    return tx


if __name__ == "__main__":
    # Инициализация Web3
    web3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))
    assert web3.is_connected(), "Не удалось подключиться к сети Arbitrum"

    amount = int(float(input("Введите количество LP токенов для добавления в vault: ")) * 10**18)

    # Проверяем баланс
    lp_token_contract = web3.eth.contract(address=GMAC_CRVUSD_ETH_POOL_ADDRESS, abi=abis.ERC20)
    balance = lp_token_contract.functions.balanceOf(WALLET_ADDRESS).call()
    logger.info(f"Balance: {balance}")

    assert balance >= amount, "Недостаточно LP токенов"

    # Проверяем разрешение
    allowance = get_allowance(
        web3=web3,
        wallet_address=WALLET_ADDRESS,
        token_address=GMAC_CRVUSD_ETH_POOL_ADDRESS,
        spender=GMAC_CRVUSD_ETH_STAKE_DAO_VAULT_ADDRESS,
    )

    logger.info(f"Allowance: {allowance}")
    if allowance < amount:
        logger.info("Выдаем разрешение...")
        approve_tx = build_approve_tx(
            web3=web3,
            wallet_address=WALLET_ADDRESS,
            token_address=GMAC_CRVUSD_ETH_POOL_ADDRESS,
            spender=GMAC_CRVUSD_ETH_STAKE_DAO_VAULT_ADDRESS,
            amount=amount,
        )

        tx_hash = send_tx(web3, approve_tx, PRIVATE_KEY)
        logger.info(f"Транзакция разрешения: {tx_hash}")

        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        logger.info(f"Разрешение добавлено: {receipt}")

    # # Совершаем добавление ликвидности
    add_liquidity_tx = build_deposit_tx(
        web3=web3,
        wallet_address=WALLET_ADDRESS,
        vault_address=GMAC_CRVUSD_ETH_STAKE_DAO_VAULT_ADDRESS,
        amount=amount,
    )

    add_liquidity_tx_hash = send_tx(web3, add_liquidity_tx, PRIVATE_KEY)
    logger.info(f"Транзакция депозита LP токена в vault: {add_liquidity_tx_hash}")
    receipt = web3.eth.wait_for_transaction_receipt(add_liquidity_tx_hash)
    logger.info(f"LP токен добавлен: {receipt}")

    # Собираем награды
    claim_tx = build_claim_tx(
        web3=web3,
        wallet_address=WALLET_ADDRESS,
        gauges_addresses=[
            GMAC_CRVUSD_ETH_GAUGE_ADDRESS,
        ],
    )

    claim_tx_hash = send_tx(web3, claim_tx, PRIVATE_KEY)
    logger.info(f"Транзакция сбора наград: {claim_tx_hash}")
    receipt = web3.eth.wait_for_transaction_receipt(claim_tx_hash)
    logger.info(f"Награды собраны: {receipt}")
