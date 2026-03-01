"""
Generate extension icons
Requires: pip install pillow
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, output_path):
    # Create image with gradient background
    img = Image.new('RGB', (size, size), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw gradient background
    for i in range(size):
        color_value = int(9 + (150 - 9) * (i / size))
        draw.rectangle([(0, i), (size, i+1)], fill=(color_value, 105, 218))
    
    # Draw code brackets symbol
    bracket_color = (255, 255, 255)
    line_width = max(2, size // 16)
    
    # Left bracket
    left_x = size // 4
    draw.line([(left_x, size//4), (left_x, size*3//4)], fill=bracket_color, width=line_width)
    draw.line([(left_x, size//4), (left_x + size//8, size//4)], fill=bracket_color, width=line_width)
    draw.line([(left_x, size*3//4), (left_x + size//8, size*3//4)], fill=bracket_color, width=line_width)
    
    # Right bracket
    right_x = size * 3 // 4
    draw.line([(right_x, size//4), (right_x, size*3//4)], fill=bracket_color, width=line_width)
    draw.line([(right_x, size//4), (right_x - size//8, size//4)], fill=bracket_color, width=line_width)
    draw.line([(right_x, size*3//4), (right_x - size//8, size*3//4)], fill=bracket_color, width=line_width)
    
    # Add checkmark in center
    check_size = size // 6
    center = size // 2
    draw.line([(center - check_size, center), (center - check_size//3, center + check_size//2)], 
              fill=(76, 217, 100), width=line_width)
    draw.line([(center - check_size//3, center + check_size//2), (center + check_size, center - check_size)], 
              fill=(76, 217, 100), width=line_width)
    
    # Save
    img.save(output_path, 'PNG')
    print(f'Created: {output_path}')

# Create icons directory
os.makedirs('icons', exist_ok=True)

# Generate all sizes
create_icon(16, 'icons/icon16.png')
create_icon(48, 'icons/icon48.png')
create_icon(128, 'icons/icon128.png')

print('✅ All icons generated!')