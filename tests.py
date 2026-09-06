import sqlite3
import pytest
from db_control import init_db, seed_categories
from transactions import (
    insert_transaction, get_category_id, get_transaction,
    edit_transaction, remove_transaction, _category_id_cache,
)
from search import search_transactions
from budgets import set_budget, check_budget, check_all_budgets, get_period_spent
from reports import aggregate_by_category, top_expenditures, rank_top_categories, build_report
from csv_importer import normalize_columns, guess_category, compute_row_hash, filter_new_rows
from recurring import normalize_merchant, detect_recurring, list_active_subscriptions
from trends import previous_period_bounds, compare_periods
from financial_sayings import determine_financial_mood, get_financial_saying, SAYINGS
from report_stats import (
    get_income_vs_expenses, get_transaction_stats,
    get_daily_average, get_projected_monthly_spend, find_biggest_movers,
    get_merchant_leaderboard, get_ytd_summary,
)
from goals import create_goal, list_goals, get_goal_progress, get_all_goal_progress

@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    init_db(connection)
    seed_categories(connection)
    _category_id_cache.clear()  # module-level cache would leak ids across tests
    yield connection
    connection.close()

# --- schema / setup ---
def test_categories_are_seeded(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories")
    names = {row[0] for row in cursor.fetchall()}
    assert names == {"Food", "Rent", "Utilities", "Transport", "Entertainment", "Salary", "Other"}
def test_get_category_id_returns_correct_id(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM categories WHERE name = 'Food'")
    expected_id = cursor.fetchone()[0]
    assert get_category_id(conn, "Food") == expected_id

# --- transactions: insert / get / edit / delete ---
def test_insert_and_get_transaction(conn):
    cat_id = get_category_id(conn, "Food")
    txn_id = insert_transaction(conn, "2026-08-01", "Sushi", -24.00, cat_id)
    row = get_transaction(conn, txn_id)
    assert row == (txn_id, "2026-08-01", "Sushi", -24.00, "Food")
def test_get_transaction_returns_none_for_missing_id(conn):
    assert get_transaction(conn, 9999) is None
def test_edit_transaction_updates_only_given_fields(conn):
    cat_id = get_category_id(conn, "Food")
    txn_id = insert_transaction(conn, "2026-08-01", "Sushi", -24.00, cat_id)
    edit_transaction(conn, txn_id, amount=-30.00)
    row = get_transaction(conn, txn_id)
    assert row[3] == -30.00
    assert row[1] == "2026-08-01"
    assert row[2] == "Sushi"
def test_edit_transaction_returns_false_for_missing_id(conn):
    assert edit_transaction(conn, 9999, amount=-10.00) is False
def test_remove_transaction_deletes_row(conn):
    cat_id = get_category_id(conn, "Food")
    txn_id = insert_transaction(conn, "2026-08-01", "Sushi", -24.00, cat_id)
    assert remove_transaction(conn, txn_id) is True
    assert get_transaction(conn, txn_id) is None
def test_remove_transaction_returns_false_for_missing_id(conn):
    assert remove_transaction(conn, 9999) is False

# --- search ---
def test_search_by_category_filters_correctly(conn):
    cat_food = get_category_id(conn, "Food")
    cat_ent = get_category_id(conn, "Entertainment")
    insert_transaction(conn, "2026-08-01", "Sushi", -24.00, cat_food)
    insert_transaction(conn, "2026-08-02", "Netflix", -15.99, cat_ent)
    results = search_transactions(conn, category="Food")
    assert len(results) == 1
    assert results[0][4] == "Food"
def test_search_combines_category_and_date_range(conn):
    cat_food = get_category_id(conn, "Food")
    insert_transaction(conn, "2026-08-01", "In range", -10.00, cat_food)
    insert_transaction(conn, "2026-09-01", "Out of range", -20.00, cat_food)
    results = search_transactions(conn, category="Food", start_date="2026-08-01", end_date="2026-08-31")
    assert len(results) == 1
    assert results[0][2] == "In range"

# --- budgets ---
def test_get_period_spent_sums_expenses_only(conn):
    cat_id = get_category_id(conn, "Food")
    insert_transaction(conn, "2026-08-01", "Groceries", -60.00, cat_id)
    insert_transaction(conn, "2026-08-05", "Sushi", -30.00, cat_id)
    insert_transaction(conn, "2026-08-10", "Refund", 20.00, cat_id)  # deposit, shouldn't count
    assert get_period_spent(conn, cat_id, "2026-08-01", "2026-08-14") == 90.00
def test_check_budget_status_under(conn):
    cat_id = get_category_id(conn, "Food")
    insert_transaction(conn, "2026-08-01", "Groceries", -50.00, cat_id)
    set_budget(conn, "Food", 100.00, "2026-08-01")
    result = check_budget(conn, "Food", "2026-08-01", "2026-08-14")
    assert result["status"] == "under"
    assert result["spent"] == 50.00
    assert result["remaining"] == 50.00
def test_check_budget_status_over(conn):
    cat_id = get_category_id(conn, "Food")
    insert_transaction(conn, "2026-08-01", "Big purchase", -150.00, cat_id)
    set_budget(conn, "Food", 100.00, "2026-08-01")
    result = check_budget(conn, "Food", "2026-08-01", "2026-08-14")
    assert result["status"] == "over"
    assert result["remaining"] == -50.00
def test_check_all_budgets_matches_individual_check_budget(conn):
    cat_id = get_category_id(conn, "Food")
    insert_transaction(conn, "2026-08-01", "Groceries", -50.00, cat_id)
    set_budget(conn, "Food", 100.00, "2026-08-01")
    individual = check_budget(conn, "Food", "2026-08-01", "2026-08-14")
    all_results = check_all_budgets(conn, "2026-08-01", "2026-08-14")
    assert len(all_results) == 1
    assert all_results[0] == individual
def test_check_all_budgets_excludes_categories_without_budgets(conn):
    cat_id = get_category_id(conn, "Food")
    insert_transaction(conn, "2026-08-01", "Groceries", -50.00, cat_id)
    set_budget(conn, "Food", 100.00, "2026-08-01")
    results = check_all_budgets(conn, "2026-08-01", "2026-08-14")
    assert [r["category"] for r in results] == ["Food"]

# --- reports ---
def test_aggregate_by_category_sums_correctly(conn):
    cat_food = get_category_id(conn, "Food")
    cat_ent = get_category_id(conn, "Entertainment")
    insert_transaction(conn, "2026-08-01", "Groceries", -60.00, cat_food)
    insert_transaction(conn, "2026-08-02", "Sushi", -20.00, cat_food)
    insert_transaction(conn, "2026-08-03", "Netflix", -15.99, cat_ent)
    totals = aggregate_by_category(conn, "2026-08-01", "2026-08-14")
    assert totals["Food"] == 80.00
    assert totals["Entertainment"] == 15.99
def test_top_expenditures_orders_descending(conn):
    cat_food = get_category_id(conn, "Food")
    cat_ent = get_category_id(conn, "Entertainment")
    cat_rent = get_category_id(conn, "Rent")
    insert_transaction(conn, "2026-08-01", "Rent", -1000.00, cat_rent)
    insert_transaction(conn, "2026-08-02", "Groceries", -80.00, cat_food)
    insert_transaction(conn, "2026-08-03", "Netflix", -15.99, cat_ent)
    top = top_expenditures(conn, "2026-08-01", "2026-08-14", n=2)
    assert top == [("Rent", 1000.00), ("Food", 80.00)]
def test_rank_top_categories_matches_top_expenditures_without_a_second_query(conn):
    # rank_top_categories() is the pure version build_report() uses to
    # avoid re-querying; confirm it ranks identically to the DB wrapper.
    cat_food = get_category_id(conn, "Food")
    cat_rent = get_category_id(conn, "Rent")
    insert_transaction(conn, "2026-08-01", "Rent", -1000.00, cat_rent)
    insert_transaction(conn, "2026-08-02", "Groceries", -80.00, cat_food)
    totals = aggregate_by_category(conn, "2026-08-01", "2026-08-14")
    via_pure_function = rank_top_categories(totals, n=2)
    via_db_wrapper = top_expenditures(conn, "2026-08-01", "2026-08-14", n=2)
    assert via_pure_function == via_db_wrapper
def test_build_report_includes_all_expected_keys(conn):
    cat_id = get_category_id(conn, "Food")
    insert_transaction(conn, "2026-08-01", "Groceries", -50.00, cat_id)
    set_budget(conn, "Food", 100.00, "2026-08-01")
    report = build_report(conn, "2026-08-01", "2026-08-14")
    for key in ("start_date", "end_date", "category_totals", "budget_statuses",
                "top_expenditures", "total_spent", "subscriptions", "trends",
                "saying", "income_vs_expenses", "transaction_stats",
                "daily_average", "projected_monthly", "biggest_movers",
                "merchant_leaderboard", "goal_progress", "ytd_summary"):
        assert key in report
    assert report["total_spent"] == 50.00

# --- csv import ---
def test_normalize_columns_maps_standard_names():
    import pandas as pd
    df = pd.DataFrame({"Transaction Date": ["08/01/2026"], "Description": ["Sushi"], "Amount": [-24.00]})
    normalized = normalize_columns(df)
    assert list(normalized.columns) == ["date", "description", "amount"]
    assert normalized["date"].iloc[0] == "2026-08-01"
def test_normalize_columns_combines_debit_credit():
    import pandas as pd
    df = pd.DataFrame({
        "Date": ["08/01/2026", "08/02/2026"], "Description": ["Groceries", "Paycheck"],
        "Debit": [60.00, None], "Credit": [None, 1500.00],
    })
    normalized = normalize_columns(df)
    assert normalized["amount"].iloc[0] == -60.00
    assert normalized["amount"].iloc[1] == 1500.00
def test_guess_category_matches_known_keywords():
    assert guess_category("UBER EATS 8492") == "Food"
    assert guess_category("NETFLIX.COM") == "Entertainment"
    assert guess_category("DIRECT DEPOSIT PAYROLL") == "Salary"
    assert guess_category("CHEESECAKE FACTORY #4471") == "Food"
    assert guess_category("TWILIGHT RENTALS") == "Rent"
def test_guess_category_disambiguates_car_rental_from_housing_rental():
    # "rental" alone is ambiguous; specific brand names must win over
    # the generic catch-all regardless of dict ordering.
    assert guess_category("ENTERPRISE RENT-A-CAR") == "Transport"
    assert guess_category("HERTZ CAR RENTAL") == "Transport"
    assert guess_category("SUNSET APARTMENTS LLC") == "Rent"
def test_compute_row_hash_is_stable():
    hash1 = compute_row_hash("2026-08-01", "Sushi", -24.00)
    hash2 = compute_row_hash("2026-08-01", "Sushi", -24.00)
    hash3 = compute_row_hash("2026-08-01", "Sushi", -25.00)
    assert hash1 == hash2
    assert hash1 != hash3
def test_filter_new_rows_skips_already_imported(conn):
    import pandas as pd
    cat_id = get_category_id(conn, "Food")
    existing_hash = compute_row_hash("2026-08-01", "Sushi", -24.00)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transactions (date, description, amount, category_id, source, import_hash) "
        "VALUES (?, ?, ?, ?, 'csv_import', ?)",
        ("2026-08-01", "Sushi", -24.00, cat_id, existing_hash),
    )
    conn.commit()
    df = pd.DataFrame({"date": ["2026-08-01", "2026-08-02"], "description": ["Sushi", "Groceries"],
                        "amount": [-24.00, -50.00]})
    new_rows = filter_new_rows(conn, df)
    assert len(new_rows) == 1
    assert new_rows.iloc[0]["description"] == "Groceries"

# --- recurring / subscriptions ---
def test_normalize_merchant_strips_trailing_codes():
    assert normalize_merchant("NETFLIX.COM #4471") == "NETFLIX COM"
    assert normalize_merchant("UBER EATS 8492") == "UBER EATS"
def test_normalize_merchant_handles_empty_input():
    assert normalize_merchant("") == ""
    assert normalize_merchant(None) == ""
def test_detect_recurring_flags_consistent_monthly_charges(conn):
    cat_id = get_category_id(conn, "Entertainment")
    for d in ["2026-05-03", "2026-06-02", "2026-07-04", "2026-08-01"]:
        insert_transaction(conn, d, "NETFLIX.COM 4471", -15.99, cat_id)
    results = detect_recurring(conn)
    assert len(results) == 1
    assert results[0]["merchant"] == "NETFLIX COM"
    assert results[0]["interval"] == "monthly"
    assert results[0]["occurrences"] == 4
def test_detect_recurring_ignores_inconsistent_amounts(conn):
    # Same merchant/timing, but amounts vary too much to be real billing.
    cat_id = get_category_id(conn, "Food")
    for d, amt in [("2026-07-01", -45.20), ("2026-07-08", -62.10),
                   ("2026-07-15", -38.75), ("2026-07-22", -71.00)]:
        insert_transaction(conn, d, "WHOLE FOODS 892", amt, cat_id)
    assert detect_recurring(conn) == []
def test_list_active_subscriptions_reflects_detection(conn):
    cat_id = get_category_id(conn, "Entertainment")
    for d in ["2026-06-05", "2026-07-05", "2026-08-05"]:
        insert_transaction(conn, d, "NETFLIX.COM", -15.99, cat_id)
    detect_recurring(conn)
    subs = list_active_subscriptions(conn)
    assert len(subs) == 1
    assert subs[0][0] == "NETFLIX COM"
    assert subs[0][2] == pytest.approx(15.99)

# --- trends ---
def test_previous_period_bounds_returns_equal_length_prior_period():
    from datetime import date
    current_start, current_end = date(2026, 8, 1), date(2026, 8, 14)
    prior_start, prior_end = previous_period_bounds(current_start, current_end)
    assert prior_start == date(2026, 7, 18)
    assert prior_end == date(2026, 7, 31)
    assert (current_end - current_start).days == (prior_end - prior_start).days
def test_previous_period_bounds_handles_month_boundary():
    from datetime import date
    current_start, current_end = date(2026, 1, 1), date(2026, 1, 14)
    _, prior_end = previous_period_bounds(current_start, current_end)
    assert prior_end == date(2025, 12, 31)
def test_compare_periods_detects_increase(conn):
    cat_id = get_category_id(conn, "Food")
    insert_transaction(conn, "2026-07-20", "Groceries", -60.00, cat_id)
    insert_transaction(conn, "2026-08-02", "Groceries", -90.00, cat_id)
    result = compare_periods(conn, "2026-08-01", "2026-08-14", "2026-07-18", "2026-07-31")
    assert result["categories"]["Food"]["current"] == 90.00
    assert result["categories"]["Food"]["prior"] == 60.00
    assert result["categories"]["Food"]["pct_change"] == pytest.approx(50.0)
def test_compare_periods_handles_no_prior_spending(conn):
    cat_id = get_category_id(conn, "Rent")
    insert_transaction(conn, "2026-08-01", "First rent payment", -1200.00, cat_id)
    result = compare_periods(conn, "2026-08-01", "2026-08-14", "2026-07-18", "2026-07-31")
    assert result["categories"]["Rent"]["pct_change"] is None
    assert result["categories"]["Rent"]["current"] == 1200.00

# --- financial sayings (mood is a priority-ordered decision table) ---
def test_mood_is_over_budget_when_any_category_is_over():
    report = {"budget_statuses": [{"status": "under"}, {"status": "over"}], "trends": {"overall_pct_change": -5}}
    assert determine_financial_mood(report) == "over_budget"
def test_mood_is_close_to_limit_when_at_status_present():
    report = {"budget_statuses": [{"status": "under"}, {"status": "at"}], "trends": {"overall_pct_change": 0}}
    assert determine_financial_mood(report) == "close_to_limit"
def test_mood_is_great_when_under_budget_and_trending_down():
    report = {"budget_statuses": [{"status": "under"}], "trends": {"overall_pct_change": -15}}
    assert determine_financial_mood(report) == "great"
def test_mood_is_trending_up_when_under_budget_but_spend_rising():
    report = {"budget_statuses": [{"status": "under"}], "trends": {"overall_pct_change": 25}}
    assert determine_financial_mood(report) == "trending_up"
def test_mood_is_good_when_under_budget_and_stable():
    report = {"budget_statuses": [{"status": "under"}], "trends": {"overall_pct_change": 2}}
    assert determine_financial_mood(report) == "good"
def test_mood_is_no_data_when_no_budgets_set():
    report = {"budget_statuses": [], "trends": {"overall_pct_change": None}}
    assert determine_financial_mood(report) == "no_data"
def test_get_financial_saying_returns_string_from_correct_tier():
    report = {"budget_statuses": [{"status": "over"}], "trends": {"overall_pct_change": 10}}
    assert get_financial_saying(report) in SAYINGS["over_budget"]
def test_every_saying_tier_is_non_empty():
    for tier_name, sayings_list in SAYINGS.items():
        assert len(sayings_list) > 0, f"Tier '{tier_name}' has no sayings"

# --- report_stats ---
def test_income_vs_expenses_computes_correctly(conn):
    cat_food = get_category_id(conn, "Food")
    cat_salary = get_category_id(conn, "Salary")
    insert_transaction(conn, "2026-08-01", "Paycheck", 1500.00, cat_salary)
    insert_transaction(conn, "2026-08-02", "Groceries", -60.00, cat_food)
    insert_transaction(conn, "2026-08-05", "Sushi", -30.00, cat_food)
    result = get_income_vs_expenses(conn, "2026-08-01", "2026-08-14")
    assert result["income"] == 1500.00
    assert result["expenses"] == 90.00
    assert result["net"] == 1410.00
    assert result["savings_rate"] == pytest.approx(94.0)
def test_income_vs_expenses_with_no_income_returns_none_savings_rate(conn):
    cat_food = get_category_id(conn, "Food")
    insert_transaction(conn, "2026-08-01", "Groceries", -60.00, cat_food)
    result = get_income_vs_expenses(conn, "2026-08-01", "2026-08-14")
    assert result["savings_rate"] is None
    assert result["net"] == -60.00
def test_transaction_stats_identifies_largest_expense(conn):
    cat_food = get_category_id(conn, "Food")
    insert_transaction(conn, "2026-08-01", "Small snack", -8.00, cat_food)
    insert_transaction(conn, "2026-08-05", "Fancy dinner", -220.00, cat_food)
    insert_transaction(conn, "2026-08-10", "Groceries", -60.00, cat_food)
    stats = get_transaction_stats(conn, "2026-08-01", "2026-08-14")
    assert stats["transaction_count"] == 3
    assert stats["average_expense"] == pytest.approx((8 + 220 + 60) / 3)
    assert stats["largest_expense"]["description"] == "Fancy dinner"
    assert stats["largest_expense"]["amount"] == 220.00
def test_transaction_stats_with_no_transactions_returns_none_largest(conn):
    stats = get_transaction_stats(conn, "2026-08-01", "2026-08-14")
    assert stats["transaction_count"] == 0
    assert stats["largest_expense"] is None
def test_get_daily_average_divides_correctly():
    assert get_daily_average(280.00, "2026-08-01", "2026-08-14") == pytest.approx(20.00)
def test_get_daily_average_handles_single_day_period():
    assert get_daily_average(50.00, "2026-08-01", "2026-08-01") == pytest.approx(50.00)
def test_get_projected_monthly_spend_scales_to_30_days():
    assert get_projected_monthly_spend(daily_average=10.00) == 300.00
def test_find_biggest_movers_identifies_increase_and_decrease():
    category_trends = {
        "Food": {"current": 90.0, "prior": 60.0, "pct_change": 50.0},
        "Entertainment": {"current": 5.0, "prior": 50.0, "pct_change": -90.0},
        "Rent": {"current": 1200.0, "prior": 1200.0, "pct_change": 0.0},
        "Transport": {"current": 40.0, "prior": 0.0, "pct_change": None},
    }
    result = find_biggest_movers(category_trends)
    assert result["biggest_increase"]["category"] == "Food"
    assert result["biggest_decrease"]["category"] == "Entertainment"
def test_find_biggest_movers_with_no_comparable_data_returns_none():
    result = find_biggest_movers({"Rent": {"current": 100.0, "prior": 0.0, "pct_change": None}})
    assert result == {"biggest_increase": None, "biggest_decrease": None}

# --- merchant leaderboard & YTD ---
def test_merchant_leaderboard_groups_by_normalized_name(conn):
    cat_food = get_category_id(conn, "Food")
    insert_transaction(conn, "2026-08-01", "STARBUCKS #4471", -6.50, cat_food)
    insert_transaction(conn, "2026-08-05", "STARBUCKS #8821", -7.25, cat_food)
    insert_transaction(conn, "2026-08-02", "UBER TRIP 552", -22.00, cat_food)
    leaderboard = get_merchant_leaderboard(conn, "2026-08-01", "2026-08-14", n=5)
    assert leaderboard[0]["merchant"] == "UBER TRIP"
    starbucks_entry = [e for e in leaderboard if e["merchant"] == "STARBUCKS"][0]
    assert starbucks_entry["total"] == pytest.approx(13.75)
    assert starbucks_entry["transaction_count"] == 2
def test_merchant_leaderboard_respects_n_limit(conn):
    cat_food = get_category_id(conn, "Food")
    for i, amount in enumerate([-10, -20, -30, -40, -50, -60]):
        insert_transaction(conn, "2026-08-01", f"MERCHANT_{i}", amount, cat_food)
    leaderboard = get_merchant_leaderboard(conn, "2026-08-01", "2026-08-14", n=3)
    assert len(leaderboard) == 3
    assert leaderboard[0]["total"] == 60
def test_ytd_summary_sums_from_january_first(conn):
    cat_food = get_category_id(conn, "Food")
    cat_salary = get_category_id(conn, "Salary")
    insert_transaction(conn, "2026-02-01", "Winter groceries", -100.00, cat_food)
    insert_transaction(conn, "2026-08-01", "Summer groceries", -50.00, cat_food)
    insert_transaction(conn, "2026-01-01", "Paycheck", 1000.00, cat_salary)
    insert_transaction(conn, "2025-12-15", "Old purchase", -999.00, cat_food)  # prior year, excluded
    ytd = get_ytd_summary(conn, "2026-08-14")
    assert ytd["year"] == 2026
    assert ytd["total_spent_ytd"] == 150.00
    assert ytd["total_income_ytd"] == 1000.00

# --- savings goals ---
def test_create_and_list_goal(conn):
    goal_id = create_goal(conn, "Emergency Fund", 2000.00, target_date="2026-12-31")
    goals = list_goals(conn)
    assert len(goals) == 1
    assert goals[0]["id"] == goal_id
    assert goals[0]["name"] == "Emergency Fund"
    assert goals[0]["target_amount"] == 2000.00
def test_goal_progress_tracks_net_savings_since_creation(conn):
    cat_food = get_category_id(conn, "Food")
    cat_salary = get_category_id(conn, "Salary")
    goal_id = create_goal(conn, "Emergency Fund", 1000.00, target_date=None)
    cursor = conn.cursor()
    cursor.execute("UPDATE goals SET created_at = ? WHERE id = ?", ("2026-08-01 00:00:00", goal_id))
    conn.commit()
    insert_transaction(conn, "2026-08-02", "Paycheck", 800.00, cat_salary)
    insert_transaction(conn, "2026-08-05", "Groceries", -200.00, cat_food)
    goal = list_goals(conn)[0]
    progress = get_goal_progress(conn, goal, "2026-08-14")
    assert progress["saved"] == 600.00
    assert progress["pct_complete"] == 60.0
    assert progress["remaining"] == 400.00
def test_goal_progress_floors_negative_saved_at_zero_percent(conn):
    cat_food = get_category_id(conn, "Food")
    goal_id = create_goal(conn, "Vacation Fund", 500.00, target_date=None)
    cursor = conn.cursor()
    cursor.execute("UPDATE goals SET created_at = ? WHERE id = ?", ("2026-08-01 00:00:00", goal_id))
    conn.commit()
    insert_transaction(conn, "2026-08-05", "Big splurge", -100.00, cat_food)
    goal = list_goals(conn)[0]
    progress = get_goal_progress(conn, goal, "2026-08-14")
    assert progress["saved"] == -100.00
    assert progress["pct_complete"] == 0.0
    assert progress["days_left"] is None
def test_get_all_goal_progress_returns_every_active_goal(conn):
    create_goal(conn, "Goal A", 500.00)
    create_goal(conn, "Goal B", 1000.00)
    progress = get_all_goal_progress(conn, "2026-08-14")
    assert len(progress) == 2
    assert {p["name"] for p in progress} == {"Goal A", "Goal B"}

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))