import numpy as np
import arcade
import os
import timeit
from functools import lru_cache

my_file = 'Alice'

map_dir = sorted([mf for mf in [mf for mf in os.listdir('./Maps') if os.path.isfile(os.path.join('./Maps', mf))] if
                  mf.endswith('.tmx')])

for file in map_dir:
    os.remove('./Maps/{}'.format(file))

MAP_SIZE = 64
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
    with open(input_file, 'rb') as input_data:
        # convert int (255) -> hex (0xff) -> two hex values (0x0f, 0x0f) -> two int values -> (15, 15) -> add 1 to each
        mario_rom = [item for sublist in [byte_to_hex(i) for i in input_data.read()] for item in sublist]

    # split the data
    level_map_data = [mario_rom[x:x+MAP_SIZE**2] for x in range(0, len(mario_rom), MAP_SIZE**2)]
    # pad the last map with empty space, so all maps are the same size
    level_map_data[-1] += [-1] * (MAP_SIZE**2 - len(level_map_data[-1]))
    maps = [np.reshape(i, (MAP_SIZE, MAP_SIZE)) for i in level_map_data]
    for map_num, cur_map in enumerate(maps):
        np.savetxt("./Maps/map_data.csv", cur_map, delimiter=",", fmt='%s')
        with open('./Maps/map_data.csv') as map_data:
            platforms = gen_map_file(cur_map.shape, map_data.read())
        with open('./Maps/level_{0:0>8}.tmx'.format(map_num), 'w') as map_level:
            print(platforms, file=map_level)

    return


def levels_to_file(input_file=my_file):
    paired_data = []
    for map_file in map_dir:
        with open('./Maps/{}'.format(map_file)) as f:
            #  cur_rom_space will be a list of lists
            cur_rom_space = [(int(i)) for i in ','.join(f.read().split('\n')[6:-4]).split(',') if i != '-1' and i != '']
            paired_data.append(list(zip(cur_rom_space[::2], cur_rom_space[1::2])))
    output_data = [b''.join([hex_to_byte(val) for val in rom_item]) for rom_item in paired_data]
    if not os.path.isfile('{}.bak'.format(input_file)):
        with open(input_file, 'br+') as src_file:
            with open('{}.bak'.format(input_file), 'wb') as backup:
                backup.write(src_file.read())
            src_file.write(b'')
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


def gen_item_menu(loi):
    menu = np.zeros((MAP_SIZE, MAP_SIZE), dtype=int)
    for item_pos, list_item in enumerate(loi):
        hex_list_item = [item for sublist in [byte_to_hex(i) for i in list_item] for item in sublist]
        item_len = len(hex_list_item)
        menu[item_pos*2, 0:item_len] = hex_list_item
    return gen_map_file((MAP_SIZE, MAP_SIZE), menu)


if __name__ == '__main__':
    print(gen_item_menu([b'Play()', b'main()']))

