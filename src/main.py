import base64
import io
from pathlib import Path
import re
import flet as ft
import tempfile

from PIL import Image, ImageDraw, ImageFont
import mcschematic
from constants import *

STRUCT_DROPPERS_SINGLE_EVEN = mcschematic.MCStructure()
STRUCT_DROPPERS_DOUBLE_EVEN = mcschematic.MCStructure()
STRUCT_DROPPERHOPPER_EVEN = mcschematic.MCStructure()
STRUCT_DROPPERS_SINGLE_ODD = mcschematic.MCStructure()
STRUCT_DROPPERS_DOUBLE_ODD = mcschematic.MCStructure()
STRUCT_DROPPERHOPPER_ODD = mcschematic.MCStructure()


def load_font(size: int = 11) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    BASE_DIR = Path(__file__).resolve().parent
    LOCAL_FONT_PATH = BASE_DIR / "assets" / "fonts" / "DepartureMono-Regular.otf"

    if LOCAL_FONT_PATH.exists():
        return ImageFont.truetype(str(LOCAL_FONT_PATH), size=size)

    import js  # type: ignore

    worker_url = str(js.self.location.href)
    base_url = worker_url.rsplit("/", 1)[0]
    font_url = f"{base_url}/fonts/DepartureMono-Regular.otf"

    req = js.XMLHttpRequest.new()
    req.open("GET", font_url, False)
    req.responseType = "arraybuffer"
    req.send(None)

    if req.status != 200:
        raise RuntimeError(f"Failed to load font from {font_url}: HTTP {req.status}")

    raw_bytes = bytes(req.response.to_py())
    return ImageFont.truetype(io.BytesIO(raw_bytes), size=size)


def letter_to_pixel_grid(letter: str, size=(5, 14)):
    img = Image.new("1", size, color=0)
    draw = ImageDraw.Draw(img)

    font = load_font()

    draw.text((size[0] / 2, size[1] / 2), letter, fill=1, font=font, anchor="mm")

    grid = []
    for y in range(size[1]):
        row = []
        for x in range(size[0]):
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

    return grid[top_row : bottom_row + 1] if top_row != -1 else grid[:2]


def create_msg_grid(msg: str):
    grid = []
    for char in msg:
        char_matrix = letter_to_pixel_grid(char)
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
    grid_even.extend([[0] * 5] * ((4 - (len(grid_even) % 4)) % 4))
    grid_odd.extend([[0] * 5] * ((4 - (len(grid_odd) % 4)) % 4))

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
        + "]}}"
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
    item_count = 0

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
                item_count += zero_count
                zero_count = 0
                wool_index = (wool_index + 1) % 16
                current_slot += 1
                fixed_slot += 1
        else:
            shulker_str += new_disc(fixed_slot, pattern) + ","
            item_count += 1
            current_slot += 1
            fixed_slot += 1

        # if the new fixed slot goes beyond 26, create a shulker and put it in the appropriate chest
        if index == len(patterns) - 1 or fixed_slot >= 27:
            if item_count < MIN_SHULKER_FILL:
                shulker_str += (
                    new_wool(fixed_slot, wool_index, MIN_SHULKER_FILL - item_count)
                    + ","
                )

            shulker_str = create_shulker(current_shulker, shulker_str)

            if current_shulker <= 27:
                chest_r += shulker_str + ","
            else:
                chest_l += shulker_str + ","

            # reset the shulker string and increment current shulker
            shulker_str = ""
            wool_index = 0
            item_count = 0
            current_shulker += 1

    # create the right and left chests
    chest_r = create_chest("right", chest_r)
    chest_l = create_chest("left", chest_l)

    return chest_r, chest_l, current_shulker - 1


# minecraft:dropper[facing=east,triggered=false]{Items:[{Slot:0b,count:1,id:"minecraft:redstone_torch"}]}
# minecraft:hopper[enabled=false,facing=east]{Items:[],TransferCooldown:0}
def initialize_structures():
    # STRUCT_DROPPERS_SINGLE_EVEN
    STRUCT_DROPPERS_SINGLE_EVEN.setBlock(
        (0, 0, 0),
        "minecraft:dropper[facing=east,triggered=false]{Items:[]}",
    )
    STRUCT_DROPPERS_SINGLE_EVEN.setBlock(
        (1, 0, 0),
        'minecraft:dropper[facing=west,triggered=false]{Items:[{Slot:0b,count:1,id:"minecraft:redstone_torch"}]}',
    )

    # STRUCT_DROPPERS_DOUBLE_EVEN
    STRUCT_DROPPERS_DOUBLE_EVEN.setBlock(
        (0, 0, 0),
        'minecraft:dropper[facing=east,triggered=false]{Items:[{Slot:0b,count:1,id:"minecraft:redstone_torch"}]}',
    )
    STRUCT_DROPPERS_DOUBLE_EVEN.setBlock(
        (1, 0, 0),
        'minecraft:dropper[facing=west,triggered=false]{Items:[{Slot:0b,count:1,id:"minecraft:redstone_torch"}]}',
    )

    # STRUCT_DROPPERHOPPER_EVEN
    STRUCT_DROPPERHOPPER_EVEN.setBlock(
        (0, 0, 0),
        "minecraft:hopper[enabled=false,facing=east]{Items:[],TransferCooldown:0}",
    )
    STRUCT_DROPPERHOPPER_EVEN.setBlock(
        (1, 0, 0), "minecraft:dispenser[facing=down,triggered=false]{Items:[]}"
    )

    # STRUCT_DROPPERS_SINGLE_ODD
    STRUCT_DROPPERS_SINGLE_ODD.setBlock(
        (0, 0, 0),
        'minecraft:dropper[facing=east,triggered=false]{Items:[{Slot:0b,count:1,id:"minecraft:redstone_torch"}]}',
    )
    STRUCT_DROPPERS_SINGLE_ODD.setBlock(
        (1, 0, 0), "minecraft:dropper[facing=west,triggered=false]{Items:[]}"
    )

    # STRUCT_DROPPERS_DOUBLE_ODD
    STRUCT_DROPPERS_DOUBLE_ODD.setBlock(
        (0, 0, 0),
        'minecraft:dropper[facing=east,triggered=false]{Items:[{Slot:0b,count:1,id:"minecraft:redstone_torch"}]}',
    )
    STRUCT_DROPPERS_DOUBLE_ODD.setBlock(
        (1, 0, 0),
        'minecraft:dropper[facing=west,triggered=false]{Items:[{Slot:0b,count:1,id:"minecraft:redstone_torch"}]}',
    )

    # STRUCT_DROPPERHOPPER_ODD
    STRUCT_DROPPERHOPPER_ODD.setBlock(
        (0, 0, 0),
        "minecraft:dispenser[facing=down,triggered=false]{Items:[]}",
    )
    STRUCT_DROPPERHOPPER_ODD.setBlock(
        (1, 0, 0),
        "minecraft:hopper[enabled=false,facing=west]{Items:[],TransferCooldown:0}",
    )


def set_even_chest(
    schem: mcschematic.MCSchematic,
    chest_l: str,
    chest_r: str,
    shulker_count: int,
    x_offset: int,
):
    schem.setBlock((OFFSET_X_EVEN + x_offset, OFFSET_Y_EVEN, OFFSET_Z_EVEN), chest_l)

    schem.setBlock(
        (OFFSET_X_EVEN + x_offset + 1, OFFSET_Y_EVEN, OFFSET_Z_EVEN), chest_r
    )

    schem.placeStructure(
        STRUCT_DROPPERHOPPER_EVEN,
        (OFFSET_X_EVEN + x_offset, OFFSET_Y_EVEN - 1, OFFSET_Z_EVEN),
    )

    if shulker_count == 1:
        schem.placeStructure(
            STRUCT_DROPPERS_SINGLE_EVEN,
            (OFFSET_X_EVEN + x_offset, OFFSET_Y_EVEN + 1, OFFSET_Z_EVEN + 3),
        )
    else:
        schem.placeStructure(
            STRUCT_DROPPERS_DOUBLE_EVEN,
            (OFFSET_X_EVEN + x_offset, OFFSET_Y_EVEN + 1, OFFSET_Z_EVEN + 3),
        )


def set_odd_chest(
    schem: mcschematic.MCSchematic,
    chest_l: str,
    chest_r: str,
    shulker_count: int,
    x_offset: int,
):
    schem.setBlock((OFFSET_X_ODD + x_offset, OFFSET_Y_ODD, OFFSET_Z_ODD), chest_l)

    schem.setBlock((OFFSET_X_ODD + x_offset + 1, OFFSET_Y_ODD, OFFSET_Z_ODD), chest_r)

    schem.placeStructure(
        STRUCT_DROPPERHOPPER_ODD,
        (OFFSET_X_ODD + x_offset, OFFSET_Y_ODD - 1, OFFSET_Z_ODD),
    )

    if shulker_count == 1:
        schem.placeStructure(
            STRUCT_DROPPERS_SINGLE_ODD,
            (OFFSET_X_ODD + x_offset, OFFSET_Y_ODD + 1, OFFSET_Z_ODD - 3),
        )
    else:
        schem.placeStructure(
            STRUCT_DROPPERS_DOUBLE_ODD,
            (OFFSET_X_ODD + x_offset, OFFSET_Y_ODD + 1, OFFSET_Z_ODD - 3),
        )


def generate_schematic(grid: list, msg: str):
    initialize_structures()

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

    even_chest_0_l, even_chest_0_r, even_chest_0_count = build_chests_from_patterns(
        even_patterns_0
    )
    even_chest_1_l, even_chest_1_r, even_chest_1_count = build_chests_from_patterns(
        even_patterns_1
    )
    even_chest_2_l, even_chest_2_r, even_chest_2_count = build_chests_from_patterns(
        even_patterns_2
    )
    even_chest_3_l, even_chest_3_r, even_chest_3_count = build_chests_from_patterns(
        even_patterns_3
    )
    even_chest_4_l, even_chest_4_r, even_chest_4_count = build_chests_from_patterns(
        even_patterns_4
    )
    # print(even_chest_0_l)
    # print(even_chest_0_r)

    odd_chest_0_l, odd_chest_0_r, odd_chest_0_count = build_chests_from_patterns(
        odd_patterns_0
    )
    odd_chest_1_l, odd_chest_1_r, odd_chest_1_count = build_chests_from_patterns(
        odd_patterns_1
    )
    odd_chest_2_l, odd_chest_2_r, odd_chest_2_count = build_chests_from_patterns(
        odd_patterns_2
    )
    odd_chest_3_l, odd_chest_3_r, odd_chest_3_count = build_chests_from_patterns(
        odd_patterns_3
    )
    odd_chest_4_l, odd_chest_4_r, odd_chest_4_count = build_chests_from_patterns(
        odd_patterns_4
    )

    schem = mcschematic.MCSchematic()
    set_even_chest(schem, even_chest_0_l, even_chest_0_r, even_chest_0_count, 0)
    set_even_chest(schem, even_chest_1_l, even_chest_1_r, even_chest_1_count, 4)
    set_even_chest(schem, even_chest_2_l, even_chest_2_r, even_chest_2_count, 8)
    set_even_chest(schem, even_chest_3_l, even_chest_3_r, even_chest_3_count, 12)
    set_even_chest(schem, even_chest_4_l, even_chest_4_r, even_chest_4_count, 16)

    set_odd_chest(schem, odd_chest_0_l, odd_chest_0_r, odd_chest_0_count, 0)
    set_odd_chest(schem, odd_chest_1_l, odd_chest_1_r, odd_chest_1_count, 4)
    set_odd_chest(schem, odd_chest_2_l, odd_chest_2_r, odd_chest_2_count, 8)
    set_odd_chest(schem, odd_chest_3_l, odd_chest_3_r, odd_chest_3_count, 12)
    set_odd_chest(schem, odd_chest_4_l, odd_chest_4_r, odd_chest_4_count, 16)

    return schem


def print_grid(grid: list):
    for row in grid:
        print("".join(["█" if pixel else "_" for pixel in row]))


def main(page: ft.Page):
    page.title = "Geyser Display"
    page.fonts = {"Departure": "fonts/DepartureMono-Regular.otf"}
    page.dark_theme = ft.Theme(
        font_family="Departure",
        color_scheme_seed=ft.Colors.RED_300,
    )
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#691F1A"

    text_input = ft.TextField(
        label="Enter text",
        multiline=True,
        min_lines=3,
        width=float("inf"),
    )

    download_button = ft.Button(
        content="Download",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
        height=50,
        disabled=True,
    )

    save_file_dialog = ft.FilePicker()

    def text_on_change(e):
        if "\n" in e.control.value or "\r" in e.control.value:
            e.control.value = e.control.value.replace("\r", "").replace("\n", "")
            e.control.update()
        download_button.disabled = not bool(e.control.value.strip())
        download_button.update()

    async def download_click(e):
        msg = text_input.value or ""
        schem_file_name = re.sub(r"[^a-zA-Z0-9]", "", msg.lower())[:10]

        grid = create_msg_grid(msg)

        schem = generate_schematic(grid, msg)

        with tempfile.TemporaryDirectory() as temp_dir:
            schem.save(
                temp_dir,
                schem_file_name,
                mcschematic.Version.JE_1_21,
            )
            file_path = Path(temp_dir) / (schem_file_name + ".schem")
            schem_bytes = file_path.read_bytes()

        await save_file_dialog.save_file(
            file_name=schem_file_name + ".schem",
            src_bytes=schem_bytes,
        )

    text_input.on_change = text_on_change
    download_button.on_click = download_click

    column = ft.Column(
        spacing=10,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text(
                value="Geyser Display Schematic Generator",
                theme_style=ft.TextThemeStyle.TITLE_LARGE,
            ),
            # row,
            ft.Container(
                alignment=ft.Alignment.CENTER,
                content=ft.Container(
                    max_width=800,
                    padding=ft.Padding.symmetric(horizontal=10),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[text_input],
                    ),
                ),
            ),
            download_button,
        ],
    )

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Container(
                content=column,
                alignment=ft.Alignment.CENTER,
            ),
        )
    )


ft.run(main)
