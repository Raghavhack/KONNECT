python : python-test env-prep

python-test :
	pytest -q ai_service/tests

env-prep :
	pip install -r ai_service/requirements.txt

