"""
Automated Test Suite for Renewal Pipeline Engine
Validates financial precision, pre-scan duplicate locking, term independence,
batch capacity boundaries, and 13-invoice ground-truth reconciliation.
Compatible with both pytest and python's built-in unittest.
"""

import unittest
from decimal import Decimal
import pandas as pd
import sys
import os

# Add parent directory to path to import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.engine import (
    parse_decimal,
    clean_str,
    clean_phone_e164,
    reconcile_renewal_pipeline,
    AuthorityCapacityVerifier,
    load_and_prescan_data
)

class TestRenewalEngine(unittest.TestCase):

    def test_decimal_precision(self):
        self.assertEqual(parse_decimal("5250.00"), Decimal("5250.00"))
        self.assertEqual(parse_decimal("₹10,500"), Decimal("10500"))
        self.assertEqual(parse_decimal("12,000.50"), Decimal("12000.50"))
        self.assertIsNone(parse_decimal("nan"))
        self.assertIsNone(parse_decimal(None))
        self.assertIsNone(parse_decimal("invalid"))

    def test_phone_normalization(self):
        self.assertEqual(clean_phone_e164("9811000001"), "+919811000001")
        self.assertEqual(clean_phone_e164("+971501234567"), "+971501234567")
        self.assertEqual(clean_phone_e164("+14155552671"), "+14155552671")
        self.assertIsNone(clean_phone_e164(None))

    def test_pre_scan_quarantines_all_duplicate_payments(self):
        invoices = pd.DataFrame([
            {"id": "INV-101", "gateway_payment_id": "PAY-REPEAT", "payment_status": "Paid", "net_amount": "6000", "amount": "6000"},
            {"id": "INV-102", "gateway_payment_id": "PAY-REPEAT", "payment_status": "Paid", "net_amount": "6000", "amount": "6000"}
        ])
        dfs = {
            "invoices": invoices,
            "faculty_forms": pd.DataFrame(columns=['invoice_id', 'student_id']),
            "booking_requests": pd.DataFrame(columns=['invoice_id']),
            "schedules": pd.DataFrame(columns=['invoice_id']),
            "roster": pd.DataFrame(columns=['student_id', 'current_classbatch_id', 'max_batch_size', 'active_students_count'])
        }
        prescan = {"duplicate_payment_ids": {"PAY-REPEAT"}, "duplicate_form_inv_ids": set()}
        summary, _, exceptions, _ = reconcile_renewal_pipeline(dfs, prescan)
        
        self.assertEqual(len(exceptions), 2)
        self.assertTrue(all(r['reason_code'] == "ERR_DUPLICATE_PAYMENT_ID" for _, r in exceptions.iterrows()))

    def test_existing_schedule_does_not_close_new_term_invoice(self):
        invoices = pd.DataFrame([
            {"id": "INV-TERM-2", "student_id": "STU-55", "gateway_payment_id": "PAY-T2", "payment_status": "Paid", "net_amount": "6000", "amount": "6000"}
        ])
        dfs = {
            "invoices": invoices,
            "faculty_forms": pd.DataFrame(columns=['invoice_id', 'student_id']),
            "booking_requests": pd.DataFrame(columns=['invoice_id']),
            # Student exists in schedule under previous term's invoice
            "schedules": pd.DataFrame([{"invoice_id": "INV-TERM-1", "student_id": "STU-55", "is_cancelled": "No"}]),
            "roster": pd.DataFrame(columns=['student_id'])
        }
        prescan = {"duplicate_payment_ids": set(), "duplicate_form_inv_ids": set()}
        summary, _, _, _ = reconcile_renewal_pipeline(dfs, prescan)
        
        record = summary.iloc[0]
        self.assertNotEqual(record['outcome_state'], "ALREADY_COMPLETED")
        self.assertEqual(record['outcome_state'], "ORPHANED_INVOICE")

    def test_batch_capacity_locking(self):
        roster = pd.DataFrame([{"current_classbatch_id": "9205", "max_batch_size": 6, "active_students_count": 6}])
        schedules = pd.DataFrame()
        verifier = AuthorityCapacityVerifier(roster, schedules)
        
        can_alloc, reason = verifier.can_allocate("9205")
        self.assertFalse(can_alloc)
        self.assertIn("FULL", reason)

        # Capacity hold simulation
        roster_open = pd.DataFrame([{"current_classbatch_id": "9202", "max_batch_size": 6, "active_students_count": 5}])
        verifier_open = AuthorityCapacityVerifier(roster_open, schedules)
        can_alloc_1, _ = verifier_open.can_allocate("9202")
        self.assertTrue(can_alloc_1)
        # Second attempt should now fail because 1 seat was held
        can_alloc_2, reason_2 = verifier_open.can_allocate("9202")
        self.assertFalse(can_alloc_2)

    def test_ground_truth_13_invoices_reconciliation(self):
        data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ops", "data"))
        dfs, prescan = load_and_prescan_data(data_dir)
        summary, auto, excep, notifications = reconcile_renewal_pipeline(dfs, prescan)

        self.assertEqual(len(summary), 13)
        self.assertEqual(len(notifications), 13)

        expected_map = {
            "84901": ("ALREADY_COMPLETED", "INFO_ALREADY_SCHEDULED", "NONE"),
            "84902": ("READY_FOR_ALLOCATION_REVIEW", "ACTION_ALLOCATION_REQUIRED", "ACADEMIC_OPS"),
            "84903": ("AWAITING_FACULTY_APPROVAL", "ACTION_OPS_VERIFY_FORM", "OPERATIONS"),
            "84904": ("AWAITING_FACULTY_APPROVAL", "ACTION_OPS_VERIFY_FORM", "OPERATIONS"),
            "84905": ("CAPACITY_EXCEPTION", "ERR_BATCH_CAPACITY_FULL", "ACADEMIC_OPS"),
            "84906": ("ORPHANED_INVOICE", "ERR_MISSING_FACULTY_FORM", "FACULTY_OPS"),
            "84907": ("AWAITING_FACULTY_APPROVAL", "ACTION_OPS_VERIFY_FORM", "OPERATIONS"),
            "84908": ("DUPLICATE_FORM_EXCEPTION", "ERR_DUPLICATE_FACULTY_FORMS", "OPS_LEAD"),
            "84909": ("FINANCIAL_EXCEPTION", "ERR_UNDERPAYMENT", "FINANCE"),
            "84910": ("ORPHANED_INVOICE", "ERR_MISSING_FACULTY_FORM", "FACULTY_OPS"),
            "84911": ("PAYMENT_EXCEPTION", "ERR_PAYMENT_NOT_PAID", "FINANCE"),
            "84912": ("AWAITING_PARENT_ACTION", "HOLD_PARENT_SLOT_SELECTION", "PARENT_SUPPORT"),
            "84913": ("RECONCILIATION_EXCEPTION", "ERR_BROKEN_INVOICE_LINK", "OPERATIONS"),
        }

        for _, row in summary.iterrows():
            inv = str(row['invoice_id'])
            self.assertIn(inv, expected_map)
            exp_state, exp_code, exp_owner = expected_map[inv]
            self.assertEqual(row['outcome_state'], exp_state, f"Mismatch on {inv} outcome_state")
            self.assertEqual(row['reason_code'], exp_code, f"Mismatch on {inv} reason_code")
            self.assertEqual(row['owner'], exp_owner, f"Mismatch on {inv} owner")

if __name__ == "__main__":
    unittest.main()

