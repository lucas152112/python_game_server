#!/usr/bin/env python3

from distutils.core import setup
from Cython.Build import cythonize
import os
import sys
import shutil
import argparse

parser = argparse.ArgumentParser(description="make so")
parser.add_argument("-c", "--clean", help="clean py", action="store_true")

args = parser.parse_args()

build_dir = "./build"
build_tmp_dir = build_dir + "/temp"

parent_dir_name = os.path.split(os.path.abspath("."))[1]

out_dir = os.path.abspath(os.path.join(build_dir, parent_dir_name))
cp_dir = os.path.abspath(os.path.abspath("."))

module_path = [
    # "games/pao_de_kuai/rules.py",
    # "games/pao_de_kuai/poker_lib.py",
    # "games/pao_de_kuai/poker.py",
    #
    # "games/pao_hu/pao_hu_zi.py",
    # "games/pao_hu/rule_48.py",
    # "games/pao_hu/rule_68.py",
    # "games/pao_hu/rule_810.py",

    # "games/cs_ma_jiang/rule_cs_ma_jiang.py",
    # "games/cs_ma_jiang/rule_ma_jiang.py",

    # "base/base_judge.py",

    # "games/jin_hua_ma_jiang/rule_ma_jiang.py",
    # "games/jin_hua_ma_jiang/rule_jh_ma_jiang.py",
]

try:
    setup(ext_modules=cythonize(module_path), script_args=["build_ext", "-b", build_dir, "-t", build_tmp_dir])
except Exception as ex:
    print(ex)
    sys.exit(0)

for dir_path, dir_names, file_names in os.walk(out_dir):
    for file_name in file_names:
        abs_path = os.path.join(dir_path, file_name)
        new_path = abs_path.replace(out_dir, cp_dir)
        if os.path.exists(abs_path):
            shutil.copy2(abs_path, new_path)
        else:
            shutil.copy2(abs_path, new_path)

for path in module_path:
    if args.clean:
        os.remove(path)
    c_path = os.path.splitext(path)[0] + ".c"
    if os.path.exists(c_path):
        os.remove(c_path)

# shutil.rmtree(build_dir)

for path in module_path:
    print(path + ": 生成so 成功")
