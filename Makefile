check:
	pep8 autoflake autoflake.py setup.py
	pep257 autoflake autoflake.py setup.py
	pylint --report=no --include-ids=yes --disable=C0103,F0401,R0903,W0622 --rcfile=/dev/null autoflake.py setup.py
	check-manifest --ignore=.travis.yml,Makefile,test_acid.py,tox.ini
	python setup.py --long-description | rst2html.py --strict > /dev/null
	scspell autoflake autoflake.py setup.py test_autoflake.py README.rst

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
