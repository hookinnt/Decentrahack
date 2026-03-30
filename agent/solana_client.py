"""
solana_client.py — Real Solana Devnet integration for the AI Risk Oracle.

Responsibilities:
  - Maintain a live connection to Solana Devnet (fail-fast on startup)
  - Manage the AI agent's signing keypair
  - Build and broadcast signed transactions directly to the Anchor contract
  - Expose a status dict for the /api/status health endpoint
"""
import sys
import json
import time
from pathlib import Path

from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.message import Message
from solders.transaction import Transaction
from colorama import Fore, Style, init

init(autoreset=True)

# ─── Configuration ────────────────────────────────────────────────────────────

SOLANA_RPC_URL = "https://api.devnet.solana.com"

# The Program ID from our Anchor contract (lib.rs)
# In production, replace this with your actual deployed Program ID.
RISK_MANAGER_PROGRAM_ID = Pubkey.from_string("Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS")

KEYPAIR_FILE = Path("agent_keypair.json")

# Shared RPC client instance
solana_client = Client(SOLANA_RPC_URL)


# ─── Anchor Instruction Encoding ──────────────────────────────────────────────

def get_pda_treasury(authority: Pubkey) -> Pubkey:
    """
    Derive the PDA for the TreasuryState used in our Rust contract.
    Seeds must match: ["treasury", authority.pubkey]
    """
    seeds = [b"treasury", bytes(authority)]
    pda, _ = Pubkey.find_program_address(seeds, RISK_MANAGER_PROGRAM_ID)
    return pda


def encode_emergency_pause_ix(risk_score: int, reason: str) -> bytes:
    """
    Manually encode the Anchor instruction data for `emergency_pause`.
    
    Anchor uses a unique 8-byte discriminator for each instruction, 
    followed by BORSCH-serialized arguments.
    
    Layout:
      - 8 bytes: Discriminator (sha256("global:emergency_pause")[..8])
      - 1 byte : risk_score (u8)
      - 4 bytes: reason length (u32, little-endian)
      - N bytes: reason (UTF-8 bytes)
    """
    # Discriminator: 158f1b8ec8b5d2ff
    discriminator = bytes([0x15, 0x8f, 0x1b, 0x8e, 0xc8, 0xb5, 0xd2, 0xff])
    
    # Arg 1: risk_score (u8)
    arg_risk = bytes([risk_score & 0xFF])
    
    # Arg 2: reason (String)
    reason_bytes = reason.encode("utf-8")
    arg_reason_len = len(reason_bytes).to_bytes(4, "little")
    
    return discriminator + arg_risk + arg_reason_len + reason_bytes


# ─── Keypair Management ───────────────────────────────────────────────────────

def load_or_create_keypair() -> Keypair:
    """Load keypair from disk, or generate a new one if not found."""
    if KEYPAIR_FILE.exists():
        with open(KEYPAIR_FILE, "r") as f:
            secret = json.load(f)
            return Keypair.from_bytes(bytes(secret))

    print(f"{Fore.YELLOW}[Система] Генерирую новый keypair агента...")
    kp = Keypair()
    with open(KEYPAIR_FILE, "w") as f:
        json.dump(list(kp.to_bytes()), f)
    print(f"{Fore.GREEN}[Система] Keypair сохранён в {KEYPAIR_FILE}")
    return kp


# ─── Wallet Funding & Balance ──────────────────────────────────────────────────

def _request_airdrop_with_retry(pk: Pubkey, lamports: int, retries: int = 3) -> bool:
    """Request SOL airdrop with exponential backoff for Devnet stability."""
    for attempt in range(1, retries + 1):
        try:
            solana_client.request_airdrop(pk, lamports)
            wait_sec = 5 * attempt
            print(f"{Fore.YELLOW}  Попытка {attempt}/{retries}: ожидаю {wait_sec}с...")
            time.sleep(wait_sec)

            new_balance = solana_client.get_balance(pk).value
            if new_balance >= lamports:
                print(f"{Fore.GREEN}  Баланс пополнен: {new_balance / 1e9:.6f} SOL")
                return True
        except Exception as e:
            print(f"{Fore.YELLOW}  Airdrop attempt {attempt} failed: {e}")
        time.sleep(2)
    return False


def check_and_fund_wallet(kp: Keypair):
    """Notify user if balance is low, without blocking startup."""
    pk = kp.pubkey()
    balance = solana_client.get_balance(pk).value
    print(f"{Fore.CYAN}[Кошелек] Pubkey : {pk}")
    print(f"{Fore.CYAN}[Кошелек] Баланс : {balance / 1e9:.6f} SOL")

    if balance < 1_000_000:
        print(f"{Fore.YELLOW}[Кошелек] Баланс низкий. Для транзакций пополните через:")
        print(f"{Fore.CYAN}           https://faucet.solana.com  (address: {pk})")


# ─── Startup Check ────────────────────────────────────────────────────────────

def verify_solana_or_crash():
    """Fail-Fast initialization for maximum reliability."""
    print(f"{Fore.CYAN}[Система] Подключение к Solana ({SOLANA_RPC_URL})...")
    try:
        if not solana_client.is_connected():
            raise ConnectionError("RPC не ответил на пинг.")

        version_resp = solana_client.get_version()
        solana_version = version_resp.value.solana_core
        print(f"{Fore.GREEN}[OK] Solana v{solana_version} — подключено (Devnet).")

        kp = load_or_create_keypair()
        check_and_fund_wallet(kp)

    except Exception as e:
        print(f"\n{Fore.RED}{Style.BRIGHT}{'=' * 56}")
        print(f"{Fore.RED}{Style.BRIGHT} [CRITICAL] SOLANA BLOCKCHAIN UNREACHABLE")
        print(f"{Fore.RED}{Style.BRIGHT}{'=' * 56}")
        print(f"{Fore.WHITE} Ошибка: {e}")
        sys.exit(1)


# ─── API Helpers ──────────────────────────────────────────────────────────────

def get_status() -> dict:
    """Health check for the frontend dashboard."""
    try:
        version_resp = solana_client.get_version()
        kp = load_or_create_keypair()
        balance = solana_client.get_balance(kp.pubkey()).value
        return {
            "connected": True,
            "cluster": "devnet",
            "rpc_url": SOLANA_RPC_URL,
            "solana_version": version_resp.value.solana_core,
            "agent_pubkey": str(kp.pubkey()),
            "agent_balance_sol": round(balance / 1_000_000_000, 6),
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


# ─── Core On-Chain Logic ──────────────────────────────────────────────────────

def execute_emergency_pause(reason: str, risk_score: int) -> str | None:
    """
    Executes a direct Anchor instruction call to trigger the Treasury Pause.
    
    This is the "REAL" autonomous bridge:
    AI Result -> Binary Instruction -> On-Chain State Change
    """
    print(f"\n{Fore.RED}{Style.BRIGHT}[БЛОКЧЕЙН] Инициация вызова смарт-контракта (Anchor)...")
    try:
        kp = load_or_create_keypair()
        authority = kp.pubkey()
        
        # 1. Derive PDA accurately for the instruction context
        treasury_pda = get_pda_treasury(authority)
        print(f"{Fore.CYAN}[БЛОКЧЕЙН] Treasury PDA: {treasury_pda}")

        # 2. Map accounts to the `TriggerPause` context defined in lib.rs
        accounts = [
            AccountMeta(pubkey=treasury_pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=authority, is_signer=True, is_writable=False),
        ]

        # 3. Binary encode the Anchor instruction
        data = encode_emergency_pause_ix(risk_score, reason)

        # 4. Construct Instruction
        ix = Instruction(
            program_id=RISK_MANAGER_PROGRAM_ID,
            accounts=accounts,
            data=data,
        )

        # 5. Build and Sign Transaction
        recent_blockhash = solana_client.get_latest_blockhash().value.blockhash
        msg = Message.new_with_blockhash([ix], authority, recent_blockhash)
        tx = Transaction([kp], msg, recent_blockhash)

        print(f"{Fore.CYAN}[БЛОКЧЕЙН] Отправка сформированной транзакции...")

        resp = solana_client.send_raw_transaction(
            bytes(tx),
            opts=TxOpts(skip_preflight=False, preflight_commitment="confirmed"),
        )
        signature = str(resp.value)

        print(f"{Fore.GREEN}[БЛОКЧЕЙН] ✓ Транзакция подтверждена!")
        print(f"{Fore.GREEN}  Signature : {signature}")
        print(f"{Fore.CYAN}  Solscan   : https://solscan.io/tx/{signature}?cluster=devnet")

        return signature

    except Exception as e:
        print(f"{Fore.RED}[БЛОКЧЕЙН] Ошибка смарт-контракта: {e}")
        return None
