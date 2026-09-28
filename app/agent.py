# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

import json
from pathlib import Path
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from google.adk.memory import VertexAiMemoryBankService

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from .a2ui_utils import a2ui_callback
from .firestore_tools import (
    add_recipe,
    fetch_online_recipes,
    generate_dish_image,
    generate_dish_video,
    get_recipe_details,
    scale_recipe_ingredients,
    search_recipes,
)

PROJECT_ID = "qwiklabs-gcp-01-590de8913652"
MEMORY_BANK_LOCATION = "us-east1"
MEMORY_BANK_ID = "3186707953713414144"


def memory_bank_service_builder() -> VertexAiMemoryBankService:
    """Memory bank service builder for Vertex AI Memory Bank integration on deployment."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location=MEMORY_BANK_LOCATION,
        agent_engine_id=MEMORY_BANK_ID,
    )


def _get_sandbox_code_executor() -> AgentEngineSandboxCodeExecutor:
    """Helper to initialize AgentEngineSandboxCodeExecutor from deployment_metadata.json."""
    metadata_path = Path(__file__).parent.parent / "deployment_metadata.json"
    engine_name = None
    sandbox_name = None
    if metadata_path.exists():
        try:
            data = json.loads(metadata_path.read_text())
            engine_name = data.get("remote_agent_runtime_id")
            sandbox_name = data.get("sandbox_resource_name")
        except Exception:
            pass

    if sandbox_name:
        return AgentEngineSandboxCodeExecutor(sandbox_resource_name=sandbox_name)
    elif engine_name:
        return AgentEngineSandboxCodeExecutor(agent_engine_resource_name=engine_name)
    else:
        return AgentEngineSandboxCodeExecutor()


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback to extract durable user facts and dietary preferences after each turn."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        pass
    return None


def get_current_time(query: str) -> str:
    """Gets the current time for a specified city or timezone.

    Args:
        query: The name of the city or timezone (e.g., 'San Francisco', 'New York').

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    elif "ny" in query.lower() or "new york" in query.lower():
        tz_identifier = "America/New_York"
    else:
        tz_identifier = "UTC"

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

SYSTEM_INSTRUCTION = schema_manager.generate_system_prompt(
    role_description=(
        "You are Chef Gemini, an expert Personal Chef and Culinary Assistant. "
        "Your mission is to help users plan meals, discover delicious recipes, customize dishes based on dietary restrictions (e.g. Gluten-Free, Low-Carb, Vegan), scale ingredient quantities, generate dish photos, calculate precise nutritional macros via Python sandbox code execution, and manage their recipe library."
    ),
    workflow_description="Analyze the user request and return structured A2UI component cards when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows and optional Image. "
        "Never nest a Card inside a Card. "
        "RECIPE COMPONENT IMAGE INSTRUCTION: Whenever returning a recipe or dish card, ALWAYS include an Image component in the card using a public https image URL (such as the URL returned by `generate_dish_image` or `fetch_online_recipes` or stored in recipe details). "
        "Set the Image component's url property to that exact https link, for example: {\"Image\": {\"url\": {\"literalString\": \"https://storage.googleapis.com/...\"}}}. "
        "If an image URL is not available for a recipe, call `generate_dish_image` to generate a dish visual and obtain a public https Cloud Storage URL. "
        "Never point an Image component at a local file path, bare filename, or artifact name. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use Table or Heading (unsupported), or Buttons, actions, or forms (they do nothing in adk web). "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for headings and emphasis. "
        "CRITICAL ALLERGY & SAFETY MEMORY INSTRUCTION: Carefully check remembered user allergies (peanuts, nuts, shellfish, dairy, gluten, etc.) FIRST and NEVER suggest recipes containing allergens the user is allergic to. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in <a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=SYSTEM_INSTRUCTION,
    code_executor=_get_sandbox_code_executor(),
    tools=[
        PreloadMemoryTool(),
        search_recipes,
        fetch_online_recipes,
        get_recipe_details,
        scale_recipe_ingredients,
        generate_dish_image,
        generate_dish_video,
        add_recipe,
        get_current_time,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
