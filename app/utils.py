from datetime import datetime
from uuid import uuid4


def generate_run_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid4())[:8]
    return f"run_{timestamp}_{unique_id}"