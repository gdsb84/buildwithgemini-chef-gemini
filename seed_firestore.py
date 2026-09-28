import logging
import subprocess
import google.oauth2.credentials
from google.cloud import firestore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ID = "qwiklabs-gcp-01-590de8913652"
COLLECTION_NAME = "recipes"

SEED_RECIPES = [
    {
        "recipe_id": "tuscan-salmon",
        "title": "Tuscan Garlic Lemon Butter Salmon",
        "cuisine": "Italian",
        "prep_time_minutes": 15,
        "cook_time_minutes": 15,
        "servings": 4,
        "dietary_tags": ["Gluten-Free", "Low-Carb", "Pescatarian"],
        "ingredients": [
            "4 salmon fillets (6 oz each)",
            "3 cloves garlic, minced",
            "2 tbsp unsalted butter",
            "1 tbsp fresh lemon juice",
            "1 cup heavy cream",
            "2 cups baby spinach",
            "1/2 cup sun-dried tomatoes, chopped",
        ],
        "instructions": [
            "Season salmon fillets with salt, pepper, and paprika.",
            "Pan-sear salmon in olive oil over medium-high heat for 4 minutes per side, then remove.",
            "In the same pan, melt butter and sauté garlic for 1 minute.",
            "Add lemon juice, heavy cream, sun-dried tomatoes, and spinach. Simmer until spinach wilts.",
            "Return salmon to the pan and spoon sauce over top before serving.",
        ],
        "calories_per_serving": 480,
        "protein_grams": 38,
        "carbs_grams": 7,
        "fat_grams": 34,
    },
    {
        "recipe_id": "quinoa-buddha-bowl",
        "title": "Mediterranean Quinoa & Roasted Veggie Buddha Bowl",
        "cuisine": "Mediterranean",
        "prep_time_minutes": 20,
        "cook_time_minutes": 25,
        "servings": 2,
        "dietary_tags": ["Vegan", "Gluten-Free", "Vegetarian", "High-Fiber"],
        "ingredients": [
            "1 cup cooked quinoa",
            "1 cup chickpeas, rinsed and drained",
            "1 cup roasted sweet potato cubes",
            "1 cup roasted broccoli florets",
            "1/2 cup cherry tomatoes, halved",
            "1/4 cup tahini dressing (tahini, lemon, garlic, warm water)",
        ],
        "instructions": [
            "Preheat oven to 400°F (200°C). Toss sweet potatoes and broccoli in olive oil, salt, and cumin.",
            "Roast vegetables on a sheet pan for 25 minutes until tender and caramelized.",
            "Divide warm quinoa into two bowls.",
            "Arrange roasted veggies, chickpeas, and fresh cherry tomatoes over the quinoa.",
            "Drizzle generously with lemon-tahini dressing.",
        ],
        "calories_per_serving": 420,
        "protein_grams": 16,
        "carbs_grams": 62,
        "fat_grams": 14,
    },
    {
        "recipe_id": "teriyaki-chicken-stirfry",
        "title": "Quick Sesame Teriyaki Chicken & Broccoli Stir-Fry",
        "cuisine": "Asian",
        "prep_time_minutes": 10,
        "cook_time_minutes": 12,
        "servings": 3,
        "dietary_tags": ["Dairy-Free", "High-Protein"],
        "ingredients": [
            "1 lb chicken breast, cut into bite-sized strips",
            "3 cups broccoli florets",
            "1 red bell pepper, sliced",
            "1/3 cup low-sodium teriyaki sauce",
            "2 tbsp sesame oil",
            "1 tbsp toasted sesame seeds",
            "2 green onions, sliced",
        ],
        "instructions": [
            "Heat sesame oil in a large wok or skillet over high heat.",
            "Add chicken strips and sear for 5-6 minutes until cooked through.",
            "Add broccoli florets and red bell pepper slices; stir-fry for 3-4 minutes until crisp-tender.",
            "Pour in teriyaki sauce and toss until everything is evenly coated and bubbly.",
            "Garnish with toasted sesame seeds and sliced green onions.",
        ],
        "calories_per_serving": 360,
        "protein_grams": 39,
        "carbs_grams": 14,
        "fat_grams": 14,
    },
]


def get_firestore_client():
    try:
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
        credentials = google.oauth2.credentials.Credentials(token)
        return firestore.Client(project=PROJECT_ID, credentials=credentials)
    except Exception as e:
        logger.warning(f"Could not fetch gcloud token ({e}); using default auth credentials.")
        return firestore.Client(project=PROJECT_ID)


def seed_database():
    db = get_firestore_client()
    recipes_ref = db.collection(COLLECTION_NAME)

    logger.info(f"Seeding {len(SEED_RECIPES)} recipes into Firestore (project={PROJECT_ID})...")
    for recipe in SEED_RECIPES:
        doc_ref = recipes_ref.document(recipe["recipe_id"])
        doc_ref.set(recipe)
        logger.info(f"  - Saved recipe: '{recipe['title']}' (ID: {recipe['recipe_id']})")

    logger.info("Firestore seeding completed successfully!")


if __name__ == "__main__":
    seed_database()
