from moviepy import AudioFileClip, ColorClip, concatenate_videoclips, CompositeVideoClip, TextClip, VideoFileClip,vfx
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

def build_background_from_timestamps(video_files, change_points, total_duration, section_map=None):
    segments = []
    video_index = 0
    
    for i, (start_time, label) in enumerate(change_points):
        if i + 1 < len(change_points):
            duration = change_points[i + 1][0] - start_time
        else:
            duration = total_duration - start_time
        
        # Use section-specific video if available
        if section_map and label in section_map:
            video_file = section_map[label]
        else:
            video_file = video_files[video_index % len(video_files)]
            video_index += 1
        
        clip = (VideoFileClip(video_file)
                .with_effects([vfx.Loop(duration=duration)])
                .resized((1920, 1080))
                .with_start(start_time))
        
        segments.append(clip)
    
    return segments

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

def process_audio_effects(artifact_filter):
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

def generate_overlay_clips(find_timestamp, make_text_clip, make_text_clip_with_bg, timestamps, overlays, clips):
    last_section_end = 0

    for kind, text in overlays:
        t = find_timestamp(text, timestamps)
        if t is None:
            print(f"WARNING: could not find timestamp for: {text}")
            continue

        # Adjust for audio offset
        t = (t / config.AUDIO_SPEED_FACTOR) + config.AUDIO_OFFSET - config.OVERLAY_ANTICIPATION
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

def create_rundown_clips(find_timestamp, make_text_clip, timestamps, clips, rundown_sentences):
    rundown_end_text = "Here is what happened"
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
    start = content.find("Sources this week:")
    if start == -1:
        return
    
    end = content.find("\n", start)
    sources_line = content[start:end].strip() if end != -1 else content[start:].strip()
    
    # Split into header and sources list
    sources_text = sources_line.replace("Sources this week:", "").strip()
    
    # Find timestamp for "Sources"
    t = find_timestamp("Sources this week", timestamps)
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