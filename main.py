import numpy as np
import arcade
import os
import time
from functools import lru_cache

my_file = 'Alice'

file_size = 0

map_dir = sorted([mf for mf in [mf for mf in os.listdir('./Maps') if os.path.isfile(os.path.join('./Maps', mf))] if
                  mf.endswith('.tmx')])
for file in map_dir:
    os.remove('./Maps/{}'.format(file))

MAP_SIZE = 64
map_header = '''<?xml version="1.0" encoding="UTF-8"?>
<map version="1.2" tiledversion="1.2.3" orientation="orthogonal" renderorder="right-down" width="{0}" height="{0}" 
tilewidth="64" tileheight="64" infinite="0" nextlayerid="2" nextobjectid="1">
 <tileset firstgid="1" source="./tiles.tsx"/>
 <layer id="1" name="Platforms" width="{0}" height="{0}">
  <data encoding="csv">'''.format(MAP_SIZE)

map_footer = '''</data>
 </layer>
</map>'''

TILE_SIZE = TILE_WIDTH, TILE_HEIGHT = (64, 64)
SCREEN_SIZE = SCREEN_WIDTH, SCREEN_HEIGHT = (TILE_WIDTH*16, TILE_HEIGHT*9)
SCREEN_TITLE = "Byte Biter"

VIEWPORT_MARGIN_TOP = TILE_HEIGHT * 3
VIEWPORT_MARGIN_BOTTOM = TILE_HEIGHT * 3
VIEWPORT_RIGHT_MARGIN = TILE_WIDTH * 6
VIEWPORT_LEFT_MARGIN = TILE_WIDTH * 6


MOVEMENT_SPEED = 5
JUMP_SPEED = 25
GRAVITY = 1


@lru_cache(None)
def byte_to_hex(pair):
    val = hex(pair)[2:].zfill(2)
    return int(val[0], 16), int(val[1].zfill(1), 16)


@lru_cache(None)
def hex_to_byte(pair):
    return bytes([int(hex(pair[0])[2] + hex(pair[1])[2], 16)])


def file_to_levels(input_file=my_file):
    global file_size
    with open(input_file, 'rb') as input_data:
        # convert int (255) -> hex (0xff) -> two hex values (0x0f, 0x0f) -> two int values -> (15, 15) -> add 1 to each
        mario_rom = [item for sublist in [byte_to_hex(i) for i in input_data.read()] for item in sublist]

    # split the data
    level_map_data = [mario_rom[x:x+MAP_SIZE**2] for x in range(0, len(mario_rom), MAP_SIZE**2)]
    # pad the last map with empty space, so all maps are the same size
    level_map_data[-1] += [-1] * (MAP_SIZE**2 - len(level_map_data[-1]))
    # convert them into numpy arrays of dimensions MAP_SIZE x MAP_SIZE
    maps = [np.reshape(i, (MAP_SIZE, MAP_SIZE)) for i in level_map_data]
    for map_num, cur_map in enumerate(maps):
        # save the array as a CSV, with header and footer data attached
        np.savetxt('./Maps/level_{0:0>8}.tmx'.format(map_num), cur_map, delimiter=",", fmt='%s', header=map_header, footer=map_footer, comments='')
    # counting starts at 0, so len is 1 too high
    file_size = len(maps) - 1
    return


def levels_to_file(input_file=my_file):
    paired_data = []
    for map_file in map_dir:
        with open('./Maps/{}'.format(map_file)) as f:
            #  cur_rom_space will be a list of lists, looking like [[4, 1, 6, 9...]...]
            cur_rom_space = [(int(i)) for i in ','.join(f.read().split('\n')[6:-4]).split(',') if i != '-1' and i != '']

            # re pair up the nums, so its [[41, 69...]...]
            paired_data.append(list(zip(cur_rom_space[::2], cur_rom_space[1::2])))

    # de-nest the lists, and convert the pairs back into bytes
    output_data = [b''.join([hex_to_byte(val) for val in rom_item]) for rom_item in paired_data]

    # if there is not a backup file, create one.
    if not os.path.isfile('{}.bak'.format(input_file)):
        with open(input_file, 'br+') as src_file:
            with open('{}.bak'.format(input_file), 'wb') as backup:
                backup.write(src_file.read())

    # write over the old data with the new
    with open(input_file, 'br+') as fw:
        for line in output_data:
            fw.write(line)
    return


def gen_map_file(map_info, map_arr):
    header = '''<?xml version="1.0" encoding="UTF-8"?>
<map version="1.2" tiledversion="1.2.3" orientation="orthogonal" renderorder="right-down" width="{0}" height="{1}" 
tilewidth="64" tileheight="64" infinite="0" nextlayerid="2" nextobjectid="1">
 <tileset firstgid="1" source="./tiles.tsx"/>
 <layer id="1" name="Platforms" width="{0}" height="{1}">
  <data encoding="csv">
{2}</data>
 </layer>
</map>'''.format(map_info[0], map_info[1], map_arr)
    return header


def write_to_map(level_data, level):
    np.savetxt("./Maps/map_data.csv", level_data, delimiter=",", fmt='%s')
    with open('./Maps/map_data.csv') as map_data_file:
        platforms = gen_map_file((MAP_SIZE, MAP_SIZE), map_data_file.read())
        with open('./Maps/level_{cur_l:0>8}.tmx'.format(cur_l=level), 'w') as open_level:
            print(platforms, file=open_level)


class NesGame(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
        file_path = os.path.dirname(os.path.abspath(__file__))
        os.chdir(file_path)

        self.cur_block = self.cur_block_y, self.cur_block_x = (0, 0)
        self.wall_list = None
        self.player_list = None
        self.player_sprite = None

        self.physics_engine = None
        self.view_left = 0
        self.view_bottom = 0

        self.my_map = None

        self.level = 0
        self.max_level = file_size

        self.end_of_map = MAP_SIZE * TILE_HEIGHT

        self.last_time = None
        self.frame_count = 0
        self.fps_message = None

        self.show_bytes = False

    def setup(self):
        self.player_list = arcade.SpriteList()
        self.player_sprite = arcade.Sprite("images/character.png", 0.5)

        self.player_sprite.center_x = TILE_WIDTH // 2
        self.player_sprite.center_y = TILE_HEIGHT // 2
        self.player_list.append(self.player_sprite)

        self.load_level()

    def load_level(self):
        self.my_map = arcade.read_tiled_map('./Maps/level_{cur_l:0>8}.tmx'.format(cur_l=self.level), 1)
        self.wall_list = arcade.generate_sprites(self.my_map, 'Platforms', 1)
        self.physics_engine = arcade.PhysicsEnginePlatformer(self.player_sprite,
                                                             self.wall_list,
                                                             gravity_constant=GRAVITY)
        self.player_sprite.bottom = TILE_HEIGHT * MAP_SIZE

    def on_draw(self):

        self.frame_count += 1
        arcade.start_render()

        # Draw all the sprites.
        self.player_list.draw()
        self.wall_list.draw()

        if self.last_time and self.frame_count % 60 == 0:
            fps = 1.0 / (time.time() - self.last_time) * 60
            self.fps_message = 'FPS: {:5.0f}'.format(fps)

        if self.fps_message:
            arcade.draw_text(self.fps_message, self.view_left + 10, self.view_bottom + 40, arcade.color.WHITE, 14)

        if self.frame_count % 60 == 0:
            self.last_time = time.time()
        if self.show_bytes:
            try:
                hex_block = self.my_map.layers_int_data['Platforms'][self.cur_block_y][abs(round(self.cur_block_x/2)*2 - 2):round(self.cur_block_x/2)*2+10]
            except IndexError:
                hex_block = (0, 0)
            v_l = self.view_left + TILE_WIDTH
            arcade.draw_text(str(b''.join([hex_to_byte(tuple(i)) for i in list(zip(hex_block[::2], hex_block[1::2]))]))[2:-1], v_l, self.view_bottom + SCREEN_HEIGHT - TILE_HEIGHT, arcade.color.WHITE, 24)

    def on_key_press(self, key, modifiers):
        if key == arcade.key.UP:
            if self.physics_engine.can_jump() or True:
                self.player_sprite.change_y = JUMP_SPEED
        if key == arcade.key.DOWN:
            if self.physics_engine.can_jump():
                self.player_sprite.bottom -= 128
            else:
                self.player_sprite.change_y -= 32
        if key == arcade.key.LEFT:
            self.player_sprite.change_x = -MOVEMENT_SPEED
        if key == arcade.key.RIGHT:
            self.player_sprite.change_x = MOVEMENT_SPEED
        if key == arcade.key.S and self.my_map.layers_int_data['Platforms'][self.cur_block_y][self.cur_block_x] > 0:
            self.my_map.layers_int_data['Platforms'][self.cur_block_y][self.cur_block_x] -= 1
            write_to_map(self.my_map.layers_int_data['Platforms'], level=self.level)
            self.load_level()
        if key == arcade.key.W and self.my_map.layers_int_data['Platforms'][self.cur_block_y][self.cur_block_x] < 15:
            self.my_map.layers_int_data['Platforms'][self.cur_block_y][self.cur_block_x] += 1
            write_to_map(self.my_map.layers_int_data['Platforms'], level=self.level)
            self.load_level()
        if key == arcade.key.ESCAPE:
            arcade.close_window()

    def on_key_release(self, key, modifiers):
        if key == arcade.key.LEFT or key == arcade.key.RIGHT:
            self.player_sprite.change_x = 0

    def update(self, delta_time):
        self.cur_block = self.cur_block_y, self.cur_block_x = MAP_SIZE - int((self.player_sprite.bottom // TILE_HEIGHT)), int(self.player_sprite.left // TILE_WIDTH) + 1

        def up_level():
            if self.level < self.max_level:
                self.level += 1
                self.load_level()
            else:
                self.level = 0
                self.load_level()
            self.player_sprite.bottom = TILE_HEIGHT * MAP_SIZE
            self.player_sprite.left = 0

        def down_level():
            if self.level > 0:
                self.level -= 1
                self.load_level()
            else:
                self.level = file_size
                self.load_level()
            self.player_sprite.bottom = TILE_HEIGHT * MAP_SIZE
            self.player_sprite.left = TILE_WIDTH * MAP_SIZE - 1
        if self.player_sprite.right >= self.end_of_map + TILE_WIDTH * 2:
            up_level()
        if self.player_sprite.left <= -(TILE_WIDTH * 2):
            down_level()
        self.physics_engine.update()

        changed = False
        left_boundary = self.view_left + VIEWPORT_LEFT_MARGIN
        if self.player_sprite.left < left_boundary:
            self.view_left -= left_boundary - self.player_sprite.left
            changed = True

        # Scroll right
        right_boundary = self.view_left + SCREEN_WIDTH - VIEWPORT_RIGHT_MARGIN
        if self.player_sprite.right > right_boundary:
            self.view_left += self.player_sprite.right - right_boundary
            changed = True

        # Scroll up
        top_boundary = self.view_bottom + SCREEN_HEIGHT - VIEWPORT_MARGIN_TOP
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
                                SCREEN_WIDTH + self.view_left,
                                self.view_bottom,
                                SCREEN_HEIGHT + self.view_bottom)


def main():
    window = NesGame()
    window.setup()
    arcade.run()


if __name__ == '__main__':
    start_time = time.time()
    file_to_levels(my_file)
    print(time.time()-start_time)
    main()
    levels_to_file(my_file)
