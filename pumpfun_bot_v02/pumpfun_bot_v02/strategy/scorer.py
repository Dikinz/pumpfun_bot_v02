from typing import Any


def score_new_token(event: dict[str, Any]) -> tuple[int, list[str]]:
    """
    Conservative creation-event score.
    IMPORTANT: creation data alone is insufficient for a high-confidence entry.
    This score is for WATCH/SKIP classification, not an automatic real-money buy.
    """
    score = 0
    reasons: list[str] = []

    market_cap_sol = _num(event.get("marketCapSol"))
    initial_buy = _num(event.get("initialBuy"))
    v_sol = _num(event.get("vSolInBondingCurve"))
    name = str(event.get("name") or "").strip()
    symbol = str(event.get("symbol") or "").strip()
    creator = event.get("traderPublicKey") or event.get("creator")

    if name and symbol:
        score += 10
        reasons.append("есть name/symbol +10")

    if creator:
        score += 10
        reasons.append("есть creator +10")

    if 20 <= market_cap_sol <= 150:
        score += 20
        reasons.append("MC_SOL в стартовом диапазоне +20")
    elif market_cap_sol > 0:
        score += 8
        reasons.append("MC_SOL доступен +8")

    if 0 < initial_buy <= 5:
        score += 15
        reasons.append("initialBuy не экстремальный +15")
    elif initial_buy > 0:
        score += 5
        reasons.append("initialBuy доступен +5")

    if v_sol > 0:
        score += 10
        reasons.append("bonding-curve SOL доступен +10")

    # Deliberately capped below auto-entry threshold.
    # Holder concentration, real buy/sell flow and liquidity checks
    # are not available from creation event alone.
    return min(score, 65), reasons


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
