import struct

# --- Constants from Previous Analysis ---

FILE_NAME = '2gb.dd' 
PARTITION_START_LBA = 39 
BOOT_SECTOR_SIZE = 512
FAT1_START_LBA = 47 # Calculated from LBA 39 + 8 Reserved Sectors

# --- Constants for FAT16 Analysis ---

FAT16_ENTRY_SIZE = 2 # 2 bytes per cluster entry
FAT16_SIGNATURE = b'\xF8\xFF' # Expected first two bytes of FAT 1

# Max entries to read for a sample: 
# (512 Bytes per Sector) / (2 Bytes per Entry) = 256 entries
SAMPLE_ENTRIES_COUNT = 32 # We'll check the first 32 clusters after the reserved entries

def read_fat_sector(file_path: str, fat_start_lba: int) -> bytes or None:
    """
    Reads the first sector of the FAT table from the specified file path.
    
    :param file_path: Path to the disk image file.
    :param fat_start_lba: The LBA where FAT 1 begins (e.g., 47).
    :return: The 512 bytes of the FAT sector data.
    """
    try:
        offset_bytes = fat_start_lba * BOOT_SECTOR_SIZE
        print(f"Reading FAT 1 sector at byte offset: {offset_bytes} (LBA {fat_start_lba})")
        
        with open(file_path, 'rb') as f:
            f.seek(offset_bytes)
            fat_data = f.read(BOOT_SECTOR_SIZE)
            
            if len(fat_data) != BOOT_SECTOR_SIZE:
                print(f"Error: File ended prematurely while reading FAT sector.")
                return None
            return fat_data
            
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'")
        return None
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return None

def interpret_fat16_entry(entry_value: int) -> str:
    """
    Interprets the 16-bit value of a FAT16 cluster entry.
    """
    if entry_value == 0x0000:
        return "FREE (0x0000)"
    elif 0xFFF8 <= entry_value <= 0xFFFF:
        return f"END OF FILE/CHAIN (0x{entry_value:04X})"
    elif entry_value == 0xFFF7:
        return "BAD CLUSTER (0xFFF7)"
    else:
        # If it's not a special value, it's the next cluster in the chain.
        return f"NEXT CLUSTER: {entry_value} (0x{entry_value:04X})"

def parse_fat16_sector(fat_data: bytes):
    """
    Parses the first sector of FAT 1 to check the signature and sample cluster entries.
    """
    
    # 1. Check FAT Signature (first two bytes)
    signature = fat_data[0:FAT16_ENTRY_SIZE]
    signature_valid = signature == FAT16_SIGNATURE
    
    # 2. Extract and interpret cluster entries
    cluster_entries = []
    
    # FAT 16 starts the cluster entries at index 0, which corresponds to reserved data.
    # The first two entries (Cluster 0 and Cluster 1) are reserved/special.
    
    for i in range(SAMPLE_ENTRIES_COUNT):
        offset = i * FAT16_ENTRY_SIZE
        entry_bytes = fat_data[offset:offset + FAT16_ENTRY_SIZE]
        
        # Use little-endian ('<H') to unpack the 2-byte (H) integer
        # We need the value to be an integer to compare against the status codes.
        entry_value = struct.unpack('<H', entry_bytes)[0]
        
        # The true cluster indexing starts at 2 for data
        cluster_index = i
        
        cluster_entries.append({
            'index': cluster_index,
            'hex_value': f"0x{entry_value:04X}",
            'status': interpret_fat16_entry(entry_value)
        })
        
    return signature_valid, cluster_entries

# --- Execution Example ---

fat_data = read_fat_sector(FILE_NAME, FAT1_START_LBA)

if fat_data:
    signature_valid, entries = parse_fat16_sector(fat_data)
    
    print("\n" + "="*50)
    print(f"      FAT16 TABLE ANALYSIS (Sector LBA {FAT1_START_LBA})")
    print("="*50)
    print(f"FAT Signature (F8 FF) Valid: {signature_valid}")
    print(f"FAT Signature Bytes: {fat_data[0:2].hex().upper()}")
    print("-" * 50)

    print("Cluster | Hex Value | Status / Next Cluster")
    print("-" * 50)
    
    for entry in entries:
        # Cluster 0 and 1 are reserved/special. Cluster 2 is the first data cluster.
        if entry['index'] < 2:
            print(f" {entry['index']:^6} | {entry['hex_value']:^9} | RESERVED/SPECIAL")
        else:
            print(f" {entry['index']:^6} | {entry['hex_value']:^9} | {entry['status']}")
            
    print("="*50)