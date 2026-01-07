import sys
import os
import webbrowser
import urllib.parse

# --- FIX START: Add parent directory to system path ---
# This gets the directory of the current script, goes up one level, and adds it to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
# --- FIX END ---

# Now this import will work because Python can see the 'pythonBackend' root
from Repos.ItemRepo import ItemRepository

def main():
    repo = ItemRepository()
    
    # 1. Get all items
    print("Fetching items from database...")
    try:
        all_items = repo.list_items()
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        return
    
    # 2. Filter for items with no image
    items_needing_images = [item for item in all_items if not item.image_url]
    
    if not items_needing_images:
        print("All items already have images! Good job.")
        return

    print(f"Found {len(items_needing_images)} items missing images.\n")
    print("Controls:")
    print("  [Paste URL] : Save image and move to next")
    print("  [Enter]     : Skip item")
    print("  'q'         : Quit script")
    print("-" * 50)

    for i, item in enumerate(items_needing_images, 1):
        print(f"\n({i}/{len(items_needing_images)}) Item: {item.name} ({item.item_type})")
        
        # 3. Automatically open Google Images search
        search_query = urllib.parse.quote(f"{item.name} hiking gear")
        search_url = f"https://www.google.com/search?tbm=isch&q={search_query}"
        
        print(f"   -> Opening search for '{item.name}'...")
        webbrowser.open(search_url)
        
        # 4. Input loop
        while True:
            user_input = input("   Paste Image URL > ").strip()
            
            if user_input.lower() == 'q':
                print("Exiting...")
                sys.exit()
            
            if user_input == "":
                print("   Skipping...")
                break
            
            if not (user_input.startswith("http") or user_input.startswith("data:")):
                print("   (!) That doesn't look like a valid URL. Try again or hit Enter to skip.")
                continue

            try:
                repo.update_item_image(item.id, user_input)
                print(f"   [SUCCESS] Updated {item.name}")
                break
            except Exception as e:
                print(f"   [ERROR] Could not save to DB: {e}")
                break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")