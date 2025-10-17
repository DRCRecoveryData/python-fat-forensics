import struct

# --- Constants for FAT32 Analysis (Assumed values for a large disk) ---

FILE_NAME = '2gb.dd' # Placeholder for a FAT32 image
BOOT_SECTOR_SIZE = 512

# Common FAT32 LBA starting points (Often starts later than FAT16)
# If this was a real trace, these LBA values would come from the MBR and VBR parsing.
PARTITION_START_LBA = 63  # Example LBA for a FAT32 partition start
RESERVED_SECTORS = 32     # Example Reserved Sector Count from VBR
FAT1_START_LBA = PARTITION_START_LBA + RESERVED_SECTORS # 63 + 32 = 95 (Example)

# --- FAT32 Specific Constants ---

FAT32_ENTRY_SIZE = 4 # 4 bytes (32 bits) per cluster entry
FAT32_SIGNATURE = b'\xF8\xFF\xFF\x0F' # First 4 bytes (Entry 0) of FAT 1 (MSB of 4th byte is reserved/masked)

# Max entries to read for a sample: 
# (512 Bytes per Sector) / (4 Bytes per Entry) = 128 entries
SAMPLE_ENTRIES_COUNT = 16 # We'll check the first 16 clusters for a sample

def read_fat_sector(file_path: str, fat_start_lba: int) -> bytes or None:
    """
    Reads the first sector of the FAT table from the specified file path.
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
        print(f"Error: File not found at '{file_path}'. Please replace with a valid FAT32 image.")
        return None
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return None

def interpret_fat32_entry(entry_value: int) -> str:
    """
    Interprets the 32-bit value of a FAT32 cluster entry.
    Note: The highest 4 bits (0xF0000000) are reserved and masked out for comparison.
    """
    # Mask out the highest 4 bits (0xF0000000) which are reserved/always zero for next cluster number.
    masked_value = entry_value & 0x0FFFFFFF 

    if masked_value == 0x00000000:
        return "FREE (0x00000000)"
    elif 0x0FFFFFF8 <= masked_value <= 0x0FFFFFFF:
        # End of File/Chain markers start from FFF FFF8 up to FFF FFFF
        return f"END OF FILE/CHAIN (0x{entry_value:08X})"
    elif masked_value == 0x0FFFFF7:
        return "BAD CLUSTER (0x0FFFFF7)"
    else:
        # If it's not a special value, it's the next cluster in the chain.
        return f"NEXT CLUSTER: {masked_value} (0x{entry_value:08X})"

def parse_fat32_sector(fat_data: bytes):
    """
    Parses the first sector of FAT 1 to check the signature and sample cluster entries.
    """
    
    # 1. Check FAT Signature (first four bytes)
    # FAT32 has a complex signature check. We check the first 4 bytes of entry 0.
    signature = fat_data[0:FAT32_ENTRY_SIZE]
    signature_valid = signature[1:4] == b'\xFF\xFF\x0F' # Check the last 3 bytes (FF FF 0F)
    
    # 2. Extract and interpret cluster entries
    cluster_entries = []
    
    for i in range(SAMPLE_ENTRIES_COUNT):
        offset = i * FAT32_ENTRY_SIZE
        entry_bytes = fat_data[offset:offset + FAT32_ENTRY_SIZE]
        
        # Use little-endian ('<I') to unpack the 4-byte (I) integer
        entry_value = struct.unpack('<I', entry_bytes)[0]
        
        cluster_entries.append({
            'index': i,
            'hex_value': f"0x{entry_value:08X}",
            'status': interpret_fat32_entry(entry_value)
        })
        
    return signature_valid, cluster_entries

# --- Execution Example ---

fat_data = read_fat_sector(FILE_NAME, FAT1_START_LBA)

if fat_data:
    signature_valid, entries = parse_fat32_sector(fat_data)
    
    print("\n" + "="*70)
    print(f"             FAT32 TABLE ANALYSIS (Sector LBA {FAT1_START_LBA} - ASSUMED)")
    print("="*70)
    # The first byte (Media Descriptor) F8 can vary, but the others are standard
    print(f"FAT Signature (F8 FFFFFF 0F) Check: {signature_valid}")
    print(f"FAT Signature Bytes: {fat_data[0:4].hex().upper()}")
    print("-" * 70)

    print("Cluster | Hex Value | Next Cluster (Masked) | Status / Next Cluster")
    print("-" * 70)
    
    for entry in entries:
        # The true cluster indexing starts at 2 for data
        cluster_index = entry['index']
        
        if cluster_index < 2:
             print(f" {cluster_index:^6} | {entry['hex_value']:^9} | {'---':^21} | RESERVED/SPECIAL")
        else:
            # Mask out the reserved upper 4 bits for display clarity
            masked_next_cluster = entry['hex_value']
            try:
                masked_next_cluster = struct.unpack('<I', struct.pack('<I', int(entry['hex_value'], 16)))[0] & 0x0FFFFFFF
            except:
                 pass # keep original value if parsing fails
            
            print(f" {cluster_index:^6} | {entry['hex_value']:^9} | {masked_next_cluster:^21} | {entry['status']}")
            
    print("="*70)