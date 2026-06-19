import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path

def register_namespaces():
    """Register namespaces to preserve prefixes in XBEL."""
    ET.register_namespace('bookmark', 'http://www.freedesktop.org/standards/desktop-bookmarks')
    ET.register_namespace('kdepriv', 'http://www.kde.org/kdepriv')
    ET.register_namespace('mime', 'http://www.freedesktop.org/standards/shared-mime-info')

def add_to_sidebar(path_str, name="Google Drive"):
    """Adds the directory to KDE Dolphin Places and GTK bookmarks (Nautilus, Thunar, etc.)."""
    abs_path = os.path.abspath(os.path.expanduser(path_str))
    
    # 1. KDE Places
    add_kde_place(abs_path, name)
    
    # 2. GTK Bookmarks
    add_gtk_bookmark(abs_path, name)

def remove_from_sidebar(path_str):
    """Removes the directory from KDE Dolphin Places and GTK bookmarks."""
    abs_path = os.path.abspath(os.path.expanduser(path_str))
    
    # 1. KDE Places
    remove_kde_place(abs_path)
    
    # 2. GTK Bookmarks
    remove_gtk_bookmark(abs_path)

def add_kde_place(abs_path, name):
    xbel_path = Path.home() / ".local" / "share" / "user-places.xbel"
    if not xbel_path.exists():
        return
        
    href = f"file://{abs_path}"
    try:
        register_namespaces()
        tree = ET.parse(xbel_path)
        root = tree.getroot()
        
        # Check if already exists
        for bookmark in root.findall('bookmark'):
            if bookmark.get('href') == href:
                return # Already exists
                
        # Create KDE place bookmark entry
        bookmark = ET.SubElement(root, 'bookmark', {'href': href})
        title = ET.SubElement(bookmark, 'title')
        title.text = name
        
        info = ET.SubElement(bookmark, 'info')
        
        metadata_fd = ET.SubElement(info, 'metadata', {'owner': 'http://freedesktop.org'})
        # XML tag name in ElementTree with namespace
        ET.SubElement(metadata_fd, '{http://www.freedesktop.org/standards/desktop-bookmarks}icon', {'name': 'folder-gdrive'})
        
        metadata_kde = ET.SubElement(info, 'metadata', {'owner': 'http://www.kde.org'})
        kde_id = ET.SubElement(metadata_kde, 'ID')
        kde_id.text = f"gdrive-{int(time.time())}"
        is_sys = ET.SubElement(metadata_kde, 'isSystemItem')
        is_sys.text = 'false'
        
        # Save XBEL file
        tree.write(xbel_path, encoding='utf-8', xml_declaration=True)
    except Exception as e:
        print(f"Error adding to KDE Places sidebar: {e}")

def remove_kde_place(abs_path):
    xbel_path = Path.home() / ".local" / "share" / "user-places.xbel"
    if not xbel_path.exists():
        return
        
    href = f"file://{abs_path}"
    try:
        register_namespaces()
        tree = ET.parse(xbel_path)
        root = tree.getroot()
        
        removed = False
        for bookmark in root.findall('bookmark'):
            if bookmark.get('href') == href:
                root.remove(bookmark)
                removed = True
                
        if removed:
            tree.write(xbel_path, encoding='utf-8', xml_declaration=True)
    except Exception as e:
        print(f"Error removing from KDE Places sidebar: {e}")

def add_gtk_bookmark(abs_path, name):
    gtk_dir = Path.home() / ".config" / "gtk-3.0"
    gtk_dir.mkdir(parents=True, exist_ok=True)
    bookmarks_file = gtk_dir / "bookmarks"
    
    href = f"file://{abs_path}"
    entry = f"{href} {name}\n"
    
    lines = []
    if bookmarks_file.exists():
        with open(bookmarks_file, 'r') as f:
            lines = f.readlines()
            
    # Check if entry already exists
    for line in lines:
        if line.strip().startswith(href):
            return # Already exists
            
    # Append to GTK bookmarks
    try:
        with open(bookmarks_file, 'a') as f:
            f.write(entry)
    except Exception as e:
        print(f"Error writing to GTK bookmarks: {e}")

def remove_gtk_bookmark(abs_path):
    bookmarks_file = Path.home() / ".config" / "gtk-3.0" / "bookmarks"
    if not bookmarks_file.exists():
        return
        
    href = f"file://{abs_path}"
    try:
        with open(bookmarks_file, 'r') as f:
            lines = f.readlines()
            
        new_lines = [line for line in lines if not line.strip().startswith(href)]
        
        if len(new_lines) != len(lines):
            with open(bookmarks_file, 'w') as f:
                f.writelines(new_lines)
    except Exception as e:
        print(f"Error removing from GTK bookmarks: {e}")
