# Load OpenAI API key from env to avoid committing secrets
import os

openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
# Name of the developer responsible for the key
key_owner = os.environ.get("OPENAI_KEY_OWNER", "Unknown")

# Get the absolute path to the project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

maze_assets_loc = f"{project_root}/environment/frontend_server/static_dirs/assets"
env_matrix = f"{maze_assets_loc}/the_ville/matrix"
env_visuals = f"{maze_assets_loc}/the_ville/visuals"

fs_storage = f"{project_root}/environment/frontend_server/storage"
fs_temp_storage = f"{project_root}/environment/frontend_server/temp_storage"

collision_block_id = "32125"

# Verbose 
debug = True