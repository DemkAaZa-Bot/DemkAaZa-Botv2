import os
import json
import requests
import asyncio
from telegram import Bot

# ===== VARIABLES A REMPLACER VIA RENDER ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")

CHECK_INTERVAL = 25  # temps entre chaque vérification des wallets en secondes

bot = Bot(token=BOT_TOKEN)
seen = set()

# ===== CHARGER LES WALLETS DEPUIS wallets.json =====
with open("wallets.json", "r") as f:
    WALLETS = json.load(f)

# ===== FONCTION POUR RECUPERER LES TRANSACTIONS =====
def fetch_txs(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}"
    r = requests.get(url)
    return r.json() if r.status_code == 200 else []

# ===== FONCTION POUR CLASSIFIER LE TYPE DE TRANSACTION =====
def classify(tx):
    t = tx.get("type")
    if t == "SWAP":
        return "🟢 Achat / 🔴 Vente"
    if t == "TRANSFER":
        return "🔁 Transfert"
    if t in ["MINT", "CREATE_TOKEN"]:
        return "🆕 Création de token"
    return None

# ===== FONCTION POUR ENVOYER LE MESSAGE SUR TELEGRAM =====
async def notify(name, wallet, action, sig):
    msg = (
        f"👤 *{name}*\n"
        f"`{wallet}`\n\n"
        f"📌 {action}\n"
        f"🔗 https://solscan.io/tx/{sig}"
    )
    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

# ===== BOUCLE PRINCIPALE =====
async def main():
    while True:
        for name, wallet in WALLETS.items():
            txs = fetch_txs(wallet)
            for tx in txs:
                sig = tx["signature"]
                if sig in seen:
                    continue
                seen.add(sig)
                action = classify(tx)
                if action:
                    await notify(name, wallet, action, sig)
        await asyncio.sleep(CHECK_INTERVAL)

# ===== LANCEMENT DU BOT =====
if __name__ == "__main__":
    asyncio.run(main())
