#!/usr/bin/env python3
"""
Cross-Report Analysis Tool for Pawly Blackbox Multiturn Tests

This script performs deep comparison analysis across multiple test reports,
identifying agreements, disagreements, root causes, and generating actionable insights.

Usage:
    python compare_reports.py [test_type] [--versions v1,v2,v3] [--disagreements-only] [--summary]

Examples:
    python compare_reports.py                    # Analyze all test types
    python compare_reports.py ethics             # Analyze only ethics reports
    python compare_reports.py --disagreements-only  # Show only disagreement cases
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime
from collections import defaultdict
import statistics


class ReportComparator:
    """Main class for cross-report analysis"""

    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.reports_by_type = defaultdict(list)
        self.analysis_results = {}

    def discover_reports(self) -> Dict[str, List[Path]]:
        """Discover and group all JSON reports by test type"""
        all_reports = list(self.results_dir.glob("*.json"))

        for report_path in all_reports:
            # Extract test type from filename
            # e.g., multiturn_ethics_report.json -> ethics
            name = report_path.stem
            if name.startswith("multiturn_"):
                parts = name.replace("multiturn_", "").split("_report")
                test_type = parts[0]
                self.reports_by_type[test_type].append(report_path)

        return dict(self.reports_by_type)

    def load_report(self, report_path: Path) -> Dict[str, Any]:
        """Load a single JSON report"""
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading {report_path.name}: {e}")
            return None

    def analyze_test_type(self, test_type: str, report_paths: List[Path]) -> Dict[str, Any]:
        """Perform cross-report analysis for a single test type"""
        print(f"\n📊 Analyzing {test_type} reports...")

        # Load all reports
        reports = []
        for path in report_paths:
            report = self.load_report(path)
            if report:
                reports.append({
                    'path': path,
                    'name': path.stem,
                    'data': report
                })

        if len(reports) < 2:
            print(f"⚠️  Only {len(reports)} report found for {test_type}, need at least 2 for comparison")
            return None

        print(f"   Found {len(reports)} reports to compare")

        # Build case index: case_name -> [results from each report]
        case_index = defaultdict(list)

        for report in reports:
            for case in report['data'].get('cases', []):
                case_index[case['name']].append({
                    'report_name': report['name'],
                    'score': case['score'],
                    'threshold': case['threshold'],
                    'status': case['status'],
                    'reason': case.get('reason', ''),
                    'turn_count': case.get('turn_count', 0)
                })

        # Analyze each case
        agreements = []
        disagreements = []
        unanimous_pass = []
        unanimous_fail = []

        for case_name, case_results in case_index.items():
            if len(case_results) != len(reports):
                continue  # Skip cases not present in all reports

            scores = [cr['score'] for cr in case_results]
            statuses = [cr['status'] for cr in case_results]
            threshold = case_results[0]['threshold']

            # Calculate agreement
            if all(s == 'passed_threshold' for s in statuses):
                unanimous_pass.append(case_name)
                agreements.append(case_name)
            elif all(s == 'below_threshold' for s in statuses):
                unanimous_fail.append(case_name)
                agreements.append(case_name)
            else:
                # Disagreement detected
                mean_score = statistics.mean(scores)
                std_dev = statistics.stdev(scores) if len(scores) > 1 else 0
                cv = (std_dev / mean_score) if mean_score > 0 else 0

                disagreements.append({
                    'case_name': case_name,
                    'threshold': threshold,
                    'scores': scores,
                    'statuses': statuses,
                    'case_results': case_results,
                    'mean': mean_score,
                    'std_dev': std_dev,
                    'cv': cv,
                    'min': min(scores),
                    'max': max(scores)
                })

        return {
            'test_type': test_type,
            'report_count': len(reports),
            'report_names': [r['name'] for r in reports],
            'total_cases': len(case_index),
            'agreements': agreements,
            'unanimous_pass': unanimous_pass,
            'unanimous_fail': unanimous_fail,
            'disagreements': disagreements,
            'agreement_rate': len(agreements) / len(case_index) if case_index else 0
        }

    def generate_markdown_report(self, analysis: Dict[str, Any], output_path: Path):
        """Generate detailed markdown report"""
        test_type = analysis['test_type']

        md_lines = []
        md_lines.append(f"# Cross-Report Analysis: {test_type}")
        md_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Executive Summary
        md_lines.append("## 📊 Executive Summary\n")
        md_lines.append(f"- **Total Cases:** {analysis['total_cases']}")
        md_lines.append(f"- **Reports Compared:** {analysis['report_count']}")
        md_lines.append(f"- **Agreement Rate:** {analysis['agreement_rate']:.1%}")
        md_lines.append(f"- **Unanimous Pass:** {len(analysis['unanimous_pass'])} cases")
        md_lines.append(f"- **Unanimous Fail:** {len(analysis['unanimous_fail'])} cases")
        md_lines.append(f"- **Disagreements:** {len(analysis['disagreements'])} cases")

        critical_issues = sum(1 for d in analysis['disagreements'] if d['cv'] > 0.3)
        md_lines.append(f"- **Critical Issues (CV > 0.3):** {critical_issues}\n")

        # Agreement Matrix
        md_lines.append("## 🎯 Agreement Matrix\n")
        md_lines.append("| Case Name | " + " | ".join(analysis['report_names']) + " | Status |")
        md_lines.append("|" + "---|" * (len(analysis['report_names']) + 2))

        # Show unanimous pass (top 5)
        for case_name in analysis['unanimous_pass'][:5]:
            md_lines.append(f"| {case_name[:40]}... | " + " | ".join(["✅"] * analysis['report_count']) + " | Unanimous Pass |")

        # Show unanimous fail (top 5)
        for case_name in analysis['unanimous_fail'][:5]:
            md_lines.append(f"| {case_name[:40]}... | " + " | ".join(["❌"] * analysis['report_count']) + " | Unanimous Fail |")

        # Show disagreements
        for disagreement in analysis['disagreements'][:5]:
            case_name = disagreement['case_name'][:40]
            score_cells = []
            for i, (score, status) in enumerate(zip(disagreement['scores'], disagreement['statuses'])):
                icon = "✅" if status == 'passed_threshold' else "❌"
                score_cells.append(f"{icon} {score:.2f}")
            md_lines.append(f"| {case_name}... | " + " | ".join(score_cells) + " | ⚠️ Disagreement |")

        md_lines.append("")

        # Detailed Disagreement Analysis
        if analysis['disagreements']:
            md_lines.append("## 🔍 Disagreement Deep Dive\n")

            for i, disagreement in enumerate(analysis['disagreements'], 1):
                md_lines.append(f"### {i}. {disagreement['case_name']}")
                md_lines.append(f"**Status:** ⚠️ Disagreement (threshold: {disagreement['threshold']})\n")

                md_lines.append("**Score Distribution:**")
                for cr in disagreement['case_results']:
                    icon = "✅" if cr['status'] == 'passed_threshold' else "❌"
                    md_lines.append(f"- {cr['report_name']}: {cr['score']:.2f} {icon}")

                md_lines.append(f"- **Mean:** {disagreement['mean']:.2f}")
                md_lines.append(f"- **StdDev:** {disagreement['std_dev']:.2f}")
                md_lines.append(f"- **CV (Coefficient of Variation):** {disagreement['cv']:.2f}")
                md_lines.append(f"- **Range:** [{disagreement['min']:.2f}, {disagreement['max']:.2f}]\n")

                md_lines.append("**Failure Reasons:**")
                for cr in disagreement['case_results']:
                    status_text = "PASS" if cr['status'] == 'passed_threshold' else "FAIL"
                    reason_preview = cr['reason'][:150] + "..." if len(cr['reason']) > 150 else cr['reason']
                    md_lines.append(f"- **{cr['report_name']}** ({status_text}): {reason_preview}\n")

                # Root Cause Hypothesis
                md_lines.append("**Root Cause Hypothesis:**")
                if disagreement['cv'] > 0.3:
                    md_lines.append("🔴 **HIGH VARIANCE** - This case shows significant inconsistency.")
                    md_lines.append("Possible causes:")
                    md_lines.append("- Evaluator instruction ambiguity")
                    md_lines.append("- Model output non-determinism in edge cases")
                    md_lines.append("- Different evaluation focus across reports")
                elif disagreement['cv'] > 0.15:
                    md_lines.append("🟡 **MODERATE VARIANCE** - Some inconsistency present.")
                    md_lines.append("This case may be borderline and sensitive to evaluation criteria interpretation.")
                else:
                    md_lines.append("🟢 **LOW VARIANCE** - Scores are close but span the threshold.")
                    md_lines.append("This is likely a borderline case where small evaluation differences matter.")

                md_lines.append("")

                # Confidence Assessment
                md_lines.append("**Confidence Assessment:**")
                pass_count = sum(1 for s in disagreement['statuses'] if s == 'passed_threshold')
                fail_count = len(disagreement['statuses']) - pass_count

                if pass_count > fail_count:
                    md_lines.append(f"🟢 Majority says PASS ({pass_count}/{len(disagreement['statuses'])})")
                    md_lines.append("Recommendation: Likely a valid pass, but review minority failures for edge cases.")
                else:
                    md_lines.append(f"🔴 Majority says FAIL ({fail_count}/{len(disagreement['statuses'])})")
                    md_lines.append("Recommendation: Likely a valid failure, investigate why some reports passed.")

                md_lines.append("\n---\n")

        # Pattern Analysis
        md_lines.append("## 📈 Pattern Analysis\n")

        if analysis['disagreements']:
            high_variance = [d for d in analysis['disagreements'] if d['cv'] > 0.3]
            medium_variance = [d for d in analysis['disagreements'] if 0.15 < d['cv'] <= 0.3]
            low_variance = [d for d in analysis['disagreements'] if d['cv'] <= 0.15]

            md_lines.append("### Variance Distribution")
            md_lines.append(f"- **High Variance (CV > 0.3):** {len(high_variance)} cases - Requires investigation")
            md_lines.append(f"- **Medium Variance (0.15 < CV ≤ 0.3):** {len(medium_variance)} cases - Acceptable but monitor")
            md_lines.append(f"- **Low Variance (CV ≤ 0.15):** {len(low_variance)} cases - Good consistency\n")

        # Actionable Insights
        md_lines.append("## 🎯 Actionable Insights\n")

        if analysis['disagreements']:
            # Critical issues
            critical = [d for d in analysis['disagreements'] if d['cv'] > 0.3]
            if critical:
                md_lines.append("### 🔴 Critical (High Variance)")
                for d in critical[:3]:
                    md_lines.append(f"- **{d['case_name']}**")
                    md_lines.append(f"  - CV: {d['cv']:.2f}, Score range: [{d['min']:.2f}, {d['max']:.2f}]")
                    md_lines.append(f"  - Action: Manual review required, evaluation criteria may be unclear\n")

            # Important issues
            borderline = [d for d in analysis['disagreements']
                         if d['cv'] <= 0.3 and abs(d['mean'] - d['threshold']) < 0.1]
            if borderline:
                md_lines.append("### 🟡 Important (Borderline Cases)")
                for d in borderline[:3]:
                    md_lines.append(f"- **{d['case_name']}**")
                    md_lines.append(f"  - Mean: {d['mean']:.2f}, Threshold: {d['threshold']:.2f}")
                    md_lines.append(f"  - Action: Consider threshold adjustment or model improvement\n")

        # Summary Statistics
        md_lines.append("## 📋 Summary Statistics\n")
        md_lines.append(f"**Agreement Rate by Category:**")
        total = analysis['total_cases']
        if total > 0:
            md_lines.append(f"- Unanimous Pass: {len(analysis['unanimous_pass'])/total:.1%}")
            md_lines.append(f"- Unanimous Fail: {len(analysis['unanimous_fail'])/total:.1%}")
            md_lines.append(f"- Disagreement: {len(analysis['disagreements'])/total:.1%}\n")

        # Data sources
        md_lines.append("## 🔬 Data Sources\n")
        for report_name in analysis['report_names']:
            md_lines.append(f"- {report_name}")

        md_lines.append(f"\n---\n*Generated by Pawly Cross-Report Comparator*")

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))

        print(f"✅ Markdown report saved to: {output_path}")

    def print_summary(self, analysis: Dict[str, Any]):
        """Print console summary"""
        print(f"\n{'='*70}")
        print(f"  {analysis['test_type'].upper()} - Cross-Report Analysis Summary")
        print(f"{'='*70}")
        print(f"Reports compared: {analysis['report_count']}")
        print(f"Total cases: {analysis['total_cases']}")
        print(f"Agreement rate: {analysis['agreement_rate']:.1%}")
        print(f"\n✅ Unanimous Pass: {len(analysis['unanimous_pass'])} cases")
        print(f"❌ Unanimous Fail: {len(analysis['unanimous_fail'])} cases")
        print(f"⚠️  Disagreements: {len(analysis['disagreements'])} cases")

        if analysis['disagreements']:
            critical = sum(1 for d in analysis['disagreements'] if d['cv'] > 0.3)
            if critical > 0:
                print(f"\n🔴 CRITICAL: {critical} high-variance disagreements detected!")

        print(f"{'='*70}\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Cross-Report Analysis Tool')
    parser.add_argument('test_type', nargs='?', help='Test type to analyze (ethics, hallucination, etc.)')
    parser.add_argument('--disagreements-only', action='store_true', help='Show only disagreement cases')
    parser.add_argument('--summary', action='store_true', help='Show only summary')

    args = parser.parse_args()

    # Determine results directory
    script_dir = Path(__file__).parent
    results_dir = script_dir / 'tests' / 'blackbox_multiturn' / 'results'

    if not results_dir.exists():
        # Try from Pawly root
        results_dir = Path.cwd() / 'tests' / 'blackbox_multiturn' / 'results'

    if not results_dir.exists():
        print(f"❌ Error: Cannot find results directory at {results_dir}")
        sys.exit(1)

    print(f"📂 Scanning: {results_dir}")

    comparator = ReportComparator(results_dir)
    reports_by_type = comparator.discover_reports()

    if not reports_by_type:
        print("❌ No reports found!")
        sys.exit(1)

    print(f"\n📊 Found test types: {', '.join(reports_by_type.keys())}")

    # Filter by test type if specified
    if args.test_type:
        if args.test_type not in reports_by_type:
            print(f"❌ Test type '{args.test_type}' not found!")
            sys.exit(1)
        test_types_to_analyze = [args.test_type]
    else:
        test_types_to_analyze = list(reports_by_type.keys())

    # Analyze each test type
    for test_type in test_types_to_analyze:
        report_paths = reports_by_type[test_type]
        analysis = comparator.analyze_test_type(test_type, report_paths)

        if analysis:
            # Generate markdown report
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = results_dir / f'cross_report_analysis_{test_type}_{timestamp}.md'
            comparator.generate_markdown_report(analysis, output_path)

            # Print summary
            if not args.summary:
                comparator.print_summary(analysis)


if __name__ == '__main__':
    main()
