from typing import List
from agent.models import NewsItem


def get_latest_news() -> List[NewsItem]:
    """
    Simulated oracle event stream — Solana ecosystem scenarios.
    Each item includes realistic TVL and volatility data so the AI
    analyzer can factor market conditions into its risk assessment.
    """
    return [
        NewsItem(
            id="1",
            headline="Firedancer Update Deployed to Solana Testnet",
            content=(
                "Solana developers successfully rolled out the Firedancer validator client "
                "update on testnet. Network throughput benchmarks show throughput exceeding "
                "1 million TPS under stress tests. The Solana Foundation confirmed stability "
                "metrics are within expected parameters. No anomalies detected."
            ),
            tvl="2.4M",
            volatility="Low",
        ),
        NewsItem(
            id="2",
            headline="Visa Expands USDC Settlement on Solana",
            content=(
                "Payment giant Visa announced expansion of its USDC settlement pilot to "
                "Solana, citing sub-second finality and sub-cent fees. Daily on-chain "
                "USDC volume on Solana surpassed $800M. DeFi protocols report increased "
                "inflows. Market sentiment is cautiously positive."
            ),
            tvl="87M",
            volatility="Medium",
        ),
        NewsItem(
            id="3",
            headline="CRITICAL: Solana DeFi Exploit — $50M USDC Drained",
            content=(
                "URGENT: An unknown attacker exploited a reentrancy vulnerability in the "
                "SolendMax liquidity pool smart contract on Solana. Approximately $50M USDC "
                "has been drained in the last 15 minutes. Security researchers identified "
                "that the Anchor program failed to validate PDA ownership, allowing the "
                "attacker to substitute a malicious account. The exploit is ongoing. "
                "All protocols sharing the same liquidity pool are at immediate risk."
            ),
            tvl="142M",
            volatility="High",
        ),
    ]
