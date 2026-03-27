# AI Product Description Generator

An automated copywriting pipeline that generates SEO-ready product descriptions at scale using the Groq API and LLaMA 3.3 70B.

---

## What It Does

- Reads a CSV of product data (name, category, features, audience, price, brand) and generates three types of copy per product: a short description, a long description, and an SEO meta description
- Runs a word-count validation loop after each generation — if a field misses its target range, the script re-prompts the model with the exact word count and requests a rewrite, up to 2 retries
- Sanitizes input data before prompting to prevent special characters (apostrophes, quotes) from breaking the model's JSON output, and falls back through lower temperatures on JSON parse errors

---

## Tech Stack

- **Language:** Python 3.11+
- **LLM Provider:** Groq API
- **Model:** LLaMA 3.3 70B Versatile
- **Data:** pandas
- **Config:** python-dotenv

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/product-description-generator.git
cd product-description-generator

# 2. Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install groq pandas python-dotenv

# 4. Add your Groq API key
# Create a .env file in the project root:
echo GROQ_API_KEY=your_key_here > .env
```

Get a free Groq API key at [console.groq.com](https://console.groq.com).

---

## How to Run

1. Add your products to `input/products.csv` with these columns:

   ```
   product_id, product_name, category, key_features, target_audience, price, brand
   ```

   Separate multiple key features with a pipe `|` character.

2. Activate your virtual environment (see Installation above).

3. Run the generator:

   ```bash
   python generator.py
   ```

4. Find your results in `output/product_descriptions.csv`.

---

## Sample Output

| Product | Short Description | Long Description | Meta Description |
|---|---|---|---|
| **ZenBook Ultra 14 Laptop** | Unlock productivity with ZenBook Ultra 14 Laptop's Intel Core i7-13th Gen, perfect for professionals and creative students needing high performance and efficiency always | You'll experience seamless performance with the ZenBook Ultra 14 Laptop. It features a 14-inch 2.8K OLED display, 32GB RAM, and 1TB NVMe SSD for efficient multitasking. With a 12-hour battery life, you can work or create all day without interruptions, making it ideal for your busy lifestyle. | ZenBook Ultra 14: Unlock productivity now |
| **PawComfort Orthopedic Dog Bed** | Give your senior dog comfort and support with PawComfort Orthopedic Dog Bed's memory foam base, perfect for large breeds alleviating joint pain and discomfort | You'll give your dog the gift of comfort with our orthopedic bed, featuring a memory foam base for support and a waterproof inner liner for protection. The removable cover is easy to wash and the non-slip bottom keeps it in place. With its durable design, it fits into your home as a cozy spot for your dog to rest and recover. | PawComfort Orthopedic Bed: Comfort for seniors, shop now |

---

## Quality Assurance

The pipeline includes three layers of automated quality control:

**1. Input Sanitization**
All product fields are cleaned before prompting — straight quotes and apostrophes are stripped or converted (e.g. `6'4"` → `6ft 4in`) to prevent them from escaping JSON string boundaries in the model's output.

**2. JSON Error Retry with Temperature Fallback**
If the API returns a malformed JSON response, the script automatically retries up to 3 times, stepping down the temperature (`0.7 → 0.3 → 0.0`) on each attempt. Lower temperature produces more deterministic, structurally safe output.

**3. Word-Count Validation and Correction Loop**
After each successful generation, the script counts the words in `short_description` (target: 30–40 words) and `long_description` (target: 80–100 words). If either field misses its range, a correction prompt is sent back to the model with the exact word count and a rewrite instruction — retried up to 2 times. The script always keeps the best attempt, and only adopts a retry if it does not introduce new violations in previously passing fields.

**Model Comparison**
The pipeline was tested on both `llama-3.1-8b-instant` and `llama-3.3-70b-versatile`. The 70B model produced substantially higher-quality copy with better benefit-led framing and second-person voice adherence. A future upgrade to the Claude API is planned for improved instruction-following on constrained word counts.

---

## Known Limitations

- **Word count brevity bias:** `llama-3.3-70b-versatile` consistently undershoots the 30–40 word and 80–100 word targets even after correction retries, averaging ~23 words (short) and ~54 words (long). This is a known RLHF-trained brevity preference in the base model. Planned fix: upgrade to the Claude API, which shows stronger compliance with explicit length constraints.
- **Rate limits:** Groq's free tier allows 30 requests/minute for the 70B model. With `time.sleep(0.5)` between calls and up to 3 correction retries per product, large batches (100+ products) may hit rate limit errors. A token-bucket rate limiter is planned.
- **CSV-only input/output:** The current pipeline reads from and writes to `.csv` only. Planned: JSON and Shopify-format export support.

---

## Results

Tested on a 50-product dataset spanning 10 categories (Electronics, Footwear, Kitchen, Fitness, Skincare, Home Decor, Pet Supplies, Office, Outdoor Gear, Sleep & Wellness):

- **50 products processed in under 60 seconds**
- **150 pieces of copy generated** (3 description types per product)
- **Zero duplicate descriptions across 50 SKUs**
- **Meta descriptions 100% SEO-compliant** (all under 155 characters)

---

## Project Structure

```
product-description-generator/
├── input/
│   └── products.csv              # Source product data
├── output/
│   └── product_descriptions.csv  # Generated copy (git-ignored)
├── generator.py                  # Main pipeline script
├── .env                          # API key (git-ignored)
├── .gitignore
└── README.md
```
