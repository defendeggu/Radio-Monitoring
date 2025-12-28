#!/usr/bin/env python3
"""
Migration script to import existing JSON transcriptions into PostgreSQL
"""

import os
import json
import glob
from datetime import datetime
from database_service import get_database_service


def migrate_recordings(recordings_dir: str = './recordings'):
    """
    Migrate all JSON files from recordings directory to database

    Args:
        recordings_dir: Path to recordings directory
    """
    db = get_database_service()

    # Find all JSON files
    json_files = glob.glob(os.path.join(recordings_dir, '*.json'))

    print(f"Found {len(json_files)} JSON files to migrate")

    migrated = 0
    skipped = 0
    errors = 0

    for json_file in json_files:
        try:
            # Skip placeholder
            if 'placeholder' in json_file:
                continue

            # Read JSON file
            with open(json_file, 'r') as f:
                data = json.load(f)

            # Get corresponding audio file
            audio_file = json_file.replace('.json', '.wav')
            if not os.path.exists(audio_file):
                print(f"Warning: Audio file not found for {json_file}")
                skipped += 1
                continue

            # Extract filename timestamp
            filename = os.path.basename(json_file)
            # Format: capture_20251228_161053.json
            if filename.startswith('capture_'):
                timestamp_str = filename.replace('capture_', '').replace('.json', '')
                try:
                    # Parse timestamp from filename
                    created_at = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                except ValueError:
                    created_at = datetime.fromtimestamp(os.path.getctime(json_file))
            else:
                created_at = datetime.fromtimestamp(os.path.getctime(json_file))

            # Get file size
            file_size = os.path.getsize(audio_file)

            # Extract data from JSON
            # Since we don't have frequency/modulation in JSON, use defaults
            # In a real migration, you might parse this from filenames or metadata
            frequency = 100000000  # Default 100 MHz
            modulation = 'FM'  # Default
            duration = int(data.get('duration', 30))
            gain = 20  # Default

            transcription_text = data.get('text', '')
            language = data.get('language')
            language_confidence = data.get('language_probability')
            segments = data.get('segments', [])

            # Save to database
            capture_id = db.save_capture(
                frequency=frequency,
                modulation=modulation,
                duration=duration,
                gain=gain,
                audio_file_path=audio_file,
                json_file_path=json_file,
                file_size=file_size,
                transcription_text=transcription_text,
                language=language,
                language_confidence=language_confidence,
                segments=segments,
                metadata={
                    'migrated_from': json_file,
                    'original_timestamp': data.get('timestamp'),
                    'created_at_override': created_at.isoformat()
                }
            )

            if capture_id > 0:
                print(f"✓ Migrated: {filename} -> ID {capture_id}")
                migrated += 1
            else:
                print(f"✗ Failed to migrate: {filename}")
                errors += 1

        except Exception as e:
            print(f"✗ Error migrating {json_file}: {e}")
            errors += 1

    print(f"\n{'='*50}")
    print(f"Migration Complete!")
    print(f"{'='*50}")
    print(f"Migrated: {migrated}")
    print(f"Skipped:  {skipped}")
    print(f"Errors:   {errors}")
    print(f"Total:    {len(json_files)}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migrate JSON transcriptions to database')
    parser.add_argument(
        '--recordings-dir',
        type=str,
        default='./recordings',
        help='Path to recordings directory'
    )

    args = parser.parse_args()

    print("Starting migration...")
    print(f"Recordings directory: {args.recordings_dir}")
    print()

    migrate_recordings(args.recordings_dir)
