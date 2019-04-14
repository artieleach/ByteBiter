import numpy as np
import arcade
import os
import array

my_file = 'smb3.nes'

map_dir = sorted([mf for mf in [mf for mf in os.listdir('./Maps') if os.path.isfile(os.path.join('./Maps', mf))] if
                  mf.endswith('.tmx')])

MAP_SIZE = 64
TILE_SIZE = TILE_WIDTH, TILE_HEIGHT = (64, 64)
SCREEN_SIZE = SCREEN_WIDTH, SCREEN_HEIGHT = (TILE_WIDTH*16, TILE_HEIGHT*9)
SCREEN_TITLE = "Rom Explorer"

VIEWPORT_MARGIN_TOP = TILE_HEIGHT
VIEWPORT_MARGIN_BOTTOM = TILE_HEIGHT
VIEWPORT_RIGHT_MARGIN = TILE_WIDTH * 6
VIEWPORT_LEFT_MARGIN = TILE_WIDTH * 6


MOVEMENT_SPEED = 5
JUMP_SPEED = 25
GRAVITY = 1


def get_data(input_file):
    with open(input_file, 'rb') as input_data:
        # convert int (255) -> hex (0xff) -> two hex values (0x0f, 0x0f) -> two int values -> (15, 15) -> add 1 to each
        mario_rom = []
        for i in input_data.read():
            v = hex(i)[2:].zfill(2)
            mario_rom.append([int(v[0], 16)+1, int(v[1].zfill(1), 16)+1])

    # unzip
    mario_rom = [item for sublist in mario_rom for item in sublist]

    # split the data
    composite_list = [mario_rom[x:x+MAP_SIZE**2] for x in range(0, len(mario_rom), MAP_SIZE**2)]

    # pad the last element with zeros, so all maps are the same size
    composite_list[-1] += [0] * (MAP_SIZE**2 - len(composite_list[-1]))

    return composite_list


def bury_data():
    final_out = []
    for file in map_dir:
        with open('./Maps/{}'.format(file)) as f:
            for cur_rom_sapce in f.read().split('\n')[6:-4]:
                cur_rom_line = list(filter(lambda a: a != -1, [(int(i) - 1) for i in cur_rom_sapce.split(',')]))
                if cur_rom_line:
                    repaired = []
                    for v, w in zip(cur_rom_line[::2], cur_rom_line[1::2]):
                        repaired.append(int(hex(v)[2]+hex(w)[2], 16))
                    final_out.append(array.array('B', repaired).tobytes())
    return final_out


def gen_map_file(map_info, map_data):
    header = '''<?xml version="1.0" encoding="UTF-8"?>
<map version="1.2" tiledversion="1.2.3" orientation="orthogonal" renderorder="right-down" width="{0}" height="{1}" 
tilewidth="64" tileheight="64" infinite="0" nextlayerid="2" nextobjectid="1">
 <tileset firstgid="1" source="./tiles.tsx"/>
 <layer id="1" name="Platforms" width="{0}" height="{1}">
  <data encoding="csv">
{2}</data>
 </layer>
</map>'''.format(map_info[0], map_info[1], map_data)
    return header

# hey artie, you're currenlty working on masking out the 1's (actually 0's) in order to make some blocks transparent
# you have a function which does that, but it's kind of slow, and you probably need to reverse it afterwards too. that's annoying
# anyway goodnight
class NesGame(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
        file_path = os.path.dirname(os.path.abspath(__file__))
        os.chdir(file_path)

        self.cur_block = (0, 0)
        self.wall_list = None
        self.player_list = None
        self.player_sprite = None

        self.physics_engine = None
        self.view_left = 0
        self.view_bottom = 0

        self.my_map = None

        self.level = 0
        self.max_level = len(maps) - 1

        self.end_of_map = MAP_SIZE * TILE_HEIGHT


    def setup(self):
        self.player_list = arcade.SpriteList()
        self.player_sprite = arcade.Sprite("images/character.png", 0.67)

        self.player_sprite.center_x = TILE_WIDTH // 2
        self.player_sprite.center_y = TILE_HEIGHT // 2
        self.player_list.append(self.player_sprite)

        self.load_level(self.level)

    def load_level(self, level):
        self.my_map = arcade.read_tiled_map('./Maps/level_{cur_l:0>8}.tmx'.format(cur_l=self.level), 1)
        map_array = self.my_map.layers_int_data['Platforms']
        self.wall_list = arcade.generate_sprites(self.my_map, 'Platforms', 1)
        self.physics_engine = arcade.PhysicsEnginePlatformer(self.player_sprite,
                                                             self.wall_list,
                                                             gravity_constant=GRAVITY)
        self.player_sprite.bottom = TILE_HEIGHT * MAP_SIZE

    def on_draw(self):
        arcade.start_render()

        # Draw all the sprites.
        self.player_list.draw()
        self.wall_list.draw()

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
        if key == arcade.key.SPACE and self.my_map.layers_int_data['Platforms'][self.cur_block[0]][self.cur_block[1]]-1:
            self.my_map.layers_int_data['Platforms'][self.cur_block[0]][self.cur_block[1]] -= 1
            write_to_map(self.my_map.layers_int_data['Platforms'], level=self.level)
            self.load_level(self.level)
        if key == arcade.key.ESCAPE:
            arcade.close_window()

    def on_key_release(self, key, modifiers):
        if key == arcade.key.LEFT or key == arcade.key.RIGHT:
            self.player_sprite.change_x = 0

    def update(self, delta_time):
        self.cur_block = int((self.player_sprite.bottom // 64)) - 64, int(self.player_sprite.left // 64) + 1

        def up_level():
            if self.level < self.max_level:
                self.level += 1
                self.load_level(self.level)
                self.player_sprite.bottom = TILE_HEIGHT * MAP_SIZE
                self.player_sprite.left = 0
            else:
                self.level = 0
                self.load_level(self.level)
                self.player_sprite.bottom = TILE_HEIGHT * MAP_SIZE
                self.player_sprite.left = 0

        def down_level():
            if self.level > 0:
                self.level -= 1
                self.load_level(self.level)
                self.player_sprite.bottom = TILE_HEIGHT * MAP_SIZE
                self.player_sprite.left = TILE_WIDTH * MAP_SIZE - 1
            else:
                self.level = len(maps) - 1
                self.load_level(self.level)
                self.player_sprite.bottom = TILE_HEIGHT * MAP_SIZE
                self.player_sprite.left = TILE_WIDTH * MAP_SIZE - 1
        if self.player_sprite.right >= self.end_of_map + TILE_WIDTH * 2:
            up_level()
        if self.player_sprite.left <= -(TILE_WIDTH * 2):
            down_level()
        self.physics_engine.update()

        changed = False
        left_bndry = self.view_left + VIEWPORT_LEFT_MARGIN
        if self.player_sprite.left < left_bndry:
            self.view_left -= left_bndry - self.player_sprite.left
            changed = True

        # Scroll right
        right_bndry = self.view_left + SCREEN_WIDTH - VIEWPORT_RIGHT_MARGIN
        if self.player_sprite.right > right_bndry:
            self.view_left += self.player_sprite.right - right_bndry
            changed = True

        # Scroll up
        top_bndry = self.view_bottom + SCREEN_HEIGHT - VIEWPORT_MARGIN_TOP
        if self.player_sprite.top > top_bndry:
            self.view_bottom += self.player_sprite.top - top_bndry
            changed = True

        # Scroll down
        bottom_bndry = self.view_bottom + VIEWPORT_MARGIN_BOTTOM
        if self.player_sprite.bottom < bottom_bndry:
            self.view_bottom -= bottom_bndry - self.player_sprite.bottom
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


def write_to_map(level_data, level):
    np.savetxt("./Maps/map_data.csv", np.asarray(level_data), delimiter=",", fmt='%s')
    with open('./Maps/map_data.csv') as map_data:
        platforms = gen_map_file((MAP_SIZE, MAP_SIZE), map_data.read())
        with open('./Maps/level_{cur_l:0>8}.tmx'.format(cur_l=level), 'w') as open_level:
            print(platforms, file=open_level)


def mask_out_zeros(level_to_mask):
    g = np.zeros(shape=level_to_mask, dtype=int)
    for (row, col), value in np.ndenumerate(level_to_mask):
        g[row, col] = value * (value > 4)
    return g


if __name__ == '__main__':
    maps = [np.reshape(i, (MAP_SIZE, MAP_SIZE)) for i in get_data(input_file=my_file)]
    for map_num, cur_map in enumerate(maps):
        np.savetxt("./Maps/map_data.csv", cur_map, delimiter=",", fmt='%s')
        with open('./Maps/map_data.csv') as map_data:
            platforms = gen_map_file(cur_map.shape, map_data.read())
            with open('./Maps/level_{0:0>8}.tmx'.format(map_num), 'w') as map_level:
                print(platforms, file=map_level)

    main()

    with open(my_file, 'br+') as src_file:
        with open('{}.bak'.format(my_file), 'wb') as backup:
            backup.write(src_file.read())
            backup.close()
        src_file.write(b'')
    with open(my_file, 'br+') as fw:
        for line in bury_data():
            fw.write(line)

