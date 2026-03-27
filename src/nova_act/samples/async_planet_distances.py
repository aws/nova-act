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
"""Search planet distances concurrently using async Nova Act.

Shows how to use the async implementation of Nova Act to search for
information about multiple planets simultaneously using asyncio.gather.

Usage:
python -m nova_act.samples.async_planet_distances
"""

import asyncio

import fire  # type: ignore

from nova_act.asyncio import NovaAct

PLANETS = [
    "Proxima Centauri b",
    "Ross 128 b",
    "Teegarden's Star b",
    "Wolf 1061c",
]


async def search_planet_distance(planet: str) -> str | None:
    async with NovaAct(headless=True, starting_page="https://nova.amazon.com/act/gym/next-dot", tty=False) as nova:
        await nova.act("Click on 'Explore Destinations'")
        result = await nova.act_get(f"Get the distance and travel time for {planet}")
        return result.response


async def main() -> None:
    results = await asyncio.gather(*[search_planet_distance(planet) for planet in PLANETS])
    for planet, result in zip(PLANETS, results):
        print(f"{planet}: {result}")


if __name__ == "__main__":
    fire.Fire(lambda: asyncio.run(main()))
