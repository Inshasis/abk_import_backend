// Copyright (c) 2023, Akhilam INC and contributors
// For license information, please see license.txt

frappe.ui.form.on('CheckIn-Out', {
	refresh: function(frm) {
		// frm.add_custom_button("Visit" , function(){
		// 	frappe.call({
		// 		method: "sales_application_plugin.api.sales.get_sales_hierarchy",
		// 		args: {
		// 			"label" : "RSM",
		// 			"parent" : "RSM",
		// 		},
		// 		freeze: true,
		// 		callback: function (r) {
		// 			console.log(r.message);
		// 		}
		// 	});
		// });
	}
});
