import logging

from web3 import Web3

import abis
from addresses import (
    CRV_ADDRESS,
    CRVUSD_ADDRESS,
    GMAC_CRVUSD_ETH_GAUGE_ADDRESS,
    GMAC_CRVUSD_ETH_POOL_ADDRESS,
    GMAC_CRVUSD_ETH_STAKE_DAO_VAULT_ADDRESS,
    ONEINCH_ROUTER_ADDRESS,
)
from config import ARBITRUM_RPC, PRIVATE_KEY, WALLET_ADDRESS
from curve import build_add_liquidity_tx
from oneinch import build_swap_tx, get_quote
from stake_dao import build_claim_tx, build_deposit_tx
from utils import approve, send_tx


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    # Инициализация Web3
    web3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))
    assert web3.is_connected(), "Не удалось подключиться к сети Arbitrum"

    TOTAL_GAS_SPENT = 0

    # Собираем награды в StakeDAO
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
    TOTAL_GAS_SPENT += receipt["gasUsed"] * receipt["effectiveGasPrice"]
    logger.debug(f"Награды собраны: {receipt}")

    # Меняем весь собранный CRV на crvUSD
    crv_contract = web3.eth.contract(address=Web3.to_checksum_address(CRV_ADDRESS), abi=abis.ERC20)
    crv_balance = crv_contract.functions.balanceOf(WALLET_ADDRESS).call()
    logger.info(f"CRV balance: {Web3.from_wei(crv_balance, 'ether'):.4f}")

    quote = get_quote(CRV_ADDRESS, CRVUSD_ADDRESS, crv_balance)
    logger.info(f"Получим примерно: {int(quote['dstAmount']) / 10**18} crvUSD")

    approved_crv = approve(
        web3=web3,
        wallet_address=WALLET_ADDRESS,
        token_address=CRV_ADDRESS,
        spender=ONEINCH_ROUTER_ADDRESS,
        balance=crv_balance,
        private_key=PRIVATE_KEY,
    )

    if approved_crv:
        TOTAL_GAS_SPENT += approved_crv["gasUsed"] * approved_crv["effectiveGasPrice"]

    swap_tx = build_swap_tx(
        wallet_address=WALLET_ADDRESS,
        from_token=CRV_ADDRESS,
        to_token=CRVUSD_ADDRESS,
        amount=crv_balance,
    )

    swap_tx_hash = send_tx(web3, swap_tx, PRIVATE_KEY)
    logger.info(f"Транзакция обмена: {swap_tx_hash}")
    receipt = web3.eth.wait_for_transaction_receipt(swap_tx_hash)
    TOTAL_GAS_SPENT += receipt["gasUsed"] * receipt["effectiveGasPrice"]
    logger.debug(f"Обмен завершен: {receipt}")

    # Добавляем весь crvUSD в пул GMAC/crvUSD/ETH
    crvUSD_contract = web3.eth.contract(address=CRVUSD_ADDRESS, abi=abis.ERC20)
    crvUSD_balance = crvUSD_contract.functions.balanceOf(WALLET_ADDRESS).call()
    logger.info(f"crvUSD balance: {Web3.from_wei(crvUSD_balance, 'ether'):.4f}")

    approved_crvUSD = approve(
        web3=web3,
        wallet_address=WALLET_ADDRESS,
        token_address=CRVUSD_ADDRESS,
        spender=GMAC_CRVUSD_ETH_POOL_ADDRESS,
        balance=crvUSD_balance,
        private_key=PRIVATE_KEY,
    )

    if approved_crvUSD:
        TOTAL_GAS_SPENT += approved_crvUSD["gasUsed"] * approved_crvUSD["effectiveGasPrice"]

    # Совершаем добавление ликвидности
    add_liquidity_tx = build_add_liquidity_tx(
        web3=web3,
        wallet_address=WALLET_ADDRESS,
        pool_address=GMAC_CRVUSD_ETH_POOL_ADDRESS,
        amounts=[crvUSD_balance, 0, 0],  # [crvUSD, ETH, GMAC]
    )

    add_liquidity_tx_hash = send_tx(web3, add_liquidity_tx, PRIVATE_KEY)
    logger.info(f"Транзакция добавления ликвидности: {add_liquidity_tx_hash}")
    receipt = web3.eth.wait_for_transaction_receipt(add_liquidity_tx_hash)
    TOTAL_GAS_SPENT += receipt["gasUsed"] * receipt["effectiveGasPrice"]
    logger.debug(f"Ликвидность добавлена: {receipt}")

    # Добавляем полученные LP токены в Vault StakeDAO
    lp_token_contract = web3.eth.contract(address=GMAC_CRVUSD_ETH_POOL_ADDRESS, abi=abis.ERC20)
    lp_token_balance = lp_token_contract.functions.balanceOf(WALLET_ADDRESS).call()
    logger.info(f"TriGemach balance: {Web3.from_wei(lp_token_balance, 'ether'):.4f}")

    approved_LP = approve(
        web3=web3,
        wallet_address=WALLET_ADDRESS,
        token_address=GMAC_CRVUSD_ETH_POOL_ADDRESS,
        spender=GMAC_CRVUSD_ETH_STAKE_DAO_VAULT_ADDRESS,
        balance=lp_token_balance,
        private_key=PRIVATE_KEY,
    )

    if approved_LP:
        TOTAL_GAS_SPENT += approved_LP["gasUsed"] * approved_LP["effectiveGasPrice"]

    deposit_tx = build_deposit_tx(
        web3=web3,
        wallet_address=WALLET_ADDRESS,
        vault_address=GMAC_CRVUSD_ETH_STAKE_DAO_VAULT_ADDRESS,
        amount=lp_token_balance,
    )

    deposit_tx_hash = send_tx(web3, deposit_tx, PRIVATE_KEY)
    logger.info(f"Транзакция депозита LP токена в vault: {deposit_tx_hash}")
    receipt = web3.eth.wait_for_transaction_receipt(deposit_tx_hash)
    TOTAL_GAS_SPENT += receipt["gasUsed"] * receipt["effectiveGasPrice"]
    logger.debug(f"TriGemach токен добавлен: {receipt}")
    logger.info(f"Всего потрачено на газ: {Web3.from_wei(TOTAL_GAS_SPENT, 'ether'):.6f} ")


if __name__ == "__main__":
    main()
