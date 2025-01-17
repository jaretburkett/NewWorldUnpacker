import gf
import os
import binascii
import re
import glob
from ctypes import cdll, c_char_p, create_string_buffer
import argparse

parser = argparse.ArgumentParser(description='New World Unpacker', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
add_arg = parser.add_argument

add_arg('--assets', type=str, help='Path to assets folder')
add_arg('--output', type=str, help='Path to output folder')

args = parser.parse_args()

direc = args.assets
out_direc = args.output

print(f'Asset dir: {direc}')
print(f'Out dir: {out_direc}')


class OodleDecompressor:
    """
    Oodle decompression implementation.
    Requires Windows and the external Oodle library.
    """

    def __init__(self, library_path: str) -> None:
        """
        Initialize instance and try to load the library.
        """
        if not os.path.exists(os.getcwd() + library_path):
            print(f'Looking in {os.getcwd() + library_path}')
            raise Exception("Could not open Oodle DLL, make sure it is configured correctly.")

        try:
            self.handle = cdll.LoadLibrary(os.getcwd() + library_path)
        except OSError as e:
            raise Exception(
                "Could not load Oodle DLL, requires Windows and 64bit python to run."
            ) from e

    def decompress(self, payload: bytes, output_size) -> bytes:
        """
        Decompress the payload using the given size.
        """
        output = create_string_buffer(output_size)
        try:
            self.handle.OodleLZ_Decompress(
                c_char_p(payload), len(payload), output, output_size,
                0, 0, 0, None, None, None, None, None, None, 3)
        except OSError:
            return False
        return output.raw


class EntryA:
    def __init__(self):
        self.pk = ''
        self.path_length = 0
        self.entry_length = 0
        self.data_offset = 0
        self.data = b''
        self.out_data = b''
        self.path = ''
        self.length_to_next_pk = 0
        self.data_length_pre = 0
        self.data_length_post = 0


class EntryB:
    def __init__(self):
        self.pk = ''
        self.path_length = 0
        self.bitflags = 0
        # self.data_length_pre = 0
        # self.data_length_post = 0
        self.path = ''
        self.entrya_offset = 0



skipped = []
def unpack():
    global skipped
    file_list = glob.glob(f'{direc}**/*.pak', recursive=True)
    # paks = [x for x in os.listdir(direc) if 'level.pak' in x]
    # file_list = [x for x in file_list if 'frontendv2' in x]
    print(file_list)
    for pak in file_list:
        print(f'Unpacking: {pak}')
        # get the folder path of the file for deeper files
        folder_path = "/".join(pak.replace(direc[:-1], '').split('\\')[:-1])
        # print('direc: ' + direc)
        # print('Folder Path: ' + folder_path)
        # exit()
        # fbin = gf.get_hex_data(direc + pak)
        fbin = gf.get_hex_data(pak)
        entriesB = []

        ret = [m.start() for m in re.finditer(b'\x50\x4B\x01\x02', fbin)]
        if not ret:
            raise Exception('no ret')
        for offset in ret:
            entry = EntryB()
            entry.pk = fbin[offset:offset+4]
            entry.bitflags = gf.get_int16(fbin, offset+4)
            entry.path_length = gf.get_int16(fbin, offset+0x1C)
            if entry.path_length == 0:
                continue  # Sometimes ends with a 0 length path for some reason
            entry.path = fbin[offset+0x2E:offset+(0x2E+entry.path_length)].decode('ansi')
            if entry.bitflags != 0x8 and entry.bitflags != 0x14:
                # print(f' - Skipping file {entry.path} as probably wrong, like in middle of chunk. Skipped {skipped}')
                skipped.append(entry.path)
                continue
            # entry.data_length_pre = gf.get_int32(fhex, offset + 0x14 * 2)
            # entry.data_length_post = gf.get_int32(fhex, offset + 0x18 * 2)
            entry.entrya_offset = gf.get_int32(fbin, offset + 0x2A)
            entriesB.append(entry)

        for entryb in entriesB:
            # print(' - ' + str(entryb.__dict__))
            try:
                ot = entryb.entrya_offset
                entry = EntryA()
                entry.pk = fbin[ot:ot+4]
                entry.path_length = gf.get_int32(fbin, ot+0x1A)
                entry.path = fbin[ot+0x1E:ot+(0x1E+entry.path_length)].decode('ansi')
                if entryb.path != entry.path:
                    raise Exception('ERROR PATHS DIFFER')
                else:
                    print(' - Path match', entry.path)
                entry.data_offset = ot + (0x1E + entry.path_length)
                entry.data_length_pre = gf.get_int32(fbin, ot + 0x12)

                entry.data_length_post = gf.get_int32(fbin, ot + 0x16)
                entry.data = fbin[entry.data_offset:entry.data_offset+entry.data_length_pre]
                out_f = out_direc
                if(len(folder_path) > 2):
                    out_f = f'{out_f}{folder_path}'
                # Write
                path = f'{out_f}/{"/".join(entry.path.split("/")[:-1])}'
                gf.mkdir(path)
                with open(f'{out_f}/{entry.path}', 'wb') as f:
                    decompressor = OodleDecompressor('/oo2core_8_win64.dll')
                    if entryb.bitflags == 0x8:
                        print(' - Compression')
                        entry.out_data = decompressor.decompress(entry.data, entry.data_length_post)
                    elif entryb.bitflags == 0x14:   # 0xA is entryA
                        print(' - No compression')
                        # No compression
                        entry.out_data = entry.data
                    else:
                        raise Exception(f'New bitflag {entry.bitflags}')
                    if not entry.out_data:
                        raise Exception('DECOMP FAILED %%%%%%%%%%')
                    f.write(entry.out_data)

            except Exception as e:
                print(' - ' + str(e))



if __name__ == '__main__':
    # direc = 'New World Alpha/assets/'
    # out_direc = 'unpacked_out/'
    gf.mkdir(out_direc)
    unpack()
    print('Unpack done! Press any key to quit...')
    print(f'Total skipped: {[x[:36] for x in skipped]}')