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
import base64

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

# Cache for generated content
content_cache = {}

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

def send_solana_transaction(sender_keypair, recipient_address, amount, token_address=None):
    """Send SOL or SPL tokens on the Solana blockchain."""
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
                    decimals=9  # Adjust based on token decimals
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

def chatbot():
    """Command-line chatbot interface."""
    print("Welcome to the DeepSeek + Solana Chatbot!")
    print("Commands:")
    print("1. connect_wallet <wallet_name> - Connect a Solana wallet")
    print("2. send <wallet_name> <recipient_address> <amount> [token_address] - Send SOL or SPL tokens")
    print("3. receive <wallet_name> [limit] - View transaction history")
    print("4. generate <prompt> [model] [max_tokens] - Generate content using DeepSeek")
    print("5. exit - Exit the chatbot")

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

            elif cmd == "generate":
                if len(args) < 1:
                    print("Usage: generate <prompt> [model] [max_tokens]")
                    continue
                prompt = args[0]
                model = args[1] if len(args) > 1 else "default"
                max_tokens = int(args[2]) if len(args) > 2 else 100
                generated_content = generate_with_deepseek(prompt, model, max_tokens)
                print("Generated Content:", generated_content)

            elif cmd == "exit":
                print("Goodbye!")
                break

            else:
                print("Invalid command. Type 'help' for a list of commands.")

        except Exception as e:
            print("Error:", str(e))

if __name__ == "__main__":
    chatbot()
