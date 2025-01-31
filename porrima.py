import requests
from solana.rpc.api import Client
from solana.publickey import PublicKey
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer
from solana.keypair import Keypair
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed
from solana.rpc.core import RPCException
from solana.sysvar import SYSVAR_RENT_PUBKEY
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import transfer_checked, TransferCheckedParams
import json
import logging
from getpass import getpass
import base58
import pyotp
import csv
import aiohttp
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# DeepSeek API details
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/generate"
DEEPSEEK_API_KEY = "your_deepseek_api_key"

# Solana network details
SOLANA_NETWORK_URL = "https://api.mainnet-beta.solana.com"  # Use "https://api.devnet.solana.com" for testing
solana_client = Client(SOLANA_NETWORK_URL)

# Wallet management
wallets = {}  # Stores multiple wallets: {wallet_name: Keypair}
current_wallet = None  # Tracks the currently active wallet

# Cache for generated content
content_cache = {}

# 2FA setup
totp = pyotp.TOTP(pyotp.random_base32())

# Helper Functions
def generate_with_deepseek(prompt, model="default", max_tokens=100):
    """Generate content using DeepSeek API with advanced options."""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "prompt": prompt,
        "model": model,
        "max_tokens": max_tokens
    }
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
        response.raise_for_status()
        generated_text = response.json()["choices"][0]["text"]
        content_cache[prompt] = generated_text  # Cache the result
        return generated_text
    except requests.exceptions.RequestException as e:
        logging.error(f"DeepSeek API Error: {e}")
        raise

def verify_2fa(code: str) -> bool:
    """Verify 2FA code."""
    return totp.verify(code)

def connect_wallet(wallet_name, private_key=None):
    """Connect a wallet by name and store it securely."""
    if not private_key:
        private_key = getpass("Enter your private key (base58 encoded): ")
    try:
        keypair = Keypair.from_secret_key(base58.b58decode(private_key))
        wallets[wallet_name] = keypair
        logging.info(f"Wallet '{wallet_name}' connected: {keypair.public_key}")
    except Exception as e:
        logging.error(f"Failed to connect wallet: {e}")
        raise

def switch_wallet(wallet_name):
    """Switch to another connected wallet."""
    global current_wallet
    if wallet_name in wallets:
        current_wallet = wallet_name
        logging.info(f"Switched to wallet '{wallet_name}'")
    else:
        logging.error(f"Wallet '{wallet_name}' not found.")

async def get_nfts(wallet_address):
    """Fetch NFTs for a wallet address."""
    url = f"https://api.simplehash.com/api/v0/nfts/owners?wallet_addresses={wallet_address}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    nfts = await response.json()
                    return nfts
                else:
                    logging.error(f"Failed to fetch NFTs: {response.status}")
                    return None
    except Exception as e:
        logging.error(f"Error fetching NFTs: {e}")
        return None

async def get_sol_price():
    """Fetch the current SOL price."""
    url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    price_data = await response.json()
                    return price_data["solana"]["usd"]
                else:
                    logging.error(f"Failed to fetch SOL price: {response.status}")
                    return None
    except Exception as e:
        logging.error(f"Error fetching SOL price: {e}")
        return None

def export_transaction_history(wallet_address, filename="transactions.csv"):
    """Export transaction history to a CSV file."""
    transactions = receive_solana_transactions(wallet_address)
    if transactions:
        with open(filename, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Signature", "Slot", "Block Time"])
            for tx in transactions["result"]:
                writer.writerow([tx["signature"], tx["slot"], tx["blockTime"]])
        logging.info(f"Transaction history exported to {filename}")

# Solana Functions
def send_solana_transaction(sender_keypair, recipient_address, amount, token_address=None, decimals=9):
    """Send SOL or SPL tokens on the Solana blockchain."""
    code = input("Enter 2FA code: ")
    if not verify_2fa(code):
        logging.error("Invalid 2FA code.")
        return

    sender_public_key = sender_keypair.public_key
    recipient_public_key = PublicKey(recipient_address)

    if token_address:
        # Transfer SPL tokens
        token_public_key = PublicKey(token_address)
        transaction = Transaction().add(
            transfer_checked(
                TransferCheckedParams(
                    program_id=TOKEN_PROGRAM_ID,
                    source=sender_public_key,
                    mint=token_public_key,
                    dest=recipient_public_key,
                    owner=sender_public_key,
                    amount=amount,
                    decimals=decimals  # Use provided decimals
                )
            )
        )
    else:
        # Transfer SOL
        transaction = Transaction().add(transfer(TransferParams(
            from_pubkey=sender_public_key,
            to_pubkey=recipient_public_key,
            lamports=amount  # Amount in lamports (1 SOL = 1,000,000,000 lamports)
        )))

    try:
        transaction.sign(sender_keypair)
        result = solana_client.send_transaction(transaction, sender_keypair, opts=TxOpts(skip_confirmation=False))
        logging.info(f"Transaction sent: {result}")
        return result
    except RPCException as e:
        logging.error(f"Transaction failed: {e}")
        raise

def receive_solana_transactions(wallet_address, limit=10):
    """Fetch transaction history for a wallet address."""
    public_key = PublicKey(wallet_address)
    try:
        transactions = solana_client.get_signatures_for_address(public_key, limit=limit)
        return transactions
    except RPCException as e:
        logging.error(f"Failed to fetch transactions: {e}")
        raise

# Chatbot Interface
def chatbot():
    """Command-line chatbot interface."""
    print("Welcome to the Advanced DeepSeek + Solana Chatbot!")
    print("Commands:")
    print("1. connect_wallet <wallet_name> - Connect a Solana wallet")
    print("2. switch_wallet <wallet_name> - Switch to another connected wallet")
    print("3. send <wallet_name> <recipient_address> <amount> [token_address] - Send SOL or SPL tokens")
    print("4. receive <wallet_name> [limit] - View transaction history")
    print("5. nfts <wallet_name> - View NFTs in the wallet")
    print("6. price - Get the current SOL price")
    print("7. generate <prompt> [model] [max_tokens] - Generate content using DeepSeek")
    print("8. export_history <wallet_name> <filename> - Export transaction history to CSV")
    print("9. exit - Exit the chatbot")

    while True:
        command = input("\nEnter command: ").strip().split()
        if not command:
            continue

        cmd = command[0].lower()
        args = command[1:]

        try:
            if cmd == "connect_wallet":
                if len(args) != 1:
                    print("Usage: connect_wallet <wallet_name>")
                    continue
                wallet_name = args[0]
                connect_wallet(wallet_name)

            elif cmd == "switch_wallet":
                if len(args) != 1:
                    print("Usage: switch_wallet <wallet_name>")
                    continue
                wallet_name = args[0]
                switch_wallet(wallet_name)

            elif cmd == "send":
                if len(args) < 3:
                    print("Usage: send <wallet_name> <recipient_address> <amount> [token_address]")
                    continue
                wallet_name, recipient_address, amount = args[0], args[1], int(args[2])
                token_address = args[3] if len(args) > 3 else None
                if wallet_name not in wallets:
                    print(f"Wallet '{wallet_name}' not found. Connect it first.")
                    continue
                result = send_solana_transaction(wallets[wallet_name], recipient_address, amount, token_address)
                print("Transaction Result:", result)

            elif cmd == "receive":
                if len(args) < 1:
                    print("Usage: receive <wallet_name> [limit]")
                    continue
                wallet_name = args[0]
                limit = int(args[1]) if len(args) > 1 else 10
                if wallet_name not in wallets:
                    print(f"Wallet '{wallet_name}' not found. Connect it first.")
                    continue
                transactions = receive_solana_transactions(wallets[wallet_name].public_key, limit)
                print("Transaction History:", json.dumps(transactions, indent=2))

            elif cmd == "nfts":
                if len(args) != 1:
                    print("Usage: nfts <wallet_name>")
                    continue
                wallet_name = args[0]
                if wallet_name not in wallets:
                    print(f"Wallet '{wallet_name}' not found. Connect it first.")
                    continue
                nfts = asyncio.run(get_nfts(wallets[wallet_name].public_key))
                print("NFTs:", json.dumps(nfts, indent=2))

            elif cmd == "price":
                price = asyncio.run(get_sol_price())
                print(f"Current SOL Price: ${price}")

            elif cmd == "generate":
                if len(args) < 1:
                    print("Usage: generate <prompt> [model] [max_tokens]")
                    continue
                prompt = args[0]
                model = args[1] if len(args) > 1 else "default"
                max_tokens = int(args[2]) if len(args) > 2 else 100
                generated_content = generate_with_deepseek(prompt, model, max_tokens)
                print("Generated Content:", generated_content)

            elif cmd == "export_history":
                if len(args) < 2:
                    print("Usage: export_history <wallet_name> <filename>")
                    continue
                wallet_name, filename = args[0], args[1]
                if wallet_name not in wallets:
                    print(f"Wallet '{wallet_name}' not found. Connect it first.")
                    continue
                export_transaction_history(wallets[wallet_name].public_key, filename)

            elif cmd == "exit":
                print("Goodbye!")
                break

            else:
                print("Invalid command. Type 'help' for a list of commands.")

        except Exception as e:
            print("Error:", str(e))

if __name__ == "__main__":
    chatbot()
