"""
Runs all tests in a directory
"""

import sys
import uos

import unittest

def find_test_modules(pathdir):
    for entry in uos.ilistdir(pathdir):
        ename = entry[0]
        fullname = pathdir + "/" + ename
        if ename.startswith("test_") and ename.endswith(".py"):
            modname = ename.replace(".py", "")
            yield modname

def test_cases(m):
    """ List TestCase classes in a module object

    Taken from the unittest main method.
    """
    for tn in dir(m):
        c = getattr(m, tn)
        if isinstance(c, object) and isinstance(c, type) and issubclass(c, unittest.TestCase):
            yield c

def run_all_tests_in_dirs(pathdirs):
    suite = unittest.TestSuite()
    for pathdir in pathdirs:
        for modname in find_test_modules(pathdir):
            mod = __import__(modname)
            for case in test_cases(mod):
                suite.addTest(case)

    runner = unittest.TestRunner()
    result = runner.run(suite)
    return result

def massage_args(arg_dirs=[]):
    if isinstance(arg_dirs, str):
        arg_dirs = [arg_dirs]

    if arg_dirs == []:
        arg_dirs = sys.path

    return arg_dirs

class TestTestAll(unittest.TestCase):

    def test_massage_args(self):
        self.assertEqual(massage_args("single_name"), ["single_name"])
        self.assertEqual(massage_args(), sys.path)

if __name__ == "__main__":
    result = run_all_tests_in_dirs(massage_args(sys.argv[1:]))
    sys.exit(result.failuresNum > 0)
