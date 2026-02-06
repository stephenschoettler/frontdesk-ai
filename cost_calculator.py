#!/usr/bin/env python3
"""
Cost Calculator for FrontDesk AI Voice Agents
Estimates cost per minute based on service pricing
"""

# Current pricing as of 2024 (check latest pricing on provider websites)
PRICING = {
    # Twilio Voice
    "twilio_inbound": 0.0085,  # per minute
    "twilio_outbound": 0.013,  # per minute

    # LLMs (per 1M tokens)
    "openai_gpt4o": {"input": 2.50, "output": 10.00},  # per 1M tokens
    "openai_gpt4o_mini": {"input": 0.15, "output": 0.60},
    "claude_sonnet": {"input": 3.00, "output": 15.00},
    "claude_haiku": {"input": 0.25, "output": 1.25},

    # STT
    "deepgram_nova2": 0.0043,  # per minute
    "deepgram_whisper": 0.0048,  # per minute

    # TTS (per 1M characters)
    "elevenlabs_turbo": 0.30,  # per 1K chars (multilingual)
    "cartesia": 0.05,  # per 1K chars
    "playht": 0.06,  # per 1K chars
    "openai_tts": 0.015,  # per 1K chars
}

# Typical usage patterns per minute of conversation
TYPICAL_USAGE = {
    "words_per_minute": 150,  # Average speaking rate
    "characters_per_word": 5,
    "input_tokens_per_min": 100,  # User speech transcribed
    "output_tokens_per_min": 150,  # AI response
}


def calculate_cost_per_minute(
    telephony="twilio_inbound",
    llm="openai_gpt4o_mini",
    stt="deepgram_nova2",
    tts="cartesia"
):
    """Calculate total cost per minute for a given stack"""

    # Telephony cost
    phone_cost = PRICING[telephony]

    # STT cost
    stt_cost = PRICING[stt]

    # LLM cost
    input_tokens = TYPICAL_USAGE["input_tokens_per_min"]
    output_tokens = TYPICAL_USAGE["output_tokens_per_min"]
    llm_input_cost = (input_tokens / 1_000_000) * PRICING[llm]["input"]
    llm_output_cost = (output_tokens / 1_000_000) * PRICING[llm]["output"]
    llm_cost = llm_input_cost + llm_output_cost

    # TTS cost
    chars_per_min = TYPICAL_USAGE["words_per_minute"] * TYPICAL_USAGE["characters_per_word"]
    tts_cost = (chars_per_min / 1_000) * PRICING[tts]

    # Total
    total = phone_cost + stt_cost + llm_cost + tts_cost

    return {
        "telephony": round(phone_cost, 4),
        "stt": round(stt_cost, 4),
        "llm": round(llm_cost, 4),
        "tts": round(tts_cost, 4),
        "total": round(total, 4)
    }


def compare_stacks():
    """Compare different technology stack costs"""

    stacks = {
        "GPT-4o-mini + ElevenLabs": {
            "telephony": "twilio_inbound",
            "llm": "openai_gpt4o_mini",
            "stt": "deepgram_nova2",
            "tts": "elevenlabs_turbo"
        },
        "GPT-4o-mini + Cartesia (Recommended)": {
            "telephony": "twilio_inbound",
            "llm": "openai_gpt4o_mini",
            "stt": "deepgram_nova2",
            "tts": "cartesia"
        },
        "GPT-4o-mini + OpenAI TTS": {
            "telephony": "twilio_inbound",
            "llm": "openai_gpt4o_mini",
            "stt": "deepgram_nova2",
            "tts": "openai_tts"
        },
        "Claude Haiku + Cartesia": {
            "telephony": "twilio_inbound",
            "llm": "claude_haiku",
            "stt": "deepgram_nova2",
            "tts": "cartesia"
        }
    }

    print("=" * 80)
    print("FRONTDESK AI - COST PER MINUTE COMPARISON")
    print("=" * 80)
    print()

    results = {}
    for name, config in stacks.items():
        costs = calculate_cost_per_minute(**config)
        results[name] = costs

        print(f"\n{name}")
        print("-" * 40)
        print(f"  Telephony:  ${costs['telephony']:.4f}")
        print(f"  STT:        ${costs['stt']:.4f}")
        print(f"  LLM:        ${costs['llm']:.4f}")
        print(f"  TTS:        ${costs['tts']:.4f}")
        print(f"  {'─' * 38}")
        print(f"  TOTAL:      ${costs['total']:.4f}/min")
        print()

    print("=" * 80)
    print("PRICING RECOMMENDATIONS")
    print("=" * 80)

    for name, costs in results.items():
        cost = costs['total']
        # Calculate pricing at different margins
        print(f"\n{name} (${cost:.4f}/min cost):")
        print(f"  40% margin: ${cost / 0.6:.4f}/min (charge ${cost / 0.6:.2f} per min)")
        print(f"  50% margin: ${cost / 0.5:.4f}/min (charge ${cost / 0.5:.2f} per min)")
        print(f"  60% margin: ${cost / 0.4:.4f}/min (charge ${cost / 0.4:.2f} per min)")


def calculate_tier_pricing():
    """Calculate subscription tier pricing"""

    optimized_cost_per_min = calculate_cost_per_minute(
        telephony="twilio_inbound",
        llm="openai_gpt4o_mini",
        stt="deepgram_nova2",
        tts="cartesia"
    )["total"]

    print("\n" + "=" * 80)
    print("SUBSCRIPTION TIER CALCULATOR (50% Target Margin)")
    print("=" * 80)

    tiers = [
        {"name": "Starter", "minutes": 500, "monthly": 49},
        {"name": "Professional", "minutes": 2000, "monthly": 149},
        {"name": "Business", "minutes": 5000, "monthly": 349},
        {"name": "Enterprise", "minutes": 10000, "monthly": 699},
    ]

    for tier in tiers:
        cost = tier["minutes"] * optimized_cost_per_min
        revenue = tier["monthly"]
        profit = revenue - cost
        margin = (profit / revenue * 100) if revenue > 0 else 0

        print(f"\n{tier['name']}: ${tier['monthly']}/mo for {tier['minutes']} minutes")
        print(f"  Cost to deliver:  ${cost:.2f}")
        print(f"  Gross profit:     ${profit:.2f}")
        print(f"  Margin:           {margin:.1f}%")

        if margin < 40:
            suggested_price = cost / 0.5  # 50% margin
            print(f"  ⚠️  LOW MARGIN! Suggest ${suggested_price:.0f}/mo")
        elif margin > 70:
            print(f"  ✅ HEALTHY MARGIN")


if __name__ == "__main__":
    compare_stacks()
    calculate_tier_pricing()

    print("\n" + "=" * 80)
    print("NOTE: These are estimates. Check your actual API bills for real costs!")
    print("=" * 80)
