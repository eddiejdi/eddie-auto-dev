#!/usr/bin/env python3
"""
Variables Catalog Report Generator
Creates human-readable reports from catalog.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

class CatalogReporter:
    """Generate various reports from variables catalog."""
    
    def __init__(self, catalog_path: str = ".variables-catalog/catalog.json"):
        self.catalog_path = Path(catalog_path)
        self.catalog = self._load_catalog()
    
    def _load_catalog(self) -> Dict:
        """Load catalog from JSON."""
        if not self.catalog_path.exists():
            raise FileNotFoundError(f"Catalog not found at {self.catalog_path}")
        
        with open(self.catalog_path) as f:
            return json.load(f)
    
    def generate_markdown_report(self, output_file: str = None) -> str:
        """Generate comprehensive markdown report."""
        if output_file is None:
            output_file = self.catalog_path.parent / "CATALOG_REPORT.md"
        else:
            output_file = Path(output_file)
        
        report = []
        report.append("# Homelab Variables Catalog Report\n")
        report.append(f"**Generated:** {self.catalog['generatedAt']}\n")
        report.append(f"**Total Variables:** {self.catalog['metadata']['totalVariables']}\n")
        report.append(f"**Source Files:** {len(self.catalog['metadata']['sourceFiles'])}\n")
        report.append("---\n")
        
        # Summary by category
        report.append("## 📊 Summary by Category\n")
        for category, variables in sorted(self.catalog['categories'].items()):
            report.append(f"### {category.capitalize()} ({len(variables)} variables)\n")
            
            # List top 10 variables in category
            top_vars = sorted(variables.items())[:10]
            for var_name, var_data in top_vars:
                var_type = var_data.get('type', 'unknown')
                sensitive = "🔒" if var_data.get('sensitive', False) else "✓"
                report.append(f"- `{var_name}` ({var_type}) {sensitive}\n")
            
            if len(variables) > 10:
                report.append(f"  ... and {len(variables) - 10} more\n")
            report.append("\n")
        
        # Sensitive variables summary
        report.append("## 🔐 Sensitive Variables Summary\n")
        sensitive_vars = []
        for category, variables in self.catalog['categories'].items():
            for var_name, var_data in variables.items():
                if var_data.get('sensitive', False):
                    sensitive_vars.append((var_name, category))
        
        report.append(f"Total sensitive variables: **{len(sensitive_vars)}**\n\n")
        for var_name, category in sorted(sensitive_vars)[:20]:
            report.append(f"- `{var_name}` (in {category})\n")
        
        if len(sensitive_vars) > 20:
            report.append(f"\n... and {len(sensitive_vars) - 20} more sensitive variables\n")
        
        report.append("\n---\n")
        report.append("## 📚 Full Variable Count\n\n")
        
        # Detailed category breakdown
        for category in sorted(self.catalog['categories'].keys()):
            variables = self.catalog['categories'][category]
            count = len(variables)
            report.append(f"| {category.capitalize()} | {count} |\n")
        
        # Write to file
        output_file.write_text("".join(report))
        print(f"✅ Report saved to: {output_file}")
        
        return "".join(report)
    
    def generate_csv_report(self, output_file: str = None) -> str:
        """Generate CSV export of variables."""
        if output_file is None:
            output_file = self.catalog_path.parent / "catalog.csv"
        else:
            output_file = Path(output_file)
        
        lines = ["variable_name,type,category,sensitive,source,contexts"]
        
        for category, variables in self.catalog['categories'].items():
            for var_name, var_data in variables.items():
                contexts = ";".join(var_data.get('contexts', []))
                sensitive = "yes" if var_data.get('sensitive', False) else "no"
                source = var_data.get('source', 'unknown')
                var_type = var_data.get('type', 'unknown')
                
                line = f'{var_name},{var_type},{category},{sensitive},{source},"{contexts}"'
                lines.append(line)
        
        output_file.write_text("\n".join(lines))
        print(f"✅ CSV report saved to: {output_file}")
        
        return "\n".join(lines)
    
    def generate_service_report(self, output_file: str = None) -> str:
        """Generate per-service variable breakdown."""
        if output_file is None:
            output_file = self.catalog_path.parent / "SERVICE_VARIABLES.md"
        else:
            output_file = Path(output_file)
        
        # Group by context/service
        services = {}
        for category, variables in self.catalog['categories'].items():
            for var_name, var_data in variables.items():
                contexts = var_data.get('contexts', [])
                for context in contexts:
                    if context not in services:
                        services[context] = []
                    services[context].append({
                        'name': var_name,
                        'type': var_data.get('type', 'unknown'),
                        'category': category,
                        'sensitive': var_data.get('sensitive', False),
                    })
        
        report = []
        report.append("# Service Variables Breakdown\n\n")
        
        for service in sorted(services.keys()):
            vars_list = services[service]
            report.append(f"## {service} ({len(vars_list)} variables)\n\n")
            
            # Group by category
            by_category = {}
            for var_info in vars_list:
                cat = var_info['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(var_info)
            
            for category in sorted(by_category.keys()):
                report.append(f"### {category.capitalize()} ({len(by_category[category])})\n")
                for var_info in sorted(by_category[category], key=lambda x: x['name']):
                    lock = "🔒" if var_info['sensitive'] else "✓"
                    report.append(f"- `{var_info['name']}` ({var_info['type']}) {lock}\n")
                report.append("\n")
        
        output_file.write_text("".join(report))
        print(f"✅ Service report saved to: {output_file}")
        
        return "".join(report)
    
    def print_stats(self):
        """Print catalog statistics."""
        print("\n" + "="*70)
        print("📊 CATALOG STATISTICS")
        print("="*70)
        
        total_vars = self.catalog['metadata']['totalVariables']
        print(f"Total variables: {total_vars}")
        
        # By category
        print("\nVariables by category:")
        for category in sorted(self.catalog['categories'].keys()):
            count = len(self.catalog['categories'][category])
            percentage = (count / total_vars * 100) if total_vars > 0 else 0
            print(f"  {category:20} {count:4} ({percentage:5.1f}%)")
        
        # Sensitive variables
        sensitive_count = 0
        for category, variables in self.catalog['categories'].items():
            for var_data in variables.values():
                if var_data.get('sensitive', False):
                    sensitive_count += 1
        
        print(f"\nSensitive variables: {sensitive_count} ({sensitive_count/total_vars*100:.1f}%)")
        
        # By type
        print("\nVariables by type:")
        types = {}
        for category, variables in self.catalog['categories'].items():
            for var_data in variables.values():
                var_type = var_data.get('type', 'unknown')
                types[var_type] = types.get(var_type, 0) + 1
        
        for var_type in sorted(types.keys(), key=lambda x: types[x], reverse=True):
            count = types[var_type]
            percentage = (count / total_vars * 100) if total_vars > 0 else 0
            print(f"  {var_type:20} {count:4} ({percentage:5.1f}%)")
        
        # Source files
        print(f"\nSource files scanned: {len(self.catalog['metadata']['sourceFiles'])}")
        
        print("="*70 + "\n")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate reports from variables catalog")
    parser.add_argument("--catalog", default=".variables-catalog/catalog.json",
                       help="Path to catalog.json")
    parser.add_argument("--markdown", action="store_true", help="Generate markdown report")
    parser.add_argument("--csv", action="store_true", help="Generate CSV report")
    parser.add_argument("--services", action="store_true", help="Generate service breakdown")
    parser.add_argument("--stats", action="store_true", help="Print statistics")
    parser.add_argument("--all", action="store_true", help="Generate all reports")
    parser.add_argument("--output-dir", default=".variables-catalog",
                       help="Output directory for reports")
    
    args = parser.parse_args()
    
    try:
        reporter = CatalogReporter(args.catalog)
        
        if args.all or (not args.markdown and not args.csv and not args.services and not args.stats):
            args.markdown = args.csv = args.services = args.stats = True
        
        if args.markdown:
            reporter.generate_markdown_report(f"{args.output_dir}/CATALOG_REPORT.md")
        
        if args.csv:
            reporter.generate_csv_report(f"{args.output_dir}/catalog.csv")
        
        if args.services:
            reporter.generate_service_report(f"{args.output_dir}/SERVICE_VARIABLES.md")
        
        if args.stats:
            reporter.print_stats()
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
