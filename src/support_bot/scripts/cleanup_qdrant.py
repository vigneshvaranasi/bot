"""
Clean up Qdrant vector database collections.

This script provides utilities to delete specific collections or all collections
from the Qdrant vector database.
"""

import os
import argparse
from typing import List, Optional

from dotenv import load_dotenv

try:
    from qdrant_client import QdrantClient
    QDRANT_AVAILABLE = True
except ImportError:
    print("Qdrant client not available. Please install with: uv add qdrant-client")
    QDRANT_AVAILABLE = False


def cleanup_qdrant_collections(
    collection_names: Optional[List[str]] = None,
    delete_all: bool = False,
    dry_run: bool = False
) -> bool:
    """
    Clean up Qdrant collections.
    
    Args:
        collection_names: List of collection names to delete
        delete_all: Whether to delete all collections
        dry_run: If True, only show what would be deleted
    
    Returns:
        True if successful, False otherwise
    """
    if not QDRANT_AVAILABLE:
        print("❌ Qdrant client not available. Cannot proceed.")
        return False
        
    load_dotenv()
    
    qdrant_url = os.getenv('QDRANT_URL')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')
    
    if not qdrant_url or not qdrant_api_key:
        print("❌ Error: QDRANT_URL and QDRANT_API_KEY must be set in .env file")
        return False
    
    print(f"🔗 Connecting to Qdrant at {qdrant_url}")
    
    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    except Exception as e:
        print(f"❌ Failed to connect to Qdrant: {e}")
        return False
    
    try:
        # Get all existing collections
        collections_response = client.get_collections()
        existing_collections = [col.name for col in collections_response.collections]
        
        if not existing_collections:
            print("ℹ️ No collections found in Qdrant database")
            return True
        
        print(f"📋 Found {len(existing_collections)} collections:")
        for col_name in existing_collections:
            print(f"   • {col_name}")
        
        # Determine which collections to delete
        if delete_all:
            collections_to_delete = existing_collections
        elif collection_names:
            collections_to_delete = [
                name for name in collection_names 
                if name in existing_collections
            ]
            
            # Warn about non-existent collections
            missing_collections = [
                name for name in collection_names 
                if name not in existing_collections
            ]
            if missing_collections:
                print(f"⚠️ Collections not found: {', '.join(missing_collections)}")
        else:
            # Default collections to clean up
            default_collections = ['incident_data', 'incident_data_gemini']
            collections_to_delete = [
                name for name in default_collections 
                if name in existing_collections
            ]
        
        if not collections_to_delete:
            print("ℹ️ No collections to delete")
            return True
        
        print(f"\n🗑️ {'Would delete' if dry_run else 'Deleting'} {len(collections_to_delete)} collections:")
        for col_name in collections_to_delete:
            print(f"   • {col_name}")
        
        if dry_run:
            print("\n🔍 Dry run mode - no actual deletions performed")
            return True
        
        # Confirm deletion
        if len(collections_to_delete) > 1 or delete_all:
            response = input(f"\n⚠️ Are you sure you want to delete {len(collections_to_delete)} collections? (y/N): ")
            if response.lower() not in ['y', 'yes']:
                print("❌ Deletion cancelled")
                return False
        
        # Delete collections
        success_count = 0
        for col_name in collections_to_delete:
            try:
                client.delete_collection(col_name)
                print(f"✅ Deleted collection: {col_name}")
                success_count += 1
            except Exception as e:
                print(f"❌ Failed to delete collection {col_name}: {e}")
        
        if success_count == len(collections_to_delete):
            print(f"\n🎉 Successfully deleted {success_count} collections!")
            return True
        else:
            print(f"\n⚠️ Deleted {success_count}/{len(collections_to_delete)} collections")
            return False
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        return False


def main():
    """Entry point for the cleanup-qdrant script."""
    parser = argparse.ArgumentParser(
        description='Clean up Qdrant vector database collections',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run cleanup-qdrant                                    # Clean default collections
  uv run cleanup-qdrant --collections incident_data       # Clean specific collection
  uv run cleanup-qdrant --all                             # Clean all collections
  uv run cleanup-qdrant --all --dry-run                   # Preview what would be deleted
        """
    )
    
    parser.add_argument(
        '--collections', 
        nargs='+',
        help='Collection names to delete'
    )
    parser.add_argument(
        '--all', 
        action='store_true',
        help='Delete all collections'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        print("🧹 Starting Qdrant cleanup process...")
        if args.all:
            print("   • Mode: Delete all collections")
        elif args.collections:
            print(f"   • Mode: Delete specific collections: {', '.join(args.collections)}")
        else:
            print("   • Mode: Delete default collections (incident_data, incident_data_gemini)")
        print(f"   • Dry run: {args.dry_run}")
    
    success = cleanup_qdrant_collections(
        collection_names=args.collections,
        delete_all=args.all,
        dry_run=args.dry_run
    )
    
    if success:
        print("✨ Cleanup completed successfully!")
        exit(0)
    else:
        print("💥 Cleanup failed!")
        exit(1)


if __name__ == "__main__":
    main()
