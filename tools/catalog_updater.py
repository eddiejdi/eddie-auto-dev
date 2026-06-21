#!/usr/bin/env python3
"""
Variables Catalog Updater Service
Automatically updates the catalog and syncs changes to homelab
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from subprocess import run, CalledProcessError
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CatalogUpdater:
    """Manages catalog updates and synchronization."""
    
    def __init__(self, project_root: str = "/workspace/eddie-auto-dev"):
        self.project_root = Path(project_root)
        self.catalog_dir = self.project_root / ".variables-catalog"
        self.catalog_file = self.catalog_dir / "catalog.json"
        
    def check_git_status(self) -> bool:
        """Check if there are uncommitted changes."""
        try:
            result = run(
                ["git", "status", "--porcelain"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True
            )
            return len(result.stdout.strip()) > 0
        except Exception as e:
            logger.error(f"Error checking git status: {e}")
            return False
    
    def load_catalog(self) -> dict:
        """Load existing catalog."""
        if self.catalog_file.exists():
            with open(self.catalog_file) as f:
                return json.load(f)
        return {}
    
    def detect_changes(self) -> dict:
        """Detect changes in environment variables."""
        old_catalog = self.load_catalog()
        
        # Run scanner
        logger.info("Running variables scanner...")
        try:
            result = run(
                ["python3", "tools/catalog_variables.py"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"Scanner error: {result.stderr}")
                return {}
            
            logger.info(result.stdout)
        except CalledProcessError as e:
            logger.error(f"Scanner failed: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {}
        
        # Compare catalogs
        new_catalog = self.load_catalog()
        
        if not old_catalog:
            logger.info("Initial catalog generation")
            return {"type": "initial", "new_variables": len(new_catalog.get('metadata', {}).get('totalVariables', 0))}
        
        old_count = old_catalog.get('metadata', {}).get('totalVariables', 0)
        new_count = new_catalog.get('metadata', {}).get('totalVariables', 0)
        
        changes = {
            'added': new_count - old_count if new_count > old_count else 0,
            'removed': old_count - new_count if old_count > new_count else 0,
            'modified': False
        }
        
        # Check if content changed significantly
        old_gen = old_catalog.get('generatedAt', '')
        new_gen = new_catalog.get('generatedAt', '')
        
        if old_gen != new_gen:
            changes['modified'] = True
        
        return changes
    
    def generate_reports(self):
        """Generate all reports."""
        logger.info("Generating reports...")
        try:
            result = run(
                ["python3", "tools/catalog_reporter.py", "--all"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info("Reports generated successfully")
                return True
            else:
                logger.error(f"Report generation error: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error generating reports: {e}")
            return False
    
    def commit_changes(self, message: str) -> bool:
        """Commit catalog changes to git."""
        try:
            # Stage catalog files
            run(
                ["git", "add", ".variables-catalog/", "docs/variables-taxonomy/"],
                cwd=str(self.project_root),
                check=True,
                capture_output=True
            )
            
            # Check if there's anything to commit
            result = run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(self.project_root),
                capture_output=True
            )
            
            if result.returncode == 0:
                logger.info("No changes to commit")
                return False
            
            # Commit
            run(
                ["git", "commit", "-m", message],
                cwd=str(self.project_root),
                check=True,
                capture_output=True
            )
            
            logger.info(f"Committed: {message}")
            return True
        except CalledProcessError as e:
            logger.error(f"Git commit failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Error committing changes: {e}")
            return False
    
    def sync_to_homelab(self) -> bool:
        """Push changes to homelab."""
        try:
            run(
                ["git", "push", "-q"],
                cwd=str(self.project_root),
                timeout=30,
                capture_output=True
            )
            logger.info("Pushed changes to remote")
            return True
        except Exception as e:
            logger.warning(f"Could not push to remote: {e}")
            return False
    
    def notify_bus(self, message: dict):
        """Publish update notification to Communication Bus."""
        try:
            # Import here to avoid circular dependencies
            sys.path.insert(0, str(self.project_root))
            from specialized_agents.agent_communication_bus import AgentCommunicationBus
            
            bus = AgentCommunicationBus()
            bus.publish_message({
                "type": "variables_updated",
                "timestamp": datetime.now().isoformat(),
                **message
            })
            logger.info("Notified Communication Bus about catalog update")
            return True
        except Exception as e:
            logger.warning(f"Could not notify bus: {e}")
            return False
    
    def run(self, commit: bool = True, sync: bool = False):
        """Run the complete update process."""
        logger.info("=" * 70)
        logger.info("🔄 VARIABLES CATALOG UPDATER")
        logger.info("=" * 70)
        
        # Detect changes
        changes = self.detect_changes()
        
        if not changes:
            logger.info("No changes detected")
            return
        
        logger.info(f"Changes detected: {changes}")
        
        # Generate reports
        if self.generate_reports():
            logger.info("✅ Reports generated")
        else:
            logger.warning("⚠️  Report generation failed")
        
        # Commit if requested
        if commit:
            message = "chore: update variables catalog"
            if changes.get('added', 0) > 0:
                message += f" (+{changes['added']} variables)"
            if changes.get('removed', 0) > 0:
                message += f" (-{changes['removed']} variables)"
            
            if self.commit_changes(message):
                logger.info("✅ Changes committed")
                
                # Sync if requested
                if sync and self.sync_to_homelab():
                    logger.info("✅ Changes synced to remote")
        
        # Notify bus
        self.notify_bus(changes)
        
        logger.info("=" * 70)
        logger.info("✅ Catalog update complete")
        logger.info("=" * 70)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Update variables catalog")
    parser.add_argument("--no-commit", action="store_true", help="Skip git commit")
    parser.add_argument("--sync", action="store_true", help="Sync to remote")
    parser.add_argument("--project", default="/workspace/eddie-auto-dev",
                       help="Project root directory")
    parser.add_argument("--loop", type=int, help="Run in loop every N seconds")
    
    args = parser.parse_args()
    
    updater = CatalogUpdater(args.project)
    
    if args.loop:
        logger.info(f"Starting loop mode: update every {args.loop} seconds")
        try:
            while True:
                updater.run(commit=not args.no_commit, sync=args.sync)
                logger.info(f"Sleeping for {args.loop} seconds...")
                time.sleep(args.loop)
        except KeyboardInterrupt:
            logger.info("Stopped by user")
    else:
        updater.run(commit=not args.no_commit, sync=args.sync)


if __name__ == "__main__":
    main()
