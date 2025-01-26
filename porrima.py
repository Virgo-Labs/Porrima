import requests
from solana.rpc.api import Client
from solana.publickey import PublicKey
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer
from solana.keypair import Keypair

# DeepSeek API details
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/generate"
DEEPSEEK_API_KEY = "your_deepseek_api_key"

# Solana network details
SOLANA_NETWORK_URL = "https://api.mainnet-beta.solana.com"  # Use "https://api.devnet.solana.com" for testing
solana_client = Client(SOLANA_NETWORK_URL)

# Wallet management
wallet_keypair = None

def generate_with_deepseek(prompt):
    """Generate content using DeepSeek API."""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "prompt": prompt,
        "max_tokens": 100
    }
    response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["choices"][0]["text"]
    else:
        raise Exception(f"DeepSeek API Error: {response.status_code} - {response.text}")

def send_solana_transaction(sender_keypair, recipient_address, amount):
    """Send a transaction on the Solana blockchain."""
    sender_public_key = sender_keypair.public_key
    recipient_public_key = PublicKey(recipient_address)

    # Create a transfer transaction
    transaction = Transaction().add(transfer(TransferParams(
        from_pubkey=sender_public_key,
        to_pubkey=recipient_public_key,
        lamports=amount  # Amount in lamports (1 SOL = 1,000,000,000 lamports)
    )))

    # Sign and send the transaction
    transaction.sign(sender_keypair)
    result = solana_client.send_transaction(transaction, sender_keypair)
    return result

def receive_solana_transactions(wallet_address):
    """Fetch transaction history for a wallet address."""
    public_key = PublicKey(wallet_address)
    transactions = solana_client.get_signatures_for_address(public_key)
    return transactions

def chatbot():
    """Command-line chatbot interface."""
    global wallet_keypair

    print("Welcome to the DeepSeek + Solana Chatbot!")
    print("Commands:")
    print("1. connect_wallet <private_key> - Connect your Solana wallet")
    print("2. send <recipient_address> <amount> - Send SOL to a recipient")
    print("3. receive - View transaction history")
    print("4. generate <prompt> - Generate content using DeepSeek")
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
                    print("Usage: connect_wallet <private_key>")
                    continue
                private_key = args[0]
                wallet_keypair = Keypair.from_secret_key(bytes.fromhex(private_key))
                print(f"Wallet connected: {wallet_keypair.public_key}")

            elif cmd == "send":
                if not wallet_keypair:
                    print("Please connect your wallet first.")
                    continue
                if len(args) != 2:
                    print("Usage: send <recipient_address> <amount>")
                    continue
                recipient_address, amount = args[0], int(args[1])
                result = send_solana_transaction(wallet_keypair, recipient_address, amount)
                print("Transaction Result:", result)

            elif cmd == "receive":
                if not wallet_keypair:
                    print("Please connect your wallet first.")
                    continue
                transactions = receive_solana_transactions(wallet_keypair.public_key)
                print("Transaction History:", transactions)

            elif cmd == "generate":
                if len(args) < 1:
                    print("Usage: generate <prompt>")
                    continue
                prompt = " ".join(args)
                generated_content = generate_with_deepseek(prompt)
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
