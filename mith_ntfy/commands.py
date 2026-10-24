import click
import frappe
from frappe.commands import pass_context


@click.command("rename-from-ntfynext")
@pass_context
def rename_from_ntfynext_cmd(context):
	"""Move this site from the old app name (ntfynext) to mith_ntfy. Run once, before migrate."""
	from mith_ntfy.patches.rename_from_ntfynext import execute

	for site in context.sites:
		frappe.init(site=site)
		frappe.connect()
		try:
			execute()
			click.echo(f"{site}: now on mith_ntfy; run `bench --site {site} migrate`")
		finally:
			frappe.destroy()


commands = [rename_from_ntfynext_cmd]
