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


def encode_initialize_ix() -> bytes:
    """
    Discriminator: af345b5a1b7ad4f4 (sha256("global:initialize"))
    """
    return bytes([0xaf, 0x34, 0x5b, 0x5a, 0x1b, 0x7a, 0xd4, 0xf4])


def encode_emergency_pause_ix(risk_score: int, reason: str) -> bytes:
    """
    Discriminator: 158f1b8ec8b5d2ff
    """
    discriminator = bytes([0x15, 0x8f, 0x1b, 0x8e, 0xc8, 0xb5, 0xd2, 0xff])
    arg_risk = bytes([risk_score & 0xFF])
    reason_bytes = reason.encode("utf-8")
    arg_reason_len = len(reason_bytes).to_bytes(4, "little")
    return discriminator + arg_risk + arg_reason_len + reason_bytes


def encode_resume_ix() -> bytes:
    """
    Discriminator: 05c088863f69eb44 (sha256("global:resume"))
    """
    return bytes([0x05, 0xc0, 0x88, 0x86, 0x3f, 0x69, 0xeb, 0x44])


def encode_update_threshold_ix(new_threshold: int) -> bytes:
    """
    Discriminator: fb2418b39d1fefea
    """
    discriminator = bytes([0xfb, 0x24, 0x18, 0xb3, 0x9d, 0x1f, 0xef, 0xea])
    arg_threshold = bytes([new_threshold & 0xFF])
    return discriminator + arg_threshold


# ─── BORSCH Data Decoding ─────────────────────────────────────────────────────

def decode_treasury_state(data: bytes) -> dict:
    """
    Decodes the 48-byte TreasuryState structure from Solana memory.
    Format: 
      - discriminator: 8 
      - is_paused    : 1 (bool)
      - authority     : 32 (pubkey)
      - bump         : 1 (u8)
      - pause_count  : 4 (u32, LE)
      - risk_score   : 1 (u8)
      - threshold    : 1 (u8)
      - last_updated : 8 (i64, LE)
    """
    import struct
    if len(data) < 48: return {}
    
    # Simple manual BORSCH parsing
    is_paused = bool(data[8])
    authority = Pubkey.from_bytes(data[9:41])
    bump = data[41]
    pause_count = struct.unpack("<I", data[42:46])[0]
    risk_score = data[46]
    threshold = data[47]
    # last_updated = struct.unpack("<q", data[48:56])[0] # Offset 48+8
    
    return {
        "is_paused": is_paused,
        "authority": str(authority),
        "pause_count": pause_count,
        "last_risk_score": risk_score,
        "risk_threshold": threshold
    }


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
        
        # Check if Treasury is initialized
        status = get_status()
        if status.get("account_missing"):
            print(f"{Fore.YELLOW}[КРИТИЧНО] Контракт казначейства не инициализирован.")
            execute_initialize()

    except Exception as e:
        print(f"\n{Fore.RED}{Style.BRIGHT}{'=' * 56}")
        print(f"{Fore.RED}{Style.BRIGHT} [CRITICAL] SOLANA BLOCKCHAIN UNREACHABLE")
        print(f"{Fore.RED}{Style.BRIGHT}{'=' * 56}")
        print(f"{Fore.WHITE} Ошибка: {e}")
        sys.exit(1)


# ─── API Helpers ──────────────────────────────────────────────────────────────

def get_status() -> dict:
    """Fetch live blockchain and wallet health, including the on-chain risk threshold."""
    try:
        version_resp = solana_client.get_version()
        kp = load_or_create_keypair()
        pubkey = kp.pubkey()
        balance = solana_client.get_balance(pubkey).value
        
        # Default state
        state = {
            "is_paused": False,
            "risk_threshold": 80,
            "pause_count": 0,
            "last_risk_score": 0
        }
        account_missing = False
        
        # Attempt to read active on-chain threshold from PDA
        try:
            treasury_pda = get_pda_treasury(pubkey)
            account_info = solana_client.get_account_info(treasury_pda)
            if account_info.value:
                state = decode_treasury_state(account_info.value.data)
            else:
                account_missing = True
        except:
            account_missing = True

        return {
            "connected": True,
            "cluster": "devnet",
            "rpc_url": SOLANA_RPC_URL,
            "solana_version": version_resp.value.solana_core,
            "agent_pubkey": str(pubkey),
            "agent_balance_sol": round(balance / 1_000_000_000, 6),
            "is_paused": state.get("is_paused"),
            "risk_threshold": state.get("risk_threshold"),
            "pause_count": state.get("pause_count"),
            "last_risk_score": state.get("last_risk_score"),
            "account_missing": account_missing
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


# ─── Core On-Chain Logic ──────────────────────────────────────────────────────

def _send_tx(instruction: Instruction, signer: Keypair) -> str | None:
    """Helper to sign and send transactions."""
    try:
        recent_blockhash = solana_client.get_latest_blockhash().value.blockhash
        msg = Message.new_with_blockhash([instruction], signer.pubkey(), recent_blockhash)
        tx = Transaction([signer], msg, recent_blockhash)

        resp = solana_client.send_raw_transaction(
            bytes(tx),
            opts=TxOpts(skip_preflight=False, preflight_commitment="confirmed"),
        )
        return str(resp.value)
    except Exception as e:
        print(f"{Fore.RED}[BLOCKCHAIN ERROR] {e}")
        return None


def execute_initialize() -> str | None:
    """Creates the Treasury PDA on Solana."""
    print(f"{Fore.CYAN}[БЛОКЧЕЙН] Инициализация аккаунта казначейства...")
    kp = load_or_create_keypair()
    authority = kp.pubkey()
    treasury_pda = get_pda_treasury(authority)
    
    # Accounts follow lib.rs's Initialize context
    accounts = [
        AccountMeta(pubkey=treasury_pda, is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority, is_signer=True, is_writable=True),
        AccountMeta(pubkey=Pubkey.from_string("11111111111111111111111111111111"), is_signer=False, is_writable=False), # System Program
    ]
    
    ix = Instruction(RISK_MANAGER_PROGRAM_ID, encode_initialize_ix(), accounts)
    sig = _send_tx(ix, kp)
    if sig: print(f"{Fore.GREEN}[OK] Казначейство создано. Sig: {sig}")
    return sig


def execute_emergency_pause(reason: str, risk_score: int) -> str | None:
    """Triggers the safe lock on-chain."""
    print(f"\n{Fore.RED}{Style.BRIGHT}[БЛОКЧЕЙН] КРИТИЧЕСКИЙ ВЫЗОВ: Emergency Pause!")
    kp = load_or_create_keypair()
    authority = kp.pubkey()
    treasury_pda = get_pda_treasury(authority)

    accounts = [
        AccountMeta(pubkey=treasury_pda, is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority, is_signer=True, is_writable=False),
    ]

    ix = Instruction(RISK_MANAGER_PROGRAM_ID, encode_emergency_pause_ix(risk_score, reason), accounts)
    sig = _send_tx(ix, kp)
    if sig: print(f"{Fore.GREEN}[OK] Казначейство ЗАБЛОКИРОВАНО. Sig: {sig}")
    return sig


def execute_resume() -> str | None:
    """Unlocks the treasury on-chain."""
    print(f"{Fore.GREEN}[БЛОКЧЕЙН] Восстановление системы: Resume...")
    kp = load_or_create_keypair()
    authority = kp.pubkey()
    treasury_pda = get_pda_treasury(authority)

    accounts = [
        AccountMeta(pubkey=treasury_pda, is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority, is_signer=True, is_writable=False),
    ]

    ix = Instruction(RISK_MANAGER_PROGRAM_ID, encode_resume_ix(), accounts)
    sig = _send_tx(ix, kp)
    if sig: print(f"{Fore.GREEN}[OK] Казначейство РАЗБЛОКИРОВАНО. Sig: {sig}")
    return sig


def execute_threshold_update(new_threshold: int) -> str | None:
    """Updates dynamic risk sensitivity (DARS)."""
    print(f"\n{Fore.YELLOW}[КОНФИГ] DARS: Изменение порога на {new_threshold}/100...")
    kp = load_or_create_keypair()
    authority = kp.pubkey()
    treasury_pda = get_pda_treasury(authority)

    accounts = [
        AccountMeta(pubkey=treasury_pda, is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority, is_signer=True, is_writable=False),
    ]

    ix = Instruction(RISK_MANAGER_PROGRAM_ID, encode_update_threshold_ix(new_threshold), accounts)
    sig = _send_tx(ix, kp)
    if sig: print(f"{Fore.GREEN}[OK] Порог обновлен. Sig: {sig}")
    return sig
