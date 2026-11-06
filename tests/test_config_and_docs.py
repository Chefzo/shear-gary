import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from gary.config import EXPECTED_MODULE_IDS, load_modules, load_settings
from gary.errors import ConfigError, UnsafePath
from gary.paths import assert_safe_data_dir, repo_root


class ConfigAndDocsTests(unittest.TestCase):
    def test_example_config_is_safe(self) -> None:
        settings = load_settings()
        self.assertEqual(settings.adapter_name, "mock")
        self.assertFalse(settings.bluebubbles_enabled)
        self.assertTrue(settings.require_human)
        text = Path(settings.config_path).read_text(encoding="utf-8")
        self.assertNotIn("password", text.lower())
        self.assertNotIn("token", text.lower())
        self.assertNotIn("http", text.lower())

    def test_secret_key_and_unattended_mode_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secret = Path(tmp) / "secret.toml"
            secret.write_text(
                "\n".join(
                    [
                        "[gary]",
                        'name = "gary"',
                        "[adapter]",
                        'name = "mock"',
                        "[bluebubbles]",
                        "enabled = false",
                        'password = "nope"',
                        "[approvals]",
                        "require_human = true",
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                load_settings(secret)

            unattended = Path(tmp) / "off.toml"
            unattended.write_text(
                Path(repo_root() / "config" / "gary.example.toml").read_text(encoding="utf-8").replace(
                    "require_human = true", "require_human = false"
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                load_settings(unattended)

    def test_eight_modules_and_only_maintenance_runs(self) -> None:
        modules = load_modules()
        self.assertEqual(tuple(spec.id for spec in modules), EXPECTED_MODULE_IDS)
        self.assertEqual([spec.id for spec in modules if spec.runnable], ["maintenance"])
        website = next(spec for spec in modules if spec.id == "website_rebuild")
        self.assertEqual(website.workflow, "docs_only")
        for spec in modules:
            self.assertIn("outbound_contact", spec.human_gates)
            self.assertIn("spend", spec.human_gates)
        maintenance = modules[0]
        self.assertIn("emergency_decision", maintenance.human_gates)

    def test_source_note_labels_user_supplied_facts(self) -> None:
        text = (repo_root() / "config" / "modules.toml").read_text(encoding="utf-8")
        self.assertIn("user-supplied", text.lower())
        self.assertIn("not independently verified", text.lower())

    def test_docs_keep_install_boxes_open_and_label_facts(self) -> None:
        root = repo_root()
        setup = (root / "docs" / "SETUP-GUIDE.md").read_text(encoding="utf-8")
        mind = (root / "docs" / "shear-galleria-ops-mindmap.md").read_text(encoding="utf-8")
        sitemap = (root / "docs" / "website" / "sitemap.md").read_text(encoding="utf-8")
        copy = (root / "docs" / "website" / "copy.md").read_text(encoding="utf-8")
        self.assertNotIn("- [x]", setup)
        self.assertIn("- [ ]", setup)
        self.assertIn("user-supplied", mind.lower())
        self.assertIn("not independently verified", mind.lower())
        self.assertIn("Unpublished", sitemap)
        self.assertIn("Do not publish", copy)
        self.assertIn("$75/month", copy)
        self.assertNotIn("Crown: $", copy)

    def test_code_and_config_do_not_embed_send_targets_or_secret_assignments(self) -> None:
        root = repo_root()
        blob = []
        for folder in ("gary", "config"):
            for path in (root / folder).rglob("*"):
                if path.suffix not in {".py", ".toml"} or not path.is_file():
                    continue
                blob.append(path.read_text(encoding="utf-8"))
        text = "\n".join(blob)
        self.assertIsNone(re.search(r"\+1[\s-]*502|\+1[\s-]*623|502-341-4647|623-206-3101", text))
        self.assertIsNone(
            re.search(
                r"(?i)(password|api_key|secret|token)\s*[:=]\s*['\"][^'\"]+['\"]",
                text,
            )
        )
        imports = re.findall(
            r"(?m)^\s*(?:import|from)\s+([a-zA-Z0-9_\.]+)",
            text,
        )
        banned = {"urllib", "http", "httpx", "requests", "socket", "aiohttp", "subprocess", "smtplib", "imaplib"}
        for name in imports:
            self.assertNotIn(name.split(".")[0], banned)

    def test_data_dir_guard_and_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            allowed = assert_safe_data_dir(Path(tmp) / "data")
            self.assertTrue(str(allowed).startswith(str(Path(tmp).resolve())))
        with self.assertRaises(UnsafePath):
            assert_safe_data_dir(Path("/"))
        with self.assertRaises(UnsafePath):
            assert_safe_data_dir(Path("/etc/gary-data"))
        result = subprocess.run(
            ["git", "check-ignore", "-q", "data/gary.sqlite"],
            cwd=repo_root(),
            check=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_readme_has_m1_commands(self) -> None:
        readme = (repo_root() / "README.md").read_text(encoding="utf-8")
        self.assertIn("python3 -m unittest discover -s tests -v", readme)
        self.assertIn("python3 -m gary demo", readme)
        self.assertIn("python3 -m gary config-check", readme)
        self.assertIn("Python 3.11", readme)


if __name__ == "__main__":
    unittest.main()
