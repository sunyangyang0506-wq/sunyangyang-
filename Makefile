.PHONY: validate eval test stats list package check
validate:
	python3 scripts/validate_skills.py
eval:
	python3 scripts/eval_golden.py --validate-only
test:
	python3 -m unittest discover -s skills/xiaohongshu-publish-orchestrator/tests -p "test_*.py" -v
	python3 -m unittest discover -s tests -p "test_*.py" -v
stats:
	python3 scripts/skill_stats.py
list:
	python3 scripts/install_skill.py --list
package:
	python3 scripts/package_release.py --output dist
check: validate eval test
