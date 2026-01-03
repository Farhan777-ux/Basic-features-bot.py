#!/usr/bin/env python3
"""
Basic Binance Futures (USDT-M) Testnet trading bot.

Requirements:
- Python 3.10+
- python-binance (pip install python-binance)
- Binance USDT-M Futures TESTNET (NOT mainnet, NOT spot)

This script:
- Initializes a Binance Futures testnet client
- Supports MARKET, LIMIT, and STOP-LIMIT orders (BUY / SELL)
- Validates CLI input
- Logs API requests/responses/errors
- Prints clean order summaries
"""

import argparse
import logging
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

from binance.client import Client
from binance.exceptions import (
    BinanceAPIException,
    BinanceRequestException,
    BinanceOrderException,
)

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

LOGGER = logging.getLogger("basic_futures_bot")


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger for the bot."""
    logger = logging.getLogger()
    logger.setLevel(level)

    # Clear any existing handlers (avoids duplicates if re-run in REPL)
    if logger.handlers:
        logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)


# ---------------------------------------------------------------------------
# Custom exceptions and data containers
# ---------------------------------------------------------------------------


class TradingBotError(Exception):
    """Base exception type for trading bot errors."""

    pass


@dataclass
class OrderParams:
    """Normalized and validated order parameters."""

    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------


class InputValidator:
    """Validation utilities for CLI/user inputs."""

    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """Validate and normalize a futures symbol (e.g., BTCUSDT)."""
        if not symbol or not symbol.strip():
            raise ValueError("Symbol must not be empty.")
        symbol = symbol.strip().upper()
        # Simple sanity check; Binance will do full validation.
        if len(symbol) < 6:
            raise ValueError("Symbol looks invalid (too short). Example: BTCUSDT.")
        return symbol

    @staticmethod
    def validate_side(side: str) -> str:
        """Validate order side: BUY or SELL."""
        if not side:
            raise ValueError("Side must be provided (BUY or SELL).")
        side_upper = side.strip().upper()
        if side_upper not in {"BUY", "SELL"}:
            raise ValueError("Side must be BUY or SELL.")
        return side_upper

    @staticmethod
    def validate_order_type(order_type: str) -> str:
        """
        Validate order type.

        Supported:
        - MARKET
        - LIMIT
        - STOP_LIMIT (advanced example)
        """
        if not order_type:
            raise ValueError("Order type must be provided.")
        t = order_type.strip().upper()
        aliases = {
            "MKT": "MARKET",
            "STOP-LIMIT": "STOP_LIMIT",
            "STOPLIMIT": "STOP_LIMIT",
        }
        t = aliases.get(t, t)

        if t not in {"MARKET", "LIMIT", "STOP_LIMIT"}:
            raise ValueError("Order type must be MARKET, LIMIT, or STOP_LIMIT.")
        return t

    @staticmethod
    def validate_positive_float(value: str, field_name: str) -> float:
        """Validate that value is a positive float."""
        try:
            f = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a number.")
        if f <= 0:
            raise ValueError(f"{field_name} must be greater than 0.")
        return f

    @staticmethod
    def validate_order_params(args: argparse.Namespace) -> OrderParams:
        """Validate and normalize all order-related CLI arguments."""
        symbol = InputValidator.validate_symbol(args.symbol)
        side = InputValidator.validate_side(args.side)
        order_type = InputValidator.validate_order_type(args.type)
        quantity = InputValidator.validate_positive_float(args.qty, "Quantity")

        price = None
        stop_price = None

        if order_type in {"LIMIT", "STOP_LIMIT"}:
            if args.price is None:
                raise ValueError("Price is required for LIMIT and STOP_LIMIT orders.")
            price = InputValidator.validate_positive_float(args.price, "Price")

        if order_type == "STOP_LIMIT":
            if args.stop_price is None:
                raise ValueError("stop-price is required for STOP_LIMIT orders.")
            stop_price = InputValidator.validate_positive_float(
                args.stop_price, "Stop price"
            )

        return OrderParams(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )


# ---------------------------------------------------------------------------
# Trading logic
# ---------------------------------------------------------------------------


class BasicBot:
    """
    Basic Binance USDT-M Futures Testnet bot.

    - Uses Binance Futures TESTNET base URL: https://testnet.binancefuture.com
    - Supports MARKET, LIMIT, and STOP-LIMIT orders.
    """

    TESTNET_FUTURES_BASE_URL = "https://testnet.binancefuture.com/fapi"

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True) -> None:
        """
        Initialize the Binance Futures testnet client.

        Parameters
        ----------
        api_key : str
            Binance API key.
        api_secret : str
            Binance API secret.
        testnet : bool
            Must be True for testnet usage.
        """
        if not testnet:
            # Enforce testnet-only usage by design.
            raise TradingBotError("This bot is restricted to Binance Futures TESTNET.")

        self.client = Client(api_key, api_secret, testnet=True)

        # Explicitly set Futures testnet base URLs to ensure we never hit mainnet.
        # Note: python-binance uses these attributes internally for futures endpoints.
        if hasattr(self.client, "FUTURES_URL"):
            self.client.FUTURES_URL = self.TESTNET_FUTURES_BASE_URL
        if hasattr(self.client, "FUTURES_DATA_URL"):
            self.client.FUTURES_DATA_URL = self.TESTNET_FUTURES_BASE_URL

        LOGGER.info("Initialized Binance Futures TESTNET client.")

    def _build_order_payload(self, params: OrderParams) -> Dict[str, Any]:
        """
        Map our normalized parameters to Binance Futures API parameters.

        This bot sends all orders as standard futures orders:
        - MARKET
        - LIMIT
        - STOP (used as STOP-LIMIT)
        """
        payload: Dict[str, Any] = {
            "symbol": params.symbol,
            "side": params.side,
            "type": None,  # filled below
            "quantity": params.quantity,
        }

        if params.order_type == "MARKET":
            payload["type"] = "MARKET"

        elif params.order_type == "LIMIT":
            payload["type"] = "LIMIT"
            payload["timeInForce"] = "GTC"
            payload["price"] = params.price

        elif params.order_type == "STOP_LIMIT":
            # Implement STOP-LIMIT as a STOP order with price + stopPrice
            # See Binance UM Futures docs for STOP orders.
            payload["type"] = "STOP"
            payload["timeInForce"] = "GTC"
            payload["price"] = params.price
            payload["stopPrice"] = params.stop_price

        else:
            raise TradingBotError(f"Unsupported internal order type: {params.order_type}")

        return payload

    def place_order(self, params: OrderParams) -> Dict[str, Any]:
        """
        Place a futures order on Binance Futures TESTNET.

        Returns
        -------
        dict
            Raw order response from Binance Futures API.
        """
        payload = self._build_order_payload(params)

        LOGGER.info(
            "Placing order | symbol=%s side=%s type=%s qty=%s price=%s stopPrice=%s",
            payload.get("symbol"),
            payload.get("side"),
            payload.get("type"),
            payload.get("quantity"),
            payload.get("price"),
            payload.get("stopPrice"),
        )

        try:
            # futures_create_order uses futures (USDT-M) endpoints, not spot.
            response = self.client.futures_create_order(**payload)
            LOGGER.info("Order placed successfully. Binance response received.")
            LOGGER.debug("Raw order response: %s", response)
            return response

        except (BinanceAPIException, BinanceOrderException, BinanceRequestException) as e:
            # Known Binance-related errors (validation, insufficient margin, etc.)
            LOGGER.error("Binance API error: %s", str(e))
            raise TradingBotError(f"Binance API error: {e}") from None
        except Exception as e:
            # Unexpected issues (network, internal bugs, etc.)
            LOGGER.error("Unexpected error while placing order: %s", str(e))
            raise TradingBotError(f"Unexpected error while placing order: {e}") from None


# ---------------------------------------------------------------------------
# CLI logic
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Basic Binance USDT-M Futures Testnet trading bot."
    )

    # Credentials (env vars strongly recommended)
    parser.add_argument(
        "--api-key",
        dest="api_key",
        help="Binance API key (or set BINANCE_API_KEY env var).",
    )
    parser.add_argument(
        "--api-secret",
        dest="api_secret",
        help="Binance API secret (or set BINANCE_API_SECRET env var).",
    )

    # Order parameters
    parser.add_argument(
        "--symbol",
        required=True,
        help="Trading symbol, e.g., BTCUSDT.",
    )
    parser.add_argument(
        "--side",
        required=True,
        help="Order side: BUY or SELL.",
    )
    parser.add_argument(
        "--type",
        required=True,
        help="Order type: MARKET, LIMIT, or STOP_LIMIT.",
    )
    parser.add_argument(
        "--qty",
        required=True,
        help="Order quantity (e.g., 0.001).",
    )
    parser.add_argument(
        "--price",
        help="Price (required for LIMIT and STOP_LIMIT).",
    )
    parser.add_argument(
        "--stop-price",
        dest="stop_price",
        help="Stop price (required for STOP_LIMIT).",
    )

    return parser.parse_args()


def resolve_credentials(args: argparse.Namespace) -> tuple[str, str]:
    """Resolve API key/secret from CLI or environment variables."""
    api_key = args.api_key or os.getenv("BINANCE_API_KEY")
    api_secret = args.api_secret or os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        raise TradingBotError(
            "API credentials are required. Provide --api-key / --api-secret or set "
            "BINANCE_API_KEY / BINANCE_API_SECRET environment variables."
        )
    return api_key, api_secret


def print_order_summary(order: Dict[str, Any]) -> None:
    """
    Print a clean order summary for the user.

    Key fields:
    - Order ID
    - Symbol
    - Side
    - Order type
    - Status
    - Executed quantity
    """
    # Binance futures response structure reference:
    # {
    #   "orderId": 12345,
    #   "symbol": "BTCUSDT",
    #   "status": "NEW",
    #   "clientOrderId": "...",
    #   "price": "0",
    #   "avgPrice": "0.0",
    #   "origQty": "0.001",
    #   "executedQty": "0",
    #   "cumQuote": "0",
    #   "timeInForce": "GTC",
    #   "type": "MARKET",
    #   "side": "BUY",
    #   ...
    # }

    order_id = order.get("orderId")
    symbol = order.get("symbol")
    side = order.get("side")
    o_type = order.get("type")
    status = order.get("status")
    executed_qty = order.get("executedQty")

    print("\n=== Order Summary ===")
    print(f"Order ID         : {order_id}")
    print(f"Symbol           : {symbol}")
    print(f"Side             : {side}")
    print(f"Type             : {o_type}")
    print(f"Status           : {status}")
    print(f"Executed Quantity: {executed_qty}")
    print("=====================\n")


def main() -> None:
    """Entry point for CLI execution."""
    setup_logging()

    try:
        args = parse_args()
        LOGGER.info("CLI arguments parsed.")
        params = InputValidator.validate_order_params(args)
        LOGGER.info(
            "Validated order params | symbol=%s side=%s type=%s qty=%s",
            params.symbol,
            params.side,
            params.order_type,
            params.quantity,
        )

        api_key, api_secret = resolve_credentials(args)
        bot = BasicBot(api_key=api_key, api_secret=api_secret, testnet=True)

        order_response = bot.place_order(params)
        print_order_summary(order_response)

    except ValueError as e:
        # Input validation errors
        LOGGER.error("Input validation error: %s", str(e))
        print(f"Error: {e}")
    except TradingBotError as e:
        # Higher-level bot/trading errors
        LOGGER.error("Trading bot error: %s", str(e))
        print(f"Error: {e}")
    except KeyboardInterrupt:
        LOGGER.warning("Execution interrupted by user.")
        print("\nExecution interrupted by user.")
    # No raw stack traces printed for normal failures.


if __name__ == "__main__":
    main()
