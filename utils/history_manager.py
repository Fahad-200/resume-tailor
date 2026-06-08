"""
History Manager - Manages version history of generated resumes.
Stores history as JSON files and keeps only the last 10 entries.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional


def save(session_data: Dict[str, Any], history_dir: str = "history", 
         outputs_dir: str = "outputs", max_entries: int = 10) -> str:
    """
    Save a new history entry.
    
    Args:
        session_data: The data to save (must include required fields)
        history_dir: Directory for history JSON files
        outputs_dir: Directory for output PDFs
        max_entries: Maximum number of history entries to keep
        
    Returns:
        The history_id (UUID)
    """
    os.makedirs(history_dir, exist_ok=True)
    
    # Generate UUID
    history_id = str(uuid.uuid4())
    
    # Add metadata
    session_data["history_id"] = history_id
    session_data["timestamp"] = datetime.now().isoformat()
    
    # Save to JSON file
    filepath = os.path.join(history_dir, f"{history_id}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, indent=2)
    
    # Cleanup old entries
    cleanup_old_entries(history_dir, outputs_dir, max_entries)
    
    return history_id


def get_all(history_dir: str = "history") -> List[Dict[str, Any]]:
    """
    Get all history entries, sorted by timestamp descending.
    
    Args:
        history_dir: Directory containing history JSON files
        
    Returns:
        List of history entries
    """
    os.makedirs(history_dir, exist_ok=True)
    
    entries = []
    
    # Read all JSON files
    for filename in os.listdir(history_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(history_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    entry = json.load(f)
                    entries.append(entry)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error reading history file {filename}: {e}")
    
    # Sort by timestamp descending
    entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return entries


def get(history_id: str, history_dir: str = "history") -> Optional[Dict[str, Any]]:
    """
    Get a specific history entry by ID.
    
    Args:
        history_id: The history UUID
        history_dir: Directory containing history JSON files
        
    Returns:
        The history entry or None if not found
    """
    filepath = os.path.join(history_dir, f"{history_id}.json")
    
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading history file: {e}")
        return None


def delete(history_id: str, history_dir: str = "history", 
           outputs_dir: str = "outputs") -> bool:
    """
    Delete a history entry and its associated output file.
    
    Args:
        history_id: The history UUID
        history_dir: Directory containing history JSON files
        outputs_dir: Directory containing output PDFs
        
    Returns:
        True if successful, False otherwise
    """
    entry = get(history_id, history_dir)

    # Delete JSON file
    json_filepath = os.path.join(history_dir, f"{history_id}.json")
    if os.path.exists(json_filepath):
        try:
            os.remove(json_filepath)
        except OSError as e:
            print(f"Error deleting history file: {e}")
            return False
    
    # Get output file ID and delete PDF
    if entry and entry.get("output_file_id"):
        output_filepath = os.path.join(outputs_dir, f"{entry['output_file_id']}.pdf")
        if os.path.exists(output_filepath):
            try:
                os.remove(output_filepath)
            except OSError as e:
                print(f"Error deleting output file: {e}")
    
    return True


def cleanup_old_entries(history_dir: str = "history", outputs_dir: str = "outputs",
                        max_entries: int = 10) -> None:
    """
    Remove old history entries beyond max_entries.
    Deletes both the JSON file and associated output PDF.
    
    Args:
        history_dir: Directory containing history JSON files
        outputs_dir: Directory containing output PDFs
        max_entries: Maximum number of entries to keep
    """
    entries = get_all(history_dir)
    
    if len(entries) <= max_entries:
        return
    
    # Get entries to delete (all beyond max_entries)
    to_delete = entries[max_entries:]
    
    for entry in to_delete:
        history_id = entry.get("history_id")
        if history_id:
            # Delete JSON
            json_path = os.path.join(history_dir, f"{history_id}.json")
            if os.path.exists(json_path):
                try:
                    os.remove(json_path)
                except OSError:
                    pass
            
            # Delete output PDF
            output_id = entry.get("output_file_id")
            if output_id:
                output_path = os.path.join(outputs_dir, f"{output_id}.pdf")
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except OSError:
                        pass


# For testing
if __name__ == "__main__":
    # Test basic operations
    import shutil
    
    test_dir = "test_history"
    test_output = "test_outputs"
    os.makedirs(test_dir, exist_ok=True)
    os.makedirs(test_output, exist_ok=True)
    
    # Test save
    data = {
        "job_title": "Software Engineer",
        "company_name": "Tech Corp",
        "ats_score_before": 45,
        "ats_score_after": 82,
        "output_file_id": "test-123",
        "file_id": "orig-123"
    }
    
    hid = save(data, test_dir, test_output)
    print(f"Saved: {hid}")
    
    # Test get_all
    entries = get_all(test_dir)
    print(f"Entries: {len(entries)}")
    
    # Test delete
    delete(hid, test_dir, test_output)
    entries = get_all(test_dir)
    print(f"After delete: {len(entries)}")
    
    # Cleanup
    shutil.rmtree(test_dir)
    shutil.rmtree(test_output)
