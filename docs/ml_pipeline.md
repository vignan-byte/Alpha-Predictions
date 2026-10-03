# ML pipeline and anti-overfitting checks

1. Retrieve and validate time-ordered candles; discard the developing candle.
2. Calculate trailing technical/structural features. The 4-hour return context is merged backward at closed higher-timeframe boundaries. No backward filling from future values is used.
3. Generate future targets separately. Remove incomplete labels and target windows crossing gaps.
4. Chronological split: 50% training, 15% calibration, 15% validation, 20% final test. Purge H origin rows at each train/calibration/validation boundary so label windows cannot cross into the following partition.
5. Fit imputers/scalers only on training data inside pipelines. Train Logistic Regression and Random Forest; optional boosters require a separate dependency install and explicit CLI flag.
6. Fit multinomial logistic probability calibrators on log probabilities from the separate calibration interval. All three classes must be present in training and calibration; otherwise report insufficient diversity.
7. Choose the candidate with lowest validation log loss. No test-based candidate search and no assumed ensemble benefit.
8. Evaluate the chosen model on held-out test origins spaced H bars apart. Report accuracy, log loss, multiclass Brier score, expected calibration error, target regression MAE and per-regime metrics.
9. Run three expanding-window, horizon-gapped walk-forward folds inside the training region as baseline diagnostics. These diagnostics are not a full nested rolling retraining simulation.
10. Save unique artifacts, feature version, dataset hash, period, partitions, candidate scores, test results and validation permutation importance. Never overwrite a version.
11. Promote only if validation beats the training class-prior baseline. Retraining also requires a wholly later validation period than incumbent history and at least 1% relative log-loss improvement on the same eligible validation rows. Test metrics do not participate in promotion.

Causal feature prefix tests compare output before and after appending future candles. Target tests explicitly inspect index boundaries. Provider histories and demo histories are deterministic for closed candles. The prediction API refuses inference before model history ends.

Remaining statistical risks: financial nonstationarity, selection from repeated human experiments, survivorship/instrument selection, provider revisions, limited sample sizes and small effective sample count in calibration/validation. The app records evidence and implements guards; it does not claim to automatically prove absence of every form of overfitting or guarantee predictive performance.

Optional booster integrations and PostgreSQL were not exercised in the delivered validation run. Individual feature importance values are diagnostic validation-loss changes, not causal explanations; correlated features can have misleading individual importance.

## Release 2.1

Macro precision/recall/F1, multiclass one-vs-rest ROC-AUC (when all three classes occur), Brier score and ordered confusion matrices are recorded alongside accuracy/log loss/calibration. Promotion exposes VALIDATED or REJECTED. Return/range/volatility regression MAE remains separate from strategy P&L.

The `session` target uses hourly bars. For each origin, the next source-market civil session supplies the label window; targets use its terminal return and extremes relative to the origin close. Complete contiguous session coverage is required. A 96-hour-row purge conservatively covers weekend waits; disjoint test sampling uses the same stride. At least 10,000 hourly bars are recommended to form sufficient disjoint test origins. Session model identity is independent of 1H/day identities. A separate synthetic session training run was executed and labeled demo in the evidence.

Regime descriptions now distinguish bullish/bearish trend, ranging, volatility extremes and EMA-transition state. These descriptive labels are not silently added as new model features; the original causal-v1 numerical features remain the trained feature set.
