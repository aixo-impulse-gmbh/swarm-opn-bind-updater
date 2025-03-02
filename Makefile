.PHONY: clean init test

#################################
# Default targes
#################################

all: init test

# Install dependencies
init:
	pip install -r requirements.txt

# Run tests
test:
	py.test

#################################
# Targes to be called explicitely
#################################

# Cleans project
clean:
	# Remove cache directories
	rm -rf __pycache__ .pytest_cache tests/__pycache__ 

	# Uninstall dependencies
	pip freeze | xargs pip uninstall -y
