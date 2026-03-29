import json

def find_artifact_regions(timestamp_file, speed_factor=1.0):
    with open(timestamp_file, "r") as f:
        data = json.load(f)
    
    characters = data["characters"]
    starts = data["character_start_times_seconds"]
    ends = data["character_end_times_seconds"]
    
    silence_regions = []
    i = 0
    
    while i < len(characters):
        if characters[i] == "<" and i + 5 < len(characters):
            tag = "".join(characters[i:i+6])
            if tag == "<break":
                j = i - 1
                while j >= 0 and characters[j] in [" ", "\n"]:
                    j -= 1
                
                if j >= 0 and ends[j] < starts[i]:
                    region_start = max(0, ends[j] - 0.05) / speed_factor
                    region_end = starts[i] / speed_factor
                    if region_end - region_start > 0.05:
                        silence_regions.append((region_start, region_end))
        i += 1
    
    return silence_regions

def build_ffmpeg_filter(silence_regions):
    if not silence_regions:
        return "anull"
    parts = [
        f"volume=enable='between(t,{s:.3f},{e:.3f})':volume=0"
        for s, e in silence_regions
    ]
    return ",".join(parts)

if __name__ == "__main__":
    import config
    regions = find_artifact_regions(config.TIMESTAMP_FILE, speed_factor = 1.0)
    print(f"Found {len(regions)} artifact regions:")
    for s, e in regions:
        print(f"  {s:.3f} - {e:.3f}")
    print()
    print("FFmpeg filter:")
    print(build_ffmpeg_filter(regions))