lint:
	@yapf -pi -r --style='{based_on_style: google, indent_width: 4, column_limit: 120}' **/*.py
	@yapf -pi -r --style='{based_on_style: google, indent_width: 4, column_limit: 120}' *.py
