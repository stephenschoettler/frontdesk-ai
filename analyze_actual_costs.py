#!/usr/bin/env python3
"""
Analyze actual costs from usage_ledger table
Requires .env file with SUPABASE credentials
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import after loading env
try:
    from services.supabase_client import get_supabase_client
except ImportError:
    print("Error: Could not import supabase_client")
    print("Make sure you're running from the frontdesk directory")
    sys.exit(1)


def analyze_usage_ledger(days=30):
    """Analyze actual costs from the database"""

    supabase = get_supabase_client()
    if not supabase:
        print("❌ Could not connect to Supabase")
        print("Make sure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set in .env")
        return

    try:
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Fetch usage data
        response = (
            supabase.table("usage_ledger")
            .select("*")
            .gte("created_at", cutoff_date)
            .execute()
        )

        data = response.data or []

        if not data:
            print(f"\n⚠️  No usage data found in last {days} days")
            print("\nYou have 3 options:")
            print("1. Make some test calls to generate data")
            print("2. Use the cost_calculator.py estimates (already ran above)")
            print("3. Check your API provider bills directly")
            return

        print(f"\n{'=' * 80}")
        print(f"ACTUAL USAGE ANALYSIS (Last {days} days)")
        print(f"{'=' * 80}\n")

        # Aggregate by metric type
        by_metric = {}
        total_cost = 0

        for row in data:
            metric = row.get("metric_type", "unknown")
            qty = row.get("quantity", 0)
            cost = row.get("cost_usd", 0) or 0

            if metric not in by_metric:
                by_metric[metric] = {"quantity": 0, "cost": 0, "count": 0}

            by_metric[metric]["quantity"] += qty
            by_metric[metric]["cost"] += cost
            by_metric[metric]["count"] += 1
            total_cost += cost

        # Display breakdown
        print("Cost Breakdown by Service:")
        print("-" * 80)

        for metric, stats in sorted(by_metric.items(), key=lambda x: x[1]["cost"], reverse=True):
            pct = (stats["cost"] / total_cost * 100) if total_cost > 0 else 0
            print(f"{metric:20s} ${stats['cost']:8.2f} ({pct:5.1f}%)  |  {stats['quantity']:,} units  |  {stats['count']:,} calls")

        print("-" * 80)
        print(f"{'TOTAL':20s} ${total_cost:8.2f}\n")

        # Calculate per-minute cost if we have duration data
        if "duration" in by_metric:
            total_minutes = by_metric["duration"]["quantity"] / 60
            cost_per_minute = total_cost / total_minutes if total_minutes > 0 else 0

            print(f"Total Minutes: {total_minutes:,.1f}")
            print(f"Cost Per Minute: ${cost_per_minute:.4f}\n")

            print("Pricing Recommendations:")
            print("-" * 80)
            print(f"40% margin: Charge ${cost_per_minute / 0.6:.4f}/min")
            print(f"50% margin: Charge ${cost_per_minute / 0.5:.4f}/min")
            print(f"60% margin: Charge ${cost_per_minute / 0.4:.4f}/min")

            # Subscription tier suggestions
            print(f"\n{'=' * 80}")
            print("SUGGESTED SUBSCRIPTION TIERS (50% Margin)")
            print(f"{'=' * 80}\n")

            tiers = [
                ("Starter", 500),
                ("Professional", 2000),
                ("Business", 5000),
                ("Enterprise", 10000),
            ]

            for name, minutes in tiers:
                cost = minutes * cost_per_minute
                price = cost / 0.5  # 50% margin
                print(f"{name:15s} {minutes:5,} min → Cost: ${cost:6.2f} → Price: ${price:6.2f}/mo")

        else:
            print("⚠️  No 'duration' metric found in ledger")
            print("Make sure your call handler is logging duration!")

    except Exception as e:
        print(f"❌ Error analyzing data: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\nChecking your actual database for usage data...\n")
    analyze_usage_ledger(30)

    print("\n" + "=" * 80)
    print("💡 TIP: Compare this with the estimates from cost_calculator.py")
    print("=" * 80)
