#!/usr/bin/env bash
set -e

. ./venv/Scripts/activate

export PYTHONPATH=$(pwd)

echo "Creating database"
python scripts/create_db.py

echo "Running unittest."
python -m unittest tests/test_*

echo "Creating alternative version of model/tables.py"
python scripts/rebuild_module.py

echo "Overriding it."
mv lexref/model/tables.py tables_save.py

mv lexref/model/tables_auto.py lexref/model/tables.py

echo "Running same unittests as before with alternative module."
python -m unittest tests/test_*

echo "Building the package."
python setup.py sdist
python setup.py bdist_wheel

echo "Reestablishing the original version of the module model/tables.py"
mv tables_save.py lexref/model/tables.py

rm -rf lexref.egg-info/
rm -rf build

echo -e "\nDone"
