import logging
import random

from web3 import Web3

import abis


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_gas_fees(web3: Web3):
    fee_history = web3.eth.fee_history(5, "latest", [50])
    base_fee = fee_history["baseFeePerGas"][-1]
    priority = int(base_fee * 0.1)

    rewards = sorted(r[0] for r in fee_history["reward"] if r)
    if rewards:
        mid = len(rewards) // 2
        priority = rewards[mid] if len(rewards) % 2 else (rewards[mid - 1] + rewards[mid]) // 2
        priority = int(priority * random.uniform(1.01, 1.03))

    return {
        "maxPriorityFeePerGas": priority,
        "maxFeePerGas": max(base_fee + priority, int(base_fee * 1.05)),
    }


def build_approve_tx(web3: Web3, wallet_address, token_address, spender, amount):
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
            "from": wallet_address,
            "nonce": web3.eth.get_transaction_count(wallet_address),
            "chainId": 42161,
            **get_gas_fees(web3),
        }
    )

    return tx


def send_tx(web3: Web3, tx, private_key):
    signed_tx = web3.eth.account.sign_transaction(tx, private_key)
    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
    return web3.to_hex(tx_hash)


def get_allowance(web3: Web3, wallet_address, token_address, spender):
    """Проверка разрешенного количества токенов"""
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=abis.ERC20,
    )

    return contract.functions.allowance(Web3.to_checksum_address(wallet_address), spender).call()


def approve(web3: Web3, wallet_address, token_address, spender, balance, private_key):
    allowance = get_allowance(
        web3=web3,
        wallet_address=wallet_address,
        token_address=token_address,
        spender=spender,
    )

    if allowance >= balance:
        return

    approve_tx = build_approve_tx(
        web3=web3,
        wallet_address=wallet_address,
        token_address=token_address,
        spender=spender,
        amount=balance,
    )

    tx_hash = send_tx(web3, approve_tx, private_key)
    logger.info(f"Транзакция разрешения: {tx_hash}")

    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    logger.debug(f"Разрешение добавлено: {receipt}")

    return receipt
