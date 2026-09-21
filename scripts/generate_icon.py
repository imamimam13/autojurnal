import os
import sys
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def create_app_icon():
    size = 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Rounded rectangle background with indigo-violet gradient
    corner_radius = 220
    
    # Create mask for rounded rect
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    margin = 40
    mask_draw.rounded_rectangle([margin, margin, size - margin, size - margin], radius=corner_radius, fill=255)

    # Generate gradient base
    gradient = Image.new("RGBA", (size, size))
    g_draw = ImageDraw.Draw(gradient)
    
    # Gradient colors: Deep indigo (top-left) to vivid purple/fuchsia (bottom-right)
    top_color = (24, 24, 38)        # Deep slate
    mid_color = (79, 70, 229)       # Indigo
    bottom_color = (147, 51, 234)   # Purple/Violet
    
    for y in range(size):
        ratio = y / size
        if ratio < 0.5:
            r = int(top_color[0] + (mid_color[0] - top_color[0]) * (ratio * 2))
            g = int(top_color[1] + (mid_color[1] - top_color[1]) * (ratio * 2))
            b = int(top_color[2] + (mid_color[2] - top_color[2]) * (ratio * 2))
        else:
            r = int(mid_color[0] + (bottom_color[0] - mid_color[0]) * ((ratio - 0.5) * 2))
            g = int(mid_color[1] + (bottom_color[1] - mid_color[1]) * ((ratio - 0.5) * 2))
            b = int(mid_color[2] + (bottom_color[2] - mid_color[2]) * ((ratio - 0.5) * 2))
        g_draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    img.paste(gradient, (0, 0), mask)

    # Draw subtle inner border
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([margin, margin, size - margin, size - margin], radius=corner_radius, outline=(255, 255, 255, 50), width=4)

    # 2. Draw Book/Journal symbol in center
    # Book spine & pages
    center_x = size // 2
    center_y = size // 2 - 20
    
    # Left page
    left_pts = [
        (center_x - 20, center_y - 180),
        (center_x - 240, center_y - 150),
        (center_x - 240, center_y + 190),
        (center_x - 20, center_y + 160)
    ]
    draw.polygon(left_pts, fill=(240, 244, 255, 245))
    
    # Right page
    right_pts = [
        (center_x + 20, center_y - 180),
        (center_x + 240, center_y - 150),
        (center_x + 240, center_y + 190),
        (center_x + 20, center_y + 160)
    ]
    draw.polygon(right_pts, fill=(255, 255, 255, 255))
    
    # Book spine center fold
    draw.line([(center_x, center_y - 180), (center_x, center_y + 165)], fill=(180, 190, 220, 200), width=8)

    # Lines on pages (mimicking text)
    line_color_left = (160, 175, 210, 180)
    line_color_right = (180, 195, 230, 180)
    
    for offset_y in range(-100, 120, 45):
        # Left lines
        draw.line([
            (center_x - 200, center_y + offset_y - 10),
            (center_x - 50, center_y + offset_y)
        ], fill=line_color_left, width=12)
        # Right lines
        draw.line([
            (center_x + 50, center_y + offset_y),
            (center_x + 200, center_y + offset_y - 10)
        ], fill=line_color_right, width=12)

    # 3. AI / Sparkle Star (top right of book)
    def draw_sparkle(cx, cy, radius, color):
        pts = [
            (cx, cy - radius),
            (cx + radius * 0.25, cy - radius * 0.25),
            (cx + radius, cy),
            (cx + radius * 0.25, cy + radius * 0.25),
            (cx, cy + radius),
            (cx - radius * 0.25, cy + radius * 0.25),
            (cx - radius, cy),
            (cx - radius * 0.25, cy - radius * 0.25)
        ]
        draw.polygon(pts, fill=color)

    # Big sparkle
    draw_sparkle(center_x + 230, center_y - 180, 90, (254, 240, 138, 255))  # Gold sparkle
    # Small sparkle
    draw_sparkle(center_x - 220, center_y + 200, 50, (191, 219, 254, 240))  # Cyan sparkle
    # Medium sparkle
    draw_sparkle(center_x + 190, center_y + 220, 60, (233, 213, 255, 250))  # Lavender sparkle

    # Save output
    out_dir = Path("scripts/build")
    out_dir.mkdir(parents=True, exist_ok=True)
    iconset_dir = out_dir / "AutoJurnal.iconset"
    iconset_dir.mkdir(exist_ok=True)

    # Save base 1024 png
    img.save(out_dir / "app_icon_1024.png")

    # Generate all icon sizes for macOS iconutil
    sizes = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]

    for fname, sz in sizes:
        resized = img.resize((sz, sz), Image.Resampling.LANCZOS)
        resized.save(iconset_dir / fname)

    # Run iconutil if on macOS
    icns_path = out_dir / "AppIcon.icns"
    if sys.platform == "darwin":
        try:
            subprocess.run(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)], check=True)
            print(f"Successfully generated macOS icon: {icns_path}")
        except Exception as e:
            print(f"Warning: Failed to run iconutil: {e}")

    # Generate Windows .ico file
    ico_path = out_dir / "AppIcon.ico"
    try:
        img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        print(f"Successfully generated Windows icon: {ico_path}")
    except Exception as e:
        print(f"Warning: Failed to save .ico: {e}")

if __name__ == "__main__":
    create_app_icon()

