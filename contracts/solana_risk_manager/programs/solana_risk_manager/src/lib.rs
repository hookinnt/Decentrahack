use anchor_lang::prelude::*;

// Program ID — will be replaced after `anchor build && anchor deploy`
declare_id!("Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS");

#[program]
pub mod solana_risk_manager {
    use super::*;

    /// Initialize the treasury PDA. Called once by the AI Oracle authority.
    /// The treasury account is a PDA derived from ["treasury", authority.key()].
    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let treasury = &mut ctx.accounts.treasury_state;
        let clock = Clock::get()?;

        treasury.is_paused = false;
        treasury.authority = ctx.accounts.authority.key();
        treasury.bump = ctx.bumps.treasury_state;
        treasury.pause_count = 0;
        treasury.last_risk_score = 0;
        treasury.risk_threshold = 80; // Default: 80/100
        treasury.last_updated = clock.unix_timestamp;

        msg!(
            "[INIT] TreasuryState initialized. Authority: {}. Threshold: {}. TS: {}",
            treasury.authority,
            treasury.risk_threshold,
            treasury.last_updated
        );
        Ok(())
    }

    /// Emergency pause — called by the AI Risk Oracle when risk_score >= 80.
    /// Permanently records the event on-chain and freezes the treasury.
    pub fn emergency_pause(
        ctx: Context<TriggerPause>,
        risk_score: u8,
        reason: String,
    ) -> Result<()> {
        // Validate AI-supplied parameters against DYNAMIC on-chain threshold
        let threshold = ctx.accounts.treasury_state.risk_threshold;
        require!(risk_score >= threshold, CustomError::RiskScoreTooLow);
        require!(reason.len() <= 200, CustomError::ReasonTooLong);
        require!(
            !ctx.accounts.treasury_state.is_paused,
            CustomError::AlreadyPaused
        );

        let treasury = &mut ctx.accounts.treasury_state;
        let clock = Clock::get()?;

        treasury.is_paused = true;
        treasury.last_risk_score = risk_score;
        treasury.pause_count = treasury.pause_count.saturating_add(1);
        treasury.last_updated = clock.unix_timestamp;

        // Emit an on-chain event — indexers and clients can subscribe to this
        emit!(EmergencyPauseEvent {
            authority: ctx.accounts.authority.key(),
            risk_score,
            reason: reason.clone(),
            timestamp: treasury.last_updated,
        });

        msg!(
            "[!!!] CRITICAL PAUSE #{}: Score={}/100. Reason: {}",
            treasury.pause_count,
            risk_score,
            reason
        );
        Ok(())
    }

    /// Resume treasury operations after threat is resolved.
    /// Only the same authority can unpause.
    pub fn resume(ctx: Context<TriggerPause>) -> Result<()> {
        require!(
            ctx.accounts.treasury_state.is_paused,
            CustomError::NotPaused
        );

        let treasury = &mut ctx.accounts.treasury_state;
        let clock = Clock::get()?;

        treasury.is_paused = false;
        treasury.last_updated = clock.unix_timestamp;

        msg!(
            "[OK] Treasury resumed by authority: {}. TS: {}",
            ctx.accounts.authority.key(),
            treasury.last_updated
        );
        Ok(())
    }

    /// Dynamically update the risk sensitivity threshold.
    /// This is the core of the DARS (Dynamic Autonomous Risk Sensitivity) feature.
    pub fn update_threshold(ctx: Context<TriggerPause>, new_threshold: u8) -> Result<()> {
        // Validate threshold range (e.g. 50-95)
        require!(
            new_threshold >= 50 && new_threshold <= 95,
            CustomError::ThresholdOutOfRange
        );

        let treasury = &mut ctx.accounts.treasury_state;
        let clock = Clock::get()?;

        treasury.risk_threshold = new_threshold;
        treasury.last_updated = clock.unix_timestamp;

        msg!(
            "[CONFIG] Sensitivity threshold updated to: {}/100 by AI Oracle authority.",
            new_threshold
        );
        Ok(())
    }
}

// ─── Account Validation Contexts ─────────────────────────────────────────────

#[derive(Accounts)]
pub struct Initialize<'info> {
    /// Treasury PDA — seeded by ["treasury", authority.pubkey].
    /// This ensures each authority has exactly one treasury account.
    #[account(
        init,
        payer = authority,
        space = 8 + TreasuryState::SIZE,
        seeds = [b"treasury", authority.key().as_ref()],
        bump
    )]
    pub treasury_state: Account<'info, TreasuryState>,

    /// The AI Oracle keypair that will own and control this treasury.
    #[account(mut)]
    pub authority: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct TriggerPause<'info> {
    /// Anchor verifies:
    ///   1. The PDA seeds are correct (prevents account substitution attacks).
    ///   2. `treasury_state.authority == authority.key()` via has_one.
    #[account(
        mut,
        seeds = [b"treasury", authority.key().as_ref()],
        bump = treasury_state.bump,
        has_one = authority @ CustomError::UnauthorizedUser,
    )]
    pub treasury_state: Account<'info, TreasuryState>,

    /// Must be the authority stored inside treasury_state at init time.
    pub authority: Signer<'info>,
}

// ─── On-Chain Account Data ────────────────────────────────────────────────────

#[account]
pub struct TreasuryState {
    /// Is the protocol currently in emergency pause mode?
    pub is_paused: bool,        // 1  byte

    /// The only pubkey authorized to call emergency_pause / resume.
    pub authority: Pubkey,      // 32 bytes

    /// PDA bump seed stored for efficient re-derivation.
    pub bump: u8,               // 1  byte

    /// How many times emergency_pause has been triggered (audit trail).
    pub pause_count: u32,       // 4  bytes

    /// Risk score from the last AI assessment that triggered a pause.
    pub last_risk_score: u8,    // 1  byte

    /// Dynamic sensitivity threshold for emergency_pause (Case 2 Adaptive Logic).
    pub risk_threshold: u8,     // 1  byte

    /// Unix timestamp of the last AI-triggered action.
    pub last_updated: i64,      // 8  bytes
}

impl TreasuryState {
    // 1 + 32 + 1 + 4 + 1 + 1 + 8 = 48 bytes
    pub const SIZE: usize = 48;
}

// ─── Events ───────────────────────────────────────────────────────────────────

/// Emitted every time emergency_pause is called.
/// Indexers (e.g., Helius webhooks) can listen to this event.
#[event]
pub struct EmergencyPauseEvent {
    pub authority: Pubkey,
    pub risk_score: u8,
    pub reason: String,
    pub timestamp: i64,
}

// ─── Custom Errors ────────────────────────────────────────────────────────────

#[error_code]
pub enum CustomError {
    #[msg("Access denied. Only the authorized AI Oracle authority can call this instruction.")]
    UnauthorizedUser,

    #[msg("Risk score must be >= the active on-chain threshold to trigger an emergency pause.")]
    RiskScoreTooLow,

    #[msg("Threshold must be between 50 and 95.")]
    ThresholdOutOfRange,

    #[msg("Reason string exceeds the 200-character limit.")]
    ReasonTooLong,

    #[msg("Treasury is already in emergency pause state.")]
    AlreadyPaused,

    #[msg("Treasury is not paused. Cannot call resume.")]
    NotPaused,
}
