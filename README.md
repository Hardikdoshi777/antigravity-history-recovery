# Antigravity IDE History Recovery Script

Standalone recovery utility for restoring missing workspace/chat history after upgrading to Antigravity IDE 2.0.0+.

## Problem

Many users are facing an issue after updating to newer Antigravity IDE versions where previous workspace/chat history is no longer visible.

This usually happens because the migration between the older Antigravity data structure and the newer `antigravity-ide` structure is incomplete.

## Supported Platforms

* macOS
* Windows
* Linux

---

# Before Running

⚠️ Important:

1. Update Antigravity IDE to the latest version
2. Completely quit/close Antigravity IDE
3. Then run the recovery script

---

# Requirements

## macOS

Most Macs already include Python.

Check with:

```bash
python3 --version
```

If Python is missing, macOS will usually prompt you to install Developer Tools automatically.

---

## Windows

Install Python:

```powershell
winget install Python.Python.3.12
```

Install required dependency:

```powershell
pip install blackboxprotobuf
```

---

# Usage

## macOS

```bash
cd ~/path_where_script_download
python3 antigravity_history_recovery.py
```

## Windows

```powershell
cd path_where_script_download
python antigravity_history_recovery.py
```

---

# What the Script Does Internally

The script automatically:

* Detects operating system paths
* Locates old Antigravity history data
* Copies missing conversation files
* Merges SQLite history databases safely
* Repairs Windows workspace URL formatting issues
* Restores workspace-linked conversations

---

# Notes

* Your existing chats are not deleted
* The script performs a safe merge operation
* Running the script multiple times is safe
* Antigravity IDE must remain closed while recovery runs

---

# Disclaimer

This is an unofficial community recovery utility created to help users restore missing Antigravity history after migration issues.
