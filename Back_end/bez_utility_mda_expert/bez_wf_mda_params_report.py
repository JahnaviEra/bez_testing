import json, logging, datetime
from dateutil.relativedelta import relativedelta

# import from bez resources
from bez_utility.bez_utils_aws import _get_record_from_table

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _wf_mda_params_report(event):
    try:
        agent_int_uid = event.get("agent_int_uid")
        reporting_date = event.get('user_prompt')
        if not agent_int_uid:
            raise Exception((f"Workflow Error: Please select an agent to continue to identify reports."))
        if not reporting_date:
            raise Exception((f"Workflow Error: Please select a reporting date to continue to identify reports."))

        input_date = datetime.datetime.strptime(reporting_date, "%Y-%m-%d").date()

        # Calculate required dates
        current_month_start = input_date.replace(day=1)
        prior_month_start = (current_month_start - datetime.timedelta(days=1)).replace(day=1)
        prior_month_end = current_month_start - datetime.timedelta(days=1)
        next_month_start = current_month_start + relativedelta(months=1)
        current_month_end = next_month_start - datetime.timedelta(days=1)
        current_ytd_start = input_date.replace(month=1, day=1)

        prior_year_same_month_start = current_month_start - relativedelta(years=1)
        prior_year_same_month_end = prior_year_same_month_start + relativedelta(months=1, days=-1)
        prior_year_prior_month_start = prior_year_same_month_start - relativedelta(months=1)
        prior_year_prior_month_end = prior_year_same_month_start - datetime.timedelta(days=1)
        prior_year_ytd_start = current_ytd_start - relativedelta(years=1)

        # Format output
        report_date = {
            "Current Month Start": current_month_start.strftime("%Y-%m-%d"),
            "Current Month End": current_month_end.strftime("%Y-%m-%d"),
            "Prior Month Start": prior_month_start.strftime("%Y-%m-%d"),
            "Prior Month End": prior_month_end.strftime("%Y-%m-%d"),
            "Prior Year Current Month Start": prior_year_same_month_start.strftime("%Y-%m-%d"),
            "Prior Year Current Month End": prior_year_same_month_end.strftime("%Y-%m-%d"),
            "Prior Year Prior Month Start": prior_year_prior_month_start.strftime("%Y-%m-%d"),
            "Prior Year Prior Month End": prior_year_prior_month_end.strftime("%Y-%m-%d"),
            "Prior Year to Date Start": prior_year_ytd_start.strftime("%Y-%m-%d"),
            "Current Year to Date Start": current_ytd_start.strftime("%Y-%m-%d")
        }
        logger.info(report_date)
        # Query the DynamoDB table
        data = {
            "table_name": "agent_mda_section_report_map",
            "keys": {"agent_int_uid": agent_int_uid},
            "gsi_name": "agent_int_uid-index"
        }
        records = _get_record_from_table(data)
        print(f"Records:{records}")

        sections = []
        reports = []
        seen_reports = []
        report_id = 0
        for record in records:
            current_report_data = []
            section_title = record['section_title']
            section_order = int(record['section_order'])
            for report in record.get("report_data", []):
                params = {}
                already_exists = False
                report_params = report["params"]
                for key, value in report_params.items():
                    params[key] = report_date.get(value, value) if key in ['start_date', 'end_date'] else value
                report_name = report["report_name"]
                params_key = tuple(sorted(params.items()))
                unique_key = (report_name, params_key)
                for seen_report in seen_reports:
                    if seen_report["unique_key"] == unique_key:
                        current_report_data.append(seen_report["report_data"])
                        already_exists = True
                if already_exists == False:
                    report_data = {"report_id": report_id,
                                   "report_name": report["report_name"],
                                   "params": params
                                   }
                    seen_reports.append({"unique_key": unique_key,
                                         "report_data": report_data})
                    reports.append(report_data)
                    report_id += 1
                    current_report_data.append(report_data)
            sections.append({"section_title": section_title,
                             "section_order": section_order,
                             "report_data": current_report_data})
        return {"reports": reports, "sections": sections}
    except Exception as e:
        raise Exception(f"Workflow Error: {str(e)}")