# Copyright 2025 Amazon Inc

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Compare product prices across multiple retailers.

Searches for a product across Target, Best Buy, and Costco concurrently
and displays pricing and promotion details in a comparison table.

Usage:
    python -m nova_act.samples.price_comparison.py [--product_name <product name>] [--product_sku <sku>] [--sources <sources>] [--headless]
    python -m nova_act.samples.price_comparison.py --product_name "iPad Pro 13-inch, 256GB Wi-Fi" --product_sku "MVX23LL/A"
    python -m nova_act.samples.price_comparison.py --sources '[("Walmart", "https://www.walmart.com"), ("Amazon", "https://www.amazon.com")]'
    python -m nova_act.samples.price_comparison.py --headless
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import fire
import pandas as pd
from nova_act import BOOL_SCHEMA, ActAgentError, NovaAct
from pydantic import BaseModel

# Global defaults
DEFAULT_PRODUCT_NAME = "iPad Pro 13-inch (M4 chip), 256GB Wi-Fi"
DEFAULT_PRODUCT_SKU = "MVX23LL/A"
DEFAULT_PRODUCT_SOURCES = [
    ("Amazon", "https://www.amazon.com"),
    ("Best Buy", "https://www.bestbuy.com"),
    ("Costco", "https://www.costco.com"),
    ("Target", "https://www.target.com"),
]


class ProductPricing(BaseModel):
    product_name: str | None
    price: float | None
    promotion_details: str | None
    source: str  # Target, Best Buy, or Costco


def check_source_price(
    product_name: str,
    product_sku: str,
    source: str,
    starting_url: str,
    headless: bool = True,
) -> ProductPricing | None:
    """Check price for a product at a specific source."""

    try:
        with NovaAct(starting_page=starting_url, headless=headless) as nova:
            # Check for captcha
            captcha_check = nova.act(
                "Is there a captcha on the screen?", schema=BOOL_SCHEMA
            )
            if captcha_check.matches_schema and captcha_check.parsed_response:
                input(f"Please solve the captcha for {source} and hit return when done")

            # Search using product SKU
            nova.act(f"Search for '{product_sku}'.")

            # Extract pricing and details from the most relevant result based on product name
            result = nova.act(
                f"""
                Close any popups if they appear.
                Review all search results and determine which one is the most relevant to the product name '{product_name}'.
                Select this item to navigate to the product page.
                Then, extract the price and any promotion details from the most relevant result that matches the product name '{product_name}'.
                If no matching product exists, return None for all fields except source. Do not attempt to re-search using a different keyword combination.
                """,
                schema=ProductPricing.model_json_schema(),
            )

            if not result.matches_schema:
                print(f"Invalid JSON from {source}: {result}")
                return None

            pricing = ProductPricing.model_validate(result.parsed_response)
            return pricing

    except ActAgentError as exc:
        print(f"Could not retrieve pricing from {source}: {exc}")
        return None


def main(
    product_name: str | None = None,
    product_sku: str | None = None,
    sources: list[tuple[str, str]] = DEFAULT_PRODUCT_SOURCES,
    headless: bool = True,
) -> None:
    """Search for product prices across multiple sources concurrently."""
    # Validate that both product_name and product_sku are provided together
    if (product_name is None) != (product_sku is None):
        raise ValueError(
            "Both product_name and product_sku must be provided together. "
            "You cannot specify only one without the other."
        )

    # Use defaults if neither was provided
    if product_name is None:
        product_name = DEFAULT_PRODUCT_NAME
        product_sku = DEFAULT_PRODUCT_SKU

    all_prices = []

    print(
        f"Searching for '{product_name}' (SKU: {product_sku}) across {len(sources)} sources...\n"
    )

    with ThreadPoolExecutor() as executor:
        future_to_source = {
            executor.submit(
                check_source_price,
                product_name,
                product_sku,
                source_name,
                source_url,
                headless,
            ): source_name
            for source_name, source_url in sources
        }

        for future in as_completed(future_to_source.keys()):
            source = future_to_source[future]
            pricing = future.result()

            if pricing is not None:
                result_dict = pricing.model_dump()
                result_dict["sku"] = product_sku
                all_prices.append(result_dict)
            else:
                all_prices.append(
                    {
                        "source": source,
                        "product_name": None,
                        "sku": product_sku,
                        "price": None,
                        "promotion_details": None,
                    }
                )

    # Create DataFrame and sort by price
    df = pd.DataFrame(all_prices)
    df = df.sort_values(by="price", na_position="last")

    # Reorder columns
    df = df[["source", "product_name", "sku", "price", "promotion_details"]]

    # Rename columns for better readability in output
    df.columns = ["Source", "Product Name", "Product SKU", "Price", "Promotion Details"]

    # Write results to CSV
    output_file = "price_comparison_results.csv"
    df.to_csv(output_file, index=False)

    print(f"\nResults written to {output_file}")


if __name__ == "__main__":
    fire.Fire(main)
