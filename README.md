# Binance Futures Testnet Trading Bot

A simplified trading bot for Binance USDT-M Futures Testnet built in Python using the python-binance library.

Testnet only — no real funds are used.

## Features
- Binance USDT-M Futures Testnet only
- Market, Limit, and Stop-Limit orders
- BUY and SELL support
- Command-line interface
- Input validation
- Logging and error handling
- Clean order execution summary

## Requirements
- Python 3.10+
- Binance Futures Testnet API key and secret

## Installation
pip install -r requirements.txt

## Configuration
export BINANCE_API_KEY="your_testnet_api_key"
export BINANCE_API_SECRET="your_testnet_api_secret"

## Usage

Market order:
python basic_bot.py --symbol BTCUSDT --side BUY --type MARKET --qty 0.001

Limit order:
python basic_bot.py --symbol BTCUSDT --side SELL --type LIMIT --qty 0.001 --price 30000

Stop-Limit order:
python basic_bot.py --symbol BTCUSDT --side BUY --type STOP_LIMIT --qty 0.001 --price 31000 --stop-price 30500

## Notes
- Uses Binance Futures Testnet only
- Mainnet and Spot trading are intentionally disabled
- Leverage and margin configuration are out of scope

## Disclaimer
For educational and evaluation purposes only.
