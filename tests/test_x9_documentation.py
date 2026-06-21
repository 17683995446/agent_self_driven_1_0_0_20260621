"""
X9：文档体验完善测试

验证文档体验完善：
1. docs/deploy_user/README.md 索引所有文档（M11）
2. troubleshooting.md 有错误码对照表（M12）
3. --help 有 epilog 示例和文档链接（M13）
4. FAQ.md 存在并合并了分散的 FAQ（L5）
5. configuration.md FAQ 不再有过时的"静默默认配置"描述

第一性原理：文档应完整、准确、易于发现；CLI 帮助应提供示例
"""

import pytest
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path("/workspace/self_driven_agent")
DOCS_DIR = PROJECT_ROOT / "docs" / "deploy_user"


class TestX9ReadmeIndex:
    """测试 README.md 索引完整（M11）"""

    def test_readme_exists(self):
        """README.md 存在"""
        assert (DOCS_DIR / "README.md").is_file()

    def test_readme_indexes_quick_start(self):
        """README 索引 quick_start.md"""
        content = (DOCS_DIR / "README.md").read_text()
        assert "quick_start.md" in content

    def test_readme_indexes_setup(self):
        """README 索引 setup.md"""
        content = (DOCS_DIR / "README.md").read_text()
        assert "setup.md" in content

    def test_readme_indexes_concepts(self):
        """README 索引 concepts.md"""
        content = (DOCS_DIR / "README.md").read_text()
        assert "concepts.md" in content

    def test_readme_indexes_configuration(self):
        """README 索引 configuration.md"""
        content = (DOCS_DIR / "README.md").read_text()
        assert "configuration.md" in content

    def test_readme_indexes_monitoring(self):
        """README 索引 monitoring.md"""
        content = (DOCS_DIR / "README.md").read_text()
        assert "monitoring.md" in content

    def test_readme_indexes_troubleshooting(self):
        """README 索引 troubleshooting.md"""
        content = (DOCS_DIR / "README.md").read_text()
        assert "troubleshooting.md" in content

    def test_readme_indexes_faq(self):
        """README 索引 FAQ.md"""
        content = (DOCS_DIR / "README.md").read_text()
        assert "FAQ.md" in content

    def test_readme_indexes_testing(self):
        """README 索引 testing.md"""
        content = (DOCS_DIR / "README.md").read_text()
        assert "testing.md" in content

    def test_readme_has_reading_path(self):
        """README 有推荐阅读路径"""
        content = (DOCS_DIR / "README.md").read_text()
        assert "阅读路径" in content or "reading path" in content.lower()

    def test_readme_has_command_cheatsheet(self):
        """README 有命令速查"""
        content = (DOCS_DIR / "README.md").read_text()
        assert "速查" in content or "cheat" in content.lower()


class TestX9TroubleshootingErrorCodes:
    """测试 troubleshooting.md 错误码对照表（M12）"""

    def test_troubleshooting_exists(self):
        """troubleshooting.md 存在"""
        assert (DOCS_DIR / "troubleshooting.md").is_file()

    def test_has_error_code_table(self):
        """有错误码对照表"""
        content = (DOCS_DIR / "troubleshooting.md").read_text()
        assert "错误码对照表" in content or "错误码" in content

    def test_has_config_not_found_code(self):
        """有 config_not_found 错误码（200003）"""
        content = (DOCS_DIR / "troubleshooting.md").read_text()
        assert "200003" in content
        assert "config_not_found" in content

    def test_has_parameter_range_error_code(self):
        """有 parameter_range_error 错误码（100004）"""
        content = (DOCS_DIR / "troubleshooting.md").read_text()
        assert "100004" in content
        assert "parameter_range_error" in content

    def test_has_resource_codes(self):
        """有资源类错误码（3xxxxx）"""
        content = (DOCS_DIR / "troubleshooting.md").read_text()
        assert "300001" in content or "resource_cpu" in content

    def test_has_task_codes(self):
        """有任务类错误码（5xxxxx）"""
        content = (DOCS_DIR / "troubleshooting.md").read_text()
        assert "500001" in content or "task_execute" in content

    def test_has_solution_column(self):
        """错误码表有解决方案列"""
        content = (DOCS_DIR / "troubleshooting.md").read_text()
        assert "解决方案" in content

    def test_has_log_analysis_section(self):
        """有日志分析章节"""
        content = (DOCS_DIR / "troubleshooting.md").read_text()
        assert "日志分析" in content or "日志位置" in content

    def test_has_diagnostic_commands(self):
        """有诊断命令章节"""
        content = (DOCS_DIR / "troubleshooting.md").read_text()
        assert "诊断命令" in content or "诊断" in content

    def test_has_graceful_shutdown_section(self):
        """有优雅停机排查章节"""
        content = (DOCS_DIR / "troubleshooting.md").read_text()
        assert "优雅停机" in content or "停机" in content


class TestX9HelpEpilog:
    """测试 --help epilog 示例与文档链接（M13）"""

    def test_help_has_examples(self):
        """--help 输出有示例"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "示例" in result.stdout or "example" in result.stdout.lower()

    def test_help_has_env_example(self):
        """--help 有 --env 示例"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "--env dev" in result.stdout

    def test_help_has_dry_run_example(self):
        """--help 有 --dry-run 示例"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "--dry-run" in result.stdout

    def test_help_has_status_example(self):
        """--help 有 --status 示例"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "--status" in result.stdout

    def test_help_has_doc_links(self):
        """--help 有文档链接"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "docs/deploy_user" in result.stdout

    def test_help_has_troubleshooting_link(self):
        """--help 有故障排查文档链接"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "troubleshooting" in result.stdout

    def test_help_has_faq_link(self):
        """--help 有 FAQ 文档链接"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert "FAQ" in result.stdout

    def test_help_exit_code_zero(self):
        """--help 退出码为 0"""
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0


class TestX9FAQ:
    """测试独立 FAQ.md（L5）"""

    def test_faq_exists(self):
        """FAQ.md 存在"""
        assert (DOCS_DIR / "FAQ.md").is_file()

    def test_faq_has_install_section(self):
        """FAQ 有安装类章节"""
        content = (DOCS_DIR / "FAQ.md").read_text()
        assert "安装" in content

    def test_faq_has_config_section(self):
        """FAQ 有配置类章节"""
        content = (DOCS_DIR / "FAQ.md").read_text()
        assert "配置" in content

    def test_faq_has_runtime_section(self):
        """FAQ 有运行类章节"""
        content = (DOCS_DIR / "FAQ.md").read_text()
        assert "运行" in content

    def test_faq_has_performance_section(self):
        """FAQ 有性能类章节"""
        content = (DOCS_DIR / "FAQ.md").read_text()
        assert "性能" in content

    def test_faq_has_log_section(self):
        """FAQ 有日志与监控类章节"""
        content = (DOCS_DIR / "FAQ.md").read_text()
        assert "日志" in content or "监控" in content

    def test_faq_merges_config_not_found_question(self):
        """FAQ 合并了"配置文件不存在"问题"""
        content = (DOCS_DIR / "FAQ.md").read_text()
        assert "配置文件不存在" in content

    def test_faq_config_not_found_no_silent_fallback(self):
        """FAQ 中配置文件不存在不再描述为静默默认配置（X2/X3 已修复）"""
        content = (DOCS_DIR / "FAQ.md").read_text()
        # 找到"配置文件不存在"段落
        idx = content.find("配置文件不存在")
        assert idx >= 0
        # 取该问题后的 500 字符检查
        section = content[idx:idx + 500]
        # 不应有过时的肯定式描述"打印警告并使用内置默认配置"
        assert "打印警告并使用内置默认配置" not in section
        # 应描述新的正确行为（抛出 ValidationError / 错误码 200003）
        assert "ValidationError" in section or "200003" in section

    def test_faq_has_multiple_questions(self):
        """FAQ 有多个问题（至少 10 个 Q:）"""
        content = (DOCS_DIR / "FAQ.md").read_text()
        q_count = content.count("### Q:")
        assert q_count >= 10, f"FAQ 应至少有 10 个问题，实际 {q_count} 个"


class TestX9ConfigurationFaqAccuracy:
    """测试 configuration.md FAQ 准确性（不再有过时描述）"""

    def test_configuration_faq_no_silent_default(self):
        """configuration.md FAQ 不再描述"静默使用默认配置"（X2/X3 已修复）"""
        content = (DOCS_DIR / "configuration.md").read_text()
        idx = content.find("配置文件不存在")
        assert idx >= 0
        section = content[idx:idx + 500]
        # 不应有过时的肯定式描述
        assert "打印警告并使用内置默认配置" not in section
        assert "系统会打印警告并使用内置默认配置" not in section

    def test_configuration_faq_mentions_error_code(self):
        """configuration.md FAQ 提及错误码或 ValidationError"""
        content = (DOCS_DIR / "configuration.md").read_text()
        idx = content.find("配置文件不存在")
        section = content[idx:idx + 500]
        assert "ValidationError" in section or "200003" in section

    def test_configuration_faq_links_to_faq(self):
        """configuration.md FAQ 链接到独立 FAQ.md"""
        content = (DOCS_DIR / "configuration.md").read_text()
        assert "FAQ.md" in content


class TestX9DocConsistency:
    """测试文档一致性"""

    def test_all_indexed_docs_exist(self):
        """README 索引的所有文档都存在"""
        readme = (DOCS_DIR / "README.md").read_text()
        import re
        # 提取所有 .md 链接
        linked = re.findall(r'\(([^)]+\.md)\)', readme)
        for link in linked:
            doc_path = DOCS_DIR / link
            assert doc_path.is_file(), f"README 索引的文档不存在: {link}"

    def test_faq_links_to_troubleshooting(self):
        """FAQ 链接到 troubleshooting.md"""
        content = (DOCS_DIR / "FAQ.md").read_text()
        assert "troubleshooting.md" in content

    def test_troubleshooting_links_to_configuration(self):
        """troubleshooting 链接到 configuration.md"""
        content = (DOCS_DIR / "troubleshooting.md").read_text()
        assert "configuration.md" in content
