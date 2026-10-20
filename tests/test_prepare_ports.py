"""Offline regression tests: no Docker, real .env, network or services needed."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_ports", ROOT / "scripts/prepare_ports.py")
ports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ports)


class PortPreparationTests(unittest.TestCase):
    def test_foreign_docker_and_busy_fallback_are_skipped(self):
        result = ports.allocate({3000, 8080}, {}, set(), {3000, 13000}, lambda p: p != 13001)
        self.assertEqual(result, {3000: 13002, 8080: 8080})

    def test_running_project_reuses_saved_ports(self):
        result = ports.allocate({3000, 8080}, {3000: 13000}, {13000, 8080}, {13000, 8080}, lambda p: False)
        self.assertEqual(result, {3000: 13000, 8080: 8080})

    def test_copied_pc_reallocates_busy_saved_port(self):
        result = ports.allocate({3000}, {3000: 13000}, set(), {13000}, lambda p: True)
        self.assertEqual(result[3000], 13001)

    def test_does_not_steal_another_running_service_port(self):
        result = ports.allocate({3000, 8080}, {8080: 13000}, {13000}, {3000, 13000}, lambda p: True)
        self.assertEqual(result, {3000: 13001, 8080: 13000})

    def test_reject_invalid_port_and_exhaustion(self):
        with self.assertRaises(RuntimeError):
            ports.allocate({3000}, {3000: 70000}, set(), set())
        with self.assertRaises(RuntimeError):
            ports.allocate({3000}, {}, set(), set(), lambda p: False)

    def test_full_preparation_and_restart_on_fixture_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "it/supabase").mkdir(parents=True)
            for path in ("compose.yaml", "it/supabase/config.toml"):
                (root / path).write_text((ROOT / path).read_text(encoding="utf-8"), encoding="utf-8")
            (root / ".env").write_text(
                "LLM_API_KEY=fixture-only-secret\n"
                "SUPABASE_DSN=postgresql://postgres:postgres@host.docker.internal:54322/postgres\n"
                "ENTERPRISE_READ_DSN=postgresql://reader:password@host.docker.internal:54322/postgres\n"
                "EFFECTS_SMTP_PORT=54325\n"
                "MCP_HOST_REWRITE=neo4j:7687=127.0.0.1:7687,dmn-mcp:8198=127.0.0.1:8198\n", encoding="utf-8")
            occupied = {3000, 13000, 8080, 8088, 54322, 54325, 7687, 8198}
            with patch.object(ports, "docker_ports", return_value=(set(), occupied)), \
                 patch.object(ports, "available", return_value=True), patch("builtins.print") as output:
                # The probe default is explicitly replaced to avoid binding ports.
                original = ports.allocate
                with patch.object(ports, "allocate", side_effect=lambda a, b, c, d: original(a, b, c, d, lambda p: True)):
                    ports.prepare(root)
            mapping = {int(p): q for p, q in json.loads((root / ".hyd-runtime/ports.json").read_text()).items()}
            self.assertEqual(mapping[3000], 13001)
            self.assertEqual(mapping[8088], 18088)
            self.assertEqual(mapping[54322], 64322)
            self.assertEqual(mapping[54325], 64325)
            self.assertEqual(len(mapping.values()), len(set(mapping.values())))
            env = ports.env_values((root / ".env").read_text())
            self.assertEqual(env["LLM_API_KEY"], "fixture-only-secret")
            self.assertIn(":64322/postgres", env["SUPABASE_DSN"])
            self.assertIn(":64322/postgres", env["ENTERPRISE_READ_DSN"])
            self.assertEqual(env["EFFECTS_SMTP_PORT"], "64325")
            self.assertIn("neo4j:7687=127.0.0.1:17687", env["MCP_HOST_REWRITE"])
            self.assertIn("localhost:18088/", env["HYD_MCP_OAUTH_CALLBACK_URL"])
            config = (root / "it/supabase/config.toml").read_text(encoding="utf-8")
            self.assertEqual(ports.config_ports(config)[54322], 64322)
            self.assertIn('site_url = "http://localhost:18088"', config)
            self.assertNotIn("fixture-only-secret", str(output.call_args_list))
            self.assertNotIn(b"\r", (root / ".env").read_bytes())
            # Running own containers retain the same mapping on the next start.
            own = set(mapping.values())
            with patch.object(ports, "docker_ports", return_value=(own, own)), patch("builtins.print"):
                with patch.object(ports, "allocate", side_effect=lambda a, b, c, d: original(a, b, c, d, lambda p: False)):
                    ports.prepare(root)
            self.assertEqual(json.loads((root / ".hyd-runtime/ports.json").read_text()), {str(k): v for k, v in mapping.items()})

    def test_preserves_remote_custom_dsn(self):
        remote = "postgresql://reader:password@db.example.org:54322/postgres"
        self.assertEqual(ports.rewrite_url(remote, {54322: 64322}), remote)

    def test_ownership_checks_project_and_directory_not_docker_process_name(self):
        def container(name, label, workdir, port):
            return {"Name": name, "Config": {"Labels": {
                "com.docker.compose.project": label,
                "com.docker.compose.project.working_dir": workdir,
            }}, "NetworkSettings": {"Ports": {"80/tcp": [{"HostPort": str(port)}]}}}
        containers = [container("/hyd-portal", "hyd-iot-edu", ROOT.as_posix(), 8088),
                      container("/foreign", "other", ROOT.as_posix(), 3000),
                      container("/other-checkout", "hyd-iot-edu", "/another-checkout", 8080),
                      container("/supabase_db_hyd-portal-latest", "", "", 54322)]
        with patch.object(ports.subprocess, "check_output", side_effect=["id1 id2 id3 id4", json.dumps(containers)]):
            owned, occupied = ports.docker_ports(ROOT, "hyd-portal-latest")
        self.assertEqual(owned, {8088, 54322})
        self.assertEqual(occupied, {8088, 3000, 8080, 54322})


if __name__ == "__main__":
    unittest.main()
