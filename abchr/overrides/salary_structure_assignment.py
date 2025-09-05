from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import (
    SalaryStructureAssignment as CoreSalaryStructureAssignment,
)


class CustomSalaryStructureAssignment(CoreSalaryStructureAssignment):
    def warn_about_missing_opening_entries(self):
        return None
