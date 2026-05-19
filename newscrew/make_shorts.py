import json
import config

path = config.SHOT_PLAN_JSON
plan = json.load(open(path))
for seg in plan['segments']:
    if seg.get('anchor_clip'):
        seg['anchor_clip'] = seg['anchor_clip'].replace('.mp4', '_short.mp4')
json.dump(plan, open(path, 'w'), indent=2)
print('Done.')