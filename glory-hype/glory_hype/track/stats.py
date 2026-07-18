"""Pure track-record statistics over resolved outcomes."""


def compute_stats(resolved: list) -> dict:
    wins = [r for r in resolved if r.get("status") == "win"]
    losses = [r for r in resolved if r.get("status") == "loss"]
    opens = [r for r in resolved if r.get("status") == "open"]
    n_closed = len(wins) + len(losses)

    win_rate = (len(wins) / n_closed) if n_closed else None
    avg_win_r = (sum(w["r_multiple"] for w in wins) / len(wins)) if wins else None
    avg_loss_r = (sum(l["r_multiple"] for l in losses) / len(losses)) if losses else None

    if n_closed and win_rate is not None:
        aw = avg_win_r or 0.0
        al = avg_loss_r or 0.0
        expectancy_r = win_rate * aw + (1 - win_rate) * al
    else:
        expectancy_r = None

    loss_sum = abs(sum(l["r_multiple"] for l in losses))
    win_sum = sum(w["r_multiple"] for w in wins)
    profit_factor = (win_sum / loss_sum) if loss_sum else None

    return {
        "n_closed": n_closed, "wins": len(wins), "losses": len(losses),
        "open_count": len(opens),
        "win_rate": win_rate, "avg_win_r": avg_win_r, "avg_loss_r": avg_loss_r,
        "expectancy_r": expectancy_r, "profit_factor": profit_factor,
    }
