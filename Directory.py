import struct

# --- Constants from Previous Analysis ---

FILE_NAME = '2gb.dd' 
BOOT_SECTOR_SIZE = 512
# Root Directory starts at LBA 519 (Calculated: 39 + 8 + (2 * 236) = 519)
ROOT_DIR_START_LBA = 519 

# --- Constants for Directory Entry Parsing ---

DIR_ENTRY_SIZE = 32 # Each directory entry is 32 bytes
SAMPLE_ENTRIES_COUNT = 8 # Read the first 8 entries for a sample

# Byte offsets within the 32-byte directory entry
OFS_NAME = 0x00      # 8 bytes
OFS_EXT = 0x08       # 3 bytes
OFS_ATTRIBUTES = 0x0B # 1 byte
OFS_MSB_CLUSTER = 0x14 # 2 bytes (FAT16: reserved/zero, but included for completeness)
OFS_TIME_MOD = 0x16  # 2 bytes
OFS_DATE_MOD = 0x18  # 2 bytes
OFS_LSB_CLUSTER = 0x1A # 2 bytes (The actual starting cluster for FAT16)
OFS_SIZE = 0x1C      # 4 bytes

# --- Functions ---

def read_directory_sector(file_path: str, dir_start_lba: int) -> bytes or None:
    """Reads the first sector of the directory (Root Directory) from the disk image."""
    try:
        offset_bytes = dir_start_lba * BOOT_SECTOR_SIZE
        print(f"Reading Directory Sector at byte offset: {offset_bytes:,} (LBA {dir_start_lba})")
        
        with open(file_path, 'rb') as f:
            f.seek(offset_bytes)
            dir_data = f.read(BOOT_SECTOR_SIZE)
            
            if len(dir_data) != BOOT_SECTOR_SIZE:
                print(f"Error: File ended prematurely while reading directory sector.")
                return None
            return dir_data
            
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'")
        return None
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return None

def decode_fat_name(name_bytes: bytes, ext_bytes: bytes) -> str:
    """Decodes the 8.3 FAT filename, handling special characters and padding."""
    
    # Remove null bytes and trailing spaces, then decode
    name = name_bytes.rstrip(b' ').decode('ascii', errors='replace')
    ext = ext_bytes.rstrip(b' ').decode('ascii', errors='replace')

    # Handle special first byte status codes
    if name.startswith('\xE5'):
        name = '?' + name[1:] # E5 (0xE5) means deleted
    elif name.startswith('\x05'):
        name = '\x05' + name[1:] # 05 means first character is 0xE5 (Kanji/EUC-JP)

    if ext:
        return f"{name}.{ext}"
    return name

def parse_directory_sector(dir_data: bytes):
    """Parses the 512-byte directory sector and extracts the entries."""
    
    entries = []
    
    for i in range(SAMPLE_ENTRIES_COUNT):
        offset = i * DIR_ENTRY_SIZE
        entry_data = dir_data[offset:offset + DIR_ENTRY_SIZE]
        
        # Check if the entry is unused (first byte is 0x00) or deleted (first byte is 0xE5)
        first_byte = entry_data[OFS_NAME]
        if first_byte == 0x00:
            # Reached end of used entries in this directory listing
            break
        
        # --- Extract Raw Fields ---
        name_bytes = entry_data[OFS_NAME : OFS_NAME + 8]
        ext_bytes = entry_data[OFS_EXT : OFS_EXT + 3]
        
        attributes = entry_data[OFS_ATTRIBUTES]
        
        # FAT16 only uses the LSB cluster field (2 bytes)
        lsb_cluster = struct.unpack('<H', entry_data[OFS_LSB_CLUSTER:OFS_LSB_CLUSTER + 2])[0]
        
        # File Size (4 bytes, little-endian unsigned integer)
        file_size = struct.unpack('<I', entry_data[OFS_SIZE:OFS_SIZE + 4])[0]
        
        # --- Interpret Status and Attributes ---
        
        is_deleted = first_byte == 0xE5
        is_dir = (attributes & 0x10) != 0 # Attribute 0x10 is Directory
        is_lfn = (attributes == 0x0F)    # Attribute 0x0F is Long File Name entry
        
        status = "Used"
        if is_deleted:
            status = "DELETED"
        elif is_lfn:
            status = "LFN (Long Name)"
            
        entries.append({
            'index': i,
            'status': status,
            'name': decode_fat_name(name_bytes, ext_bytes) if not is_lfn else "LFN Fragment",
            'is_dir': is_dir,
            'attributes': f"0x{attributes:02X}",
            'start_cluster': lsb_cluster,
            'file_size': file_size
        })
        
    return entries

# --- Execution Example ---

dir_data = read_directory_sector(FILE_NAME, ROOT_DIR_START_LBA)

if dir_data:
    entries = parse_directory_sector(dir_data)
    
    print("\n" + "="*80)
    print(f"      FAT ROOT DIRECTORY ANALYSIS (Sector LBA {ROOT_DIR_START_LBA})")
    print("="*80)

    print(f"{'Idx':<4} | {'Status':<8} | {'Attributes':<10} | {'Start Cluster':<15} | {'Size (Bytes)':<15} | {'Name (8.3)'}")
    print("-" * 80)
    
    for entry in entries:
        cluster_display = f"Cluster {entry['start_cluster']}"
        if entry['is_dir']:
            cluster_display = f"DIR: {entry['start_cluster']}"
        elif entry['start_cluster'] == 0:
             cluster_display = "ROOT DIR"
            
        print(f"{entry['index']:<4} | {entry['status']:<8} | {entry['attributes']:<10} | {cluster_display:<15} | {entry['file_size']:,<15} | {entry['name']}")
            
    print("="*80)