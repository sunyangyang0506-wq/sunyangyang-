.PHONY: validate test stats list check

validate:
	python3 scripts/validate_skills.py

test:
	python3 -m unittest discover -s tests -p "test_*.py" -v

stats:
	python3 scripts/skill_stats.py

list:
	python3 scripts/install_skill.py --list

check: validate test
