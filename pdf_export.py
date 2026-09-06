import os
import matplotlib
matplotlib.use("Agg")  # non-interactive backend — required for generating
                        # images on a server/script with no display screen
import matplotlib.pyplot as plt
from fpdf import FPDF


def _safe_text(text):
    """Converts text to Latin-1 encoding so it can be safely rendered using fpdf2's built-in fonts. 
    Characters that cannot be represented are replaced instead of causing PDF generation to fail."""
    
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _make_bar_chart_image(category_totals, output_path):
    """Creates a horizontal bar chart showing spending by category and saves it as a PNG image."""

    if not category_totals:
        return None


    sorted_items = sorted(category_totals.items(), key=lambda pair: pair[1], reverse=True)
    categories = [pair[0] for pair in sorted_items]
    totals = [pair[1] for pair in sorted_items]

    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=150)

    bars = ax.barh(categories[::-1], totals[::-1], color="#4C72B0")

    ax.set_xlabel("Amount Spent ($)")
    ax.set_title("Spending by Category")

    for bar, total in zip(bars, totals[::-1]):
        ax.text(bar.get_width() + max(totals) * 0.01, bar.get_y() + bar.get_height() / 2,
                 f"${total:,.2f}", va="center", fontsize=8)

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)  # free memory

    return output_path


def _make_pie_chart_image(category_totals, output_path):
    """Creates a pie chart showing each spending category's percentage of total spending and saves it as a PNG image."""

    if not category_totals:
        return None

    sorted_items = sorted(category_totals.items(), key=lambda pair: pair[1], reverse=True)
    categories = [pair[0] for pair in sorted_items]
    totals = [pair[1] for pair in sorted_items]

    fig, ax = plt.subplots(figsize=(5, 5), dpi=150)

    ax.pie(totals, labels=categories, autopct="%1.0f%%", startangle=90,
           colors=plt.cm.Set2.colors)
    ax.axis("equal")  

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)

    return output_path


def _make_trend_comparison_chart(trends_data, output_path):
    """Creates a grouped bar chart comparing spending for each category between the current and previous periods."""

    categories_data = trends_data.get("categories", {})
    if not categories_data:
        return None

    items = [(name, data) for name, data in categories_data.items()
             if data["current"] > 0 or data["prior"] > 0]
    if not items:
        return None

    items.sort(key=lambda pair: pair[1]["current"], reverse=True)

    categories = [name for name, _ in items]
    current_values = [data["current"] for _, data in items]
    prior_values = [data["prior"] for _, data in items]

    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=150)

    x_pos = range(len(categories))
    bar_width = 0.35

    ax.bar([x - bar_width / 2 for x in x_pos], prior_values, bar_width,
           label="Prior Period", color="#B0B0B0")
    ax.bar([x + bar_width / 2 for x in x_pos], current_values, bar_width,
           label="This Period", color="#4C72B0")

    ax.set_xticks(list(x_pos))
    ax.set_xticklabels(categories, rotation=30, ha="right")
    ax.set_ylabel("Amount Spent ($)")
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)

    return output_path


def _make_budget_vs_actual_chart(budget_statuses, output_path):
 
    """Creates a grouped bar chart comparing each category's budget limit with its actual spending."""


    chartable = [check for check in budget_statuses if check["limit"] is not None]
    if not chartable:
        return None

    categories = [check["category"] for check in chartable]
    limits = [check["limit"] for check in chartable]
    spent = [check["spent"] for check in chartable]

    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=150)

    x_pos = range(len(categories))
    bar_width = 0.35

    ax.bar([x - bar_width / 2 for x in x_pos], limits, bar_width,
           label="Budget", color="#B0B0B0")

    spent_colors = ["#D65F5F" if s > l else "#55A868" for s, l in zip(spent, limits)]
    ax.bar([x + bar_width / 2 for x in x_pos], spent, bar_width,
           label="Spent", color=spent_colors)

    ax.set_xticks(list(x_pos))
    ax.set_xticklabels(categories, rotation=30, ha="right")
    ax.set_ylabel("Amount ($)")
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)

    return output_path


def export_report_pdf(report_data, output_path):
    """
    Renders report_data (the same dict build_report() produces)
    into a PDF at output_path. Returns the saved file path.
    """
    pdf = FPDF()
    pdf.add_page()

    # Make sure the destination folder exists 
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # ---- Title ----
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Spending Report", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Period: {report_data['start_date']} to {report_data['end_date']}", ln=True)

    # Build the "Total spent" line, with a trend suffix appended
    # if we have prior-period data to compare against.
    total_line = f"Total spent: ${report_data['total_spent']:,.2f}"
    overall_pct = report_data.get("trends", {}).get("overall_pct_change")
    if overall_pct is not None:
        direction = "up" if overall_pct > 0 else "down" if overall_pct < 0 else "flat"
        if direction == "flat":
            total_line += " (flat vs last period)"
        else:
            total_line += f" ({direction} {abs(overall_pct):.0f}% vs last period)"
    pdf.cell(0, 8, _safe_text(total_line), ln=True)

    # ---- Financial mood saying ----
    if report_data.get("saying"):
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 7, _safe_text(f'"{report_data["saying"]}"'), ln=True)

    pdf.ln(4)

    # ---- CHART 1: Category spend bar chart (always page 1, if data exists) ----
    chart_path = output_path.replace(".pdf", "_bar.png")
    chart_file = _make_bar_chart_image(report_data["category_totals"], chart_path)

    if chart_file:
        pdf.image(chart_file, x=15, w=180)
        os.remove(chart_file)

    # ---- CHART 2: Pie chart breakdown (own page) ----
    pie_path = output_path.replace(".pdf", "_pie.png")
    pie_file = _make_pie_chart_image(report_data["category_totals"], pie_path)

    if pie_file:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Spending Breakdown", ln=True)
        pdf.image(pie_file, x=45, w=120)
        os.remove(pie_file)

    # ---- CHART 3: This period vs. prior period, per category ----
    trend_path = output_path.replace(".pdf", "_trend.png")
    trend_file = _make_trend_comparison_chart(report_data.get("trends", {}), trend_path)

    if trend_file:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Period Comparison", ln=True)
        pdf.image(trend_file, x=15, w=180)
        os.remove(trend_file)

    # ---- CHART 4: Budget vs. actual spend, per category ----
    budget_chart_path = output_path.replace(".pdf", "_budget.png")
    budget_chart_file = _make_budget_vs_actual_chart(report_data["budget_statuses"], budget_chart_path)

    if budget_chart_file:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Budget vs. Actual", ln=True)
        pdf.image(budget_chart_file, x=15, w=180)
        os.remove(budget_chart_file)

    # ---- Text sections: their own page, so charts above are never
    pdf.add_page()

    # ---- Overview stats
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Overview", ln=True)
    pdf.set_font("Helvetica", "", 11)

    iv = report_data["income_vs_expenses"]
    pdf.cell(0, 7, _safe_text(f"  Income: ${iv['income']:,.2f}  |  Expenses: ${iv['expenses']:,.2f}  "
                               f"|  Net: ${iv['net']:,.2f}"), ln=True)
    if iv["savings_rate"] is not None:
        pdf.cell(0, 7, _safe_text(f"  Savings rate: {iv['savings_rate']:.0f}% of income"), ln=True)

    ts = report_data["transaction_stats"]
    pdf.cell(0, 7, _safe_text(f"  Transactions this period: {ts['transaction_count']} "
                               f"(avg ${ts['average_expense']:,.2f} per expense)"), ln=True)
    if ts["largest_expense"]:
        le = ts["largest_expense"]
        pdf.cell(0, 7, _safe_text(f"  Biggest single purchase: {le['description']} - "
                                   f"${le['amount']:,.2f} ({le['category']}, {le['date']})"), ln=True)

    pdf.cell(0, 7, _safe_text(f"  Daily average spend: ${report_data['daily_average']:,.2f}  |  "
                               f"Projected monthly pace: ${report_data['projected_monthly']:,.2f}"), ln=True)

    movers = report_data["biggest_movers"]
    if movers["biggest_increase"]:
        m = movers["biggest_increase"]
        pdf.cell(0, 7, _safe_text(f"  Biggest increase: {m['category']} up {m['pct_change']:.0f}% "
                                   f"vs last period"), ln=True)
    if movers["biggest_decrease"]:
        m = movers["biggest_decrease"]
        pdf.cell(0, 7, _safe_text(f"  Biggest decrease: {m['category']} down {abs(m['pct_change']):.0f}% "
                                   f"vs last period"), ln=True)
    pdf.ln(4)

    # ---- Savings goals ----
    goals = report_data.get("goal_progress", [])
    if goals:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Savings Goals", ln=True)
        pdf.set_font("Helvetica", "", 11)
        for g in goals:
            line = (f"  {g['name']}: ${g['saved']:,.2f} of ${g['target_amount']:,.2f} "
                    f"({g['pct_complete']:.0f}%)")
            if g["days_left"] is not None:
                line += f" - {g['days_left']} days left" if g["days_left"] >= 0 else " - past target date"
            pdf.cell(0, 7, _safe_text(line), ln=True)
        pdf.ln(4)

    # ---- Top merchants ----
    leaderboard = report_data.get("merchant_leaderboard", [])
    if leaderboard:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Top Merchants", ln=True)
        pdf.set_font("Helvetica", "", 11)
        for rank, entry in enumerate(leaderboard, 1):
            plural = "s" if entry["transaction_count"] != 1 else ""
            pdf.cell(0, 7, _safe_text(f"  {rank}. {entry['merchant'].title()}: ${entry['total']:,.2f} "
                                       f"({entry['transaction_count']} charge{plural})"), ln=True)
        pdf.ln(4)

    # ---- Year to date ----
    ytd = report_data.get("ytd_summary")
    if ytd:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Year to Date", ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, _safe_text(f"  {ytd['year']} so far - Spent: ${ytd['total_spent_ytd']:,.2f}  |  "
                                   f"Income: ${ytd['total_income_ytd']:,.2f}  |  Net: ${ytd['net_ytd']:,.2f}"), ln=True)
        pdf.cell(0, 7, _safe_text(f"  Average pace: ${ytd['avg_per_period']:,.2f} per biweekly period"), ln=True)
        pdf.ln(4)

    # ---- Category breakdown table ----
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Spend by Category", ln=True)
    pdf.set_font("Helvetica", "", 11)

    if not report_data["category_totals"]:
        pdf.cell(0, 8, "No spending recorded this period.", ln=True)
    else:
        category_trends = report_data.get("trends", {}).get("categories", {})
        for category, total in report_data["category_totals"].items():
            line = f"  {category}: ${total:,.2f}"
            pct_change = category_trends.get(category, {}).get("pct_change")
            if pct_change is not None:
                direction = "up" if pct_change > 0 else "down" if pct_change < 0 else "flat"
                if direction == "flat":
                    line += " (flat vs last period)"
                else:
                    line += f" ({direction} {abs(pct_change):.0f}% vs last period)"
            pdf.cell(0, 7, _safe_text(line), ln=True)
    pdf.ln(4)

    # ---- Top expenditures ----
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Top Expenditures", ln=True)
    pdf.set_font("Helvetica", "", 11)

    if not report_data["top_expenditures"]:
        pdf.cell(0, 8, "No expenditures to rank.", ln=True)
    else:
        for rank, (category, total) in enumerate(report_data["top_expenditures"], 1):
            pdf.cell(0, 7, _safe_text(f"  {rank}. {category}: ${total:,.2f}"), ln=True)
    pdf.ln(4)

    # ---- Budget status ----
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Budget Status", ln=True)
    pdf.set_font("Helvetica", "", 11)

    if not report_data["budget_statuses"]:
        pdf.cell(0, 8, "No budgets set.", ln=True)
    else:
        for check in report_data["budget_statuses"]:
            if check["status"] == "no budget set":
                line = f"  {check['category']}: ${check['spent']:,.2f} spent, no budget set"
            else:
                line = (f"  {check['category']}: ${check['spent']:,.2f} of ${check['limit']:,.2f} "
                        f"({check['pct_used']:.0f}% used) - {check['status'].upper()}")
            pdf.cell(0, 7, _safe_text(line), ln=True)
    pdf.ln(4)

    # ---- Active subscriptions (optional section) ----
    if "subscriptions" in report_data and report_data["subscriptions"]:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Active Subscriptions", ln=True)
        pdf.set_font("Helvetica", "", 11)
        for merchant, category, amount, interval_days, next_date in report_data["subscriptions"]:
            pdf.cell(0, 7, _safe_text(f"  {merchant.title()} ({category}): ${amount:,.2f}, next {next_date}"), ln=True)

    pdf.output(output_path)
    return output_path


if __name__ == "__main__":
    sample_report = {
        "start_date": "2026-08-01",
        "end_date": "2026-08-14",
        "category_totals": {"Food": 99.50, "Transport": 45.00, "Other": 32.10, "Entertainment": 15.99},
        "top_expenditures": [("Food", 99.50), ("Transport", 45.00), ("Other", 32.10)],
        "budget_statuses": [
            {"category": "Food", "spent": 99.50, "limit": 100.00, "remaining": 0.50, "pct_used": 99.5, "status": "under"},
        ],
        "total_spent": 192.59,
        "subscriptions": [("NETFLIX COM", "Entertainment", 15.99, 30, "2026-08-31")],
    }
    path = export_report_pdf(sample_report, "reports/test_report.pdf")
    print(f"Saved PDF to: {path}")
