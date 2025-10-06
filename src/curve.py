import logging

from web3 import Web3

import abis
from addresses import CRVUSD_ADDRESS, GMAC_CRVUSD_ETH_POOL_ADDRESS
from config import ARBITRUM_RPC, PRIVATE_KEY, WALLET_ADDRESS
from utils import build_approve_tx, get_allowance, get_gas_fees, send_tx


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Инициализация Web3
web3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))
assert web3.is_connected(), "Не удалось подключиться к сети Arbitrum"


def build_add_liquidity_tx(web3: Web3, wallet_address, pool_address, amounts, slippage=0.1):
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(pool_address),
        abi=abis.CURVE_TRICRYPTO_POOL,
    )

    min_mint_amount = contract.functions.calc_token_amount(amounts, True).call()

    tx = contract.functions.add_liquidity(
        amounts,
        int(min_mint_amount * (1 - slippage / 100)),
        True,
    ).build_transaction(
        {
            "from": wallet_address,
            "nonce": web3.eth.get_transaction_count(wallet_address),
            **get_gas_fees(web3),
        }
    )

    return tx


if __name__ == "__main__":
    amount = int(float(input("Введите количество crvUSD для добавления в пул: ")) * 10**18)

    # Проверяем баланс
    crvUSD_contract = web3.eth.contract(address=CRVUSD_ADDRESS, abi=abis.ERC20)
    balance = crvUSD_contract.functions.balanceOf(WALLET_ADDRESS).call()
    assert balance >= amount, "Недостаточно crvUSD токенов"

    # Проверяем разрешение
    allowance = get_allowance(
        web3=web3,
        wallet_address=WALLET_ADDRESS,
        token_address=CRVUSD_ADDRESS,
        spender=GMAC_CRVUSD_ETH_POOL_ADDRESS,
    )

    logger.info(f"Allowance: {allowance}")
    if allowance < amount:
        logger.info("Выдаем разрешение...")
        approve_tx = build_approve_tx(
            web3=web3,
            wallet_address=WALLET_ADDRESS,
            token_address=CRVUSD_ADDRESS,
            spender=GMAC_CRVUSD_ETH_POOL_ADDRESS,
            amount=amount,
        )

        tx_hash = send_tx(web3, approve_tx, PRIVATE_KEY)
        logger.info(f"Транзакция разрешения: {tx_hash}")

        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        logger.info(f"Разрешение добавлено: {receipt}")

    # Совершаем добавление ликвидности
    add_liquidity_tx = build_add_liquidity_tx(
        web3=web3,
        wallet_address=WALLET_ADDRESS,
        pool_address=GMAC_CRVUSD_ETH_POOL_ADDRESS,
        amounts=[amount, 0, 0],  # [crvUSD, ETH, GMAC]
    )

    add_liquidity_tx_hash = send_tx(web3, add_liquidity_tx, PRIVATE_KEY)
    logger.info(f"Транзакция добавления ликвидности: {add_liquidity_tx_hash}")
