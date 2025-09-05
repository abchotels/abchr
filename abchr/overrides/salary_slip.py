from math import ceil
import frappe
from frappe.utils import flt, getdate
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip as CoreSalarySlip
from hrms.payroll.doctype.salary_slip.salary_slip import calculate_tax_by_tax_slab

from hrms.payroll.doctype.salary_slip.salary_slip_loan_utils import (
    cancel_loan_repayment_entry,
    make_loan_repayment_entry,
    process_loan_interest_accrual_and_demand,
    set_loan_repayment,
)
from hrms.payroll.doctype.payroll_period.payroll_period import (
    get_payroll_period,
    get_period_factor,
)


class CustomSalarySlip(CoreSalarySlip):
    """
    Override HRMS projection to:
      - Use ONLY current month's taxable base × 12
      - Ignore previous and future periods entirely
      - Ignore 'income tax deducted till date' when splitting monthly
    """

    def compute_ctc(self):
        return self.current_structured_taxable_earnings_before_exemption * 12

    def compute_annual_deductions_before_tax_calculation(self):
        current_period_exempted_amount = 0
        for d in self.get("deductions"):
            if d.exempted_from_income_tax:
                current_period_exempted_amount += d.amount
        return current_period_exempted_amount * 12 or 0

    def calculate_variable_tax(self, tax_component):
        self.previous_total_paid_taxes = self.get_tax_paid_in_period(
            self.payroll_period.start_date, self.start_date, tax_component
        )

        # Structured tax amount
        eval_locals, default_data = self.get_data_for_eval()
        self.total_structured_tax_amount, __ = calculate_tax_by_tax_slab(
            self.total_taxable_earnings_without_full_tax_addl_components,
            self.tax_slab,
            self.whitelisted_globals,
            eval_locals,
        )

        self.current_structured_tax_amount = self.total_structured_tax_amount / 12

        # Total taxable earnings with additional earnings with full tax
        self.full_tax_on_additional_earnings = 0.0
        if self.current_additional_earnings_with_full_tax:
            self.total_tax_amount, __ = calculate_tax_by_tax_slab(
                self.total_taxable_earnings,
                self.tax_slab,
                self.whitelisted_globals,
                eval_locals,
            )
            self.full_tax_on_additional_earnings = (
                self.total_tax_amount - self.total_structured_tax_amount
            )

        current_tax_amount = (
            self.current_structured_tax_amount + self.full_tax_on_additional_earnings
        )
        if flt(current_tax_amount) < 0:
            current_tax_amount = 0

        self._component_based_variable_tax[tax_component].update(
            {
                "previous_total_paid_taxes": self.previous_total_paid_taxes,
                "total_structured_tax_amount": self.total_structured_tax_amount,
                "current_structured_tax_amount": self.current_structured_tax_amount,
                "full_tax_on_additional_earnings": self.full_tax_on_additional_earnings,
                "current_tax_amount": current_tax_amount,
            }
        )

        return current_tax_amount

    def compute_taxable_earnings_for_year(self):
        # get taxable_earnings, opening_taxable_earning, paid_taxes for previous period
        self.previous_taxable_earnings, exempted_amount = (
            self.get_taxable_earnings_for_prev_period(
                self.payroll_period.start_date,
                self.start_date,
                self.tax_slab.allow_tax_exemption,
            )
        )

        self.previous_taxable_earnings_before_exemption = (
            self.previous_taxable_earnings + exempted_amount
        )

        self.compute_current_and_future_taxable_earnings()

        # Deduct taxes forcefully for unsubmitted tax exemption proof and unclaimed benefits in the last period
        if self.payroll_period.end_date <= getdate(self.end_date):
            self.deduct_tax_for_unsubmitted_tax_exemption_proof = 1
            self.deduct_tax_for_unclaimed_employee_benefits = 1

        # Get taxable unclaimed benefits
        self.unclaimed_taxable_benefits = 0
        if self.deduct_tax_for_unclaimed_employee_benefits:
            self.unclaimed_taxable_benefits = (
                self.calculate_unclaimed_taxable_benefits()
            )

        # Total exemption amount based on tax exemption declaration
        self.total_exemption_amount = self.get_total_exemption_amount()

        # Employee Other Incomes
        self.other_incomes = self.get_income_form_other_sources() or 0.0

        # Total taxable earnings including additional and other incomes
        self.total_taxable_earnings = (
            self.current_structured_taxable_earnings * 12
        ) - self.total_exemption_amount

        # Total taxable earnings without additional earnings with full tax
        self.total_taxable_earnings_without_full_tax_addl_components = (
            self.total_taxable_earnings - self.current_additional_earnings_with_full_tax
        )
