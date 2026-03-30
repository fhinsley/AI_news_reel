from moviepy import AudioFileClip, concatenate_videoclips, CompositeVideoClip, TextClip, VideoFileClip,vfx
from silence_artifacts import find_artifact_regions, build_ffmpeg_filter

import config
import json
import subprocess


def load_timestamps(filepath):
    with open(filepath, "r") as f:
        return json.load(f)

def find_timestamp(search_text, timestamps):
    full_text = "".join(timestamps["characters"])
    pos = full_text.find(search_text)
    if pos == -1:
        return None
    return timestamps["character_start_times_seconds"][pos]

def parse_script(filepath):
    overlays = []
    with open(filepath, "r") as f:
        lines = [line.strip() for line in f.readlines()]
    for line in lines:
        if not line:
            continue
        if line.startswith("<break"):
            continue
        if line.startswith("Sources this week"):
            continue
        if line in config.SECTION_HEADERS:
            overlays.append(("section", line))
        elif len(line) < 60 and not line.endswith("."):
            overlays.append(("story", line))
    return overlays

def make_text_clip(text, font_size, color, duration, position):
    return (
        TextClip(text=text, font=config.FONT, font_size=font_size, color=color)
        .with_position(position)
        .with_duration(duration)
    )


def build_background(video_files, clip_duration, total_duration):
    segments = []
    current_time = 0
    i = 0
    while current_time < total_duration:
        clip = VideoFileClip(video_files[i % len(video_files)])
        # Loop clip to fill clip_duration seconds
        segment = clip.with_effects([vfx.Loop(duration=clip_duration)]).resized((1920, 1080))
        segments.append(segment)
        current_time += clip_duration
        i += 1
    background = concatenate_videoclips(segments).subclipped(0, total_duration)
    return background

def parse_rundown(filepath):
    with open(filepath, "r") as f:
        content = f.read()
    
    start = content.find("This week:")
    if start == -1:
        return []
    
    end = content.find("<break", start)
    rundown_text = content[start:end].strip()
    
    # Remove the "This week:" prefix
    rundown_text = rundown_text.replace("This week:", "").strip()
    
    # Split into sentences and clean up
    sentences = [s.strip() for s in rundown_text.split(".") if s.strip()]
    
    return sentences

# --- Build video ---

# Step 1 - Silence artifacts

regions = find_artifact_regions(config.TIMESTAMP_FILE, speed_factor = 1.0)
artifact_filter = build_ffmpeg_filter(regions)
print(f"Silencing {len(regions)} artifact regions")

subprocess.run([
    "ffmpeg", "-i", config.EL_OUTPUT_FILE,
    "-af", artifact_filter,
    "-c:a", "libmp3lame",
    "-y", config.EL_FIXED_FILE
], check=True)

# Step 2 - Slow audio
subprocess.run([
    "ffmpeg", "-i", config.EL_FIXED_FILE,
    "-filter:a", f"atempo={config.AUDIO_SPEED_FACTOR}",
    "-y", config.EL_SLOW_FILE
], check=True)

# Step 3 - Add delay
subprocess.run([
    "ffmpeg", "-i", config.EL_SLOW_FILE,
    "-af", "adelay=2000|2000",
    "-y", config.EL_DELAY_FILE
], check=True)

audio = AudioFileClip(config.EL_DELAY_FILE)
timestamps = load_timestamps(config.TIMESTAMP_FILE)
overlays = parse_script(config.EL_INPUT_FILE)
total_duration = audio.duration

background = build_background(config.BG_VIDEOS, config.BG_CLIP_DURATION, total_duration)

clips = [background]

# Opening title card
opening = make_text_clip(
    text=config.OPENING_TITLE,
    font_size=config.OPENING_STYLE["font_size"],
    color=config.OPENING_STYLE["color"],
    duration=config.OPENING_STYLE["duration"],
    position=config.OPENING_STYLE["position"]
)
clips.append(opening)

rundown_sentences = parse_rundown(config.EL_INPUT_FILE)

for i, sentence in enumerate(rundown_sentences):
    t = find_timestamp(sentence[:20], timestamps)
    if t is None:
        continue

    t = (t / config.AUDIO_SPEED_FACTOR) + config.AUDIO_OFFSET - config.OVERLAY_ANTICIPATION

    # Find end timestamp for rundown
    rundown_end_text = "Here is what happened"
    t_end = find_timestamp(rundown_end_text, timestamps)
    if t_end is not None:
        t_end = (t_end / config.AUDIO_SPEED_FACTOR) + config.AUDIO_OFFSET

    # Each line stays for 30 seconds from when it appears

    # Duration runs from when this line appears until "Here is what happened"
    duration = t_end - t if t_end is not None else 20

    # Header appears with first sentence
    if i == 0:
        header = make_text_clip(
            config.RUNDOWN_HEADER,
            config.RUNDOWN_HEADER_STYLE["font_size"],
            config.RUNDOWN_HEADER_STYLE["color"],
            duration,
            ("center", config.RUNDOWN_Y_START)
        ).with_start(t)
        clips.append(header)

    # Each sentence on its own line below header
    y_pos = config.RUNDOWN_Y_START + config.RUNDOWN_LINE_HEIGHT + (i * config.RUNDOWN_LINE_HEIGHT)
    line = make_text_clip(
        sentence,
        config.RUNDOWN_STYLE["font_size"],
        config.RUNDOWN_STYLE["color"],
        duration,
        ("center", y_pos)
    ).with_start(t)
    clips.append(line)


# Section and story overlays
last_section_end = 0

for kind, text in overlays:
    t = find_timestamp(text, timestamps)
    if t is None:
        print(f"WARNING: could not find timestamp for: {text}")
        continue

    # Adjust for audio offset
    t = (t / config.AUDIO_SPEED_FACTOR) + config.AUDIO_OFFSET - config.OVERLAY_ANTICIPATION
    if kind == "section":
        clip = make_text_clip(
            text=text,
            font_size=config.SECTION_STYLE["font_size"],
            color=config.SECTION_STYLE["color"],
            duration=config.SECTION_STYLE["duration"],
            position=config.SECTION_STYLE["position"]
        )
        clip = clip.with_start(t)
        clips.append(clip)
        last_section_end = t + config.SECTION_STYLE["duration"] 

    elif kind == "story":
        # Phase 1 starts after section overlay clears
        phase1_start = max(t, last_section_end)

        phase1 = make_text_clip(
            text=text,
            font_size=config.STORY_STYLE1["font_size"],
            color=config.STORY_STYLE1["color"],
            duration=config.STORY_STYLE1["duration"],
            position=config.STORY_STYLE1["position"]
        )
        phase1 = phase1.with_start(phase1_start)
        clips.append(phase1)

        # Phase 2 starts after phase 1 ends
        phase2 = make_text_clip(
            text=text,
            font_size=config.STORY_STYLE2["font_size"],
            color=config.STORY_STYLE2["color"],
            duration=config.STORY_STYLE2["duration"],
            position=config.STORY_STYLE2["position"]
        )
        phase2 = phase2.with_start(phase1_start + config.STORY_STYLE1["duration"])
        clips.append(phase2)

final = CompositeVideoClip(clips)
final = final.with_audio(audio)
final.write_videofile(config.OUTPUT_VIDEO, fps=24, audio_codec=config.AUDIO_CODEC)
print(f"Done! Saved to {config.OUTPUT_VIDEO}")