"""Stitch screenshot frames into an animated GIF for SMS sharing."""
from PIL import Image
import glob

# Collect frames in order
frame_files = sorted(glob.glob("gif-frames/*.png"))
print(f"Found {len(frame_files)} frames:")
for f in frame_files:
    print(f"  {f}")

# Open and convert to RGB (GIF doesn't support RGBA)
frames = []
for f in frame_files:
    img = Image.open(f).convert("RGB")
    # Resize to a mobile-friendly width for SMS (480px wide)
    ratio = 480 / img.width
    new_size = (480, int(img.height * ratio))
    img = img.resize(new_size, Image.LANCZOS)
    frames.append(img)

# Save as animated GIF
# 3000ms per frame, with the dashboard holding for 5 seconds
durations = [3000] * len(frames)
durations[-1] = 5000  # Hold on dashboard longer

frames[0].save(
    "foodcartos-demo.gif",
    save_all=True,
    append_images=frames[1:],
    duration=durations,
    loop=0,  # Loop forever
    optimize=True,
)

# Report file size
import os
size_mb = os.path.getsize("foodcartos-demo.gif") / (1024 * 1024)
print(f"\nCreated: foodcartos-demo.gif ({size_mb:.1f} MB)")
if size_mb > 1:
    print("Note: For SMS, you may want to compress further or use MMS.")
