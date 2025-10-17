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
