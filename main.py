"""Main file for ByteBiter, a game wherein you explore files. Based off a bug from SML2"""

import time
import os
from functools import lru_cache
import multiprocessing as mp
import numpy as np
import arcade

TILE_W, TILE_H = 64, 64
SCREEN_W, SCREEN_H = TILE_W * 16, TILE_H * 9

VIEWPORT_MARGIN_TOP = TILE_H * 3
VIEWPORT_MARGIN_BOTTOM = TILE_H * 3
VIEWPORT_RIGHT_MARGIN = TILE_W * 3
VIEWPORT_LEFT_MARGIN = TILE_W * 3

MAP_SIZE = 32

MOVEMENT_SPEED = 5
JUMP_SPEED = 25
GRAVITY = 1

MY_FILE = 'Alice'

SCREEN_TITLE = MY_FILE.split('.')[0]

MAP_DIR = sorted([mf for mf in
                  [mf for mf in os.listdir('./Maps') if os.path.isfile(os.path.join('./Maps', mf))]
                  if mf.endswith('.tmx') and 'level' in mf])
for file in MAP_DIR:
    os.remove(f'./Maps/{file}')

MAP_HEADER = f'''<?xml version="1.0" encoding="UTF-8"?>
<map version="1.2" tiledversion="1.2.3" orientation="orthogonal" renderorder="right-down" width="{MAP_SIZE}" height="{MAP_SIZE}" 
tilewidth="64" tileheight="64" infinite="0" nextlayerid="2" nextobjectid="1">
 <tileset firstgid="1" source="./tiles.tsx"/>
 <layer id="1" name="Platforms" width="{MAP_SIZE}" height="{MAP_SIZE}">
  <data encoding="csv">'''

MAP_FOOTER = '''</data>
 </layer>
</map>'''


def write_map(level_data, level):
    """Generate a "valid" tmx file, though due to differences in EOL characters
    it cannot be opened with Tiled. Works for my purposes regardless.

    :param np.array level_data: a numpy array of integers
    :param string level: the filename

    """
    np.savetxt(f'./Maps/{level}', level_data, delimiter=",", fmt='%s',
               header=MAP_HEADER, footer=MAP_FOOTER, comments='')


@lru_cache(256)
def byte_to_hex(pair):
    """Converts a pair of bytes into a pair of hex values.

    :param int pair: a pair of bytes
    :returns: a pair of hex values

    """
    # (0xa, 0xb) -> (10, 11)
    val = hex(pair)[2:].zfill(2)
    return int(val[0], 16), int(val[1].zfill(1), 16)


@lru_cache(256)
def hex_to_byte(pair):
    """Converts a pair of bytes into a pair of hex values.

    :param tuple pair: a pair of hex values
    :returns: a byte or pair of bytes

    """
    # (10, 10) -> (0xa, 0xa)
    if -1 in pair:
        return b' '
    return bytes([int(hex(pair[0])[2] + hex(pair[1])[2], 16)])


@lru_cache(None)
def get_block(coord: int):
    """Rounds a value to it's nearest tile.

    :param int coord: an integer
    :returns: that integer rounded to the nearest tile

    """
    return int(coord // TILE_H * TILE_H)


def file_to_levels():
    """Converts a binary file into a TMX level."""

    with open(MY_FILE, 'rb') as input_data:
        # int (255) -> hex (0xff) -> two hex values (0x0f, 0x0f) -> two int values -> (15, 15)
        rom = [item for sublist in [byte_to_hex(i) for i in input_data.read()] for item in sublist]

    # split the data
    level_map_data = [rom[x:x+MAP_SIZE**2] for x in range(0, len(rom), MAP_SIZE**2)]

    # pad the last map with empty space, so all maps are the same size
    level_map_data[-1] += [-1] * (MAP_SIZE**2 - len(level_map_data[-1]))

    # convert them into numpy arrays of dimensions MAP_SIZE x MAP_SIZE
    maps = [np.reshape(i, (MAP_SIZE, MAP_SIZE)) for i in level_map_data]

    for map_num, cur_map in enumerate(maps):
        # save the array as a CSV, with header and footer data attached
        write_map(cur_map, f'level_{map_num:0>8}.tmx')


def levels_to_file():
    """Converts TMX level data into a binary file."""

    paired_data = []
    for map_file in MAP_DIR:
        with open(f'./Maps/{map_file}') as cur_map:
            # map_data will be a list of strings, looking like ['4', '1', '6', '9'...] with some
            # "impossible" values, '-1' and ''
            map_data = ','.join(cur_map.read().split('\n')[6:-4]).split(',')
            #  cur_rom_space will be a list of lists, looking like [[4, 1, 6, 9...]...]
            cur_rom_space = [(int(i)) for i in map_data if i not in ('-1', '')]

            # re pair up the nums, so it's [[41, 69], [42, 20]...]
            paired_data.append(list(zip(cur_rom_space[::2], cur_rom_space[1::2])))

    # de-nest the lists, and convert the pairs back into bytes, then string them all together.
    output_data = [b''.join([hex_to_byte(val) for val in rom_item]) for rom_item in paired_data]

    # if there is not a backup file, create one.
    if not os.path.isfile(f'{MY_FILE}.bak'):
        with open(MY_FILE, 'br+') as src_file:
            with open(f'{MY_FILE}.bak', 'wb') as backup:
                backup.write(src_file.read())

    # write over the old data with the new
    with open(MY_FILE, 'br+') as cur_map:
        for line in output_data:
            cur_map.write(line)


def gen_item_menu(menu_items):
    """Generate a level with menu items inside
     such that the player can choose options while still playing like normal."""

    # create a blank array
    menu = np.zeros((MAP_SIZE, MAP_SIZE), dtype=int)

    for item_pos, list_item in enumerate(menu_items):

        # convert each menu item into data, then flatten the data
        hex_dat_item = [item for sublist in [byte_to_hex(i) for i in list_item] for item in sublist]

        # place each menu item on the array, skipping lines
        item_len = len(hex_dat_item)
        menu[item_pos*2, 0:item_len] = hex_dat_item

    # make it into a map and send it out
    write_map(menu, 'Menu.tmx')


def write_wrapper():
    """A simple holder function to run while the main game runs. It writes the levels to a file,
    then generates a level based off of that file.
    It's ordered this way so that changes are not reverted each time the level is updated."""

    while True:
        levels_to_file()
        file_to_levels()


class NesGame(arcade.Window):
    """The game function. Produces a scene with:
    - A hexadecimal representation of a given file
    - A player sprite capable of making arbitrary modifications to the representation"""

    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        super().__init__(SCREEN_W, SCREEN_H, SCREEN_TITLE)
        file_path = os.path.dirname(os.path.abspath(__file__))
        os.chdir(file_path)

        # Player stuff
        self.p_block_y, self.p_block_x = (0, 0)
        self.wall_list = None
        self.player_list = None
        self.player_sprite = None

        # Game stuff
        self.physics_engine = None
        self.view_left = 0
        self.view_bottom = 0

        self.my_map = None

        self.level = 0

        self.end_of_map = MAP_SIZE * TILE_H

    def setup(self):
        """Generates a player sprite and sets it's position/center"""

        self.player_list = arcade.SpriteList()
        self.player_sprite = arcade.Sprite("images/character.png", 1)

        self.player_sprite.center_x = TILE_W // 2
        self.player_sprite.center_y = TILE_H // 2
        self.player_list.append(self.player_sprite)
        self.player_sprite.bottom = TILE_H * MAP_SIZE

        self.load_level()

    def load_level(self):
        """Loads the next or previous chunk of data,
        then re-initializes the platformer engine."""

        self.my_map = arcade.read_tiled_map(f'./Maps/level_{self.level:0>8}.tmx', 1)
        self.wall_list = arcade.generate_sprites(self.my_map, 'Platforms', 1)
        self.physics_engine = arcade.PhysicsEnginePlatformer(self.player_sprite,
                                                             self.wall_list,
                                                             gravity_constant=GRAVITY)
        self.physics_engine.enable_multi_jump(1)

    def on_draw(self):
        """Draws the player, walls, current text, and FPS."""

        arcade.start_render()
        # Draw all the sprites
        self.player_list.draw()
        self.wall_list.draw()

        # highlight which block the player is standing on
        arcade.draw_lrtb_rectangle_outline(*map(get_block, [self.player_sprite.left,
                                                            self.player_sprite.left + TILE_W,
                                                            self.player_sprite.bottom,
                                                            self.player_sprite.bottom - TILE_H]),
                                           color=[255, 00, 00, 100], border_width=8)

        # grab the pair of blocks that the player is standing on
        byte_x = round(self.p_block_x/2) * 2
        if byte_x < 2:
            # ensure the pair is above 2 so everything renders properly
            byte_x = 2
        # grab five blocks, starting right behind the player
        hex_block = self.my_map.layers_int_data['Platforms'][self.p_block_y][byte_x-2:byte_x+10]
        # pair them all up and get their byte-string representations
        paired_blocks = [hex_to_byte(tuple(i)) for i in list(zip(hex_block[::2], hex_block[1::2]))]
        # do some formatting and draw the text on screen
        arcade.draw_text(str(b''.join(paired_blocks)).replace('\\x00', ' ')[2:-1],
                         self.view_left + TILE_W, self.view_bottom + SCREEN_H - TILE_H,
                         arcade.color.WHITE, 24)

    def on_key_press(self, symbol, modifiers):
        """Controls user input

        UP      -   Jump
        DOWN    -   either fall to the ground if the player is in the air
                    or go down a row of blocks
        LEFT    -   Move the player left, currently there is no acceleration
        RIGHT   -   Move the player right, currently there is no acceleration
        W       -   Change the value of the block the player is standing on up by one
        S       -   Change the value of the block the player is standing on down by one

        """
        try:
            cur_block = self.my_map.layers_int_data['Platforms'][self.p_block_y][self.p_block_x]
        except IndexError:
            cur_block = 0
        if symbol == arcade.key.UP:
            if self.physics_engine.can_jump():
                self.player_sprite.change_y = JUMP_SPEED
        if symbol == arcade.key.DOWN:
            if self.physics_engine.can_jump():
                self.player_sprite.bottom -= 128
            else:
                self.player_sprite.change_y -= 32
        if symbol == arcade.key.LEFT:
            self.player_sprite.change_x = -MOVEMENT_SPEED
        if symbol == arcade.key.RIGHT:
            self.player_sprite.change_x = MOVEMENT_SPEED
        if symbol == arcade.key.S and cur_block > 0:
            self.my_map.layers_int_data['Platforms'][self.p_block_y][self.p_block_x] -= 1
            write_map(self.my_map.layers_int_data['Platforms'], level=f'level_{self.level:0>8}.tmx')
            self.load_level()
        if symbol == arcade.key.W and cur_block < 15:
            self.my_map.layers_int_data['Platforms'][self.p_block_y][self.p_block_x] += 1
            write_map(self.my_map.layers_int_data['Platforms'], level=f'level_{self.level:0>8}.tmx')
            self.load_level()
        if symbol == arcade.key.ESCAPE:
            arcade.close_window()

    def on_key_release(self, symbol, modifiers):
        """Stops the players horizontal when LEFT or RIGHT are released"""

        if symbol in (arcade.key.LEFT, arcade.key.RIGHT):
            self.player_sprite.change_x = 0

    def update(self, delta_time):
        """Frame update function

        controls switching levels,
        deciding which block the player is standing on,
        and moving the camera.
        """
        self.p_block_y = MAP_SIZE - get_block(self.player_sprite.bottom) // TILE_H
        self.p_block_x = get_block(self.player_sprite.left) // TILE_W + 1

        if self.player_sprite.right >= self.end_of_map + TILE_W * 2:
            if self.level < len(MAP_DIR) - 1:
                self.level += 1
            else:
                self.level = 0
            self.load_level()
            self.player_sprite.left = 0
        if self.player_sprite.left <= -(TILE_W * 2):
            if self.level > 0:
                self.level -= 1
            else:
                self.level = len(MAP_DIR) - 1
            self.load_level()
            self.player_sprite.left = TILE_W * MAP_SIZE - 1
        self.physics_engine.update()

        changed = False
        left_boundary = self.view_left + VIEWPORT_LEFT_MARGIN
        if self.player_sprite.left < left_boundary:
            self.view_left -= left_boundary - self.player_sprite.left
            changed = True

        # Scroll right
        right_boundary = self.view_left + SCREEN_W - VIEWPORT_RIGHT_MARGIN
        if self.player_sprite.right > right_boundary:
            self.view_left += self.player_sprite.right - right_boundary
            changed = True

        # Scroll up
        top_boundary = self.view_bottom + SCREEN_H - VIEWPORT_MARGIN_TOP
        if self.player_sprite.top > top_boundary:
            self.view_bottom += self.player_sprite.top - top_boundary
            changed = True

        # Scroll down
        bottom_boundary = self.view_bottom + VIEWPORT_MARGIN_BOTTOM
        if self.player_sprite.bottom < bottom_boundary:
            self.view_bottom -= bottom_boundary - self.player_sprite.bottom
            changed = True

        if changed:
            self.view_left = int(self.view_left)
            self.view_bottom = int(self.view_bottom)
            arcade.set_viewport(self.view_left,
                                SCREEN_W + self.view_left,
                                self.view_bottom,
                                SCREEN_H + self.view_bottom)


def main():
    """generates a window and runs the game code, the read/write code is disconnected from this."""

    window = NesGame()
    window.setup()
    arcade.run()


if __name__ == '__main__':
    # run this once to generate the initial levels
    file_to_levels()

    # the game process runs the game, the write process controls updating the files and maps
    GAME_PROCESS = mp.Process(target=main)
    WRITE_PROCESS = mp.Process(target=write_wrapper, daemon=True)
    GAME_PROCESS.start()
    WRITE_PROCESS.start()
    # when the game is killed, kill the write process
    while True:
        if not GAME_PROCESS.is_alive() and not WRITE_PROCESS.is_alive():
            break

        if GAME_PROCESS.is_alive() and not WRITE_PROCESS.is_alive():
            GAME_PROCESS.terminate()
            break

        if not GAME_PROCESS.is_alive() and WRITE_PROCESS.is_alive():
            WRITE_PROCESS.terminate()
            break
        # one update per second is real time enough
        time.sleep(1)

    # I have no idea what joining them does, but the internet told me to
    GAME_PROCESS.join()
    WRITE_PROCESS.join()
