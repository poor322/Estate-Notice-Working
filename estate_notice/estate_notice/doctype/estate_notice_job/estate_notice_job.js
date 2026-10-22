// Copyright (c) 2026, GenEra and contributors
// For license information, please see license.txt

const RESULTS_METHOD = "estate_notice.estate_notice.doctype.estate_notice_job.estate_notice_job";

frappe.ui.form.on("Estate Notice Job", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (!["Queued", "Running"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Re-run"), () => rerun_job(frm));
		}
		render_results(frm);
	},
});

function rerun_job(frm) {
	frappe.confirm(
		__(
			"Re-run this job? Its current Estate Notices will be replaced when the new run finishes."
		),
		() =>
			frappe
				.call({ method: `${RESULTS_METHOD}.rerun`, args: { job: frm.doc.name } })
				.then(() => frm.reload_doc())
	);
}

function render_results(frm) {
	const empty_message = ["Queued", "Running"].includes(frm.doc.status)
		? __("The job is still running.")
		: __("No notices at this confidence level.");

	frappe
		.call({ method: `${RESULTS_METHOD}.get_job_results`, args: { job: frm.doc.name } })
		.then(({ message }) => {
			const notices = message.notices || [];
			set_html(
				frm,
				"high_notices_html",
				notice_grid(
					notices.filter((n) => n.confidence === "High"),
					empty_message
				)
			);
			set_html(
				frm,
				"medium_notices_html",
				notice_grid(
					notices.filter((n) => n.confidence === "Medium"),
					empty_message
				)
			);
			set_html(frm, "raw_results_html", raw_results(frm, message.results));
		});
}

function set_html(frm, fieldname, html) {
	frm.get_field(fieldname).$wrapper.html(html);
}

function notice_grid(notices, empty_message) {
	if (!notices.length) {
		return `<p class="text-muted">${empty_message}</p>`;
	}
	return `<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: var(--padding-md);">
		${notices.map(notice_card).join("")}
	</div>`;
}

function notice_card(notice) {
	const esc = frappe.utils.escape_html;
	const url = `/app/estate-notice/${encodeURIComponent(notice.name)}`;
	const thumbnail = notice.notice_image
		? `<img src="${esc(notice.notice_image)}" alt="${__("Notice image")}" loading="lazy"
			style="width: 100%; height: 160px; object-fit: contain; background: var(--subtle-fg); border-radius: var(--border-radius);">`
		: `<div class="text-muted small" style="height: 160px; display: flex; align-items: center; justify-content: center;
			background: var(--subtle-fg); border-radius: var(--border-radius);">
			${notice.record_level === "Page" ? __("Whole page (not split)") : __("No image")}</div>`;

	const facts = [
		[__("Relevance"), notice.classification],
		[__("Transaction"), notice.transaction_type],
		[__("Property"), notice.property_number],
		[__("Address"), notice.property_address],
		[__("Village"), notice.village],
		[__("Owners"), notice.owner_names],
		[__("Phones"), notice.phone_numbers],
		[__("Objection days"), notice.objection_period_days],
	]
		.filter(([, value]) => value)
		.map(
			([label, value]) =>
				`<div class="small"><span class="text-muted">${label}:</span> ${esc(value)}</div>`
		)
		.join("");

	const title =
		notice.record_level === "Page"
			? __("Page {0}", [notice.page_number])
			: __("Page {0}, notice {1}", [notice.page_number, notice.notice_number]);

	return `<div class="frappe-card" style="padding: var(--padding-sm); display: flex; flex-direction: column; gap: 6px;">
		<a href="${url}">${thumbnail}</a>
		<div class="flex justify-between align-center">
			<a href="${url}" class="bold">${title}</a>
			<span class="indicator-pill ${review_colour(notice.review_status)}">${esc(
		__(notice.review_status)
	)}</span>
		</div>
		<div class="small">${esc(notice.category || __("Uncategorised"))} · ${__("score {0}", [
		notice.score,
	])}</div>
		${facts || `<div class="small text-muted">${__("No fields extracted")}</div>`}
	</div>`;
}

function review_colour(status) {
	return { Confirmed: "green", Rejected: "red", Duplicate: "gray" }[status] || "orange";
}

function raw_results(frm, results) {
	if (!results) {
		return `<p class="text-muted">${__("No results yet.")}</p>`;
	}
	const esc = frappe.utils.escape_html;
	const link = frm.doc.results_json
		? `<p><a href="${esc(frm.doc.results_json)}" target="_blank">${__(
				"Open the attached results file"
		  )}</a></p>`
		: "";
	return `${link}<details>
		<summary>${__("Show formatted JSON")}</summary>
		<pre style="max-height: 500px; overflow: auto; font-size: var(--text-xs);">${esc(
			JSON.stringify(results, null, 2)
		)}</pre>
	</details>`;
}
