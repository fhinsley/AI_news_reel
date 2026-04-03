import base64
import re
import config

# TODO: create weekly folder here once claude API is in place.

# --- Read the script ---
with open(config.EL_INPUT_FILE, "r") as f:
    script_text = f.read()

# Strip newlines but preserve break tag separation
processed_text = re.sub(r'\n+(<break)', r' \1', script_text)
processed_text = re.sub(r'(/>)\n+', r'\1 ', processed_text)
processed_text = processed_text.replace('\n', ' ')

print(config.EL_INPUT_FILE)
print(config.EL_OUTPUT_FILE)
print(config.EL_DELAY_FILE)
print(config.TIMESTAMP_FILE)
print(config.OUTPUT_VIDEO)

print(config.AUDIO_SPEED_FACTOR)
print(config.EL_FIXED_FILE)
print(config.EL_SLOW_FILE)