from moviepy import AudioFileClip, ColorClip, concatenate_videoclips, CompositeVideoClip, TextClip, VideoFileClip,vfx
from silence_artifacts import find_artifact_regions, build_ffmpeg_filter

import config
import json
import subprocess

def load_timestamps(filepath):
    with open(filepath, "r") as f:
        return json.load(f)


# Find the timestamp for a given text string,
# using the character-level timestamps from the TTS output 
def find_timestamp(search_text, timestamps):
    full_text = "".join(timestamps["characters"])
    pos = full_text.find(search_text)
    if pos == -1:
        return None
    return timestamps["character_start_times_seconds"][pos]

# --- Main functions for building the video ---

# Parse the script to identify section headers and story lines for overlays
def parse_script(filepath):
    overlays = []
    with open(filepath, "r") as f:
        lines = [line.strip() for line in f.readlines()]
    for line in lines:
        if not line:
            continue
        if line.startswith("<break"):
            continue
        if line.startswith(config.SOURCE_PHRASE):
            continue
        if line in config.SECTION_HEADERS:
            overlays.append(("section", line))
        elif len(line) < 60 and not line.endswith("."):
            overlays.append(("story", line))
    return overlays

# Functions to create text clips for overlays
def make_text_clip(text, font_size, color, duration, position):
    return (
        TextClip(text=text, font=config.FONT, font_size=font_size, color=color)
        .with_position(position)
        .with_duration(duration)
    )

# Function to create a text clip with a semi-transparent background for better readability
def make_text_clip_with_bg(text, font_size, color, duration, position):
    txt = TextClip(text=text, font=config.FONT, font_size=font_size, color=color)
    w, h = txt.size
    
    bg = (ColorClip(size=(w + config.OVERLAY_BG_PADDING*2, h + config.OVERLAY_BG_PADDING*2), 
                    color=config.OVERLAY_BG_COLOR)
          .with_opacity(config.OVERLAY_BG_OPACITY)
          .with_duration(duration)
          .with_position(position))
    
    txt = txt.with_duration(duration).with_position(position)
    
    return bg, txt

# Build background video segments based on section/story change points
def build_background_from_timestamps(video_files, change_points, total_duration, section_map=None):
    segments = []
    video_index = 0
    
    # Iterate through change points to create video segments
    for i, (start_time, label) in enumerate(change_points):
        # Determine the end time for this segment based on the next change point or total duration
        if i + 1 < len(change_points):
            duration = change_points[i + 1][0] - start_time
        else:
            duration = total_duration - start_time
        
        # Use section-specific video if available
        if section_map and label in section_map:
            video_file = section_map[label]
        # Otherwise, cycle through the provided video files
        else:
            video_file = video_files[video_index % len(video_files)]
            video_index += 1
        
        # Loop the video segment to fill the duration and resize to fit the output dimensions
        clip = (VideoFileClip(video_file)
                .with_effects([vfx.Loop(duration=duration)])
                .resized((1920, 1080))
                .with_start(start_time))
        
        # Add the clip to the list of segments
        segments.append(clip)
    
    return segments

# Build the FFmpeg filter string to silence artifact regions
def parse_rundown(filepath):
    with open(filepath, "r") as f:
        content = f.read()
    
    # Extract the rundown section between "This week:" and the next break tag
    start = content.find(config.WEEK_PHRASE)
    if start == -1:
        return []
    
    # Find the end of the rundown section, which is either the next break tag or the end of the content
    end = content.find("<break", start)
    rundown_text = content[start:end].strip()
    
    # Remove the "This week:" prefix
    rundown_text = rundown_text.replace(config.WEEK_PHRASE, "").strip()
    
    # Split into sentences and clean up
    sentences = [s.strip() for s in rundown_text.split(".") if s.strip()]
    
    return sentences

# Apply audio effects to silence artifacts, slow down, and add delay
def process_audio_effects(artifact_filter):
    
    # Step 1 - Silence artifacts
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

    # Step 3 - Add delay - this is a hack that will be removed in the next iteration or two
    subprocess.run([
        "ffmpeg", "-i", config.EL_SLOW_FILE,
        "-af", "adelay=2000|2000",
        "-y", config.EL_DELAY_FILE
    ], check=True)

# Generate text overlay clips for sections and stories, with proper timing and layering
def generate_overlay_clips(find_timestamp, make_text_clip, make_text_clip_with_bg, timestamps, overlays, clips):
    last_section_end = 0

    # Iterate through the identified overlays and create text clips based on their timestamps
    for kind, text in overlays:
        t = find_timestamp(text, timestamps)
        if t is None:
            print(f"WARNING: could not find timestamp for: {text}")
            continue

        # Adjust for audio offset
        t = (t / config.AUDIO_SPEED_FACTOR) + config.AUDIO_OFFSET - config.OVERLAY_ANTICIPATION
        
        # For sections, create a text clip with a background and ensure it stays on screen for the configured duration
        if kind == "section":
            bg, txt = make_text_clip_with_bg(
            text=text,
            font_size=config.SECTION_STYLE["font_size"],
            color=config.SECTION_STYLE["color"],
            duration=config.SECTION_STYLE["duration"],
            position=config.SECTION_STYLE["position"]
        )
            bg = bg.with_start(t)
            txt = txt.with_start(t)
            clips.append(bg)
            clips.append(txt)
            last_section_end = t + config.SECTION_STYLE["duration"]

        # For stories, create two phases of text clips: the first with a larger font that appears immediately,
        # and the second with a smaller font that appears after the first one fades out, to provide emphasis
        # and layering for important story lines
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
            text=text ,
            font_size=config.STORY_STYLE2["font_size"],
            color=config.STORY_STYLE2["color"],
            duration=config.STORY_STYLE2["duration"],
            position=config.STORY_STYLE2["position"]
        )
            phase2 = phase2.with_start(phase1_start + config.STORY_STYLE1["duration"])
            clips.append(phase2)

# Create a special section at the end to list sources,
# which is parsed separately from the script and can accommodate
# a longer list of items with smaller text

def create_rundown_clips(find_timestamp, make_text_clip, timestamps, clips, rundown_sentences):
    rundown_end_text = config.RUNDOWN_END_PHRASE
    t_end = find_timestamp(rundown_end_text, timestamps)
    if t_end is not None:
        t_end = (t_end / config.AUDIO_SPEED_FACTOR) + config.AUDIO_OFFSET

    for i, sentence in enumerate(rundown_sentences):
        t = find_timestamp(sentence[:20], timestamps)
        if t is None:
            continue

        t = (t / config.AUDIO_SPEED_FACTOR) + config.AUDIO_OFFSET - config.OVERLAY_ANTICIPATION
        duration = t_end - t if t_end is not None else 20

        print(f"sentence {i}: t={t:.2f}, t_end={t_end:.2f}, duration={duration:.2f}")

        if i == 0:
            header = make_text_clip(
                config.RUNDOWN_HEADER,
                config.RUNDOWN_HEADER_STYLE["font_size"],
                config.RUNDOWN_HEADER_STYLE["color"],
                duration,
                ("center", config.RUNDOWN_Y_START)
            ).with_start(t)
            clips.append(header)

        y_pos = config.RUNDOWN_Y_START + config.RUNDOWN_LINE_HEIGHT + (i * config.RUNDOWN_LINE_HEIGHT)
        line = make_text_clip(
            sentence,
            config.RUNDOWN_STYLE["font_size"],
            config.RUNDOWN_STYLE["color"],
            duration,
            ("center", y_pos)
        ).with_start(t)
        clips.append(line)

def create_sources_clip(find_timestamp, make_text_clip, timestamps, clips, script_file, total_duration):
    with open(script_file, "r") as f:
        content = f.read()
    
    # Find the sources line
    start = content.find(config.SOURCE_PHRASE)
    if start == -1:
        return
    
    end = content.find("\n", start)
    sources_line = content[start:end].strip() if end != -1 else content[start:].strip()
    
    # Split into header and sources list
    sources_text = sources_line.replace(config.SOURCE_PHRASE, "").strip()
    
    # Find timestamp for "Sources"
    t = find_timestamp(config.SOURCE_PHRASE, timestamps)
    if t is None:
        return
    
    t = (t / config.AUDIO_SPEED_FACTOR) + config.AUDIO_OFFSET - config.OVERLAY_ANTICIPATION
    duration = total_duration - t
    
    # Header line
    header = make_text_clip(
        "Sources",
        config.SECTION_STYLE["font_size"],
        config.SECTION_STYLE["color"],
        duration,
        ("center", 400)
    ).with_start(t)
    clips.append(header)
    
    # Sources list
    sources = make_text_clip(
        wrap_sources(sources_text),
        config.RUNDOWN_STYLE["font_size"],
        config.RUNDOWN_STYLE["color"],
        duration,
        ("center", 480)
    ).with_start(t)
    clips.append(sources)

# Build change points from section and story timestamps


def get_change_points(find_timestamp, timestamps, overlays):
    change_points = [(0, "intro")]
    for kind, text in overlays:
        t = find_timestamp(text, timestamps)
        if t is None:
            continue
        t = (t / config.AUDIO_SPEED_FACTOR) + config.AUDIO_OFFSET
        change_points.append((t, text))
    
    t_outro = find_timestamp(config.OUTRO_PHRASE, timestamps)
    if t_outro is not None:
        t_outro = (t_outro / config.AUDIO_SPEED_FACTOR) + config.AUDIO_OFFSET
        change_points.append((t_outro, "outro"))

    change_points.sort(key=lambda x: x[0])
    return change_points

def wrap_sources(sources_text, max_line_length=40):
    items = [s.strip() for s in sources_text.split(",")]
    lines = []
    current_line = ""
    
    for item in items:
        test_line = current_line + ", " + item if current_line else item
        if len(test_line) > max_line_length and current_line:
            lines.append(current_line + ",")
            current_line = item
        else:
            current_line = test_line
    
    if current_line:
        lines.append(current_line)
    
    return "\n".join(lines)


# --- Build video ---

# Step 1 - Silence artifacts

regions = find_artifact_regions(config.TIMESTAMP_FILE, speed_factor = 1.0)
artifact_filter = build_ffmpeg_filter(regions)

print(f"Silencing {len(regions)} artifact regions")
process_audio_effects(artifact_filter)

audio = AudioFileClip(config.EL_DELAY_FILE)
timestamps = load_timestamps(config.TIMESTAMP_FILE)
overlays = parse_script(config.EL_INPUT_FILE)
total_duration = audio.duration

change_points = get_change_points(find_timestamp, timestamps, overlays)

background_clips = build_background_from_timestamps(config.BG_VIDEOS, change_points, total_duration, section_map=config.SECTION_VIDEOS)

# Opening title card
opening = make_text_clip(
    text=config.OPENING_TITLE,
    font_size=config.OPENING_STYLE["font_size"],
    color=config.OPENING_STYLE["color"],
    duration=config.OPENING_STYLE["duration"],
    position=config.OPENING_STYLE["position"]
)

clips = background_clips + [opening]
rundown_sentences = parse_rundown(config.EL_INPUT_FILE)

create_rundown_clips(find_timestamp, make_text_clip, timestamps, clips, rundown_sentences)

# Section and story overlays
generate_overlay_clips(find_timestamp, make_text_clip, make_text_clip_with_bg, timestamps, overlays, clips)
create_sources_clip(find_timestamp, make_text_clip, timestamps, clips, config.EL_INPUT_FILE, total_duration)

final = CompositeVideoClip(clips)
final = final.with_audio(audio)
final.write_videofile(config.OUTPUT_VIDEO, fps=24, audio_codec=config.AUDIO_CODEC)
print(f"Done! Saved to {config.OUTPUT_VIDEO}")