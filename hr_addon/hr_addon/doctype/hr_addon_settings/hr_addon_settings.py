# Copyright (c) 2022, Jide Olayinka and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, os
from frappe.model.document import Document
from frappe import _
from frappe.utils.data import date_diff
from frappe.utils import getdate, today, comma_sep
from frappe.core.doctype.role.role import get_info_based_on_role

class HRAddonSettings(Document):
	def before_save(self):
		# remove the old ics file
		old_doc = self.get_doc_before_save()
		if old_doc:
			old_file_name = old_doc.name_of_calendar_export_ics_file
			if old_file_name != self.name_of_calendar_export_ics_file:
				os.remove("{}/public/files/{}.ics".format(frappe.utils.get_site_path(), old_file_name))

		# remove also the Urlaubskalender.ics, if exist
		if os.path.exists("{}/public/files/Urlaubskalender.ics".format(frappe.utils.get_site_path())):
			os.remove("{}/public/files/Urlaubskalender.ics".format(frappe.utils.get_site_path()))


@frappe.whitelist()
def download_ics_file():
	settings = frappe.get_doc("HR Addon Settings")

	file_name = ""
	if settings.ics_folder_path:
		file_name = os.path.join(settings.ics_folder_path, settings.name_of_calendar_export_ics_file + ".ics")
	else:
		file_name = "{}/public/files/{}.ics".format(frappe.utils.get_site_path(), settings.name_of_calendar_export_ics_file)
	
	if os.path.exists(file_name):
		with open(file_name, 'r') as file:
			file_content = file.read()
		return file_content
	else:
		frappe.throw(f"File '{file_name}' not found.")


# ----------------------------------------------------------------------
# WORK ANNIVERSARY REMINDERS SEND TO EMPLOYEES LIST IN HR-ADDON-SETTINGS
# ----------------------------------------------------------------------
def send_work_anniversary_notification():
    """Send Employee Work Anniversary Reminders if 'Send Work Anniversary Reminders' is checked"""
    if not int(frappe.db.get_single_value("HR Addon Settings", "enable_work_anniversaries_notification")):
        return
    
    ############## Sending email to specified employees in HR Addon Settings field anniversary_notification_email_list
    emp_email_list = frappe.db.get_all("Employee Item", {"parent": "HR Addon Settings", "parentfield": "anniversary_notification_email_list"}, "employee")
    recipients = []
    for employee in emp_email_list:
        employee_doc = frappe.get_doc("Employee", employee)
        employee_email = employee_doc.get("user_id") or employee_doc.get("personal_email") or employee_doc.get("company_email")
        if employee_email:
            recipients.append({"employee_email": employee_email, "company": employee_doc.company})
        else:
            frappe.throw(_("Email not set for {0}".format(employee)))

    if not recipients:
        frappe.throw(_("Recipient Employees not set in field 'Anniversary Notification Email List'"))

    joining_date = today()
    employees_joined_today = get_employees_having_an_event_on_given_date("work_anniversary", joining_date)
    send_emails(employees_joined_today, recipients, joining_date)

    ############## Sending email to specified employees with Role in HR Addon Settings field anniversary_notification_email_recipient_role
    email_recipient_role = frappe.db.get_single_value("HR Addon Settings", "anniversary_notification_email_recipient_role")
    notification_x_days_before = int(frappe.db.get_single_value("HR Addon Settings", "notification_x_days_before"))
    joining_date = frappe.utils.add_days(today(), notification_x_days_before)
    employees_joined_seven_days_later = get_employees_having_an_event_on_given_date("work_anniversary", joining_date)
    if email_recipient_role:
        role_email_recipients = []
        users_with_role = get_info_based_on_role(email_recipient_role, field="email")
        for user in users_with_role:
            emp_data = frappe.get_cached_value("Employee", {"user_id": user}, ["company", "user_id"], as_dict=True)
            if emp_data:
                role_email_recipients.extend([{"employee_email": emp_data.get("user_id"), "company": emp_data.get("company")}])
            else:
                # leave approver not set
                pass
                # frappe.msgprint(cstr(anniversary_person))

        if role_email_recipients:
            send_emails(employees_joined_seven_days_later, role_email_recipients, joining_date)

    ############## Sending email to specified employee leave approvers if HR Addon Settings field enable_work_anniversaries_notification_for_leave_approvers is checked
    if int(frappe.db.get_single_value("HR Addon Settings", "enable_work_anniversaries_notification_for_leave_approvers")):
        for company, anniversary_persons in employees_joined_seven_days_later.items():
            for anniversary_person in anniversary_persons:
                if anniversary_person.get("leave_approver"):
                    leave_approver_recipients = [anniversary_person.get("leave_approver")]
                    
                    reminder_text, message = get_work_anniversary_reminder_text_and_message(anniversary_persons, joining_date)
                    send_work_anniversary_reminder(leave_approver_recipients, reminder_text, anniversary_persons, message)

                else:
                    # leave approver not set
                    pass
                    # frappe.msgprint(cstr(anniversary_person))
		

def send_emails(employees_joined_today, recipients, joining_date):

    for company, anniversary_persons in employees_joined_today.items():
        reminder_text, message = get_work_anniversary_reminder_text_and_message(anniversary_persons, joining_date)
        recipients_by_company = [d.get('employee_email') for d in recipients if d.get('company') == company ]
        if recipients_by_company:
            send_work_anniversary_reminder(recipients_by_company, reminder_text, anniversary_persons, message)


def get_employees_having_an_event_on_given_date(event_type, date):
    """Get all employee who have `event_type` on specific_date
    & group them based on their company. `event_type`
    can be `birthday` or `work_anniversary`"""

    from collections import defaultdict

    # Set column based on event type
    if event_type == "birthday":
        condition_column = "date_of_birth"
    elif event_type == "work_anniversary":
        condition_column = "date_of_joining"
    else:
        return

    employees_born_on_given_date = frappe.db.sql("""
            SELECT `personal_email`, `company`, `company_email`, `user_id`, `employee_name` AS 'name', `leave_approver`, `image`, `date_of_joining`
            FROM `tabEmployee`
            WHERE
                DAY({0}) = DAY(%(date)s)
            AND
                MONTH({0}) = MONTH(%(date)s)
            AND
                YEAR({0}) < YEAR(%(date)s)
            AND
                `status` = 'Active'
        """.format(condition_column), {"date": date}, as_dict=1
    )
    grouped_employees = defaultdict(lambda: [])

    for employee_doc in employees_born_on_given_date:
        grouped_employees[employee_doc.get("company")].append(employee_doc)

    return grouped_employees


def get_work_anniversary_reminder_text_and_message(anniversary_persons, joining_date):
    today_date = today()
    if joining_date == today_date:
        days_alias = "Today"
        completed = "completed"

    elif joining_date > today_date:
        days_alias = "{0} days later".format(date_diff(joining_date, today_date))
        completed = "will complete"

    if len(anniversary_persons) == 1:
        anniversary_person = anniversary_persons[0]["name"]
        persons_name = anniversary_person
        # Number of years completed at the company
        completed_years = getdate().year - anniversary_persons[0]["date_of_joining"].year
        anniversary_person += f" {completed} {get_pluralized_years(completed_years)}"
    else:
        person_names_with_years = []
        names = []
        for person in anniversary_persons:
            person_text = person["name"]
            names.append(person_text)
            # Number of years completed at the company
            completed_years = getdate().year - person["date_of_joining"].year
            person_text += f" {completed} {get_pluralized_years(completed_years)}"
            person_names_with_years.append(person_text)

        # converts ["Jim", "Rim", "Dim"] to Jim, Rim & Dim
        anniversary_person = comma_sep(person_names_with_years, frappe._("{0} & {1}"), False)
        persons_name = comma_sep(names, frappe._("{0} & {1}"), False)

    reminder_text = _("{0} {1} at our Company! 🎉").format(days_alias, anniversary_person)
    message = _("A friendly reminder of an important date for our team.")
    message += "<br>"
    message += _("Everyone, let’s congratulate {0} on their work anniversary!").format(persons_name)

    return reminder_text, message


def send_work_anniversary_reminder(recipients, reminder_text, anniversary_persons, message):
    frappe.sendmail(
        recipients=recipients,
        subject=_("Work Anniversary Reminder"),
        template="anniversary_reminder",
        args=dict(
            reminder_text=reminder_text,
            anniversary_persons=anniversary_persons,
            message=message,
        ),
        header=_("Work Anniversary Reminder"),
    )


def get_pluralized_years(years):
    if years == 1:
        return "1 year"
    return f"{years} years"