# Multiverse methods

These are statistical diagnostics under a fitted market model. They do not establish future profitability. Contract 1.0.0 fixes the units, formulas and decision thresholds. All market histories are log returns; strategy returns are simple returns after trading costs.

## PBO

Probability of Backtest Overfitting checks whether choosing the best strategy within one sample tends to select a weak performer in another. We divide real-history strategy returns into 16 equal blocks, drop the earliest remainder, and evaluate all 12,870 choices of eight blocks. Each choice selects the highest in-sample Sharpe variant and ranks it out of sample. With ascending rank `r` among `V` variants, `omega = r/(V+1)`, `lambda = ln(omega/(1-omega))`, and `PBO = mean(lambda <= 0)`. This finite-rank convention is specified by the project contract. Exact ties use variant order, so fully duplicated variants receive a conservative score; they are not independent evidence. [Bailey, Borwein, Lopez de Prado and Zhu, *The Probability of Backtest Overfitting* (2015), §§2–3](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

## DSR

The Deflated Sharpe Ratio estimates significance after accounting for a search across variants and non-normal returns. Daily Sharpes use sample standard deviations; their sample variance supplies the search dispersion. With `gamma` the Euler–Mascheroni constant and `Phi` the normal CDF, `SR0 = sqrt(var(SR)) * [(1-gamma) Phi^-1(1-1/V) + gamma Phi^-1(1-1/(V*e))]`. Then `DSR = Phi((SR-SR0)*sqrt(T-1) / sqrt(1-skew*SR+(kurtosis-1)*SR²/4))`. Kurtosis is Pearson, with normal equal to three. Payload Sharpes multiply daily values by `sqrt(252)`. The code reproduces the paper's treasury example, DSR 0.9004, using its original 250-day convention. [Bailey and Lopez de Prado, *The Deflated Sharpe Ratio* (2014), equations 1–2 and pp.9–10](https://davidhbailey.com/dhbpapers/deflated-sharpe.pdf).

## Survival

Headline survival is `mean(selected_strategy_sharpe > buy_and_hold_sharpe)` across synthetic histories, including entry costs for buy-and-hold. The Survival Map measures a different quantity: the share of non-overlapping 252-day windows with positive strategy Sharpe. Market windows can belong to several regimes. Crash means drawdown at least 20%; volatility regimes use pooled terciles; upward trend means return at least 15%; downward trend means return at most -10% while excluding crashes. Cells also show median annualized Sharpe and median negative maximum drawdown. Empty regimes remain null. These definitions come from [API Contract §2.5](API_CONTRACT.md#25-metrics--person-b-provides-a-consumes).

## Realism

Eight diagnostics compare the real history with the synthetic 5th–95th percentile band: daily kurtosis, Hill absolute-tail index, return autocorrelation, absolute/squared-return persistence, leverage correlations, and 5-/20-day aggregate kurtosis. A test passes exactly when its real statistic lies inside the band. Return densities use a shared 200-bin histogram; density zeros become null for logarithmic plotting. ACF uses demeaned lagged products divided by total centered sum of squares. Hill uses the largest 5% of absolute returns. Degenerate constant series return finite zero diagnostics. These are project diagnostics, not independent hypothesis tests or a formal joint confidence region. See [API Contract §2.5](API_CONTRACT.md#25-metrics--person-b-provides-a-consumes).

## Verdict

Luck takes priority when PBO is at least 0.50 or DSR is below 0.50. Otherwise Skill requires PBO below 0.25, DSR at least 0.95, and survival at least 0.60. All other cases are Inconclusive. Thresholds are returned with each audit. Demo IDs `overfit` and `robust` identify configurations; they do not force a label. The current slow-trend baseline also scores Luck on the downloaded Nifty history and fitted GARCH model. Tests verify synthetic noise produces Luck and a planted edge produces Skill, but Gate 2 remains failed because the real slow-trend preset does not meet Skill thresholds. Thresholds and metric results have not been altered to manufacture a demo result.

## Backtest assumptions

Signals use close prices only and become positions held over the following interval. Positions are long or flat; each unit position change costs `costs_bps/10000`. Warm-up is flat. SMA compares fast and slow rolling means; momentum compares trailing simple return with its threshold; RSI uses Wilder smoothing with an initial mean seed; breakout compares close against preceding highs/lows. Real-history maximum Sharpe selects the variant, with first-index ties. Flat or effectively zero-variance returns receive zero Sharpe to keep diagnostics finite. Paths are batched in groups of 100, and no `(paths, days, variants)` return cube is allocated.
