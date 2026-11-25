"""Tests for the CADRO control-plane modules.

Run from the repository root:
    python -m unittest cadro.saas.test_saas -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from cadro.saas import control_plane, db, manage_tenant, provision_site, subscription, tenant, webhook
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
        db.mark_exported("a.example.com")
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


class FakeActions:
    """Records what the control plane would do to sites, without running bench."""

    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def suspend(self, site):
        if self.fail_on == ("suspend", site):
            raise RuntimeError("bench is down")
        self.calls.append(("suspend", site))

    def reactivate(self, site):
        if self.fail_on == ("reactivate", site):
            raise RuntimeError("bench is down")
        self.calls.append(("reactivate", site))


def make_payload(event, event_id, site="a.example.com", **kwargs):
    fields = {"tenant_id": site.replace(".", "-"), "invoice_id": None, "amount": None, "currency": None}
    if event == webhook.WebhookEvent.PAYMENT_SUCCEEDED:
        fields.update(amount=250.0, currency="TRY")
    fields.update(kwargs)
    return webhook.WebhookPayload(event=event, event_id=event_id, site_name=site, **fields)


class TestWebhookHandling(ControlPlaneTestCase):
    E = webhook.WebhookEvent

    def setUp(self):
        super().setUp()
        self.actions = FakeActions()
        db.create_tenant("a.example.com")

    def handle(self, event, event_id, **kwargs):
        return webhook.handle_webhook(make_payload(event, event_id, **kwargs), self.actions)

    def status(self, site="a.example.com"):
        return db.get_tenant(site).status

    def test_first_payment_turns_a_trial_into_an_active_tenant(self):
        self.assertEqual(self.handle(self.E.PAYMENT_SUCCEEDED, "evt-1", invoice_id="INV-1"), "applied")
        self.assertEqual(self.status(), TenantStatus.ACTIVE)
        self.assertEqual(self.actions.calls, [])

    def test_redelivered_event_changes_nothing(self):
        self.handle(self.E.PAYMENT_SUCCEEDED, "evt-1", invoice_id="INV-1")
        db.set_tenant_status("a.example.com", TenantStatus.SUSPENDED)
        self.assertEqual(self.handle(self.E.PAYMENT_SUCCEEDED, "evt-1", invoice_id="INV-1"), "duplicate")
        self.assertEqual(self.status(), TenantStatus.SUSPENDED)
        self.assertEqual(self.actions.calls, [])

    def test_same_invoice_under_another_event_id_is_ignored(self):
        self.handle(self.E.PAYMENT_SUCCEEDED, "evt-1", invoice_id="INV-1")
        db.set_tenant_status("a.example.com", TenantStatus.SUSPENDED)
        self.assertEqual(self.handle(self.E.PAYMENT_SUCCEEDED, "evt-2", invoice_id="INV-1"), "ignored")
        self.assertEqual(self.status(), TenantStatus.SUSPENDED)

    def test_payment_reactivates_a_suspended_tenant_and_clears_the_failure(self):
        self.handle(self.E.PAYMENT_FAILED, "evt-1")
        db.set_tenant_status("a.example.com", TenantStatus.SUSPENDED)
        self.assertEqual(self.handle(self.E.PAYMENT_SUCCEEDED, "evt-2", invoice_id="INV-2"), "applied")
        self.assertEqual(self.actions.calls, [("reactivate", "a.example.com")])
        record = db.get_tenant("a.example.com")
        self.assertEqual(record.status, TenantStatus.ACTIVE)
        self.assertIsNone(record.payment_failed_since)

    def test_failed_payment_is_forgiven_during_grace_and_suspends_after_it(self):
        self.assertEqual(self.handle(self.E.PAYMENT_FAILED, "evt-1"), "grace")
        record = db.get_tenant("a.example.com")
        self.assertIsNotNone(record.payment_failed_since)
        self.assertEqual(self.actions.calls, [])

        # A retry two days later keeps the original start of the failure.
        self.assertEqual(self.handle(self.E.PAYMENT_FAILED, "evt-2"), "grace")
        self.assertEqual(db.get_tenant("a.example.com").payment_failed_since, record.payment_failed_since)

        db.set_payment_failed_since("a.example.com", utcnow() - timedelta(days=8))
        self.assertEqual(self.handle(self.E.PAYMENT_FAILED, "evt-3"), "suspended")
        self.assertEqual(self.actions.calls, [("suspend", "a.example.com")])
        self.assertEqual(self.status(), TenantStatus.SUSPENDED)

        # Further failures do not suspend the site a second time.
        self.assertEqual(self.handle(self.E.PAYMENT_FAILED, "evt-4"), "suspended")
        self.assertEqual(self.actions.calls, [("suspend", "a.example.com")])

    def test_cancellation_suspends_and_a_late_payment_cannot_revive_the_tenant(self):
        self.assertEqual(self.handle(self.E.SUBSCRIPTION_CANCELLED, "evt-1"), "applied")
        self.assertEqual(self.actions.calls, [("suspend", "a.example.com")])
        self.assertEqual(self.status(), TenantStatus.CANCELLED)
        self.assertEqual(self.handle(self.E.PAYMENT_SUCCEEDED, "evt-2", invoice_id="INV-9"), "ignored")
        self.assertEqual(self.status(), TenantStatus.CANCELLED)

    def test_informational_events_are_only_recorded(self):
        self.assertEqual(self.handle(self.E.TRIAL_ENDING, "evt-1"), "recorded")
        self.assertEqual(self.handle(self.E.SUBSCRIPTION_CREATED, "evt-2"), "recorded")
        self.assertEqual(self.status(), TenantStatus.TRIAL)

    def test_event_must_belong_to_the_tenant_it_names(self):
        db.create_tenant("b.example.com")
        with self.assertRaises(ValueError):
            webhook.handle_webhook(
                make_payload(self.E.PAYMENT_SUCCEEDED, "evt-1", tenant_id="b-example-com"), self.actions
            )
        self.assertEqual(self.status(), TenantStatus.TRIAL)
        # Nothing was claimed, so a corrected delivery of the same event still works.
        self.assertEqual(self.handle(self.E.PAYMENT_SUCCEEDED, "evt-1"), "applied")

    def test_unknown_site_and_bad_payloads(self):
        with self.assertRaises(LookupError):
            self.handle(self.E.PAYMENT_FAILED, "evt-1", site="nobody.example.com")
        with self.assertRaises(ValueError):
            self.handle(self.E.PAYMENT_FAILED, "")
        with self.assertRaises(ValueError):
            self.handle(self.E.PAYMENT_SUCCEEDED, "evt-2", amount=None)
        for amount in (0, -5, float("nan"), float("inf")):
            with self.assertRaises(ValueError, msg=str(amount)):
                self.handle(self.E.PAYMENT_SUCCEEDED, "evt-3", amount=amount)
        with self.assertRaises(ValueError):
            self.handle(self.E.PAYMENT_FAILED, "evt-4", site="A b")

    def test_failed_processing_releases_the_event_so_the_retry_is_handled(self):
        db.set_tenant_status("a.example.com", TenantStatus.SUSPENDED)
        self.actions.fail_on = ("reactivate", "a.example.com")
        with self.assertRaises(RuntimeError):
            self.handle(self.E.PAYMENT_SUCCEEDED, "evt-1", invoice_id="INV-1")
        self.assertEqual(self.status(), TenantStatus.SUSPENDED)

        self.actions.fail_on = None
        self.assertEqual(self.handle(self.E.PAYMENT_SUCCEEDED, "evt-1", invoice_id="INV-1"), "applied")
        self.assertEqual(self.status(), TenantStatus.ACTIVE)


class TestSweepOverdue(ControlPlaneTestCase):
    def age(self, site, trial_days=None):
        with db._connect() as conn:
            conn.execute(
                "UPDATE tenants SET trial_ends_at = ? WHERE site_name = ?",
                ((utcnow() - timedelta(days=trial_days)).isoformat(), site),
            )

    def test_suspends_only_tenants_that_are_overdue(self):
        for site in ("expired.example.com", "late.example.com", "fine.example.com", "paid.example.com"):
            db.create_tenant(site)
        self.age("expired.example.com", trial_days=1)
        db.set_tenant_status("late.example.com", TenantStatus.ACTIVE)
        db.set_payment_failed_since("late.example.com", utcnow() - timedelta(days=10))
        db.set_tenant_status("paid.example.com", TenantStatus.ACTIVE)
        db.set_payment_failed_since("paid.example.com", utcnow() - timedelta(days=2))

        actions = FakeActions()
        suspended = webhook.sweep_overdue(actions)

        self.assertEqual(sorted(suspended), ["expired.example.com", "late.example.com"])
        self.assertEqual(sorted(site for _, site in actions.calls), sorted(suspended))
        self.assertEqual(db.get_tenant("expired.example.com").status, TenantStatus.SUSPENDED)
        self.assertEqual(db.get_tenant("fine.example.com").status, TenantStatus.TRIAL)
        self.assertEqual(db.get_tenant("paid.example.com").status, TenantStatus.ACTIVE)
        self.assertEqual(webhook.sweep_overdue(actions), [])  # nothing left to do

    def test_one_failing_site_does_not_stop_the_others(self):
        for site in ("a.example.com", "b.example.com"):
            db.create_tenant(site)
            self.age(site, trial_days=1)
        actions = FakeActions(fail_on=("suspend", "a.example.com"))
        with self.assertLogs("cadro.saas.webhook", level="ERROR"):
            self.assertEqual(webhook.sweep_overdue(actions), ["b.example.com"])
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.TRIAL)


class TestRegistryMigration(ControlPlaneTestCase):
    def test_a_registry_from_before_the_payment_columns_is_upgraded(self):
        import sqlite3

        conn = sqlite3.connect(str(db.DB_PATH))
        conn.execute(
            "CREATE TABLE tenants (tenant_id TEXT PRIMARY KEY, site_name TEXT UNIQUE NOT NULL, plan TEXT NOT NULL DEFAULT 'starter', "
            "status TEXT NOT NULL DEFAULT 'trial', trial_ends_at TEXT, created_at TEXT NOT NULL, max_users INTEGER NOT NULL DEFAULT 5, "
            "max_companies INTEGER NOT NULL DEFAULT 1, max_storage_gb INTEGER NOT NULL DEFAULT 5, max_api_calls_per_minute INTEGER NOT NULL DEFAULT 300)"
        )
        conn.execute("INSERT INTO tenants (tenant_id, site_name, created_at) VALUES ('old-example-com', 'old.example.com', '2026-11-01T00:00:00+00:00')")
        conn.commit()
        conn.close()

        record = db.get_tenant("old.example.com")
        self.assertIsNone(record.payment_failed_since)
        db.set_payment_failed_since("old.example.com", utcnow())
        self.assertIsNotNone(db.get_tenant("old.example.com").payment_failed_since)


class TestExportBeforeOffboard(ControlPlaneTestCase):
    def fake_bench(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        return calls, patch.object(manage_tenant.subprocess, "run", fake_run)

    def test_offboard_is_refused_without_a_recent_export(self):
        db.create_tenant("a.example.com")
        calls, patcher = self.fake_bench()
        with patcher:
            with self.assertRaises(RuntimeError) as caught:
                manage_tenant.offboard("a.example.com")
        self.assertIn("export", str(caught.exception))
        self.assertEqual(calls, [])  # nothing was dropped
        self.assertNotEqual(db.get_tenant("a.example.com").status, TenantStatus.CANCELLED)

    def test_an_old_export_does_not_count(self):
        db.create_tenant("a.example.com")
        db.mark_exported("a.example.com", utcnow() - timedelta(days=manage_tenant.EXPORT_MAX_AGE_DAYS + 1))
        calls, patcher = self.fake_bench()
        with patcher:
            with self.assertRaises(RuntimeError):
                manage_tenant.offboard("a.example.com")
        self.assertEqual(calls, [])

    def test_export_backs_up_with_files_and_unlocks_offboarding(self):
        db.create_tenant("a.example.com")
        calls, patcher = self.fake_bench()
        with patcher:
            path = manage_tenant.export_tenant("a.example.com", self._tmp.name)
            self.assertTrue(Path(path).is_dir())
            self.assertIn("--with-files", calls[0])
            self.assertIn(path, calls[0])
            manage_tenant.offboard("a.example.com")
        self.assertIn("drop-site", calls[1])
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.CANCELLED)

    def test_skip_flag_and_unregistered_sites(self):
        calls, patcher = self.fake_bench()
        with patcher:
            with self.assertRaises(RuntimeError):
                manage_tenant.offboard("manual.example.com")  # unregistered: no export on record
            manage_tenant.offboard("manual.example.com", skip_export_check=True)
        self.assertEqual(len(calls), 1)

    def test_offboard_passes_the_db_root_password_from_the_secret_file(self):
        secret = Path(self._tmp.name) / "db_password"
        secret.write_text("s3cret\n", encoding="utf-8")
        db.create_tenant("a.example.com")
        db.mark_exported("a.example.com")
        calls, patcher = self.fake_bench()
        with patcher, patch.dict(manage_tenant.os.environ, {"DB_PASSWORD_FILE": str(secret)}):
            manage_tenant.offboard("a.example.com")
        self.assertEqual(calls[0][calls[0].index("--db-root-password") + 1], "s3cret")

    def test_failed_backup_records_no_export(self):
        db.create_tenant("a.example.com")

        def failing_run(command, **kwargs):
            return types.SimpleNamespace(returncode=1, stdout="", stderr="disk full")

        with patch.object(manage_tenant.subprocess, "run", failing_run):
            with self.assertRaises(RuntimeError):
                manage_tenant.export_tenant("a.example.com", self._tmp.name)
        self.assertIsNone(db.get_tenant("a.example.com").exported_at)


class TestPriceReconciliation(ControlPlaneTestCase):
    E = webhook.WebhookEvent

    def setUp(self):
        super().setUp()
        self.actions = FakeActions()
        db.create_tenant("a.example.com", PlanTier.PROFESSIONAL)
        db.set_plan_price(PlanTier.PROFESSIONAL, "try", 1500)

    def pay(self, event_id, amount, currency="TRY"):
        payload = make_payload(
            self.E.PAYMENT_SUCCEEDED, event_id, amount=amount, currency=currency, invoice_id=f"INV-{event_id}"
        )
        return webhook.handle_webhook(payload, self.actions)

    def test_the_exact_price_activates_the_tenant(self):
        self.assertEqual(self.pay("e1", 1500), "applied")
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.ACTIVE)

    def test_an_underpayment_is_flagged_and_does_not_activate(self):
        db.set_tenant_status("a.example.com", TenantStatus.SUSPENDED)
        with self.assertLogs("cadro.saas.webhook", level="WARNING"):
            self.assertEqual(self.pay("e1", 1000), "mismatch")
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.SUSPENDED)
        self.assertEqual(self.actions.calls, [])  # not reactivated
        self.assertEqual(db.count_webhook_outcomes(), {"mismatch": 1})

    def test_a_currency_without_a_price_is_flagged(self):
        with self.assertLogs("cadro.saas.webhook", level="WARNING"):
            self.assertEqual(self.pay("e1", 1500, currency="EUR"), "mismatch")
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.TRIAL)

    def test_a_flagged_invoice_can_still_be_paid_correctly_later(self):
        with self.assertLogs("cadro.saas.webhook", level="WARNING"):
            self.pay("e1", 1000)
        payload = make_payload(
            self.E.PAYMENT_SUCCEEDED, "e2", amount=1500, currency="TRY", invoice_id="INV-e1"
        )
        self.assertEqual(webhook.handle_webhook(payload, self.actions), "applied")

    def test_no_configured_price_means_no_check(self):
        db.create_tenant("b.example.com", PlanTier.STARTER)
        payload = make_payload(
            self.E.PAYMENT_SUCCEEDED, "e1", site="b.example.com", amount=1, currency="TRY", invoice_id="X"
        )
        self.assertEqual(webhook.handle_webhook(payload, self.actions), "applied")

    def test_price_validation(self):
        for amount in (0, -5, float("nan"), float("inf"), "10"):
            with self.assertRaises(ValueError, msg=repr(amount)):
                db.set_plan_price(PlanTier.STARTER, "TRY", amount)
        for currency in ("", "T", "TRY1", "12", None):
            with self.assertRaises(ValueError, msg=repr(currency)):
                db.set_plan_price(PlanTier.STARTER, currency, 10)
        db.set_plan_price(PlanTier.STARTER, "eur", 10)
        db.set_plan_price(PlanTier.STARTER, "EUR", 12)  # replaces
        self.assertEqual(db.get_plan_prices(PlanTier.STARTER), {"EUR": 12.0})


SECRET = b"unit-test-secret"


def signed(body: dict | bytes, secret=SECRET, timestamp=None):
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    ts = timestamp or str(int(utcnow().timestamp()))
    return raw, webhook.sign(ts, raw, secret), ts


def event_body(event="payment.succeeded", event_id="evt-1", **extra):
    body = {
        "event_id": event_id,
        "event": event,
        "tenant_id": "a-example-com",
        "site_name": "a.example.com",
        "amount": 250,
        "currency": "TRY",
        "invoice_id": "INV-1",
    }
    body.update(extra)
    return body


class TestSignatureAndNormalizer(unittest.TestCase):
    def test_valid_request_is_accepted(self):
        raw, signature, ts = signed(event_body())
        payload = webhook.normalize_generic(raw, signature, ts, SECRET)
        self.assertEqual(payload.event, webhook.WebhookEvent.PAYMENT_SUCCEEDED)
        self.assertEqual((payload.event_id, payload.site_name, payload.amount, payload.currency), ("evt-1", "a.example.com", 250.0, "TRY"))

    def test_forged_tampered_or_stale_requests_are_refused(self):
        raw, signature, ts = signed(event_body())
        for args in (
            (raw, signature, ts, b"another-secret"),
            (raw.replace(b"250", b"999"), signature, ts, SECRET),
            (raw, "", ts, SECRET),
            (raw, "é" * 64, ts, SECRET),
            (raw, signature, "not-a-number", SECRET),
            (raw, signature, ts, b""),
        ):
            with self.assertRaises(webhook.InvalidSignature, msg=repr(args[1:3])):
                webhook.normalize_generic(*args)

        old_raw, old_signature, old_ts = signed(event_body(), timestamp=str(int(utcnow().timestamp()) - 3600))
        with self.assertRaises(webhook.InvalidSignature):
            webhook.normalize_generic(old_raw, old_signature, old_ts, SECRET)

    def test_signature_binds_the_timestamp(self):
        raw, signature, ts = signed(event_body())
        with self.assertRaises(webhook.InvalidSignature):
            webhook.normalize_generic(raw, signature, str(int(ts) + 1), SECRET)

    def test_malformed_bodies_are_value_errors(self):
        for body in (b"not json", b"[1, 2]", b'"text"', event_body(event="refund.created"), event_body(amount=True),
                     event_body(amount="250"), {k: v for k, v in event_body().items() if k != "event_id"},
                     event_body(site_name=""), event_body(currency=5)):
            raw, signature, ts = signed(body)
            with self.assertRaises(ValueError, msg=repr(body)):
                webhook.normalize_generic(raw, signature, ts, SECRET)


class TestControlPlaneHTTP(ControlPlaneTestCase):
    def setUp(self):
        super().setUp()
        import threading
        from http.server import ThreadingHTTPServer

        self.actions = FakeActions()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), control_plane.make_handler(SECRET, self.actions))
        self.port = self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        db.create_tenant("a.example.com")

    def request(self, method, path, raw=b"", signature="", timestamp="", content_length=None):
        import http.client

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            headers = {"X-Cadro-Signature": signature, "X-Cadro-Timestamp": timestamp}
            if content_length is not None:
                headers["Content-Length"] = content_length
            conn.request(method, path, body=raw if method == "POST" else None, headers=headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read() or b"{}")
        finally:
            conn.close()

    def post(self, body, **kwargs):
        raw, signature, ts = signed(body, **kwargs)
        return self.request("POST", "/webhooks/generic", raw, signature, ts)

    def test_health_and_unknown_paths(self):
        self.assertEqual(self.request("GET", "/healthz"), (200, {"status": "ok"}))
        self.assertEqual(self.request("GET", "/nope")[0], 404)
        self.assertEqual(self.request("POST", "/webhooks/stripe")[0], 404)

    def test_signed_payment_activates_the_tenant_and_a_redelivery_is_a_duplicate(self):
        self.assertEqual(self.post(event_body()), (200, {"outcome": "applied"}))
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.ACTIVE)
        self.assertEqual(self.post(event_body()), (200, {"outcome": "duplicate"}))

    def test_bad_signature_changes_nothing(self):
        status, body = self.post(event_body(), secret=b"wrong")
        self.assertEqual(status, 401)
        self.assertNotIn("secret", json.dumps(body))
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.TRIAL)

    def test_error_statuses(self):
        self.assertEqual(self.post(event_body(site_name="nobody.example.com", tenant_id="nobody-example-com"))[0], 404)
        self.assertEqual(self.post(event_body(tenant_id="other-tenant"))[0], 400)
        self.assertEqual(self.post(b"not json")[0], 400)
        self.assertEqual(self.request("POST", "/webhooks/generic", b"{}", "x", "1", content_length="abc")[0], 400)

    def test_failed_site_action_answers_500_and_the_retry_succeeds(self):
        db.set_tenant_status("a.example.com", TenantStatus.SUSPENDED)
        self.actions.fail_on = ("reactivate", "a.example.com")
        with self.assertLogs("cadro.saas.control_plane", level="ERROR"):
            self.assertEqual(self.post(event_body()), (500, {"error": "processing failed"}))
        self.actions.fail_on = None
        self.assertEqual(self.post(event_body()), (200, {"outcome": "applied"}))
        self.assertEqual(db.get_tenant("a.example.com").status, TenantStatus.ACTIVE)

    def signed_get(self, path, secret=SECRET, timestamp=None):
        ts = timestamp or str(int(utcnow().timestamp()))
        signature = webhook.sign(ts, f"GET {path}".encode(), secret)
        return self.request("GET", path, b"", signature, ts)

    def test_metrics_expose_tenant_and_webhook_counters(self):
        import http.client

        self.post(event_body())  # trial -> active, one applied event
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/metrics")
        response = conn.getresponse()
        text = response.read().decode()
        conn.close()
        self.assertEqual(response.status, 200)
        self.assertIn('cadro_tenants{status="active"} 1', text)
        self.assertIn('cadro_tenants{status="trial"} 0', text)
        self.assertIn('cadro_webhook_events_total{outcome="applied"} 1', text)

    def test_signed_access_lookup(self):
        status, body = self.signed_get("/v1/access/a.example.com")
        self.assertEqual(status, 200)
        self.assertEqual((body["site"], body["status"], body["can_access"]), ("a.example.com", "trial", True))
        db.set_tenant_status("a.example.com", TenantStatus.SUSPENDED)
        self.assertFalse(self.signed_get("/v1/access/a.example.com")[1]["can_access"])

    def test_access_lookup_refuses_unsigned_forged_and_invalid_requests(self):
        self.assertEqual(self.request("GET", "/v1/access/a.example.com")[0], 401)
        self.assertEqual(self.signed_get("/v1/access/a.example.com", secret=b"wrong")[0], 401)
        self.assertEqual(self.signed_get("/v1/access/nobody.example.com")[0], 404)
        self.assertEqual(self.signed_get("/v1/access/A_b")[0], 400)
        # A signature for one site is useless for another.
        ts = str(int(utcnow().timestamp()))
        signature = webhook.sign(ts, b"GET /v1/access/a.example.com", SECRET)
        db.create_tenant("b.example.com")
        self.assertEqual(self.request("GET", "/v1/access/b.example.com", b"", signature, ts)[0], 401)

    def test_secret_comes_from_a_file(self):
        secret_file = Path(self._tmp.name) / "secret"
        secret_file.write_text(SECRET.decode() + "\n", encoding="utf-8")
        with patch.dict(control_plane.os.environ, {"CADRO_WEBHOOK_SECRET_FILE": str(secret_file)}):
            self.assertEqual(control_plane.load_secret(), SECRET)
        with patch.dict(control_plane.os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                control_plane.load_secret()


if __name__ == "__main__":
    unittest.main()
