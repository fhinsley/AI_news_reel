import base64
import re
import config
from elevenlabs.client import ElevenLabs

# --- Connect to ElevenLabs ---
client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
 
# --- Read the script ---
with open(config.EL_INPUT_FILE, "r") as f:
    script_text = f.read()

# Strip newlines but preserve break tag separation
processed_text = re.sub(r'\n+(<break)', r' \1', script_text)
processed_text = re.sub(r'(/>)\n+', r'\1 ', processed_text)
processed_text = processed_text.replace('\n', ' ')

response = client.text_to_speech.convert_with_timestamps(
    text=processed_text,
    voice_id=config.EL_VOICE_NAME,
    model_id=config.EL_MODEL_ID,
)

# Save audio
with open(config.EL_OUTPUT_FILE, "wb") as f:
    f.write(base64.b64decode(response.audio_base_64))

# Save timestamps
import json
with open(config.TIMESTAMP_FILE, "w") as f:
    alignment_data = {
        "characters": response.alignment.characters,
        "character_start_times_seconds": response.alignment.character_start_times_seconds,
        "character_end_times_seconds": response.alignment.character_end_times_seconds,
    }
    json.dump(alignment_data, f, indent=2)

print(f"Audio saved to {config.EL_OUTPUT_FILE}")
print(f"Timestamps saved to {config.TIMESTAMP_FILE}")
