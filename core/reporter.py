"""Report generator for test results."""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import jinja2

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate test reports in various formats."""
    
    def __init__(self, output_dir: str = "result/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_json_report(self, results: List[Dict[str, Any]], filename: str = None) -> str:
        """Generate JSON format report."""
        if not filename:
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report_path = self.output_dir / filename
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': self._calculate_summary(results),
            'results': results
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"JSON report generated: {report_path}")
        return str(report_path)
    
    def generate_html_report(self, results: List[Dict[str, Any]], filename: str = None) -> str:
        """Generate HTML format report."""
        if not filename:
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        report_path = self.output_dir / filename
        
        summary = self._calculate_summary(results)
        
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>NIC Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .summary { background: #f0f0f0; padding: 15px; margin-bottom: 20px; }
        .passed { color: green; }
        .failed { color: red; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>NIC稳定性测试报告</h1>
    <div class="summary">
        <h2>测试摘要</h2>
        <p>生成时间: {{ generated_at }}</p>
        <p>总用例数: {{ summary.total }}</p>
        <p>通过: <span class="passed">{{ summary.passed }}</span></p>
        <p>失败: <span class="failed">{{ summary.failed }}</span></p>
        <p>通过率: {{ "%.2f" % (summary.pass_rate * 100) }}%</p>
    </div>
    <table>
        <tr>
            <th>用例ID</th>
            <th>用例名称</th>
            <th>状态</th>
            <th>详情</th>
        </tr>
        {% for result in results %}
        <tr>
            <td>{{ result.get('test_id', 'N/A') }}</td>
            <td>{{ result.get('test_name', 'N/A') }}</td>
            <td class="{% if result.get('passed') %}passed{% else %}failed{% endif %}">
                {{ "通过" if result.get('passed') else "失败" }}
            </td>
            <td>{{ result.get('error', '-') if not result.get('passed') else '-' }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""
        
        template = jinja2.Template(html_template)
        html_content = template.render(
            results=results,
            summary=summary,
            generated_at=datetime.now().isoformat()
        )
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {report_path}")
        return str(report_path)
    
    def _calculate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate test summary statistics."""
        total = len(results)
        passed = sum(1 for r in results if r.get('passed', False))
        failed = total - passed
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': passed / total if total > 0 else 0.0
        }
