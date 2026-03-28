use anchor_lang::prelude::*;

// Уникальный идентификатор контракта (будет заменён после `anchor build`)
declare_id!("Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS");

#[program]
pub mod solana_risk_manager {
    use super::*;

    /// Инициализация параметров казначейства. Вызывается один раз.
    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let treasury = &mut ctx.accounts.treasury_state;
        treasury.is_paused = false;
        treasury.authority = *ctx.accounts.authority.key;
        Ok(())
    }

    /// Экстренная заморозка средств смарт-контракта.
    /// Может быть вызвана строго авторизованным AI-Агентом.
    pub fn emergency_pause(ctx: Context<TriggerPause>) -> Result<()> {
        let treasury = &mut ctx.accounts.treasury_state;
        
        // КРИТИЧЕСКИ ВАЖНО: Только AI-Agent (authority) имеет право нажать "Стоп-кран"
        require!(
            treasury.authority == *ctx.accounts.authority.key, 
            CustomError::UnauthorizedUser
        );
        
        treasury.is_paused = true;
        msg!("[!!!] CRITICAL: Казначейство протокола экстренно заморожено по команде AI риска.");
        
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init, 
        payer = authority, 
        space = 8 + 1 + 32 // discriminator (8) + bool (1) + pubkey (32)
    )]
    pub treasury_state: Account<'info, TreasuryState>,
    
    #[account(mut)]
    pub authority: Signer<'info>,
    
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct TriggerPause<'info> {
    #[account(mut)]
    pub treasury_state: Account<'info, TreasuryState>,
    
    // Подписывает транзакцию (должен совпадать с ключом из State)
    pub authority: Signer<'info>,
}

#[account]
pub struct TreasuryState {
    pub is_paused: bool,    // Статус работы казначейства
    pub authority: Pubkey,  // Аккаунт оракула (нашего AI), имеющий права
}

#[error_code]
pub enum CustomError {
    #[msg("Отказано в доступе. Вызов разрешен только авторизованному AI-Оракулу.")]
    UnauthorizedUser,
}
