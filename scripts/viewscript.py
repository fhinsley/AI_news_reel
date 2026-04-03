import config
import re

# --- Read the script ---
with open(config.EL_INPUT_FILE, "r") as f:
    script_text = f.read()

# Strip newlines but preserve break tag separation
processed_text = re.sub(r'\n+(<break)', r' \1', script_text)
processed_text = re.sub(r'(/>)\n+', r'\1 ', processed_text)
processed_text = processed_text.replace('\n', ' ')
print(processed_text)
