check:
	pep8 autoflake autoflake.py setup.py
	pylint \
		--reports=no \
		--msg-template='{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}' \
		--disable=C0103,F0401,R0903 \
		--rcfile=/dev/null \
		autoflake.py setup.py
	pep257 autoflake.py setup.py
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
