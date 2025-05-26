import os
from pathlib import Path
from dotenv import load_dotenv

os.environ["ROOT_DIR"] = str(Path(__file__).parent.parent.parent.absolute().resolve())

# env_path = Path(os.environ["ROOT_DIR"]) / ".env"

# load_dotenv(env_path)

load_dotenv()