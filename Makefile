check:
	pep8 autoflake.py setup.py
	pylint \
		--reports=no \
		--disable=invalid-name,no-member,too-few-public-methods \
		--rcfile=/dev/null \
		autoflake.py setup.py
	pep257 autoflake.py setup.py
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
