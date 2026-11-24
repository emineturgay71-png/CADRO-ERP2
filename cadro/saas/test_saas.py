"""Tests for the CADRO control-plane modules.

Run from the repository root:
    python -m unittest cadro.saas.test_saas -v
"""

from __future__ import annotations

import sys
import tempfile
import types
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from cadro.saas import db, manage_tenant, provision_site, subscription, tenant
from cadro.saas.tenant import PlanTier, TenantStatus, utcnow, validate_site_name


class ControlPlaneTestCase(unittest.TestCase):
    """Each test runs against its own control-plane database."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = patch.object(db, "DB_PATH", Path(self._tmp.name) / "control_plane.db")
        patcher.start()
        self.addCleanup(patcher.stop)


class TestSiteName(unittest.TestCase):
    def test_accepts_plain_host_names(self):
        for name in ("cadro-pilot.localhost", "tenant1.example.com", "a", "a1"):
            self.assertEqual(validate_site_name(name), name)

    def test_rejects_anything_else(self):
        for name in ("", "-rf", "Tenant.example.com", "a b", "a;b", "a/../b", "a_b", "x" * 300, None):
            with self.assertRaises(ValueError, msg=repr(name)):
                validate_site_name(name)


class TestTenantRegistry(ControlPlaneTestCase):
    def test_new_tenant_is_a_trial_with_plan_quota(self):
        record = db.create_tenant("a.example.com", PlanTier.PROFESSIONAL)
        self.assertEqual(record.status, TenantStatus.TRIAL)
        self.assertEqual(record.quota.max_users, 20)
        self.assertTrue(record.can_access())
        # The stored record round-trips with timezone-aware timestamps.
        stored = db.get_tenant("a.example.com")
        self.assertIsNotNone(stored.trial_ends_at.tzinfo)
        self.assertTrue(stored.can_access())

    def test_duplicate_site_is_refused(self):
        db.create_tenant("a.example.com")
        with self.assertRaises(ValueError):
            db.create_tenant("a.example.com")

    def test_expired_trial_loses_access(self):
        db.create_tenant("a.example.com")
        with patch.object(tenant, "utcnow", return_value=utcnow() + timedelta(days=15)):
            self.assertFalse(db.get_tenant("a.example.com").can_access())

    def test_status_changes_control_access(self):
        db.create_tenant("a.example.com")
        db.set_tenant_status("a.example.com", TenantStatus.ACTIVE)
        self.assertTrue(db.get_tenant("a.example.com").can_access())
        db.set_tenant_status("a.example.com", TenantStatus.SUSPENDED)
        self.assertFalse(db.get_tenant("a.example.com").can_access())
        with self.assertRaises(PermissionError):
            tenant.enforce_tenant_active("a.example.com")

    def test_unknown_site(self):
        self.assertIsNone(tenant.tenant_from_site("nobody.example.com"))
        tenant.enforce_tenant_active("nobody.example.com")  # left to the framework's 404
        with self.assertRaises(LookupError):
            db.set_tenant_status("nobody.example.com", TenantStatus.ACTIVE)

    def test_list_filters_by_status(self):
        db.create_tenant("a.example.com")
        db.create_tenant("b.example.com")
        db.set_tenant_status("b.example.com", TenantStatus.ACTIVE)
        self.assertEqual([t.site_name for t in db.list_tenants(TenantStatus.ACTIVE)], ["b.example.com"])
        self.assertEqual(len(db.list_tenants()), 2)


class TestManageTenant(ControlPlaneTestCase):
    def run_manage(self, action, site="a.example.com"):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(manage_tenant.subprocess, "run", fake_run):
            getattr(manage_tenant, action)(site)
        return calls

    def test_suspend_touches_only_the_tenant_site(self):
        db.create_tenant("a.example.com")
        calls = self.run_manage("suspend")
        flat = [" ".join(call) for call in calls]
        self.assertTrue(all("--site a.example.com" in call for call in flat), flat)
        self.assertFalse(any(" -g " in f" {call} " for call in flat), flat)
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.SUSPENDED)

    def test_reactivate_and_offboard_update_the_registry(self):
        db.create_tenant("a.example.com")
        self.run_manage("suspend")
        self.run_manage("reactivate")
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.ACTIVE)
        calls = self.run_manage("offboard")
        self.assertIn("drop-site", calls[0])
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.CANCELLED)

    def test_unregistered_site_is_still_managed(self):
        self.run_manage("suspend", site="manual.example.com")

    def test_invalid_site_never_reaches_bench(self):
        with patch.object(manage_tenant.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                manage_tenant.suspend("-g")
            run.assert_not_called()

    def test_bench_failure_is_reported_and_registry_unchanged(self):
        db.create_tenant("a.example.com")

        def failing_run(command, **kwargs):
            return types.SimpleNamespace(returncode=1, stdout="", stderr="boom")

        with patch.object(manage_tenant.subprocess, "run", failing_run):
            with self.assertRaises(RuntimeError):
                manage_tenant.suspend("a.example.com")
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.TRIAL)

    def test_offboard_needs_the_site_name_as_confirmation(self):
        db.create_tenant("a.example.com")
        with patch.object(sys, "argv", ["manage_tenant", "--site", "a.example.com", "--action", "offboard", "--confirm", "YES"]):
            with patch.object(manage_tenant.subprocess, "run") as run:
                with self.assertRaises(SystemExit):
                    manage_tenant.main()
                run.assert_not_called()


class TestProvisionSite(ControlPlaneTestCase):
    def test_refuses_a_bench_that_is_not_at_the_pins(self):
        with patch.object(provision_site, "installed_commit", return_value="0" * 40):
            with self.assertRaises(RuntimeError):
                provision_site.provision("a.example.com", "pw", "dbpw", PlanTier.STARTER)
        self.assertIsNone(db.get_tenant("a.example.com"))

    def test_registers_the_tenant_after_creating_the_site(self):
        commands = []

        def fake_bench(*args, check=True):
            commands.append(args)
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(provision_site, "installed_commit", side_effect=lambda bench_path, app: provision_site.resolve_commit(app)), \
                patch.object(provision_site, "bench", fake_bench):
            provision_site.provision("a.example.com", "pw", "dbpw", PlanTier.ENTERPRISE)
        self.assertEqual(commands[0][0], "new-site")
        self.assertNotIn("-g", [part for command in commands for part in command])
        self.assertEqual(db.get_tenant("a.example.com").quota.max_companies, 10)

    def test_invalid_site_and_duplicates_are_refused(self):
        with self.assertRaises(ValueError):
            provision_site.provision("A b", "pw", "dbpw", PlanTier.STARTER)
        db.create_tenant("a.example.com")
        with patch.object(provision_site, "installed_commit", side_effect=lambda bench_path, app: provision_site.resolve_commit(app)):
            with self.assertRaises(RuntimeError):
                provision_site.provision("a.example.com", "pw", "dbpw", PlanTier.STARTER)


class TestSubscription(ControlPlaneTestCase):
    def test_grace_period_and_suspension_rules(self):
        now = utcnow()
        state = subscription.SubscriptionState(TenantStatus.ACTIVE, "starter", payment_failed_since=now - timedelta(days=3))
        self.assertTrue(state.is_grace_period)
        self.assertFalse(state.should_suspend)
        state.payment_failed_since = now - timedelta(days=8)
        self.assertTrue(state.should_suspend)
        trial = subscription.SubscriptionState(TenantStatus.TRIAL, "starter", trial_ends_at=now - timedelta(days=1))
        self.assertTrue(trial.should_suspend)

    def test_decorator_blocks_a_suspended_tenant(self):
        db.create_tenant("a.example.com")
        db.set_tenant_status("a.example.com", TenantStatus.SUSPENDED)

        class Thrown(Exception):
            pass

        def throw(message, title=None):
            raise Thrown(message)

        fake_frappe = types.SimpleNamespace(local=types.SimpleNamespace(site="a.example.com"), throw=throw, _=lambda text: text)

        @subscription.require_active_subscription
        def endpoint():
            return "ok"

        with patch.dict(sys.modules, {"frappe": fake_frappe}):
            with self.assertRaises(Thrown):
                endpoint()
            db.set_tenant_status("a.example.com", TenantStatus.ACTIVE)
            self.assertEqual(endpoint(), "ok")


if __name__ == "__main__":
    unittest.main()
