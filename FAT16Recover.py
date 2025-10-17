import struct
import os

# --- CORE CONSTANTS ---
FILE_NAME = '2gb.dd' 
RECOVERY_DIR = 'RECOVERED_DATA' 
SECTOR_SIZE = 512
MBR_PARTITION_FORMAT = '<B3sB3sII'
PARTITION_TABLE_OFFSET = 0x1BE
LFN_ATTRIBUTES = 0x0F # Attribute for Long File Name entries

# --- GLOBAL DISK PARAMETERS (Populated by setup_disk_params) ---
PARTITION_START_LBA = 0
RESERVED_SECTORS = 0
NUM_FATS = 0
FAT_SIZE_SECTORS = 0
ROOT_DIR_SECTORS = 0
SECTORS_PER_CLUSTER = 0 
FAT1_START_LBA = 0
ROOT_DIR_START_LBA = 0 
DATA_REGION_START_LBA = 0
GLOBAL_FAT_DATA = None 

# --- CORE FILE READING FUNCTIONS ---

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
    except Exception:
        return None

# --- DISK SETUP ---

def setup_disk_params():
    """Parses MBR and VBR to populate global disk parameters."""
    global PARTITION_START_LBA, RESERVED_SECTORS, NUM_FATS, FAT_SIZE_SECTORS, ROOT_DIR_SECTORS, SECTORS_PER_CLUSTER
    global FAT1_START_LBA, ROOT_DIR_START_LBA, DATA_REGION_START_LBA, GLOBAL_FAT_DATA 

    # MBR Parsing (Reads Partition Start LBA)
    mbr_data = read_sector(FILE_NAME, 0)
    if not mbr_data or mbr_data[0x1FE:0x200] != b'\x55\xAA':
        print("Error: Invalid MBR or signature.")
        return False
    
    entry_data = mbr_data[PARTITION_TABLE_OFFSET : PARTITION_TABLE_OFFSET + 16]
    (_, _, type_id, _, start_lba, _) = struct.unpack(MBR_PARTITION_FORMAT, entry_data)
    PARTITION_START_LBA = start_lba

    # VBR Parsing (Reads FAT Geometry)
    vbr_data = read_sector(FILE_NAME, PARTITION_START_LBA)
    if not vbr_data: return False

    SECTORS_PER_CLUSTER = struct.unpack('<B', vbr_data[0x0D:0x0E])[0]
    RESERVED_SECTORS = struct.unpack('<H', vbr_data[0x0E:0x10])[0]
    NUM_FATS = struct.unpack('<B', vbr_data[0x10:0x11])[0]
    root_entries = struct.unpack('<H', vbr_data[0x11:0x13])[0]
    FAT_SIZE_SECTORS = struct.unpack('<H', vbr_data[0x16:0x18])[0]

    # Calculate key LBA values
    ROOT_DIR_SECTORS = (root_entries * 32 + SECTOR_SIZE - 1) // SECTOR_SIZE
    FAT1_START_LBA = PARTITION_START_LBA + RESERVED_SECTORS
    ROOT_DIR_START_LBA = FAT1_START_LBA + (NUM_FATS * FAT_SIZE_SECTORS)
    DATA_REGION_START_LBA = ROOT_DIR_START_LBA + ROOT_DIR_SECTORS
    
    # Read entire FAT for chain tracing
    GLOBAL_FAT_DATA = read_sector(FILE_NAME, FAT1_START_LBA, count=FAT_SIZE_SECTORS)
    if not GLOBAL_FAT_DATA:
        print("Error: Could not read FAT table.")
        return False

    return True

# --- FAT TRACE LOGIC ---

def trace_fat_chain(start_cluster: int):
    """Traces the cluster chain for a given starting cluster in FAT16 using the global FAT data."""
    current_cluster = start_cluster
    chain = []

    while True:
        # FAT16 Entry size is 2 bytes
        offset = current_cluster * 2
        if offset + 2 > len(GLOBAL_FAT_DATA):
            break

        entry_bytes = GLOBAL_FAT_DATA[offset : offset + 2]
        next_cluster = struct.unpack('<H', entry_bytes)[0]
        
        chain.append(current_cluster)

        if 0xFFF8 <= next_cluster <= 0xFFFF: # End-Of-Chain marker
            break
        elif next_cluster == 0x0000: # Free/Broken chain marker (treat as end)
            break 
        elif next_cluster == 0xFFF7: # Bad cluster (treat as end)
            break 
        else:
            current_cluster = next_cluster
            
            if len(chain) > 65535: # Safety break (for extremely long, potentially circular chains)
                break
    
    return chain

# --- RECOVERY FUNCTION ---

def recover_file(start_cluster: int, file_size: int, output_path: str):
    """Recovers data from a file's cluster chain."""
    
    if start_cluster < 2 or file_size == 0: return False 
    
    cluster_chain = trace_fat_chain(start_cluster)
    
    if not cluster_chain:
        return False

    bytes_per_cluster = SECTORS_PER_CLUSTER * SECTOR_SIZE
    
    try:
        with open(output_path, 'wb') as outfile:
            bytes_recovered = 0
            
            for cluster in cluster_chain:
                # Calculate LBA for the cluster
                lba = DATA_REGION_START_LBA + (cluster - 2) * SECTORS_PER_CLUSTER
                
                # Read the data for the cluster
                cluster_data = read_sector(FILE_NAME, lba, count=SECTORS_PER_CLUSTER)
                
                if not cluster_data: 
                    break
                
                # Determine how much data to write (to trim the last cluster based on file size)
                bytes_remaining = file_size - bytes_recovered
                bytes_to_write = min(bytes_per_cluster, bytes_remaining)
                
                outfile.write(cluster_data[:bytes_to_write])
                bytes_recovered += bytes_to_write

                if bytes_recovered >= file_size: break # Finished writing all bytes

        print(f" [+] RECOVERED: {output_path} ({bytes_recovered:,} bytes)")
        return True
    except Exception as e:
        print(f" [!] Error writing file {output_path}: {e}")
        return False

# --- LFN UTILITIES ---

def decode_lfn_fragment(entry_data: bytes) -> str:
    """Decodes LFN characters from a 32-byte LFN directory entry."""
    # LFN characters are stored in three non-contiguous chunks in UCS-2 Little Endian
    chars = []
    
    # Block 1: offset 0x01 (5 chars)
    chars.append(entry_data[0x01:0x0B])
    # Block 2: offset 0x0E (6 chars)
    chars.append(entry_data[0x0E:0x1A])
    # Block 3: offset 0x1C (2 chars)
    chars.append(entry_data[0x1C:0x20])
    
    # Concatenate and decode using UTF-16LE (UCS-2)
    full_chars = b''.join(chars)
    
    # Remove null terminators (0x0000) and padding (0xFFFF)
    name = full_chars.decode('utf-16-le', errors='replace')
    return name.split('\x00')[0].strip()

# --- RECURSIVE DIRECTORY PARSING & RECOVERY ---

def parse_and_recover_directory(start_lba: int, dir_path: str):
    """
    Parses a directory and recursively calls itself for any valid subdirectories. 
    Attempts to recover files found in the directory.
    """
    global SECTORS_PER_CLUSTER, ROOT_DIR_SECTORS, DATA_REGION_START_LBA, ROOT_DIR_START_LBA

    if start_lba == ROOT_DIR_START_LBA:
        read_count = ROOT_DIR_SECTORS
    else:
        # For subdirectories, read the first cluster
        read_count = SECTORS_PER_CLUSTER
        
    dir_data = read_sector(FILE_NAME, start_lba, count=read_count)
    if not dir_data:
        print(f" [!] Failed to read directory at LBA {start_lba}.")
        return

    print(f"\n{'='*20} Scanning Directory: {dir_path if dir_path else '(Root)'} (LBA {start_lba}) {'='*20}")
    
    # LFN fragments must be collected in reverse order, starting with the last fragment.
    lfn_fragments = []
    
    # Process 32-byte directory entries
    for i in range(len(dir_data) // 32):
        offset = i * 32
        entry_data = dir_data[offset:offset + 32]
        
        first_byte = entry_data[0x00]
        attributes = entry_data[0x0B]
        
        if first_byte == 0x00: 
            break # End of directory
            
        # --- LFN ENTRY HANDLING (LFNs precede the SFN entry) ---
        if attributes == LFN_ATTRIBUTES:
            # Check if this is a deleted LFN fragment (first byte 0xE5)
            # We collect all LFN fragments, deleted or not, to attempt name restoration.
            if first_byte != 0xE5:
                # Sequence number is the first byte. The last fragment has bit 6 set (0x40).
                # We store the decoded fragment along with its sequence number.
                sequence = entry_data[0x00] & 0x1F # mask off the last fragment bit
                fragment = decode_lfn_fragment(entry_data)
                lfn_fragments.append((sequence, fragment))
            continue 
            
        # --- SFN ENTRY HANDLING (File/Directory entry) ---
        
        # If the entry is a valid file/directory, we process it and reset the LFN fragments
        
        is_deleted = first_byte == 0xE5
        is_dir = (attributes & 0x10) != 0
        file_size = struct.unpack('<I', entry_data[0x1C:0x20])[0]
        start_cluster = struct.unpack('<H', entry_data[0x1A:0x1C])[0]
        
        # --- 1. Determine Final Name (LFN priority) ---
        
        final_name = ""
        
        if lfn_fragments:
            # Sort fragments by sequence number and join them to get the LFN
            lfn_fragments.sort(key=lambda x: x[0])
            final_name = "".join([f[1] for f in lfn_fragments])
        
        if not final_name:
            # Fallback to SFN
            name_bytes = bytearray(entry_data[0x00:0x0B])
            
            if is_deleted:
                # DMDE's logic for deleted file prefixes:
                
                # 1. Check for Deleted macOS Resource Fork: SFN starts with 0xE5 and second byte is 0x5F ('_')
                if len(name_bytes) > 1 and name_bytes[1] == 0x5F:
                    # Restore the file name to start with '._'
                    name_bytes[0] = 0x2E # Restore '.' (0x2E)
                else:
                    # 2. Standard deleted file: Replace 0xE5 with 0x5F ('_')
                    name_bytes[0] = 0x5F 
            
            # Decode the file name (base + extension) using ASCII
            base_name = name_bytes[0:8].decode('ascii', errors='replace').rstrip()
            ext = name_bytes[8:11].decode('ascii', errors='replace').rstrip()
            final_name = f"{base_name}.{ext}" if ext else base_name

        # Reset LFN fragments for the next file/directory entry
        lfn_fragments = []
        
        # Clean up any unsafe/replacement characters ('?') and leading spaces
        final_name = final_name.replace('?', '_').replace('/', '_').replace('\\', '_').strip()
        
        # Skip '.' and '..'
        if final_name == '.' or final_name == '..':
             continue
        
        current_full_path = os.path.join(dir_path, final_name)
        
        # --- 2. RECOVERY / RECURSION LOGIC ---
        
        if is_dir:
            if start_cluster < 2:
                continue

            # 1. Create the directory path on the host system
            os.makedirs(os.path.join(RECOVERY_DIR, current_full_path), exist_ok=True)
            
            # 2. Calculate LBA for the new subdirectory's first cluster
            sub_dir_lba = DATA_REGION_START_LBA + (start_cluster - 2) * SECTORS_PER_CLUSTER
            
            # 3. Recursively call the function for the subdirectory
            parse_and_recover_directory(sub_dir_lba, current_full_path)
            
        elif file_size > 0 and start_cluster >= 2:
            
            # 1. Create a path on the host system relative to RECOVERY_DIR
            relative_path = os.path.join(RECOVERY_DIR, current_full_path)
            os.makedirs(os.path.dirname(relative_path), exist_ok=True)
            
            # 2. Attempt file recovery
            recover_file(start_cluster, file_size, relative_path)
            
# --- MAIN EXECUTION ---

def run_recovery_tool():
    """Initializes disk parameters and starts the recursive directory traversal."""
    
    if not setup_disk_params():
        print("\nFAT16 Initialization failed. Cannot run recovery.")
        return

    # Clear/Create the main recovery directory
    os.makedirs(RECOVERY_DIR, exist_ok=True)
    
    print("\n" + "="*80)
    print("FAT16 RECURSIVE DATA RECOVERY TOOL STARTED (with LFN Support)")
    print("="*80)
    
    # Start the recursive recovery from the Root Directory
    parse_and_recover_directory(ROOT_DIR_START_LBA, "")
    
    print("\n" + "="*80)
    print(f"Recovery attempt finished. Check the '{RECOVERY_DIR}' folder for recovered files.")
    print("="*80)

if __name__ == "__main__":
    run_recovery_tool()