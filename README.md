# python-fat-forensics

A comprehensive Python toolkit for analyzing and performing data recovery on **FAT16** and **FAT32** file systems.

This project provides fundamental scripts for disk forensics, allowing users to parse key structures like the **Master Boot Record (MBR)**, **Volume Boot Record (VBR)**, **File Allocation Tables (FAT)**, and **Directory Entries** from raw disk images.

---

## 📁 Project Structure

The repository contains modular Python scripts, each focusing on a specific part of the FAT file system structure:

| File Name | Description |
| :--- | :--- |
| **`MBR.py`** | Parses the **Master Boot Record (MBR)** and the **Partition Table** to locate active partitions. |
| **`Boot.py`** | Parses the **Volume Boot Record (VBR)/Boot Sector** to extract essential file system parameters (e.g., sectors per cluster, FAT size). |
| **`FAT16.py`** | Parses and analyzes the entries of a **FAT16** table. |
| **`FAT32.py`** | Parses and analyzes the entries of a **FAT32** table, handling 32-bit cluster values. |
| **`Directory.py`** | Parses a sector of a directory to extract **8.3 file names** and identify **Long File Names (LFNs)**. |
| **`ForensicTrace.py`** | A simple utility to follow a file's **cluster chain** through the FAT table for data integrity checks. |
| **`FAT16Recover.py`** | A recursive tool designed to **recover deleted files** from a FAT16 disk image by examining unallocated directory entries. |

---
<img width="1920" height="1128" alt="image" src="https://github.com/user-attachments/assets/142ab271-9318-4b3c-9ccb-c8a3e6d66ad5" />

**MBR**

<img width="1920" height="1128" alt="image" src="https://github.com/user-attachments/assets/25764cba-46ef-436d-aeea-542b8808bd02" />

**Boot**

<img width="1920" height="1128" alt="image" src="https://github.com/user-attachments/assets/ce1834c1-6c03-4666-a105-63e31a88f742" />

**FAT16**


<img width="1920" height="1128" alt="image" src="https://github.com/user-attachments/assets/be310e2e-4a91-4b90-8141-9fb4141bd274" />

**FAT32**

<img width="1920" height="1128" alt="image" src="https://github.com/user-attachments/assets/fc241861-76bc-4cfe-96f4-b0fb5e3e4aef" />

**Directory**

<img width="1920" height="1128" alt="image" src="https://github.com/user-attachments/assets/5941e4d8-d4d3-407e-a0a0-ed9c69da65bb" />

**ForensicTrace**

<img width="1920" height="1128" alt="image" src="https://github.com/user-attachments/assets/b86506fb-8d10-4f34-a6a3-8991251c00b1" />

**FAT16Recover**






## 🚀 Usage

These scripts are primarily designed for educational and investigative purposes and assume you are working with a raw disk image (commonly referenced as `2gb.dd` within the scripts).

1.  **Prerequisites:** You need **Python 3** installed.
2.  **Disk Image:** Ensure your disk image file (e.g., `2gb.dd`) is present in the same directory and is correctly referenced in the `FILE_NAME` constant at the top of each script.
3.  **Execution:** Run the individual scripts from your terminal to analyze the respective disk components:

    ```bash
    python3 MBR.py
    python3 Boot.py
    # ... and so on for other modules
    ```

---

## License

This project is open source and available under the [Specify License, e.g., MIT] license.
