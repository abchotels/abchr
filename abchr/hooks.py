app_name = "abchr"
app_title = "Abchr"
app_publisher = "darwishdev"
app_description = "hr system edits"
app_email = "a.darwish.dev@gmail.com"
app_license = "mit"

override_doctype_class = {
    "Salary Slip": "abchr.overrides.salary_slip.CustomSalarySlip",
    "Salary Structure Assignment": "abchr.overrides.salary_structure_assignment.CustomSalaryStructureAssignment",
}
doc_events = {
    "Employee": {
        "after_insert": "abchr.hr.auto_ssa.after_insert_employee",
    }
}
