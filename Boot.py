import struct
import os

# --- Constants for FAT Boot Sector Parsing ---

BOOT_SECTOR_SIZE = 512
SIGNATURE_OFFSET = 0x1FE
SIGNATURE = b'\x55\xAA'

# General FAT Fields (Offsets are relative to the start of the 512-byte sector)
# The structure changes after offset 0x0C, but the common fields are:
# Offset 0x0B (11 decimal) to 0x17 (23 decimal) are the essential layout parameters.
# All fields are read using Little-Endian ('<').

# Offset 0x0B: Bytes Per Sector (2 bytes)
OFS_SECTOR_SIZE = 0x0B
FMT_SECTOR_SIZE = '<H' # H: unsigned short (2 bytes)

# Offset 0x0D: Sectors Per Cluster (1 byte)
OFS_CLUSTER_SIZE = 0x0D
FMT_CLUSTER_SIZE = '<B' # B: unsigned char (1 byte)

# Offset 0x0E: Reserved Sector Count (2 bytes) - The number of sectors before the first FAT.
OFS_RESERVED_COUNT = 0x0E
FMT_RESERVED_COUNT = '<H' # H: unsigned short (2 bytes)

# Offset 0x10: Number of FATs (1 byte)
OFS_NUM_FATS = 0x10
FMT_NUM_FATS = '<B' # B: unsigned char (1 byte)

# --- FAT16 Specific Fields (for FAT16 structure) ---

# Offset 0x11: Root Directory Entries (2 bytes) - Used to calculate the size of the Root Directory.
OFS_ROOT_ENTRIES = 0x11
FMT_ROOT_ENTRIES = '<H' # H: unsigned short (2 bytes)

# Offset 0x13: Total Sectors (2 bytes) - Only used if the partition is small (< 32MB).
# If 0, the 4-byte total sector count (at 0x20) is used.
OFS_TOTAL_SECTORS_SMALL = 0x13 
FMT_TOTAL_SECTORS_SMALL = '<H' # H: unsigned short (2 bytes)

# Offset 0x16: FAT Size (2 bytes) - Size of one FAT copy in sectors.
OFS_FAT_SIZE = 0x16
FMT_FAT_SIZE = '<H' # H: unsigned short (2 bytes)

# --- Extended Field (if total sectors > 65535) ---
# Offset 0x20: Total Sectors (4 bytes) - Only used if the 2-byte field at 0x13 is zero.
OFS_TOTAL_SECTORS_LARGE = 0x20
FMT_TOTAL_SECTORS_LARGE = '<I' # I: unsigned int (4 bytes)


def read_boot_sector_from_file(file_path: str, partition_start_lba: int) -> bytes or None:
    """
    Reads the boot sector from the specified file path at the start of the partition.
    
    :param file_path: Path to the disk image file (e.g., '2gb.dd').
    :param partition_start_lba: The LBA where the partition begins (e.g., 39).
    :return: The 512 bytes of the boot sector data.
    """
    try:
        offset_bytes = partition_start_lba * BOOT_SECTOR_SIZE
        print(f"Reading boot sector at byte offset: {offset_bytes} (LBA {partition_start_lba})")
        
        with open(file_path, 'rb') as f:
            f.seek(offset_bytes)
            boot_data = f.read(BOOT_SECTOR_SIZE)
            
            if len(boot_data) != BOOT_SECTOR_SIZE:
                print(f"Error: File ended prematurely while reading boot sector.")
                return None
            return boot_data
            
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'")
        return None
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return None

def parse_fat16_boot_sector(boot_data: bytes, partition_start_lba: int):
    """
    Parses the 512 bytes of a FAT16 Boot Sector.
    """
    if len(boot_data) != BOOT_SECTOR_SIZE:
        raise ValueError(f"Boot sector data must be exactly {BOOT_SECTOR_SIZE} bytes.")

    result = {
        'signature_valid': boot_data[SIGNATURE_OFFSET:SIGNATURE_OFFSET + 2] == SIGNATURE,
        'parameters': {}
    }
    
    # 1. Check Signature
    if not result['signature_valid']:
        print(f"Warning: Boot Sector signature is INVALID. Expected 55 AA.")
        
    p = result['parameters']
    
    # 2. Extract Common Parameters
    # Bytes Per Sector (H: 2 bytes)
    p['bytes_per_sector'] = struct.unpack(FMT_SECTOR_SIZE, boot_data[OFS_SECTOR_SIZE:OFS_SECTOR_SIZE + 2])[0]
    
    # Sectors Per Cluster (B: 1 byte)
    p['sectors_per_cluster'] = struct.unpack(FMT_CLUSTER_SIZE, boot_data[OFS_CLUSTER_SIZE:OFS_CLUSTER_SIZE + 1])[0]
    
    # Reserved Sector Count (H: 2 bytes)
    p['reserved_sectors'] = struct.unpack(FMT_RESERVED_COUNT, boot_data[OFS_RESERVED_COUNT:OFS_RESERVED_COUNT + 2])[0]
    
    # Number of FATs (B: 1 byte)
    p['num_fats'] = struct.unpack(FMT_NUM_FATS, boot_data[OFS_NUM_FATS:OFS_NUM_FATS + 1])[0]
    
    # 3. Extract FAT16 Specific Parameters
    
    # Root Entry Count (H: 2 bytes)
    root_entries = struct.unpack(FMT_ROOT_ENTRIES, boot_data[OFS_ROOT_ENTRIES:OFS_ROOT_ENTRIES + 2])[0]
    p['root_entry_count'] = root_entries
    p['root_size_bytes'] = root_entries * 32 # Size = Root_Size * 32
    p['root_size_sectors'] = (p['root_size_bytes'] + p['bytes_per_sector'] - 1) // p['bytes_per_sector'] # Size in sectors (ceiling division)

    # FAT Size (H: 2 bytes)
    p['fat_size_sectors'] = struct.unpack(FMT_FAT_SIZE, boot_data[OFS_FAT_SIZE:OFS_FAT_SIZE + 2])[0]

    # Total Sectors - Check small field first (H: 2 bytes)
    total_sectors_small = struct.unpack(FMT_TOTAL_SECTORS_SMALL, boot_data[OFS_TOTAL_SECTORS_SMALL:OFS_TOTAL_SECTORS_SMALL + 2])[0]
    
    if total_sectors_small != 0:
        # For smaller disks (<= 65535 sectors)
        p['total_sectors'] = total_sectors_small
    else:
        # Use the 4-byte field (I: 4 bytes) for larger disks
        p['total_sectors'] = struct.unpack(FMT_TOTAL_SECTORS_LARGE, boot_data[OFS_TOTAL_SECTORS_LARGE:OFS_TOTAL_SECTORS_LARGE + 4])[0]

    # 4. Calculate important locations
    p['first_fat_sector'] = partition_start_lba + p['reserved_sectors']
    p['root_dir_sector'] = p['first_fat_sector'] + (p['num_fats'] * p['fat_size_sectors'])
    p['data_region_sector'] = p['root_dir_sector'] + p['root_size_sectors']

    return result

# --- Execution Example ---

FILE_NAME = '2gb.dd' 
PARTITION_START_LBA = 39 # Assuming LBA 39 from previous MBR analysis

boot_data = read_boot_sector_from_file(FILE_NAME, PARTITION_START_LBA)

if boot_data:
    try:
        parsed_result = parse_fat16_boot_sector(boot_data, PARTITION_START_LBA)
        
        print("\n" + "="*45)
        print(f"      FAT16 BOOT SECTOR PARSING RESULTS")
        print("="*45)
        print(f"Boot Sector Signature (55 AA) Valid: {parsed_result['signature_valid']}")
        print("-" * 45)
        
        params = parsed_result['parameters']
        
        print("  [File System Layout]")
        print(f"  Bytes/Sector: {params['bytes_per_sector']} (0x{params['bytes_per_sector']:X})")
        print(f"  Sectors/Cluster: {params['sectors_per_cluster']}")
        print(f"  Total Sectors (FS Used): {params['total_sectors']:,}")
        print(f"  Total Size (FS Used): {params['total_sectors'] * params['bytes_per_sector'] / (1024*1024):,.2f} MB")
        print("-" * 45)

        print("  [FAT Structure]")
        print(f"  Reserved Sectors: {params['reserved_sectors']}")
        print(f"  Number of FATs (N): {params['num_fats']}")
        print(f"  FAT Size (Sectors): {params['fat_size_sectors']}")
        print(f"  Root Entries: {params['root_entry_count']}")
        print(f"  Root Dir Size: {params['root_size_sectors']} sectors")
        print("-" * 45)

        print("  [Calculated Locations (LBA)]")
        print(f"  Partition Start: {PARTITION_START_LBA}")
        print(f"  First FAT Starts At: {params['first_fat_sector']}")
        print(f"  Root Dir Starts At: {params['root_dir_sector']}")
        print(f"  Data Region Starts At: {params['data_region_sector']}")
        print("="*45)

    except ValueError as e:
        print(f"Parsing error: {e}")