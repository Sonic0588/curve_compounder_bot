import logging
import random
from decimal import Decimal

from web3 import Web3

import abis


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class GasTracker:
    """Класс для отслеживания газовых затрат"""

    def __init__(self, web3: Web3):
        self.web3 = web3
        self.transactions: list[tuple[str, int, int, int | Decimal]] = []  # (name, gas_used, gas_price, cost_eth)

    def add_transaction(self, name: str, tx_hash) -> None:
        """Добавляет транзакцию для отслеживания газа"""
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
        gas_used = receipt["gasUsed"]

        # Получаем транзакцию для получения gas price
        tx = self.web3.eth.get_transaction(tx_hash)
        gas_price = tx["gasPrice"]

        # Вычисляем стоимость в ETH
        cost_wei = gas_used * gas_price
        cost_eth = Web3.from_wei(cost_wei, "ether")

        self.transactions.append((name, gas_used, gas_price, cost_eth))
        logger.info(f"Gas для {name}: {gas_used:,} единиц, цена: {gas_price:,} wei, стоимость: {cost_eth:.6f} ETH")

    def get_total_cost(self) -> tuple[int, int | Decimal]:
        """Возвращает общие затраты газа"""
        total_gas = sum(tx[1] for tx in self.transactions)
        total_cost_eth = sum(tx[3] for tx in self.transactions)
        return total_gas, total_cost_eth

    def print_summary(self) -> None:
        """Выводит сводку по газовым затратам"""
        if not self.transactions:
            logger.info("Транзакций не было выполнено")
            return

        print("\n" + "=" * 80)
        print("СВОДКА ГАЗОВЫХ ЗАТРАТ")
        print("=" * 80)

        for i, (name, gas_used, gas_price, cost_eth) in enumerate(self.transactions, 1):
            print(f"{i}. {name}")
            print(f"   Газ использован: {gas_used:,} единиц")
            print(f"   Цена газа: {gas_price:,} wei ({gas_price / 10**9:.2f} gwei)")
            print(f"   Стоимость: {cost_eth:.6f} ETH")
            print()

        total_gas, total_cost_eth = self.get_total_cost()
        print("-" * 80)
        print("ИТОГО:")
        print(f"Общий газ: {total_gas:,} единиц")
        print(f"Общая стоимость: {total_cost_eth:.6f} ETH")

        # Получаем текущую цену ETH для конвертации в USD (опционально)
        try:
            # Здесь можно добавить получение курса ETH/USD через API
            print("Примечание: Для конвертации в USD используйте текущий курс ETH")
        except Exception as e:
            logger.debug(f"Не удалось получить курс ETH: {e}")

        print("=" * 80)


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


def send_tx_with_tracking(web3: Web3, tx: dict, private_key: str, gas_tracker: GasTracker, tx_name: str) -> str:
    """Отправляет транзакцию и добавляет её в трекер газа"""
    tx_hash = send_tx(web3, tx, private_key)
    gas_tracker.add_transaction(tx_name, tx_hash)
    return tx_hash


def get_allowance(web3: Web3, wallet_address, token_address, spender):
    """Проверка разрешенного количества токенов"""
    contract = web3.eth.contract(
        address=Web3.to_checksum_address(token_address),
        abi=abis.ERC20,
    )

    return contract.functions.allowance(Web3.to_checksum_address(wallet_address), spender).call()


def approve(web3: Web3, wallet_address, token_address, spender, balance, private_key, gas_tracker):
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

    tx_hash = send_tx_with_tracking(web3, approve_tx, private_key, gas_tracker, "Разрешение токена")

    return tx_hash
