import frappe
from frappe.utils import getdate


def _get_default_structure(company: str | None) -> str | None:
    return "General"


def _get_default_tax_slab(company: str | None) -> str | None:
    return "egy m"


def _create_ssa(employee_name: str, company: str | None, from_date):
    """
    Create & submit a Salary Structure Assignment if the employee doesn't have one.
    Uses default Salary Structure + default Income Tax Slab.
    """
    struct = _get_default_structure(company)
    slab = _get_default_tax_slab(company)

    if not struct:
        frappe.msgprint(
            "Auto-SSA: No default Salary Structure found (is_default=1). Skipping.",
            alert=True,
            indicator="orange",
        )
        return

    # If they already have an assignment, skip.
    if frappe.db.exists("Salary Structure Assignment", {"employee": employee_name}):
        return

    ssa = frappe.new_doc("Salary Structure Assignment")
    # Opening fields (avoid tax prompt)
    ssa.taxable_earnings_till_date = 0
    ssa.tax_deducted_till_date = 0
    ssa.employee = employee_name
    ssa.company = company
    ssa.salary_structure = struct
    if slab:
        ssa.income_tax_slab = slab
    ssa.from_date = getdate(from_date)

    ssa.name = None
    ssa.insert(ignore_permissions=True)

    try:
        ssa.submit()
    except Exception:
        # Some setups prefer keeping SSA in draft; if submit fails, keep as draft and log.
        frappe.log_error(f"Could not submit SSA for {employee_name}", "abchr Auto SSA")


def after_insert_employee(doc, method=None):
    """
    Hook: Employee.after_insert
    Auto-create a Salary Structure Assignment with defaults.
    """
    from_date = doc.get("date_of_joining") or today()
    _create_ssa(doc.name, doc.get("company"), from_date)
