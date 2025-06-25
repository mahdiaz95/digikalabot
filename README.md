# 🤖 Digikala Competitive Pricing Telegram Bot

This project is an **automated Telegram bot** that helps Digikala sellers periodically adjust their product prices **based on competitor pricing**.

## ✨ Features

- User authentication via Digikala store token
- Fetch seller product data from Digikala
- Generate an Excel file with product information
- Accept edited Excel to activate selected products for price adjustment
- Apply automatic price reduction algorithm based on competitors
- Define minimum price and undercut value
- Repeats the pricing process at user-defined intervals

## 🧠 How It Works

1. User submits their Digikala store token.
2. The bot fetches product data and sends an Excel file.
3. User edits the file to mark products for pricing.
4. The bot reads the file and applies pricing logic accordingly.
5. The pricing process is repeated periodically (e.g., every 10 minutes).

## 🛠 Requirements

- Python 3.9+
- Required libraries:
  - `aiohttp`, `aiofiles`, `pandas`, `playwright`, `python-telegram-bot`, `apscheduler`, `persiantools`, `openpyxl`
- Install Playwright:
  ```bash
  pip install playwright
  playwright install
🚀 Running the Bot

    Set your bot token and authorized users in the code or via environment variables.

    Run the bot:

python main.py

##🔒 Access Control

Only users listed in the AUTHORIZED_USERS dictionary are allowed to use the bot.

⚠️ Important Notes

Only specific columns in the Excel file should be edited.
Prices must be reasonable and valid.
Products must be active in the Digikala seller panel.
