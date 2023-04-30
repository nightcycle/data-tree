source env/Scripts/Activate
pip install $1==$2
pip install $1==$2
sh scripts/to_exe.sh
sh scripts/test.sh
