import os
import sys
import sqlite3
import base64
import shutil
import platform
import re
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description="Migrate Antigravity chat history to the new IDE.")
    parser.add_argument("--old-db-dir", type=str, help="Optional: Custom path to the OLD Antigravity state database directory.")
    parser.add_argument("--new-db-dir", type=str, help="Optional: Custom path to the NEW Antigravity IDE state database directory.")
    parser.add_argument("--old-conv-dir", type=str, help="Optional: Custom path to the OLD .gemini/antigravity/conversations folder.")
    parser.add_argument("--new-conv-dir", type=str, help="Optional: Custom path to the NEW .gemini/antigravity-ide/conversations folder.")
    parser.add_argument("--old-brain-dir", type=str, help="Optional: Custom path to the OLD .gemini/antigravity/brain folder.")
    parser.add_argument("--new-brain-dir", type=str, help="Optional: Custom path to the NEW .gemini/antigravity-ide/brain folder.")
    return parser.parse_args()

def get_app_data_dirs(args):
    system = platform.system()
    home = os.path.expanduser("~")
    
    old_dir = args.old_db_dir
    new_dir = args.new_db_dir
    
    if not old_dir or not new_dir:
        if system == "Windows":
            old_dir = old_dir or os.path.join(home, "AppData", "Roaming", "Antigravity")
            new_dir = new_dir or os.path.join(home, "AppData", "Roaming", "Antigravity IDE")
        elif system == "Darwin": # macOS
            old_dir = old_dir or os.path.join(home, "Library", "Application Support", "Antigravity")
            new_dir = new_dir or os.path.join(home, "Library", "Application Support", "Antigravity IDE")
        else: # Linux
            old_dir = old_dir or os.path.join(home, ".config", "Antigravity")
            new_dir = new_dir or os.path.join(home, ".config", "Antigravity IDE")
            
    return old_dir, new_dir

def merge_directories(src, dst):
    """Safely merges directories recursively without using deprecated distutils."""
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            merge_directories(s, d)
        else:
            if not os.path.exists(d) or os.path.getmtime(s) > os.path.getmtime(d):
                shutil.copy2(s, d)

def migrate_files(args):
    home = os.path.expanduser("~")
    
    # Migrate Conversations
    old_conv_dir = args.old_conv_dir or os.path.join(home, ".gemini", "antigravity", "conversations")
    new_conv_dir = args.new_conv_dir or os.path.join(home, ".gemini", "antigravity-ide", "conversations")
    
    if os.path.exists(old_conv_dir):
        os.makedirs(new_conv_dir, exist_ok=True)
        copied = 0
        for filename in os.listdir(old_conv_dir):
            if filename.endswith(".pb"):
                src = os.path.join(old_conv_dir, filename)
                dst = os.path.join(new_conv_dir, filename)
                if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
                    shutil.copy2(src, dst)
                    copied += 1
        print(f"[*] Copied/Updated {copied} chat files to the new IDE folder.")
    else:
        print(f"[!] Old conversations folder not found at {old_conv_dir}. Skipping file migration.")
        
    # Migrate Brain (Artifacts, Images, Logs)
    old_brain_dir = args.old_brain_dir or os.path.join(home, ".gemini", "antigravity", "brain")
    new_brain_dir = args.new_brain_dir or os.path.join(home, ".gemini", "antigravity-ide", "brain")
    
    if os.path.exists(old_brain_dir):
        copied_brain = 0
        for item in os.listdir(old_brain_dir):
            src_item = os.path.join(old_brain_dir, item)
            dst_item = os.path.join(new_brain_dir, item)
            
            if os.path.isdir(src_item):
                # Copy or merge entire chat ID folder (e.g. artifacts, scratch, logs)
                try:
                    merge_directories(src_item, dst_item)
                    copied_brain += 1
                except Exception as e:
                    print(f"[!] Failed to merge brain directory {src_item}: {e}")
        print(f"[*] Migrated {copied_brain} artifact/brain folders to the new IDE.")
    else:
        print(f"[!] Old brain folder not found at {old_brain_dir}. Skipping artifact migration.")

def replace_in_dict_recursive(d):
    # This requires blackboxprotobuf to be imported
    import blackboxprotobuf
    changed = False
    
    # Regex to match any drive letter with URL encoded colon: e.g. file:///c%3A/ or file:///D%3a/
    url_pattern = re.compile(rb"(?i)file:///([a-zA-Z])%3a/")
    
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, dict):
                changed = replace_in_dict_recursive(v) or changed
            elif isinstance(v, list):
                for i in range(len(v)):
                    if isinstance(v[i], dict):
                        changed = replace_in_dict_recursive(v[i]) or changed
                    elif isinstance(v[i], (bytes, bytearray)):
                        if url_pattern.search(v[i]):
                            v[i] = url_pattern.sub(rb"file:///\1:/", v[i])
                            changed = True
                        else:
                            try:
                                decoded_bytes = base64.b64decode(v[i])
                                inner_msg, inner_type = blackboxprotobuf.decode_message(decoded_bytes)
                                inner_changed = replace_in_dict_recursive(inner_msg)
                                if inner_changed:
                                    new_inner_bytes = blackboxprotobuf.encode_message(inner_msg, inner_type)
                                    v[i] = base64.b64encode(new_inner_bytes)
                                    changed = True
                            except Exception:
                                pass
            elif isinstance(v, (bytes, bytearray)):
                if url_pattern.search(v):
                    d[k] = url_pattern.sub(rb"file:///\1:/", v)
                    changed = True
                else:
                    try:
                        decoded_bytes = base64.b64decode(v)
                        inner_msg, inner_type = blackboxprotobuf.decode_message(decoded_bytes)
                        inner_changed = replace_in_dict_recursive(inner_msg)
                        if inner_changed:
                            new_inner_bytes = blackboxprotobuf.encode_message(inner_msg, inner_type)
                            d[k] = base64.b64encode(new_inner_bytes)
                            changed = True
                    except Exception:
                        pass
    return changed

def patch_windows_urls(raw_bytes):
    try:
        import blackboxprotobuf
    except ImportError:
        print("[!] The 'blackboxprotobuf' library is required to patch URLs on Windows.")
        print("    Please run: pip install blackboxprotobuf")
        print("    Continuing with standard merge, but Windows users may still not see their chats if URLs are mismatched.")
        return raw_bytes
        
    try:
        message, typedef = blackboxprotobuf.decode_message(raw_bytes)
        changed = replace_in_dict_recursive(message)
        if changed:
            print("[*] Successfully patched Windows encoded URLs in the binary data.")
            return blackboxprotobuf.encode_message(message, typedef)
    except Exception as e:
        print(f"[!] Failed to patch Windows URLs: {e}")
    return raw_bytes

def deduplicate_protobuf_list(raw_bytes):
    try:
        import blackboxprotobuf
        message, typedef = blackboxprotobuf.decode_message(raw_bytes)
        
        changed = False
        # The trajectory summaries is usually a dictionary with a repeated field (list of dicts)
        for k, v in message.items():
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                seen_ids = {}
                deduped_list = []
                for item in v:
                    # Find the UUID field (Chat ID)
                    uuid_val = None
                    for sub_k, sub_v in item.items():
                        if isinstance(sub_v, (bytes, bytearray)):
                            try:
                                decoded_str = sub_v.decode('utf-8')
                                # Regex for standard UUID
                                if re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", decoded_str):
                                    uuid_val = decoded_str
                                    break
                            except: pass
                    
                    if uuid_val:
                        # Overwrite if we see it again - the LAST occurrence in the list wins!
                        seen_ids[uuid_val] = item
                    else:
                        deduped_list.append(item)
                
                final_list = deduped_list + list(seen_ids.values())
                if len(final_list) < len(v):
                    message[k] = final_list
                    changed = True
                    
        if changed:
            print("[*] Successfully deduplicated ghost chats from the database!")
            return blackboxprotobuf.encode_message(message, typedef)
    except ImportError:
        print("[!] 'blackboxprotobuf' is missing! We highly recommend running 'pip install blackboxprotobuf'.")
        print("    Without it, we cannot deduplicate ghost chats. Falling back to overwriting new database with old database to prevent duplicates.")
        return None
    except Exception as e:
        print(f"[!] Deduplication failed: {e}")
        
    return raw_bytes

def merge_db_keys(old_db_dir, new_db_dir):
    old_db = os.path.join(old_db_dir, "User", "globalStorage", "state.vscdb")
    new_db = os.path.join(new_db_dir, "User", "globalStorage", "state.vscdb")
    
    if not os.path.exists(old_db):
        print(f"[!] Old state database not found at {old_db}")
        return
    if not os.path.exists(new_db):
        print(f"[!] New state database not found at {new_db}")
        return
        
    print(f"[*] Connecting to databases...")
    try:
        conn_old = sqlite3.connect(old_db)
        cursor_old = conn_old.cursor()
        conn_new = sqlite3.connect(new_db)
        cursor_new = conn_new.cursor()
        
        keys_to_merge = ["antigravityUnifiedStateSync.trajectorySummaries", "antigravityUnifiedStateSync.sidebarWorkspaces"]
        
        for key in keys_to_merge:
            cursor_old.execute("SELECT value FROM ItemTable WHERE key = ?", (key,))
            old_row = cursor_old.fetchone()
            if not old_row or not old_row[0]:
                continue
                
            old_val_str = old_row[0]
            old_val_bytes = base64.b64decode(old_val_str) if isinstance(old_val_str, str) else base64.b64decode(old_val_str.decode('utf-8'))
            
            # Patch Windows URLs if on Windows (e.g. c%3A -> c:)
            if platform.system() == "Windows":
                old_val_bytes = patch_windows_urls(old_val_bytes)
            
            cursor_new.execute("SELECT value FROM ItemTable WHERE key = ?", (key,))
            new_row = cursor_new.fetchone()
            
            if new_row and new_row[0]:
                new_val_str = new_row[0]
                new_val_bytes = base64.b64decode(new_val_str) if isinstance(new_val_str, str) else base64.b64decode(new_val_str.decode('utf-8'))
                
                # First, concatenate raw bytes (NEW comes first, OLD comes last so it overrides NEW during deduplication!)
                merged_bytes = new_val_bytes + old_val_bytes
                
                # Attempt to safely deduplicate the merged list
                deduped_bytes = deduplicate_protobuf_list(merged_bytes)
                
                if deduped_bytes is None:
                    # Fallback if blackboxprotobuf is not installed: Overwrite the new DB completely with the old DB 
                    # rather than raw concatenating, to prevent ghost duplicates in the IDE!
                    merged_str = base64.b64encode(old_val_bytes).decode('utf-8')
                    print(f"[*] Overwrote data for key: {key} (install blackboxprotobuf for a true merge)")
                else:
                    merged_str = base64.b64encode(deduped_bytes).decode('utf-8')
                    print(f"[*] Safely merged and deduplicated data for key: {key}")
            else:
                merged_str = base64.b64encode(old_val_bytes).decode('utf-8')
                print(f"[*] Inserted old data for key: {key}")
                
            cursor_new.execute("INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)", (key, merged_str))
            
        conn_new.commit()
        conn_new.close()
        conn_old.close()
        print("[*] Database migration completed successfully!")
    except Exception as e:
        print(f"[!] Error during database migration: {e}")

if __name__ == "__main__":
    args = parse_arguments()
    
    print("==============================================")
    print(" Antigravity IDE History Recovery Tool v1.0")
    print("==============================================")
    print("WARNING: Please ensure you have completely CLOSED Antigravity IDE before continuing.")
    print("If it is open, the changes will be overwritten when it shuts down.")
    input("Press Enter when you have confirmed the IDE is closed...")
    
    old_app_dir, new_app_dir = get_app_data_dirs(args)
    print(f"\n[1/2] Migrating physical chat log files...")
    migrate_files(args)
    
    print(f"\n[2/2] Migrating and merging database keys...")
    merge_db_keys(old_app_dir, new_app_dir)
    
    print("\n==============================================")
    print(" Migration Complete! You may now open Antigravity IDE.")
    print("==============================================")
