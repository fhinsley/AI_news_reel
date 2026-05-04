import requests
import config

NAME="Annie"

resp = requests.get(
    "https://api.heygen.com/v2/avatars",
    headers={"X-Api-Key": config.HEYGEN_API_KEY},
)

avatars = resp.json()["data"]["avatars"]
annie = [a for a in avatars if NAME in a.get("avatar_name", "")]
for a in annie:
    print(a["avatar_id"], a["avatar_name"])