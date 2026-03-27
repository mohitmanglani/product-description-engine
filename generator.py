import os
import re
import sys
import json
import time
import pandas as pd

# Ensure emoji and Unicode print correctly on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"

SHORT_MIN, SHORT_MAX = 30, 40
LONG_MIN,  LONG_MAX  = 80, 100


def sanitize(value):
    """Remove characters that break Groq's JSON validator when embedded in output."""
    value = str(value)
    value = value.replace('"', '')
    value = re.sub(r"(\d)'(\d)", r"\1ft \2in", value)  # 6'4" → 6ft 4in
    value = value.replace("'", "")
    return value.strip()


def wc(text):
    """Return word count of a string."""
    return len(str(text).split())


def check_word_counts(descriptions):
    """
    Returns a list of correction messages for any field outside its target range.
    Empty list means everything passed.
    """
    issues = []
    sw = wc(descriptions.get("short_description", ""))
    lw = wc(descriptions.get("long_description", ""))

    if not (SHORT_MIN <= sw <= SHORT_MAX):
        issues.append(
            f'Your short_description was {sw} words. '
            f'Rewrite it to be strictly {SHORT_MIN}-{SHORT_MAX} words.'
        )
    if not (LONG_MIN <= lw <= LONG_MAX):
        issues.append(
            f'Your long_description was {lw} words. '
            f'Rewrite it to be strictly {LONG_MIN}-{LONG_MAX} words.'
        )
    return issues


def build_prompt(row):
    return f"""You are an expert e-commerce copywriter. Generate product descriptions for the following product.

Product Details:
- Name: {sanitize(row['product_name'])}
- Category: {sanitize(row['category'])}
- Key Features: {sanitize(row['key_features'])}
- Target Audience: {sanitize(row['target_audience'])}
- Price: ${row['price']}
- Brand: {sanitize(row['brand'])}

Return ONLY a JSON object with exactly these three keys, no extra text:
{{
  "short_description": "EXACTLY 30-40 words. One to two sentences. Lead with the customer benefit. Include the top feature and who it's for. No filler words.",
  "long_description": "EXACTLY 80-100 words. Three to four sentences. Sentence 1: lead benefit. Sentence 2-3: expand on key features with specific details. Sentence 4: close with a use case or lifestyle fit. Write in second person (you/your).",
  "meta_description": "STRICTLY under 155 characters. Include product name. Lead with top benefit. End with a subtle CTA."
}}"""


def generate_descriptions(row):
    """
    Call the API, then run up to 2 word-count correction retries.
    Falls back through temperatures [0.7, 0.3, 0.0] on JSON errors.
    """
    temperatures = [0.7, 0.3, 0.0]
    descriptions = None

    # ── Step 1: Initial generation with JSON-error retry ──────────────────
    for attempt, temperature in enumerate(temperatures, start=1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert e-commerce copywriter. Always respond with valid JSON only. No markdown, no explanation."
                    },
                    {
                        "role": "user",
                        "content": build_prompt(row)
                    }
                ],
                temperature=temperature,
                max_tokens=600,
                response_format={"type": "json_object"}
            )
            descriptions = json.loads(response.choices[0].message.content.strip())
            if attempt > 1:
                print(f"    ✅ JSON recovered on attempt {attempt} (temp={temperature})")
            break

        except Exception as e:
            if attempt < len(temperatures):
                print(f"    ⚠️  JSON attempt {attempt} failed — retrying at lower temperature...")
                time.sleep(1)
            else:
                print(f"  ❌ All JSON attempts failed for {row['product_name']}: {e}")
                return {
                    "short_description": "ERROR",
                    "long_description": "ERROR",
                    "meta_description": "ERROR"
                }

    # ── Step 2: Word-count validation + correction retries ────────────────
    best = descriptions
    for wc_attempt in range(1, 3):          # up to 2 correction passes
        issues = check_word_counts(best)
        if not issues:
            break                           # all fields within range — done

        correction = " ".join(issues) + " Return the full JSON with all three keys."
        print(f"    📏 Word-count retry {wc_attempt}: {' | '.join(issues)}")

        try:
            fix_response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert e-commerce copywriter. Always respond with valid JSON only. No markdown, no explanation."
                    },
                    {
                        "role": "user",
                        "content": build_prompt(row)
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps(best)
                    },
                    {
                        "role": "user",
                        "content": correction
                    }
                ],
                temperature=0.3,
                max_tokens=600,
                response_format={"type": "json_object"}
            )
            candidate = json.loads(fix_response.choices[0].message.content.strip())

            # Only adopt the fix if it's at least as good as what we have
            current_issues = len(check_word_counts(best))
            candidate_issues = len(check_word_counts(candidate))
            if candidate_issues <= current_issues:
                best = candidate
            else:
                print(f"    ↩️  Correction made things worse — keeping previous best.")

        except Exception as e:
            print(f"    ⚠️  Word-count retry {wc_attempt} failed: {e}")
            break

    # Log final word counts if still out of range after retries
    remaining = check_word_counts(best)
    if remaining:
        sw = wc(best.get("short_description", ""))
        lw = wc(best.get("long_description", ""))
        print(f"    ⚠️  Accepted best attempt — short: {sw}w, long: {lw}w")

    return best


def main():
    print("Starting Product Description Generator\n")
    print(f"Model : {MODEL}")
    print(f"Targets: short {SHORT_MIN}-{SHORT_MAX}w | long {LONG_MIN}-{LONG_MAX}w | meta <155c\n")

    df = pd.read_csv("input/products.csv")
    print(f"📦 Found {len(df)} products to process\n")

    results = []
    errors = []
    wc_retried = []

    for index, row in df.iterrows():
        print(f"  ✍️  Generating: {row['product_name']} ({index + 1}/{len(df)})")
        descriptions = generate_descriptions(row)

        # Track which products needed a word-count retry
        if descriptions.get("short_description") == "ERROR":
            errors.append(row["product_name"])
        elif not check_word_counts(descriptions) == []:
            wc_retried.append(row["product_name"])

        results.append({
            "product_id":        row["product_id"],
            "product_name":      row["product_name"],
            "short_description": descriptions.get("short_description", ""),
            "long_description":  descriptions.get("long_description", ""),
            "meta_description":  descriptions.get("meta_description", "")
        })

        time.sleep(0.5)

    output_df = pd.DataFrame(results)
    output_path = "output/product_descriptions.csv"
    output_df.to_csv(output_path, index=False)

    success_count = len(results) - len(errors)
    print(f"\n✅ Done! {success_count}/{len(results)} descriptions saved to {output_path}")
    if wc_retried:
        print(f"📏 Word-count retried ({len(wc_retried)}): {', '.join(wc_retried)}")
    if errors:
        print(f"❌ Failed ({len(errors)}): {', '.join(errors)}")
    print(f"💰 Estimated cost: ~$0.00 (Groq free tier)")


if __name__ == "__main__":
    main()
