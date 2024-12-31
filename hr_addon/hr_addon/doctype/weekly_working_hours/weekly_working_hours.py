# Copyright (c) 2022, Jide Olayinka and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate
from frappe.model.naming import make_autoname
from frappe import _

class WeeklyWorkingHours(Document):
	def autoname(self):
		Company = frappe.qb.DocType('Company')
		query = (
			frappe.qb.from_(Company)
			.select(Company.abbr)
			.where(Company.name == self.company)
		).run()

		coy = query[0][0] if query else None
		e_name = self.employee
		name_key = coy+'-.YYYY.-'+e_name+'-.####'
		self.name = make_autoname(name_key)
		self.title_hour= self.name

	def validate(self):
		self.validate_if_employee_is_active()
		self.validate_overlapping_records_in_specific_interval()

	def validate_if_employee_is_active(self):
		if self.employee and frappe.get_value('Employee', self.employee, 'status') != "Active":
			frappe.throw(_("{0} is not active").format(frappe.get_desk_link('Employee', self.employee)))

	def validate_overlapping_records_in_specific_interval(self):
		if not self.valid_from or not self.valid_to:
			frappe.throw("From Date and To Date are required.")
		
		if not self.employee:
			frappe.throw("Employee required.")

		valid_from = getdate(self.valid_from)
		valid_to = getdate(self.valid_to)

		filters = {"valid_from": valid_from, "valid_to": valid_to, "employee": self.employee}

		wwh = frappe.qb.DocType("Weekly Working Hours")
		overlapping_records = (
			frappe.qb.from_(wwh)
			.select(wwh.name)
			.where(
				(
					(wwh.valid_from <= filters["valid_from"])
					& (wwh.valid_to >= filters["valid_to"])
				)
				| (
					(wwh.valid_from >= filters["valid_from"])
					& (wwh.valid_to <= filters["valid_to"])
				)
			)
			.where(wwh.employee == filters["employee"])
			.where(wwh.docstatus == 1)
		)

		if not self.is_new():
			filters["name"] = self.name
			overlapping_records = overlapping_records.where(wwh.name != filters["name"])

		results = overlapping_records.run(as_dict=True)

		if results:
			overlapping_links = "<br> ".join([frappe.get_desk_link("Weekly Working Hours", d.name) for d in results])
			frappe.throw("Following Weekly Working Hours record already exists for {0} for the specified date range:<br> {1}".format(
				frappe.get_desk_link("Employee", self.employee), overlapping_links))


@frappe.whitelist()
def set_from_to_dates():
    # Ensure fiscal year data is present
	FiscalYear = frappe.qb.DocType('Fiscal Year')
	fiscal_year = (
		frappe.qb.from_(FiscalYear)
		.select(FiscalYear.year_start_date ,FiscalYear.year_end_date)
		.where(FiscalYear.disabled == 0)
	).run(as_dict=True)
    
	if not fiscal_year:
		frappe.throw("No active fiscal year found.")
    
	year_start_date = fiscal_year[0].year_start_date
	year_end_date = fiscal_year[0].year_end_date

    # Update the valid_from and valid_to fields
	wwh = frappe.qb.DocType("Weekly Working Hours")
	Employee = frappe.qb.DocType("Employee")

	subquery = (
		frappe.qb.from_(Employee)
		.select(Employee.name)
		.where(Employee.permanent == 1)
	)

	update_query = (
		frappe.qb.update(wwh)
		.set(wwh.valid_from, year_start_date)
		.set(wwh.valid_to, year_end_date)
		.where(wwh.employee.isin(subquery))
	).run()
	
	frappe.db.commit()