from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils.data import date_diff
from frappe.utils import getdate, today, comma_sep, date_diff
from frappe.core.doctype.role.role import get_info_based_on_role
from frappe.query_builder import DocType

# ----------------------------------------------------------------------
# WORK ANNIVERSARY REMINDERS SEND TO EMPLOYEES LIST IN HR-ADDON-SETTINGS
# ----------------------------------------------------------------------
def send_work_anniversary_notification():
    hr_addon_settings = frappe.get_single("HR Addon Settings")
    if not hr_addon_settings.enable_work_anniversaries_notification:
        return
    
    """
        Sending email to employees set in HR Addon Settings field anniversary_notification_email_list.
        Filtering recipient employees from just in case employees inactive at some later point in time.
    """
    Employee = DocType("Employee")
    EmployeeItem = DocType("Employee Item")
    emp_email_list = (
        frappe.qb.from_(Employee)
        .join(EmployeeItem)
        .on(Employee.name == EmployeeItem.employee)
        .where(
            (Employee.status == "Active") &
            (EmployeeItem.parent == "HR Addon Settings") &
            (EmployeeItem.parentfield == "anniversary_notification_email_list")
        )
        .select(Employee.name, Employee.user_id, Employee.personal_email, Employee.company_email, Employee.company)
    ).run(as_dict=True)

    recipients = []
    for employee in emp_email_list:
        employee_email = employee.get("user_id") or employee.get("personal_email") or employee.get("company_email")
        if employee_email:
            recipients.append({"employee_email": employee_email, "company": employee.company})

    joining_date = today()
    employees_joined_today = get_employees_having_an_event_on_given_date("work_anniversary", joining_date)
    send_work_anniversary_reminder(employees_joined_today, recipients, joining_date)

    """
        Sending email to specified employees with Role in HR Addon Settings field anniversary_notification_email_recipient_role
    """
    email_recipient_role = hr_addon_settings.anniversary_notification_email_recipient_role
    notification_x_days_before = hr_addon_settings.notification_x_days_before
    joining_date = frappe.utils.add_days(today(), notification_x_days_before)
    employees_joined_seven_days_later = get_employees_having_an_event_on_given_date("work_anniversary", joining_date)
    if email_recipient_role:
        role_email_recipients = []
        users_with_role = get_info_based_on_role(email_recipient_role, field="email")
        for user in users_with_role:
            user_data = frappe.get_cached_value("Employee", {"user_id": user, "status": "Active"}, ["company"], as_dict=True)
            if user_data:
                role_email_recipients.extend([{"employee_email": user, "company": user_data.get("company")}])
            else:
                # TODO: if user not found in employee, then what?
                pass

        send_work_anniversary_reminder(employees_joined_seven_days_later, role_email_recipients, joining_date)

    """
        Sending email to specified employee leave approvers if HR Addon Settings field 
        enable_work_anniversaries_notification_for_leave_approvers is checked
    """
    if int(hr_addon_settings.enable_work_anniversaries_notification_for_leave_approvers):
        leave_approvers_email_list = {}
        for company, anniversary_persons in employees_joined_seven_days_later.items():
            leave_approvers_email_list.setdefault(company, {"leave_approver_missing": [], "leave_approver_not_active": []})
            for anniversary_person in anniversary_persons:
                leave_approver = anniversary_person.get("leave_approver")
                if leave_approver:
                    if frappe.db.exists("Employee", {"user_id": leave_approver, "status": "Active"}):
                        approver_key = leave_approver
                    else:
                        approver_key = "leave_approver_not_active"

                else:
                    approver_key = "leave_approver_missing"

                leave_approvers_email_list[company].setdefault(approver_key, [])
                leave_approvers_email_list[company][approver_key].append(anniversary_person)

        for company, leave_approvers_email_list_by_company in leave_approvers_email_list.items():
            for leave_approver, anniversary_persons in leave_approvers_email_list_by_company.items():
                if leave_approver not in ["leave_approver_missing", "leave_approver_not_active"]:
                    reminder_text, message = get_work_anniversary_reminder_text_and_message(anniversary_persons, joining_date)
                    send_emails(leave_approver, reminder_text, anniversary_persons, message)


def send_work_anniversary_reminder(employees_joined_today, recipients, joining_date):
    for company, anniversary_persons in employees_joined_today.items():
        reminder_text, message = get_work_anniversary_reminder_text_and_message(anniversary_persons, joining_date)
        recipients_by_company = [d.get('employee_email') for d in recipients if d.get('company') == company ]
        if recipients_by_company:
            send_emails(recipients_by_company, reminder_text, anniversary_persons, message)


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


def send_emails(recipients, reminder_text, anniversary_persons, message):
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
