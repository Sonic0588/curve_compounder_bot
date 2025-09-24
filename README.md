# Curve Compounder Bot

> [!NOTE]
> **Status:** Active Development / Alpha / Beta

Автоматизированный бот для отслеживания и реинвестирования (компаундинга) доходности позиций в пулах ликвидности на Curve Finance.

## 🚀 Основная функциональность

*   Отслеживание позиции в Curve pool.
*   Расчет текущей доходности (APY).
*   Автоматическое выполнение операции `claim_rewards`, `swap_rewards` и `add_liquidity`.
*   (Опционально) Уведомления в Telegram.

## 🛠 Технологический стек

*   **Language:** Python 3.12+
*   **Web3 Library:** Web3.py
*   **Config:** Pydantic (для валидации конфигурации)
*   **Testing:** Pytest
*   **Containerization:** Docker

## 📦 Установка и запуск

2.  Установите зависимости:
    ```bash
    pip install -r requirements.txt
    ```

3.  Настройте конфигурацию:
    ```bash
    cp .env.example .env
    # Отредактируйте .env: добавьте RPC URL, приватный ключ, адреса контрактов
    ```

4.  Запустите в режиме теста (без реальных транзакций):
    ```bash
    python -m src.curve_compounder.main --dry-run
    ```
   
