#!/usr/bin/env python3
"""
Script to analyze the JSON structure of backlinks file after decompression
This will help understand the exact field names used in the JSON
"""

import json
import gzip
import sys
from pathlib import Path

def analyze_backlinks_json(file_path):
    """Analyze the structure of a backlinks JSON file"""
    
    # Check if file exists
    if not Path(file_path).exists():
        print(f"File not found: {file_path}")
        return
    
    try:
        # Check if it's gzipped
        with open(file_path, 'rb') as f:
            magic = f.read(2)
            f.seek(0)
            
            if magic == b'\x1f\x8b':  # gzip magic number
                print("File is gzipped, decompressing...")
                with gzip.open(file_path, 'rt', encoding='utf-8') as gz_file:
                    data = json.load(gz_file)
            else:
                print("File is not gzipped, reading as plain JSON...")
                with open(file_path, 'r', encoding='utf-8') as json_file:
                    data = json.load(json_file)
        
        # Analyze the structure
        print(f"\n=== JSON Structure Analysis ===")
        print(f"Type: {type(data)}")
        
        # If it's a dict, check for common wrapper properties
        if isinstance(data, dict):
            print(f"Top-level keys: {list(data.keys())}")
            
            # Check for common array properties
            for key in ['data', 'backlinks', 'items', 'result', 'results']:
                if key in data and isinstance(data[key], list):
                    print(f"\nFound array in '{key}' property with {len(data[key])} items")
                    data = data[key]  # Use this array for analysis
                    break
        
        # If it's an array, analyze the items
        if isinstance(data, list):
            print(f"\nTotal items: {len(data)}")
            
            if len(data) > 0:
                print(f"\n=== First Item Structure ===")
                first_item = data[0]
                print(f"Fields: {list(first_item.keys())}")
                
                print(f"\n=== Sample of First Item ===")
                print(json.dumps(first_item, indent=2)[:2000])  # First 2000 chars
                
                # Analyze field types
                print(f"\n=== Field Types ===")
                for key, value in first_item.items():
                    print(f"  {key}: {type(value).__name__} = {repr(value)[:100]}")
                
                # Look for common SEO backlink fields
                print(f"\n=== Looking for Common Backlink Fields ===")
                common_fields = {
                    'URL': ['url_from', 'source_url', 'url', 'referring_url', 'page_from', 'from_url'],
                    'Anchor': ['anchor', 'anchor_text', 'text', 'link_text', 'anchor_from'],
                    'Domain Rating': ['domain_from_rating', 'domain_rating', 'dr', 'domain_rank'],
                    'Spam Score': ['spam_score', 'backlinks_spam_score', 'ss', 'spam'],
                    'DoFollow': ['dofollow', 'nofollow', 'follow', 'rel'],
                    'Type': ['type', 'link_type', 'link_attribute'],
                }
                
                for field_group, field_names in common_fields.items():
                    found = [f for f in field_names if f in first_item]
                    if found:
                        print(f"  {field_group}: Found fields: {found}")
                
                # Show a few more samples
                print(f"\n=== Sample of First 3 Items ===")
                for i, item in enumerate(data[:3], 1):
                    print(f"\nItem {i}:")
                    for key in list(item.keys())[:10]:  # Show first 10 fields
                        print(f"  {key}: {repr(item.get(key, ''))[:100]}")
        
        else:
            print("Data is not an array, cannot analyze items")
            
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        print("File might not be valid JSON")
    except Exception as e:
        print(f"Error analyzing file: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Default test path
        file_path = input("Enter path to backlinks JSON/gzipped file: ")
    
    analyze_backlinks_json(file_path)