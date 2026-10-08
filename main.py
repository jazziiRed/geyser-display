from PIL import Image, ImageDraw, ImageFont


def letter_to_pixel_grid(font_path, letter, size=(5, 14)):
    img = Image.new("1", size, color=0)
    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype(font_path, size=11)

    draw.text((size[0] / 2, size[1] / 2), letter, fill=1, font=font, anchor="mm")

    # 4. Read the pixels out line-by-line
    grid = []
    for y in range(size[1]):
        row = []
        for x in range(size[0]):
            # getpixel returns 1 if white/text, 0 if black/background
            pixel_value = img.getpixel((x, y))
            row.append(pixel_value)
        grid.append(row)

    return grid


def trim_grid(grid):
    top_row = -1
    bottom_row = -1
    for index, row in enumerate(grid):
        if row != [0, 0, 0, 0, 0] and top_row == bottom_row == -1:
            top_row = bottom_row = index
        elif row != [0, 0, 0, 0, 0]:
            bottom_row = index

    return grid[top_row : bottom_row + 1] if top_row != -1 else [grid[0]]


def print_grid(grid):
    for row in grid:
        print("".join(["█" if pixel else "_" for pixel in row]))


def main():
    FONT_FILE = "fonts/DepartureMono-Regular.otf"
    msg = "A quick brown fox jumps over the lazy dog"

    try:
        for char in msg:
            char_matrix = letter_to_pixel_grid(FONT_FILE, char)
            trimmed_matrix = trim_grid(char_matrix)
            # print(f"Visual representation of {char}:")
            # print_grid(char_matrix)
            print()
            print_grid(trimmed_matrix)

            # print("\nRaw Data Array:")
            # print(char_matrix)
    except IOError:
        print("Please provide a valid path to a .ttf font file.")


if __name__ == "__main__":
    main()
