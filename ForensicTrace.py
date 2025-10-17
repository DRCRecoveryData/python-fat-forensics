import struct
import os

# --- CORE CONSTANTS ---
FILE_NAME = '2gb.dd' # Ensure this file is present and is FAT16
SECTOR_SIZE = 512
MBR_SIZE = 512

# MBR Offsets
PARTITION_TABLE_OFFSET = 0x1BE
PARTITION_ENTRY_SIZE = 16
MBR_PARTITION_FORMAT = '<B3sB3sII'

# --- TRACE STATE VARIABLES (Global variables updated during the trace) ---
PARTITION_START_LBA = 0
RESERVED_SECTORS = 0
NUM_FATS = 0
FAT_SIZE_SECTORS = 0
ROOT_DIR_SECTORS = 0
SECTORS_PER_CLUSTER = 0 
ROOT_DIR_ENTRY_COUNT = 0

FAT1_START_LBA = 0
ROOT_DIR_START_LBA = 0
DATA_REGION_START_LBA = 0

# --- CORE FILE READING FUNCTION ---

def read_sector(file_path: str, lba: int, count: int = 1) -> bytes or None:
    """Reads one or more sectors starting at the given LBA."""
    try:
        offset_bytes = lba * SECTOR_SIZE
        with open(file_path, 'rb') as f:
            f.seek(offset_bytes)
            data = f.read(SECTOR_SIZE * count)
            if len(data) != SECTOR_SIZE * count:
                return None
            return data
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'")
        return None
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return None

# --- STAGE 1: MBR PARSING (To get Partition Start LBA) ---

def parse_mbr():
    global PARTITION_START_LBA
    mbr_data = read_sector(FILE_NAME, 0)
    if not mbr_data: return False

    if mbr_data[0x1FE:0x200] != b'\x55\xAA':
        print("Error: MBR Signature 55 AA not found.")
        return False

    entry_data = mbr_data[PARTITION_TABLE_OFFSET : PARTITION_TABLE_OFFSET + PARTITION_ENTRY_SIZE]

    try:
        (flag, chs_start_raw, type_id, chs_end_raw, start_lba, size_sectors) = \
            struct.unpack(MBR_PARTITION_FORMAT, entry_data)

        PARTITION_START_LBA = start_lba
        print(f"MBR SUCCESS: Partition Type 0x{type_id:02X} (FAT16) found at LBA {start_lba}")
        return True
    except struct.error as e:
        print(f"Error unpacking MBR entry: {e}")
        return False

# --- STAGE 2: VBR PARSING (To get FAT and Directory locations) ---

def parse_vbr():
    global RESERVED_SECTORS, NUM_FATS, FAT_SIZE_SECTORS, ROOT_DIR_SECTORS, SECTORS_PER_CLUSTER
    global FAT1_START_LBA, ROOT_DIR_START_LBA, DATA_REGION_START_LBA, ROOT_DIR_ENTRY_COUNT

    vbr_data = read_sector(FILE_NAME, PARTITION_START_LBA)
    if not vbr_data: return False

    # Extract FAT16 specific fields (Little-Endian)
    # 0x0D: Sectors Per Cluster (B: 1 byte)
    SECTORS_PER_CLUSTER = struct.unpack('<B', vbr_data[0x0D:0x0E])[0]
    # 0x0E: Reserved Sector Count (H: 2 bytes)
    RESERVED_SECTORS = struct.unpack('<H', vbr_data[0x0E:0x10])[0]
    # 0x10: Number of FATs (B: 1 byte)
    NUM_FATS = struct.unpack('<B', vbr_data[0x10:0x11])[0]
    # 0x11: Root Directory Entries (H: 2 bytes)
    ROOT_DIR_ENTRY_COUNT = struct.unpack('<H', vbr_data[0x11:0x13])[0]
    # 0x16: FAT Size in Sectors (H: 2 bytes)
    FAT_SIZE_SECTORS = struct.unpack('<H', vbr_data[0x16:0x18])[0]

    # Calculate Root Directory Size in Sectors
    ROOT_DIR_SECTORS = (ROOT_DIR_ENTRY_COUNT * 32 + SECTOR_SIZE - 1) // SECTOR_SIZE
    
    # Calculate the key LBA locations
    FAT1_START_LBA = PARTITION_START_LBA + RESERVED_SECTORS
    ROOT_DIR_START_LBA = FAT1_START_LBA + (NUM_FATS * FAT_SIZE_SECTORS)
    DATA_REGION_START_LBA = ROOT_DIR_START_LBA + ROOT_DIR_SECTORS
    
    print("VBR SUCCESS: File system layout parameters calculated.")
    return True

# --- STAGE 3: FAT TRACE LOGIC (To get the starting cluster of a file/dir) ---

def trace_fat_chain(start_cluster: int, fat_data: bytes):
    """Traces the cluster chain for a given starting cluster in FAT16."""
    
    current_cluster = start_cluster
    chain = [start_cluster]

    while True:
        # FAT16 entry is at offset (Cluster * 2) from the start of the FAT table
        offset = current_cluster * 2
        
        if offset + 2 > len(fat_data):
            chain.append("...")
            break

        entry_bytes = fat_data[offset : offset + 2]
        next_cluster = struct.unpack('<H', entry_bytes)[0]
        
        if 0xFFF8 <= next_cluster <= 0xFFFF:
            chain.append(f"EOC (0x{next_cluster:04X})")
            break
        elif next_cluster == 0x0000:
            chain.append("FREE")
            break
        elif next_cluster == 0xFFF7:
            chain.append("BAD")
            break
        else:
            current_cluster = next_cluster
            chain.append(current_cluster)
            
            if len(chain) > 8: 
                chain.append("...")
                break
    
    return chain

# --- STAGE 4: DIRECTORY PARSING & TRACE EXECUTION ---

def parse_directory_and_trace(dir_lba: int):
    """Reads a directory, parses entries, and traces the cluster chain for each."""
    
    dir_data = read_sector(FILE_NAME, dir_lba, count=ROOT_DIR_SECTORS)
    if not dir_data: return

    fat_data = read_sector(FILE_NAME, FAT1_START_LBA, count=FAT_SIZE_SECTORS)
    if not fat_data: 
        if FAT_SIZE_SECTORS == 0:
            print("FAT ERROR: FAT size is 0. Cannot trace clusters.")
        return

    print("\n" + "="*95)
    print(f"      STAGE 4: DIRECTORY PARSING & CLUSTER TRACING (LBA {dir_lba})")
    print("="*95)
    print(f"{'Idx':<4} | {'Name (8.3)':<12} | {'Type':<4} | {'Start Cluster':<15} | {'Cluster Chain'}")
    print("-" * 95)
    
    for i in range(len(dir_data) // 32):
        offset = i * 32
        entry_data = dir_data[offset:offset + 32]
        
        first_byte = entry_data[0x00]
        if first_byte == 0x00: break 
        
        attributes = entry_data[0x0B]
        if attributes == 0x0F: continue 
        
        name = entry_data[0x00:0x0B].rstrip(b' ').decode('ascii', errors='replace').replace('\xE5', '?')
        is_dir = (attributes & 0x10) != 0

        start_cluster = struct.unpack('<H', entry_data[0x1A:0x1C])[0]
        
        type_str = "DIR" if is_dir else "FILE"
        cluster_display = f"Cluster {start_cluster}"

        chain_str = ""
        if start_cluster >= 2:
            chain = trace_fat_chain(start_cluster, fat_data)
            chain_str = ' -> '.join(map(str, chain))
        
        print(f"{i:<4} | {name:<12} | {type_str:<4} | {cluster_display:<15} | {chain_str}")

    print("="*95)


# --- MAIN EXECUTION ---

if __name__ == "__main__":
    if parse_mbr():
        if parse_vbr():
            # Start the trace at the Root Directory LBA
            parse_directory_and_trace(ROOT_DIR_START_LBA)