import logging
import subprocess
from typing import List, Optional
from google.cloud import firestore
import google.oauth2.credentials
from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


# Hardcoded project ID as required for Agent Platform compatibility
FIRESTORE_PROJECT = "qwiklabs-gcp-01-590de8913652"
GCS_BUCKET_NAME = "chef-gemini-media-qwiklabs-gcp-01-590de8913652"
COLLECTION_NAME = "recipes"



def _get_firestore_client() -> firestore.Client:
    """Helper to get a Firestore client with local fallback or service account credentials."""
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"], text=True, timeout=3
        ).strip()
        credentials = google.oauth2.credentials.Credentials(token)
        return firestore.Client(project=FIRESTORE_PROJECT, credentials=credentials)
    except Exception:
        return firestore.Client(project=FIRESTORE_PROJECT)


def search_recipes(query: str = "", dietary_tag: str = "", max_results: int = 5) -> str:
    """Search for recipes in the Firestore database by keyword or dietary preference.

    Args:
        query: Optional search term to match against recipe title, cuisine, or ingredients (e.g. 'salmon', 'Italian').
        dietary_tag: Optional dietary tag to filter by (e.g. 'Gluten-Free', 'Low-Carb', 'Vegan', 'High-Protein').
        max_results: Maximum number of matching recipes to return.

    Returns:
        A list of matching recipe summaries with their IDs, titles, prep times, and dietary tags.
    """
    try:
        db = _get_firestore_client()
        docs = list(db.collection(COLLECTION_NAME).stream())

        results = []
        q_lower = query.lower().strip()
        tag_lower = dietary_tag.lower().strip()

        for doc in docs:
            data = doc.to_dict()
            data["recipe_id"] = doc.id

            # Filter by dietary tag if requested
            if tag_lower:
                recipe_tags = [t.lower() for t in data.get("dietary_tags", [])]
                if tag_lower not in recipe_tags:
                    continue

            # Filter by search query if requested
            if q_lower:
                title_match = q_lower in data.get("title", "").lower()
                cuisine_match = q_lower in data.get("cuisine", "").lower()
                ingr_match = any(q_lower in ingr.lower() for ingr in data.get("ingredients", []))
                if not (title_match or cuisine_match or ingr_match):
                    continue

            results.append(data)

        if not results:
            filter_str = f" matching query '{query}'" if query else ""
            tag_str = f" with tag '{dietary_tag}'" if dietary_tag else ""
            return f"No recipes found in database{filter_str}{tag_str}."

        results = results[:max_results]
        formatted = []
        for r in results:
            tags = ", ".join(r.get("dietary_tags", []))
            formatted.append(
                f"• ID: {r['recipe_id']} | Title: {r.get('title')} | Cuisine: {r.get('cuisine')} | "
                f"Prep: {r.get('prep_time_minutes')}m | Cook: {r.get('cook_time_minutes')}m | "
                f"Dietary Tags: [{tags}]"
            )

        return f"Found {len(results)} recipe(s):\n" + "\n".join(formatted)
    except Exception as e:
        logger.exception("Failed to search recipes in Firestore")
        return f"Error searching recipes in database: {str(e)}"


def get_recipe_details(recipe_id: str) -> str:
    """Retrieve full step-by-step instructions, ingredients, and nutrition details for a recipe from Firestore.

    Args:
        recipe_id: The unique identifier of the recipe (e.g. 'tuscan-salmon', 'quinoa-buddha-bowl').

    Returns:
        Complete details of the recipe including ingredients, instructions, servings, and nutrition breakdown.
    """
    try:
        db = _get_firestore_client()
        doc = db.collection(COLLECTION_NAME).document(recipe_id.strip()).get()

        if not doc.exists:
            return f"Recipe with ID '{recipe_id}' not found in the database."

        data = doc.to_dict()
        title = data.get("title", "Untitled Recipe")
        cuisine = data.get("cuisine", "General")
        prep = data.get("prep_time_minutes", 0)
        cook = data.get("cook_time_minutes", 0)
        servings = data.get("servings", 1)
        tags = ", ".join(data.get("dietary_tags", []))

        ingredients = "\n".join(f"  - {ingr}" for ingr in data.get("ingredients", []))
        instructions = "\n".join(f"  {idx+1}. {step}" for idx, step in enumerate(data.get("instructions", [])))

        calories = data.get("calories_per_serving", 0)
        protein = data.get("protein_grams", 0)
        carbs = data.get("carbs_grams", 0)
        fat = data.get("fat_grams", 0)

        image_url = data.get("image_url", "")
        img_line = f"Image URL: {image_url}\n" if image_url else ""

        return (
            f"=== {title} ===\n"
            f"ID: {recipe_id}\n"
            f"Cuisine: {cuisine} | Servings: {servings}\n"
            f"Prep Time: {prep} mins | Cook Time: {cook} mins\n"
            f"Dietary Tags: {tags}\n"
            f"{img_line}\n"
            f"INGREDIENTS:\n{ingredients}\n\n"
            f"INSTRUCTIONS:\n{instructions}\n\n"
            f"NUTRITION (per serving):\n"
            f"  Calories: {calories} kcal | Protein: {protein}g | Carbs: {carbs}g | Fat: {fat}g"
        )
    except Exception as e:
        logger.exception(f"Failed to fetch recipe details for {recipe_id}")
        return f"Error retrieving recipe details: {str(e)}"


def add_recipe(
    title: str,
    cuisine: str,
    prep_time_minutes: int,
    cook_time_minutes: int,
    servings: int,
    ingredients: List[str],
    instructions: List[str],
    dietary_tags: Optional[List[str]] = None,
    calories_per_serving: int = 0,
    protein_grams: int = 0,
    carbs_grams: int = 0,
    fat_grams: int = 0,
    image_url: Optional[str] = "",
) -> str:
    """Save a new recipe or update an existing recipe in the Firestore database.

    Args:
        title: Title of the recipe (e.g. 'Avocado Toast with Poached Egg').
        cuisine: Cuisine classification (e.g. 'American', 'Mexican', 'Italian').
        prep_time_minutes: Active preparation time in minutes.
        cook_time_minutes: Cooking time in minutes.
        servings: Number of servings this recipe yields.
        ingredients: List of ingredient strings with quantities (e.g. ['2 eggs', '1 avocado']).
        instructions: Step-by-step cooking instructions list.
        dietary_tags: Optional list of dietary tags (e.g. ['Vegetarian', 'Keto', 'Gluten-Free']).
        calories_per_serving: Estimated calories per serving.
        protein_grams: Protein in grams per serving.
        carbs_grams: Carbohydrates in grams per serving.
        fat_grams: Fat in grams per serving.
        image_url: Optional public https image URL for the recipe.

    Returns:
        Confirmation message with the generated recipe ID.
    """
    try:
        db = _get_firestore_client()
        # Generate a clean slug for recipe_id
        recipe_id = title.lower().strip().replace(" ", "-")
        # Remove non-alphanumeric chars from slug
        recipe_id = "".join(c for c in recipe_id if c.isalnum() or c == "-")

        recipe_data = {
            "recipe_id": recipe_id,
            "title": title.strip(),
            "cuisine": cuisine.strip(),
            "prep_time_minutes": prep_time_minutes,
            "cook_time_minutes": cook_time_minutes,
            "servings": servings,
            "ingredients": ingredients,
            "instructions": instructions,
            "dietary_tags": dietary_tags or [],
            "calories_per_serving": calories_per_serving,
            "protein_grams": protein_grams,
            "carbs_grams": carbs_grams,
            "fat_grams": fat_grams,
            "image_url": image_url or "",
        }

        db.collection(COLLECTION_NAME).document(recipe_id).set(recipe_data)
        return f"Successfully saved recipe '{title}' to Firestore with ID '{recipe_id}'."
    except Exception as e:
        logger.exception("Failed to add recipe to Firestore")
        return f"Error adding recipe to database: {str(e)}"


def scale_recipe_ingredients(
    ingredients: List[str], original_servings: int, target_servings: int
) -> str:
    """Scale ingredient quantities for a target number of servings.

    Args:
        ingredients: List of ingredient strings (e.g. ['4 salmon fillets', '2 tbsp butter', '1 cup heavy cream']).
        original_servings: Original serving count (e.g. 4).
        target_servings: Desired target serving count (e.g. 2).

    Returns:
        Formatted list of scaled ingredients for target_servings.
    """
    import re

    if original_servings <= 0 or target_servings <= 0:
        return "Error: original_servings and target_servings must be greater than 0."

    scale_factor = target_servings / original_servings
    scaled_items = []

    for item in ingredients:
        match = re.match(r"^(\d+(?:\.\d+)?)\s*(.*)", item.strip())
        if match:
            num = float(match.group(1))
            new_num = round(num * scale_factor, 2)
            num_str = f"{int(new_num)}" if new_num.is_integer() else f"{new_num}"
            rest = match.group(2)
            scaled_items.append(f"• {num_str} {rest}")
        else:
            scaled_items.append(f"• {item} (scaled {scale_factor:.2f}x)")

    return (
        f"Scaled recipe ingredients from {original_servings} serving(s) to {target_servings} serving(s):\n"
        + "\n".join(scaled_items)
    )


def fetch_online_recipes(query: str) -> str:
    """Fetch real-world recipes and culinary ideas from the free public TheMealDB API.

    Args:
        query: Search term for online recipes (e.g. 'chicken', 'pasta', 'arrabiata', 'curry').

    Returns:
        A list of real online recipe ideas with title, category, cuisine area, image URL, and preparation preview.
    """
    import os
    import urllib.request
    import urllib.parse
    import json

    api_key = os.environ.get("MEALDB_API_KEY", "1")
    url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={urllib.parse.quote(query.strip())}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ChefGemini/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        meals = data.get("meals")
        if not meals:
            return f"No online recipes found matching '{query}' on TheMealDB."

        results = []
        for m in meals[:4]:
            name = m.get("strMeal", "Unknown")
            cat = m.get("strCategory", "General")
            area = m.get("strArea", "International")
            thumb = m.get("strMealThumb", "")
            instructions = m.get("strInstructions", "")
            short_inst = (instructions[:140] + "...") if len(instructions) > 140 else instructions
            results.append(
                f"• Title: {name} | Category: {cat} | Cuisine: {area}\n"
                f"  Image URL: {thumb}\n"
                f"  Preview: {short_inst}"
            )

        return f"Found {len(meals)} online recipe(s) for '{query}':\n\n" + "\n\n".join(results)
    except Exception as e:
        logger.exception("Failed to fetch online recipes from TheMealDB")
        return f"Error fetching online recipes: {str(e)}"


async def generate_dish_image(
    prompt: str,
    tool_context: ToolContext,
) -> str:
    """Generate a photographic presentation of a dish using gemini-3.1-flash-lite-image.

    Saves the image bytes as an artifact in the local Playground and uploads the bytes directly to public Cloud Storage.

    Args:
        prompt: Description of the culinary dish or plated presentation (e.g. 'Plated Tuscan garlic salmon with spinach and lemon').
        tool_context: ADK ToolContext provided automatically by the agent framework.

    Returns:
        The public Cloud Storage HTTPS URL of the generated image (https://storage.googleapis.com/<bucket>/<object>).
    """
    import uuid
    from google import genai
    from google.genai import types
    from google.cloud import storage

    try:
        # Generate image using gemini-3.1-flash-lite-image in the global region
        genai_client = genai.Client(
            vertexai=True,
            project=FIRESTORE_PROJECT,
            location="global",
        )

        full_prompt = f"A professional food photography shot of: {prompt.strip()}"
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=full_prompt,
        )

        image_bytes = None
        mime_type = "image/jpeg"

        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/jpeg"
                    break

        if not image_bytes:
            return "Error: Image generation failed — no image bytes returned by model."

        unique_id = uuid.uuid4().hex[:8]
        filename = f"dish_{unique_id}.jpg"

        # 1. Save image as artifact in Playground via tool_context.save_artifact
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes directly to public GCS bucket (no local file writing)
        try:
            token = subprocess.check_output(
                ["gcloud", "auth", "print-access-token"], text=True, timeout=3
            ).strip()
            creds = google.oauth2.credentials.Credentials(token)
            gcs_client = storage.Client(project=FIRESTORE_PROJECT, credentials=creds)
        except Exception:
            gcs_client = storage.Client(project=FIRESTORE_PROJECT)

        bucket = gcs_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return f"Dish image generated successfully! Public GCS URL: {public_url}"

    except Exception as e:
        logger.exception("Failed to generate dish image")
        return f"Error generating dish image: {str(e)}"


async def generate_dish_video(
    prompt: str,
    tool_context: ToolContext,
) -> str:
    """Generate a short culinary video of a dish using gemini-omni-flash-preview.

    Saves the video bytes as an artifact in the local Playground and uploads the bytes directly to public Cloud Storage.

    Args:
        prompt: Description of the culinary dish or cooking process (e.g. 'Sizzling garlic butter steak in a hot skillet').
        tool_context: ADK ToolContext provided automatically by the agent framework.

    Returns:
        The public Cloud Storage HTTPS URL of the generated video (https://storage.googleapis.com/<bucket>/<object>).
    """
    import base64
    import uuid
    import subprocess
    import google.oauth2.credentials
    from google import genai
    from google.genai import types
    from google.cloud import storage

    try:
        genai_client = genai.Client(
            vertexai=True,
            project=FIRESTORE_PROJECT,
            location="global",
        )

        video_prompt = f"A short food video showing: {prompt.strip()}"
        interaction = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=video_prompt,
        )

        video_bytes = None
        mime_type = "video/mp4"

        if hasattr(interaction, "output_video") and interaction.output_video:
            data = getattr(interaction.output_video, "data", None)
            if data:
                if isinstance(data, bytes):
                    video_bytes = data
                elif isinstance(data, str):
                    try:
                        video_bytes = base64.b64decode(data)
                    except Exception:
                        video_bytes = data.encode("utf-8")
            mt = getattr(interaction.output_video, "mime_type", None)
            if mt:
                mime_type = mt

        if not video_bytes:
            return "Error: Video generation failed — no video data returned by model."

        unique_id = uuid.uuid4().hex[:8]
        filename = f"video_{unique_id}.mp4"

        # 1. Save video as artifact in Playground via tool_context.save_artifact
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload video bytes directly to public GCS bucket (no local file writing)
        try:
            token = subprocess.check_output(
                ["gcloud", "auth", "print-access-token"], text=True, timeout=3
            ).strip()
            creds = google.oauth2.credentials.Credentials(token)
            gcs_client = storage.Client(project=FIRESTORE_PROJECT, credentials=creds)
        except Exception:
            gcs_client = storage.Client(project=FIRESTORE_PROJECT)

        bucket = gcs_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return f"Dish video generated successfully! Public GCS URL: {public_url}"

    except Exception as e:
        logger.exception("Failed to generate dish video")
        return f"Error generating dish video: {str(e)}"




