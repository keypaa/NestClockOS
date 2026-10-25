# NestClockOS — Phase 1 design note: destructive-action safety lives downstream of the router

Status: filed during Phase 0.5 (run-2 analysis), to be enforced in Phase 1 application design.

## Rule

Any action that cancels, deletes, or turns off persistent state (cancel/delete
alarm, cancel timer, stop playback, etc.) MUST require an explicit confirmation
step, regardless of router confidence — even at 1.00.

## Rationale

Laya's router predicts a coarse `category` (alarm / timer / music / weather /
fallback). It never sees the sub-action: "set an alarm" and "cancel the alarm"
are the same category. Therefore no confidence threshold, at any accuracy
level — including a hypothetical 100%-accurate router — can distinguish a
constructive action from a destructive one. Destructive-action safety enforced
at the routing-confidence layer is unenforceable by construction: there is no
signal there to enforce it with.

## Consequence for the fine-tune gating bar

The gating criterion (`local_WRONG == 0`) is the right bar for
`fallback → action` mistakes (acting on chatter without review) but was never
capable of covering destructive sub-actions, before or after fine-tuning.
Phase 0.5's residual-risk conversation (runs 1–2) concerns benign-direction
errors; destructive-action safety is closed by this confirmation rule, not by
further router training. Do not chase destructive-action safety through the
router in future runs.
