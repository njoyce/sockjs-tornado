PYTHON=python
# name of the directory to install the virtualenv
VENV=venv

all:
	$(PYTHON) setup.py build

clean:
	rm -rf $(VENV)
	find . -name \*.pyc | xargs rm

#### Dependencies

# install the python dependencies in to the virtualenv
test_deps: $(VENV)/.test_deps

# Create a virtualenv to run the examples/tests
$(VENV):
	virtualenv $(VENV) --python=$(PYTHON)
	$(VENV)/bin/pip install --upgrade pip setuptools

# install the python dependencies in to the virtualenv
$(VENV)/.test_deps: $(VENV)
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip install -r requirements-dev.txt
	$(VENV)/bin/pip install -e .

	touch $(VENV)/.test_deps

# run the sockjs-protocol compatible server
test_server: test_deps
	$(VENV)/bin/python examples/test/test.py
