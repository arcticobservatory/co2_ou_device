"""
Runs all tests in a directory
"""

import sys
import uos

import unittest

def listdir(path):
    if hasattr(uos, "listdir"):
        return uos.listdir(path)
    elif hasattr(uos, "ilistdir"):
        return [entry[0] for entry in uos.ilistdir(path)]
    else:
        raise Exception("Don't know how to listdir in this uos")

def find_test_modules(pathdir):
    for ename in listdir(pathdir):
        if ename.startswith("test_") and (ename.endswith(".py") or ename.endswith(".mpy")):
            modname = ename.replace(".py", "").replace(".mpy", "")
            yield modname

def test_cases(m):
    """ List TestCase classes in a module object

    Taken from the unittest main method.
    """
    for tn in dir(m):
        c = getattr(m, tn)
        if isinstance(c, object) and isinstance(c, type) and issubclass(c, unittest.TestCase):
            yield c

def main(pathdirs=[]):
    pathdirs = massage_args(pathdirs)
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
    result = main(sys.argv[1:])
    sys.exit(result.failuresNum > 0)
