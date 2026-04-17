from moviepy import ColorClip, AudioFileClip, CompositeVideoClip

# Simple test - create a 5 second dark blue video
clip = ColorClip(size=(1920, 1080), color=(15, 20, 40), duration=5)
clip.write_videofile("test_output.mp4", fps=24)
print("Success!")