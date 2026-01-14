import os
import json
import requests
import asyncio
import threading
from telegram import Bot
from datetime import datetime
from flask import Flask

# ===== VARIABLES VIA RENDER ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

CHECK_INTERVAL = 60  # secondes (augmenté pour 10 wallets)

bot = Bot(token=BOT_TOKEN)
seen = set()

# ===== FLASK APP POUR RENDER =====
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Crypto Wallet Bot is running!<br>Transactions are being monitored."

@app.route('/health')
def health():
    return "OK", 200

# ===== CHARGER LES WALLETS =====
try:
    with open("wallets.json", "r") as f:
        WALLETS = json.load(f)
except FileNotFoundError:
    print("❌ wallets.json not found!")
    WALLETS = {}

# ===== RECUPERER LES TRANSACTIONS =====
def fetch_txs(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"Error fetching transactions for {wallet}: {e}")
        return []

# ===== CLASSIFIER LES TRANSACTIONS =====
def classify(tx):
    t = tx.get("type")
    if t == "SWAP":
        return "🟢 Achat / 🔴 Vente"
    if t == "TRANSFER":
        return "🔁 Transfert"
    if t in ["MINT", "CREATE_TOKEN"]:
        return "🆕 Création de token"
    if t == "NFT_SALE":
        return "💰 Vente NFT"
    if t == "NFT_MINT":
        return "🎨 Mint NFT"
    return "⚡ Autre"

# ===== FORMATER LES DETAILLES DE TRANSACTION =====
def format_transaction_details(tx, wallet_address, wallet_name):
    tx_signature = tx.get("signature", "N/A")[:8] + "..."
    timestamp = tx.get("timestamp", int(datetime.now().timestamp()))
    
    try:
        tx_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except:
        tx_time = "N/A"
    
    tx_type = classify(tx)
    
    amount = "N/A"
    if "nativeTransfers" in tx and tx["nativeTransfers"]:
        amount = tx["nativeTransfers"][0].get("amount", 0) / 1e9
        amount = f"{amount:.4f} SOL"
    
    token_info = ""
    if "tokenTransfers" in tx and tx["tokenTransfers"]:
        token_transfer = tx["tokenTransfers"][0]
        token_amount = token_transfer.get("tokenAmount", 0)
        token_symbol = token_transfer.get("symbol", "Unknown")
        token_info = f"\n💰 Token: {token_amount} {token_symbol}"
    
    message = f"""
🏦 **Wallet:** {wallet_name}
📝 **Signature:** `{tx_signature}`
⏰ **Heure:** {tx_time}
📊 **Type:** {tx_type}
💸 **Montant:** {amount}{token_info}
🔗 **Explorer:** https://solscan.io/tx/{tx.get('signature', '')}
📎 **Adresse:** `{wallet_address[:8]}...{wallet_address[-6:]}`
"""
    return message

# ===== ENVOYER MESSAGE TELEGRAM =====
async def send_telegram_message(message):
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        print(f"✓ Message sent to Telegram")
    except Exception as e:
        print(f"✗ Error sending message: {e}")

# ===== TRAITER LES NOUVELLES TRANSACTIONS =====
async def process_wallet(wallet_address, wallet_name):
    if not wallet_address or wallet_address == "":
        return
    
    print(f"Checking wallet: {wallet_name} ({wallet_address[:8]}...)")
    
    transactions = fetch_txs(wallet_address)
    if not transactions:
        return
    
    transactions.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    
    for tx in transactions[:3]:  # Seulement 3 transactions récentes
        tx_id = tx.get("signature")
        
        if not tx_id:
            continue
        
        if tx_id not in seen:
            seen.add(tx_id)
            
            await asyncio.sleep(2)
            
            message = format_transaction_details(tx, wallet_address, wallet_name)
            await send_telegram_message(message)
            
            print(f"New transaction for {wallet_name}: {tx_id[:10]}...")

# ===== BOUCLE PRINCIPALE DU BOT =====
async def bot_main():
    print("🤖 Bot started! Monitoring wallets...")
    
    # Initialisation
    print("Initializing: fetching existing transactions...")
    init_count = 0
    for wallet_address, wallet_name in WALLETS.items():
        if wallet_address and wallet_address != "":
            transactions = fetch_txs(wallet_address)
            if transactions:
                for tx in transactions[:5]:
                    tx_id = tx.get("signature")
                    if tx_id:
                        seen.add(tx_id)
                        init_count += 1
    
    print(f"Loaded {init_count} existing transactions into memory")
    
    # Boucle de surveillance
    while True:
        try:
            print(f"\n🔍 Checking {len(WALLETS)} wallets at {datetime.now().strftime('%H:%M:%S')}")
            
            for wallet_address, wallet_name in WALLETS.items():
                if wallet_address and wallet_address != "":
                    await process_wallet(wallet_address, wallet_name)
                    await asyncio.sleep(2)  # Pause entre wallets
            
            print(f"Sleeping for {CHECK_INTERVAL} seconds...")
            await asyncio.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Error in main loop: {e}")
            await asyncio.sleep(30)

# ===== FONCTION POUR DEMARRER FLASK =====
def run_flask():
    app.run(host='0.0.0.0', port=10000)

# ===== POINT D'ENTREE PRINCIPAL =====
if __name__ == "__main__":
    # Vérifier les variables d'environnement
    required_vars = ["BOT_TOKEN", "CHAT_ID", "HELIUS_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        exit(1)
    
    # Vérifier wallets.json
    if not WALLETS:
        print("❌ No wallets found in wallets.json!")
        exit(1)
    
    print(f"✅ Found {len(WALLETS)} wallets to monitor")
    
    # Démarrer Flask dans un thread séparé
    print("Starting Flask server on port 10000...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Démarrer le bot
    print("Starting bot monitoring...")
    
    try:
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
