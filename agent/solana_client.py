"""
solana_client.py — Real Solana Devnet integration for the AI Risk Oracle.

Responsibilities:
  - Maintain a live connection to Solana Devnet (fail-fast on startup)
  - Manage the AI agent's signing keypair
  - Build and broadcast signed Anchor instructions to the smart contract
  - Expose a status dict for the /api/status health endpoint
"""
import sys
import json
import struct
from pathlib import Path
import os

from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.message import Message
from solders.transaction import Transaction
from colorama import Fore, Style, init
from dotenv import load_dotenv

init(autoreset=True)
load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────

SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.devnet.solana.com")

# Program ID should match deployed Anchor contract (lib.rs declare_id!).
RISK_MANAGER_PROGRAM_ID = Pubkey.from_string(
    os.getenv("PROGRAM_ID", "Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS")
)

SYSTEM_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")

KEYPAIR_FILE = Path(__file__).parent.parent / "agent_keypair.json"

# Single shared RPC client instance
rpc = Client(SOLANA_RPC_URL)


# ─── PDA Derivation ───────────────────────────────────────────────────────────

def get_treasury_pda(authority: Pubkey) -> Pubkey:
    """
    Derives the TreasuryState PDA.
    Seeds must exactly match Rust: [b"treasury", authority.key().as_ref()]
    """
    seeds = [b"treasury", bytes(authority)]
    pda, _ = Pubkey.find_program_address(seeds, RISK_MANAGER_PROGRAM_ID)
    return pda


# ─── Anchor Instruction Discriminators ───────────────────────────────────────
# Each discriminator is the first 8 bytes of sha256("global:<instruction_name>").
# These must match the compiled Anchor IDL exactly.

def _disc(name: str) -> bytes:
    """Compute Anchor discriminator: sha256('global:<name>')[0:8]"""
    import hashlib
    return hashlib.sha256(f"global:{name}".encode()).digest()[:8]


def _encode_initialize() -> bytes:
    return _disc("initialize")


def _encode_emergency_pause(risk_score: int, reason: str) -> bytes:
    disc = _disc("emergency_pause")
    arg_score = bytes([risk_score & 0xFF])
    reason_bytes = reason.encode("utf-8")[:199]  # clamp to 200-char contract limit
    arg_len = len(reason_bytes).to_bytes(4, "little")
    return disc + arg_score + arg_len + reason_bytes


def _encode_resume() -> bytes:
    return _disc("resume")


def _encode_update_threshold(new_threshold: int) -> bytes:
    disc = _disc("update_threshold")
    return disc + bytes([new_threshold & 0xFF])


def _validate_threshold(new_threshold: int):
    if not 50 <= int(new_threshold) <= 95:
        raise ValueError("Threshold must be within 50..95.")


# ─── BORSH Decoding ───────────────────────────────────────────────────────────

def _decode_treasury_state(data: bytes) -> dict:
    """
    Decodes TreasuryState account data (Anchor BORSH layout).
    Layout after 8-byte discriminator:
      is_paused:      bool  1 byte  @ offset 8
      authority:      Pubkey 32 bytes @ offset 9
      bump:           u8    1 byte  @ offset 41
      pause_count:    u32   4 bytes @ offset 42
      last_risk_score:u8    1 byte  @ offset 46
      risk_threshold: u8    1 byte  @ offset 47
      last_updated:   i64   8 bytes @ offset 48
    Total: 8 + 1 + 32 + 1 + 4 + 1 + 1 + 8 = 56 bytes
    """
    if len(data) < 56:
        return {}

    is_paused      = bool(data[8])
    authority      = Pubkey.from_bytes(data[9:41])
    bump           = data[41]
    pause_count    = struct.unpack_from("<I", data, 42)[0]
    last_risk_score = data[46]
    risk_threshold = data[47]
    last_updated   = struct.unpack_from("<q", data, 48)[0]

    return {
        "is_paused":       is_paused,
        "authority":       str(authority),
        "bump":            bump,
        "pause_count":     pause_count,
        "last_risk_score": last_risk_score,
        "risk_threshold":  risk_threshold,
        "last_updated":    last_updated,
    }


# ─── Keypair Management ───────────────────────────────────────────────────────

def _load_keypair() -> Keypair:
    """Load keypair from disk. Generate and save a new one if not found."""
    if KEYPAIR_FILE.exists():
        with open(KEYPAIR_FILE, "r") as f:
            secret = json.load(f)
        return Keypair.from_bytes(bytes(secret))

    print(f"{Fore.YELLOW}[Keypair] Generating new agent keypair...")
    kp = Keypair()
    KEYPAIR_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(KEYPAIR_FILE, "w") as f:
        json.dump(list(kp.to_bytes()), f)
    print(f"{Fore.GREEN}[Keypair] Saved to {KEYPAIR_FILE}")
    return kp


# ─── Startup Verification ─────────────────────────────────────────────────────

def verify_solana_or_crash():
    """
    Fail-fast startup check. Exits with code 1 if Solana is unreachable.
    Also initializes the Treasury PDA if it doesn't exist yet.
    """
    print(f"{Fore.CYAN}[Blockchain] Connecting to Solana ({SOLANA_RPC_URL})...")
    try:
        if not rpc.is_connected():
            raise ConnectionError("RPC endpoint did not respond.")

        version = rpc.get_version().value.solana_core
        print(f"{Fore.GREEN}[OK] Solana v{version} — Devnet connected.")

        kp = _load_keypair()
        balance = rpc.get_balance(kp.pubkey()).value
        balance_sol = balance / 1e9
        print(f"{Fore.CYAN}[Wallet] Pubkey : {kp.pubkey()}")
        print(f"{Fore.CYAN}[Wallet] Balance: {balance_sol:.6f} SOL")

        if balance < 1_000_000:  # < 0.001 SOL
            print(f"{Fore.YELLOW}[Wallet] Balance too low for transactions.")
            print(f"{Fore.CYAN}         Fund at: https://faucet.solana.com/?address={kp.pubkey()}")

        # Auto-initialize PDA if missing
        status = get_status()
        if status.get("account_missing"):
            print(f"{Fore.YELLOW}[Contract] Treasury PDA not found. Initializing...")
            sig, err = execute_initialize()
            if sig:
                print(f"{Fore.GREEN}[Contract] Initialized: {sig}")
            elif err:
                print(f"{Fore.YELLOW}[Contract] Init failed (may need SOL): {err}")

    except Exception as e:
        print(f"\n{Fore.RED}{Style.BRIGHT}{'=' * 56}")
        print(f"{Fore.RED}{Style.BRIGHT} [CRITICAL] SOLANA BLOCKCHAIN UNREACHABLE")
        print(f"{Fore.RED}{Style.BRIGHT}{'=' * 56}")
        print(f"{Fore.WHITE} Error: {e}")
        sys.exit(1)


# ─── Status / Health ──────────────────────────────────────────────────────────

def get_status() -> dict:
    """
    Returns live blockchain and contract state.
    Used by /api/status and the background monitor.
    """
    try:
        kp = _load_keypair()
        pubkey = kp.pubkey()

        version = rpc.get_version().value.solana_core
        balance = rpc.get_balance(pubkey).value
        balance_sol = round(balance / 1e9, 6)

        on_chain_state = {
            "is_paused":       False,
            "risk_threshold":  80,
            "pause_count":     0,
            "last_risk_score": 0,
        }
        account_missing = False

        try:
            treasury_pda = get_treasury_pda(pubkey)
            account_info = rpc.get_account_info(treasury_pda)
            if account_info.value and account_info.value.data:
                decoded = _decode_treasury_state(bytes(account_info.value.data))
                if decoded:
                    on_chain_state.update(decoded)
            else:
                account_missing = True
        except Exception:
            account_missing = True

        return {
            "connected":         True,
            "cluster":           "devnet",
            "rpc_url":           SOLANA_RPC_URL,
            "solana_version":    version,
            "agent_pubkey":      str(pubkey),
            "agent_balance_sol": balance_sol,
            "balance_status":    "LOW" if balance_sol < 0.01 else "OK",
            "is_paused":         on_chain_state["is_paused"],
            "risk_threshold":    on_chain_state["risk_threshold"],
            "pause_count":       on_chain_state["pause_count"],
            "last_risk_score":   on_chain_state["last_risk_score"],
            "account_missing":   account_missing,
        }

    except Exception as e:
        return {
            "connected":     False,
            "error":         str(e),
            "is_paused":     False,
            "risk_threshold": 80,
            "account_missing": True,
        }


# ─── Transaction Helpers ──────────────────────────────────────────────────────

def _send_tx(instruction: Instruction, signer: Keypair) -> tuple[str | None, str | None]:
    """
    Builds, signs, and sends a transaction.
    Returns (signature_str, None) on success or (None, error_str) on failure.
    """
    try:
        blockhash_resp = rpc.get_latest_blockhash()
        recent_blockhash = blockhash_resp.value.blockhash

        msg = Message.new_with_blockhash(
            [instruction],
            signer.pubkey(),
            recent_blockhash,
        )
        tx = Transaction([signer], msg, recent_blockhash)

        resp = rpc.send_raw_transaction(
            bytes(tx),
            opts=TxOpts(skip_preflight=False, preflight_commitment="confirmed"),
        )
        sig = str(resp.value)
        print(f"{Fore.GREEN}[TX] Sent: https://solscan.io/tx/{sig}?cluster=devnet")
        return sig, None

    except Exception as e:
        err = str(e)
        if "InsufficientFundsForRent" in err or "debit" in err or "credit" in err:
            err = "Insufficient SOL balance. Fund the agent wallet."
        elif "AccountNotFound" in err:
            err = "Treasury PDA not found. Call initialize first."
        print(f"{Fore.RED}[TX ERROR] {err}")
        return None, err


# ─── On-Chain Instructions ────────────────────────────────────────────────────

def execute_initialize() -> tuple[str | None, str | None]:
    """Creates the Treasury PDA account on Solana Devnet."""
    kp = _load_keypair()
    authority = kp.pubkey()
    treasury_pda = get_treasury_pda(authority)

    accounts = [
        AccountMeta(pubkey=treasury_pda,   is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority,       is_signer=True,  is_writable=True),
        AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
    ]
    ix = Instruction(RISK_MANAGER_PROGRAM_ID, _encode_initialize(), accounts)
    return _send_tx(ix, kp)


def execute_emergency_pause(reason: str, risk_score: int) -> tuple[str | None, str | None]:
    """
    Triggers the on-chain emergency_pause instruction.
    risk_score must be >= the contract's active risk_threshold.
    """
    print(f"\n{Fore.RED}{Style.BRIGHT}[Blockchain] EMERGENCY PAUSE — score={risk_score}")
    kp = _load_keypair()
    authority = kp.pubkey()
    treasury_pda = get_treasury_pda(authority)

    accounts = [
        AccountMeta(pubkey=treasury_pda, is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority,    is_signer=True,  is_writable=False),
    ]
    ix = Instruction(
        RISK_MANAGER_PROGRAM_ID,
        _encode_emergency_pause(risk_score, reason),
        accounts,
    )
    return _send_tx(ix, kp)


def execute_resume() -> tuple[str | None, str | None]:
    """Unlocks the treasury by calling resume on-chain."""
    print(f"{Fore.GREEN}[Blockchain] Resume treasury...")
    kp = _load_keypair()
    authority = kp.pubkey()
    treasury_pda = get_treasury_pda(authority)

    accounts = [
        AccountMeta(pubkey=treasury_pda, is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority,    is_signer=True,  is_writable=False),
    ]
    ix = Instruction(RISK_MANAGER_PROGRAM_ID, _encode_resume(), accounts)
    return _send_tx(ix, kp)


def execute_threshold_update(new_threshold: int) -> tuple[str | None, str | None]:
    """Updates DARS sensitivity threshold on-chain (must be 50–95)."""
    _validate_threshold(new_threshold)
    print(f"{Fore.YELLOW}[Blockchain] DARS threshold → {new_threshold}")
    kp = _load_keypair()
    authority = kp.pubkey()
    treasury_pda = get_treasury_pda(authority)

    accounts = [
        AccountMeta(pubkey=treasury_pda, is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority,    is_signer=True,  is_writable=False),
    ]
    ix = Instruction(
        RISK_MANAGER_PROGRAM_ID,
        _encode_update_threshold(new_threshold),
        accounts,
    )
    return _send_tx(ix, kp)
