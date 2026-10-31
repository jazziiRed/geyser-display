from PIL import Image, ImageDraw, ImageFont
import mcschematic
from constants import *


def letter_to_pixel_grid(font_path: str, letter: str, size=(5, 14)):
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


def trim_grid(grid: list):
    top_row = -1
    bottom_row = -1
    for index, row in enumerate(grid):
        if row != [0, 0, 0, 0, 0] and top_row == bottom_row == -1:
            top_row = bottom_row = index
        elif row != [0, 0, 0, 0, 0]:
            bottom_row = index

    return grid[top_row : bottom_row + 1] if top_row != -1 else [grid[0]]


def create_msg_grid(msg: str, font_file: str):
    grid = []
    for char in msg:
        char_matrix = letter_to_pixel_grid(font_file, char)
        trimmed_matrix = trim_grid(char_matrix)
        for row in trimmed_matrix:
            grid.append(row)
        grid.append([0] * 5)

    if len(grid) > 0:
        grid.pop()

    return grid


def split_grid(grid: list):
    grid_even = []
    grid_odd = []

    for index, row in enumerate(grid):
        if index % 2 == 0:
            grid_even.append(row)
        else:
            grid_odd.append(row)

    # append empty rows as needed to be a multiple of 4
    grid_even.append(([0] * 5) * ((4 - (len(grid_even) % 4)) % 4))
    grid_odd.append(([0] * 5) * ((4 - (len(grid_odd) % 4)) % 4))

    return grid_even, grid_odd


def extract_patterns(grid: list):
    col0 = []
    col1 = []
    col2 = []
    col3 = []
    col4 = []

    while len(grid) > 0:
        pattern0 = 0b0
        pattern1 = 0b0
        pattern2 = 0b0
        pattern3 = 0b0
        pattern4 = 0b0

        for row in grid[:4]:
            pattern0 = (pattern0 << 1) + row[0]
            pattern1 = (pattern1 << 1) + row[1]
            pattern2 = (pattern2 << 1) + row[2]
            pattern3 = (pattern3 << 1) + row[3]
            pattern4 = (pattern4 << 1) + row[4]

        col0.append(pattern0)
        col1.append(pattern1)
        col2.append(pattern2)
        col3.append(pattern3)
        col4.append(pattern4)

        del grid[:4]

    # remove trailing 0b0000 patterns
    while col0[len(col0) - 1] == 0b0000:
        del col0[len(col0) - 1]
    while col1[len(col1) - 1] == 0b0000:
        del col1[len(col1) - 1]
    while col2[len(col2) - 1] == 0b0000:
        del col2[len(col2) - 1]
    while col3[len(col3) - 1] == 0b0000:
        del col3[len(col3) - 1]
    while col4[len(col4) - 1] == 0b0000:
        del col4[len(col4) - 1]

    return col0, col1, col2, col3, col4


def new_disc(slot: int, pattern: int):
    disc_name = SIGNAL_STRENGTH_TO_DISC_NAME[GREY_CODE[pattern]]
    return '{item:{count:1,id:"' + disc_name + '"},slot:' + str(slot) + "}"


# {item:{count:64,id:"minecraft:white_wool"},slot:0}
def new_wool(slot: int, color_index: int, count: int):
    wool_name = WOOL_BLOCK_IDS[color_index]
    return (
        "{item:{count:"
        + str(count)
        + ',id:"'
        + wool_name
        + '"},slot:'
        + str(slot)
        + "}"
    )


# minecraft:chest[facing=south,type=right,waterlogged=false]{Items:[{Slot:0b,count:1,id:"minecraft:shulker_box",components:{"minecraft:container":[{slot:0,item:{count:1,id:"minecraft:music_disc_blocks"}}],"minecraft:custom_name":{"text":"1"}}}]}
def create_shulker(current_shulker: int, contents: str):
    # print("creating shulker with contents: " + contents)
    slot = (current_shulker - 1) % 27
    # remove trailing comma
    if len(contents) > 0:
        contents = contents[: len(contents) - 1]
    return (
        "{Slot:"
        + str(slot)
        + 'b,count:1,id:"minecraft:shulker_box",components:{"minecraft:container":['
        + contents
        + '],"minecraft:custom_name":{"text":"'
        + str(current_shulker)
        + '"}}}'
    )


# minecraft:chest[facing=south,type=right,waterlogged=false]{Items:[{Slot:0b,count:1,id:"minecraft:shulker_box",components:{"minecraft:container":[{slot:0,item:{count:1,id:"minecraft:music_disc_blocks"}}],"minecraft:custom_name":{"text":"1"}}}]}
def create_chest(type: str, contents: str):
    # remove trailing comma
    if len(contents) > 0:
        contents = contents[: len(contents) - 1]
    return (
        "minecraft:chest[facing=south,type="
        + type
        + ",waterlogged=false]{Items:["
        + contents
        + "]}"
    )


def build_chests_from_patterns(patterns: list):
    chest_r = ""
    chest_l = ""
    shulker_str = ""
    zero_count = 0
    wool_index = 0
    current_slot = 0
    current_shulker = 1

    for index, pattern in enumerate(patterns):
        # rectify the running slot number to 0-26
        fixed_slot = current_slot % 27
        # print("index: " + str(index))
        # print("pattern: " + str(pattern))

        # read the current pattern and insert items
        if pattern == 0b0000:
            zero_count += 1
            if index == len(patterns) - 1 or patterns[index + 1] != 0b0000:
                shulker_str += new_wool(fixed_slot, wool_index, zero_count) + ","
                zero_count = 0
                wool_index = (wool_index + 1) % 16
                current_slot += 1
                fixed_slot += 1
        else:
            shulker_str += new_disc(fixed_slot, pattern) + ","
            current_slot += 1
            fixed_slot += 1

        # if the new fixed slot goes beyond 26, create a shulker and put it in the appropriate chest
        if index == len(patterns) - 1 or fixed_slot >= 27:
            shulker_str = create_shulker(current_shulker, shulker_str)

            if current_shulker <= 27:
                chest_r += shulker_str + ","
            else:
                chest_l += shulker_str + ","

            # reset the shulker string and increment current shulker
            shulker_str = ""
            wool_index = 0
            current_shulker += 1

    # create the right and left chests
    chest_r = create_chest("right", chest_r)
    chest_l = create_chest("left", chest_l)

    return chest_r, chest_l


def generate_schematic(grid: list, msg: str):
    grid_even, grid_odd = split_grid(grid)
    # print_grid(grid_even)
    # print_grid(grid_odd)

    (
        even_patterns_0,
        even_patterns_1,
        even_patterns_2,
        even_patterns_3,
        even_patterns_4,
    ) = extract_patterns(grid_even)
    (
        odd_patterns_0,
        odd_patterns_1,
        odd_patterns_2,
        odd_patterns_3,
        odd_patterns_4,
    ) = extract_patterns(grid_odd)
    # print(even_patterns_0)
    # print(even_patterns_1)

    even_0_chest_l, even_0_chest_r = build_chests_from_patterns(even_patterns_0)
    even_1_chest_l, even_1_chest_r = build_chests_from_patterns(even_patterns_1)
    even_2_chest_l, even_2_chest_r = build_chests_from_patterns(even_patterns_2)
    even_3_chest_l, even_3_chest_r = build_chests_from_patterns(even_patterns_3)
    even_4_chest_l, even_4_chest_r = build_chests_from_patterns(even_patterns_4)
    # print(even_0_chest_l)
    # print(even_0_chest_r)

    odd_0_chest_l, odd_0_chest_r = build_chests_from_patterns(odd_patterns_0)
    odd_1_chest_l, odd_1_chest_r = build_chests_from_patterns(odd_patterns_1)
    odd_2_chest_l, odd_2_chest_r = build_chests_from_patterns(odd_patterns_2)
    odd_3_chest_l, odd_3_chest_r = build_chests_from_patterns(odd_patterns_3)
    odd_4_chest_l, odd_4_chest_r = build_chests_from_patterns(odd_patterns_4)

    schem = mcschematic.MCSchematic()
    schem.setBlock((0, 0, -1), even_0_chest_l)
    schem.setBlock((1, 0, -1), even_0_chest_r)
    schem.setBlock((2, 0, -1), even_1_chest_l)
    schem.setBlock((3, 0, -1), even_1_chest_r)
    schem.setBlock((4, 0, -1), even_2_chest_l)
    schem.setBlock((5, 0, -1), even_2_chest_r)
    schem.setBlock((6, 0, -1), even_3_chest_l)
    schem.setBlock((7, 0, -1), even_3_chest_r)
    schem.setBlock((8, 0, -1), even_4_chest_l)
    schem.setBlock((9, 0, -1), even_4_chest_r)

    schem.setBlock((0, -1, -1), odd_0_chest_l)
    schem.setBlock((1, -1, -1), odd_0_chest_r)
    schem.setBlock((2, -1, -1), odd_1_chest_l)
    schem.setBlock((3, -1, -1), odd_1_chest_r)
    schem.setBlock((4, -1, -1), odd_2_chest_l)
    schem.setBlock((5, -1, -1), odd_2_chest_r)
    schem.setBlock((6, -1, -1), odd_3_chest_l)
    schem.setBlock((7, -1, -1), odd_3_chest_r)
    schem.setBlock((8, -1, -1), odd_4_chest_l)
    schem.setBlock((9, -1, -1), odd_4_chest_r)
    schem.save(
        "schems",
        re.sub(r"[^a-zA-Z0-9]", "", msg.lower())[:10],
        mcschematic.Version.JE_1_21,
    )


def print_grid(grid: list):
    for row in grid:
        print("".join(["█" if pixel else "_" for pixel in row]))


def main():
    FONT_FILE = "fonts/DepartureMono-Regular.otf"
    msg = "A quick brown fox jumps over the lazy dog"
    # msg = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum"

    grid = create_msg_grid(msg, FONT_FILE)
    # print_grid(grid)

    generate_schematic(grid, msg)


if __name__ == "__main__":
    main()
