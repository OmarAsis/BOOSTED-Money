import random

SAYINGS = {
    # Spending is down significantly vs last period, or budgets
    # are comfortably under limit with no red flags.
    "great": [
        "Look at you, out here making your future self proud.",
        "Your wallet just breathed a sigh of relief.",
        "This is the budgeting equivalent of sticking the landing.",
        "Spending less, saving more - the classic combo.",
        "Somewhere, a tiny version of you in a suit is nodding approvingly.",
        "You're not just staying on budget, you're setting the pace.",
        "This period's a keeper. Frame it. Put it on the fridge.",
    ],
    # Under budget, no major red flags, nothing dramatic either way.
    "good": [
        "Steady as it goes - no drama, just good habits.",
        "Boring in the best way: everything's under control.",
        "You're doing the unglamorous work of staying on track. Respect.",
        "Nothing to see here, just a budget quietly behaving itself.",
        "Consistency is underrated. You're proof it works.",
        "This is what 'having your act together' looks like on paper.",
    ],
    # Spending is trending up noticeably, but nothing's over budget yet.
    "trending_up": [
        "Spending's creeping up - not a crisis, just a heads up.",
        "Your wallet sent a polite little warning flare. No big deal yet.",
        "Things are trending pricier this period. Worth a glance.",
        "Not over budget, just... warming up. Keep an eye on it.",
        "The numbers are climbing. Nothing dramatic, just noted.",
    ],
    # Some category is sitting right at its limit.
    "close_to_limit": [
        "Right on the edge - this is basically a budgeting tightrope walk.",
        "You're toeing the line like a pro. Literally.",
        "So close to the limit you could high-five it.",
        "Precision budgeting: spending exactly what you meant to.",
    ],
    # Something is over budget. Encouraging, not guilt-inducing.
    "over_budget": [
        "A category ran hot this period - happens to everyone. Onward.",
        "Overspent somewhere? Consider it data, not a verdict.",
        "Budgets are guidelines having a rough week, not moral report cards.",
        "One category went rogue. The rest of your plan still stands.",
        "This period pushed back a little. Next one's a clean slate.",
        "Overbudget isn't a character flaw, it's just Tuesday sometimes.",
    ],
    # No budgets set yet, or genuinely no data to compare.
    "no_data": [
        "No budgets set yet - a blank canvas, if you're feeling ambitious.",
        "Nothing to compare against yet. First data point of many.",
        "You're early in the story. No verdicts yet, just numbers.",
        "Set a budget and future-you will have something to compare to.",
    ],
}


def determine_financial_mood(report_data):

    budget_statuses = report_data.get("budget_statuses", [])
    overall_pct_change = report_data.get("trends", {}).get("overall_pct_change")

    if not budget_statuses:
        return "no_data"

    statuses = [check["status"] for check in budget_statuses]

    if "over" in statuses:
        return "over_budget"
    if "at" in statuses:
        return "close_to_limit"

    if overall_pct_change is not None:
        if overall_pct_change <= -10:
            return "great"
        if overall_pct_change >= 20:
            return "trending_up"

    return "good"


def get_financial_saying(report_data):
    mood = determine_financial_mood(report_data)
    return random.choice(SAYINGS[mood])



if __name__ == "__main__":
    #Mock Data
    scenarios = {
        "Over budget": {
            "budget_statuses": [{"status": "over"}],
            "trends": {"overall_pct_change": 15},
        },
        "Under budget, spending way down": {
            "budget_statuses": [{"status": "under"}],
            "trends": {"overall_pct_change": -25},
        },
        "Under budget, spending creeping up": {
            "budget_statuses": [{"status": "under"}],
            "trends": {"overall_pct_change": 30},
        },
        "At the limit": {
            "budget_statuses": [{"status": "at"}],
            "trends": {"overall_pct_change": 0},
        },
        "No budgets set": {
            "budget_statuses": [],
            "trends": {"overall_pct_change": None},
        },
    }

    for label, fake_report in scenarios.items():
        mood = determine_financial_mood(fake_report)
        saying = get_financial_saying(fake_report)
        print(f"[{label}] mood={mood}")
        print(f"  -> {saying}")
