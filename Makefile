check:
	pycodestyle autoflake.py setup.py
	pylint \
		--reports=no \
		--disable=invalid-name \
		--disable=too-few-public-methods \
		--disable=no-else-return \
		--disable=redefined-builtin \
		--rcfile=/dev/null \
		autoflake.py setup.py
	pydocstyle autoflake.py setup.py
	check-manifest
	python setup.py --long-description | rstcheck -
	scspell autoflake.py setup.py test_autoflake.py README.rst

coverage:
	@coverage erase
	@coverage run test_autoflake.py
	@coverage report
	@coverage html
	@python -m webbrowser -n "file://${PWD}/htmlcov/index.html"

mutant:
	@mut.py --disable-operator RIL -t autoflake -u test_autoflake -mc

readme:
	@restview --long-description --strict
