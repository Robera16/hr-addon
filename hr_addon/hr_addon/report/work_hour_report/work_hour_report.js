// Copyright (c) 2022, Jide Olayinka and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Work Hour Report"] = {
	"filters": [
		{
			"fieldname":"date_from_filter",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1,
			"width": "35px"
		},
		{
			"fieldname":"date_to_filter",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
			"width": "35px"
		},
		{
			"fieldname":"employee_id",
			"label": __("Employee Id"),
			"fieldtype": "Link",
			"options": "Employee",
			"reqd": 1,
			"width": "35px"
		},
	],
	"formatter": function (value, row, column, data, default_formatter) {
		
		value = default_formatter(value, row, column, data);
		
		if (column.fieldname == "name" ) {
			//if (!(row ===undefined)) console.log('yt: ',row.meta);
			
			if (!(row ===undefined)) {
				//console.log('yt: ',row.length);
				//console.log(row);
				if (row.meta.rowIndex===row.length){
					//console.log('yt: ',row.meta.rowIndex);
					
				}
			}
			
		}
		if (column.fieldname == "total_work_seconds" ) {
			if(value < 0) {
				
				 
					value = "<span style='color:red'>" +'-' + hitt(value ,true) + "</span>";
				
			
			}
			else if(value > 0){
				value = "<span style='color:green'>" + hitt(value,true) + "</span>";
			}
			else{
				value = hitt(value);
			}	
			
		}

		if (column.fieldname == "total_break_seconds" ) {
			if(value < 0) {
				value = "<span style='color:red'>" + hitt(value) + "</span>";
			}
			else if(value > 0){
				value = "<span style='color:green'>" + hitt(value) + "</span>";
			}
			else{
				value = hitt(value);
			}
			
		}

		if (column.fieldname == "actual_working_seconds" ) {
			if(value < 0) {
				value = "<span style='color:red'>" +'-'+ hitt(value,true) + "</span>";
			}
			else if(value > 0){
				value = "<span style='color:green'>" + hitt(value,true) + "</span>";
			}
			else{
				value = hitt(value);
			}
			
		}

		if (column.fieldname == "total_target_seconds" ) {
			value = hitt(value);
		}
		if (column.fieldname == "expected_break_hours" ) {
			value = hitt(value);	
		}

		if (column.fieldname == "diff_log" ) {
			if(value < 0) {
				value = "<span style='color:#FF8C00'>" + hitt(value,true) + "</span>";
				
			}
			else if(value > 0){
				value = "<span style='color:blue'>" + hitt(value,true) + "</span>";
			}
			else{
				value = hitt(value,true);
			}
			
			
		}

		if (column.fieldname == "actual_diff_log" ) {
			if(value < 0) {
				// value = "<span style='color:#FF8C00'>" + hitt(value,true) + "</span>";
				value = "<span style='color:red'>" +"-"+ hitt(value,true) + "</span>";
			}
			else if(value > 0){
				value = "<span style='color:blue'>" + hitt(value,true) + "</span>";
			}
			else{
				value = hitt(value,true);
			}
			
			
		}
		

		return value;
	},
};
hitt = (fir, calDiff=false) => {
    // Handle negative values and calDiff case
	if (fir < 0 && !calDiff) {
        console.log(fir); // Log the negative value
        return fir; // Return the negative value directly
    }

	if (fir < 0 && calDiff) {
		fir = fir.toString().replace(/^-+/, ''); // Convert to positive for display
		
	}

    const d = Number(fir);
	if (d == 0) return "0"; // Return string "0" for zero

    
	
	var h = Math.floor(d / (60 * 60));
	var m = Math.floor(d % (60 * 60) / 60);

	var hDisplay = h > 0 ? h + "h " : "";
	var mDisplay = m > 0 ? m + "m " : "";
	const results = hDisplay + mDisplay;

    // If the original fir value was negative, prepend the negative sign
    return (fir < 0 ? "-" : "") + results; 
};

