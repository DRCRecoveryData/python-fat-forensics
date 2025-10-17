import struct
import os

# --- MBR Constants and Definitions ---
MBR_SIZE = 512
PARTITION_TABLE_OFFSET = 0x1BE  # 446 in decimal
PARTITION_ENTRY_SIZE = 16
SIGNATURE_OFFSET = 0x1FE        # 510 in decimal
SIGNATURE = b'\x55\xAA'

# Format string for a single 16-byte MBR Partition Entry:
# < : little-endian
# B  : 1 byte (Flag)
# 3s : 3-byte string (Reserved CHS Start)
# B  : 1 byte (Type ID)
# 3s : 3-byte string (Reserved CHS End)
# I  : 4 bytes (LBA Start Address)
# I  : 4 bytes (Sector Count)
PARTITION_ENTRY_FORMAT = '<B3sB3sII'

PARTITION_TYPES = {
    0x04: 'FAT16 (less than 32MB)',
    0x06: 'FAT16',
    0x0E: 'FAT16 LBA',
    0x0B: 'FAT32',
    0x0C: 'FAT32 LBA',
    0x07: 'NTFS / exFAT / HPFS',
    0x05: 'Extended DOS Partition',
    0x0F: 'Extended LBA Partition'
}

# --- Core Functions ---

def read_mbr_from_file(file_path: str) -> bytes or None:
    """
    Reads the first 512 bytes (the MBR) from the specified file path.
    """
    try:
        print(f"Attempting to read MBR from: {file_path}")
        with open(file_path, 'rb') as f:
            mbr_data = f.read(MBR_SIZE)
            if len(mbr_data) != MBR_SIZE:
                print(f"Error: File is too small (only {len(mbr_data)} bytes read).")
                return None
            return mbr_data
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'")
        return None
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return None

def parse_mbr(mbr_data: bytes):
    """
    Parses the 512 bytes of MBR data and extracts partition information.
    """
    if len(mbr_data) != MBR_SIZE:
        raise ValueError(f"MBR data must be exactly {MBR_SIZE} bytes.")

    result = {
        'signature_valid': False,
        'partitions': []
    }

    # 1. Check the MBR signature (55 AA)
    signature = mbr_data[SIGNATURE_OFFSET:SIGNATURE_OFFSET + 2]
    if signature == SIGNATURE:
        result['signature_valid'] = True
    else:
        print(f"Warning: MBR signature is INVALID ({signature.hex().upper()} instead of 55AA).")

    # 2. Extract and parse the four partition entries
    partition_table = mbr_data[PARTITION_TABLE_OFFSET:SIGNATURE_OFFSET]
    
    for i in range(4):
        offset = i * PARTITION_ENTRY_SIZE
        entry_data = partition_table[offset:offset + PARTITION_ENTRY_SIZE]

        # Check if the entry is all zeros (empty/unused partition slot)
        if entry_data == b'\x00' * PARTITION_ENTRY_SIZE:
            continue
            
        # Unpack the 16-byte structure
        (flag, chs_start_raw, type_id, chs_end_raw, start_lba, size_sectors) = \
            struct.unpack(PARTITION_ENTRY_FORMAT, entry_data)

        partition = {
            'index': i + 1,
            'bootable': flag == 0x80,
            'type_id': f"0x{type_id:02X}",
            'type_description': PARTITION_TYPES.get(type_id, 'Unknown'),
            'start_lba': start_lba,
            'size_sectors': size_sectors,
            'size_bytes': size_sectors * 512,
        }
        result['partitions'].append(partition)
        
    return result

# --- Execution ---

FILE_NAME = '2gb.dd'

mbr_data = read_mbr_from_file(FILE_NAME)

if mbr_data:
    try:
        parsed_result = parse_mbr(mbr_data)
        
        print("\n" + "="*40)
        print("         MBR PARSING RESULTS")
        print("="*40)
        print(f"MBR Signature (55 AA) Valid: {parsed_result['signature_valid']}")
        print(f"Total Partitions Found: {len(parsed_result['partitions'])}")
        print("="*40)

        for p in parsed_result['partitions']:
            print(f"Partition {p['index']} (LBA Start: {p['start_lba']}):")
            print(f"  > Bootable: {'Yes (0x80)' if p['bootable'] else 'No (0x00)'}")
            print(f"  > Type: {p['type_description']} ({p['type_id']})")
            print(f"  > Size: {p['size_sectors']:,} sectors")
            print(f"  > Size: {p['size_bytes'] / (1024*1024):,.2f} MB ({p['size_bytes']:,} bytes)")
            print("-" * 40)

    except ValueError as e:
        print(f"Parsing error: {e}")