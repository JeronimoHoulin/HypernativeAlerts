import os
import requests
from dotenv import load_dotenv
load_dotenv()

# api-key
header = {
    "x-client-id": os.getenv("ID_HYPERNATIVE"),
    "x-client-secret": os.getenv("KEY_HYPERNATIVE"),
    "Content-Type": "application/json",
}