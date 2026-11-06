.PHONY: test demo check

# Run from the repo root. No virtualenv and no third-party packages.

test:
	python3 -m unittest discover -s tests -v

demo:
	python3 -m gary demo

check:
	python3 -m gary config-check
	python3 -m gary modules
