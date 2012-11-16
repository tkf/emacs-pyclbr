import os
import sys
import re
import pyclbr


def find_files(root):
    for (dirpath, dirnames, filenames) in os.walk(root):
        for fname in filenames:
            yield os.path.join(dirpath, fname)
        for dname in dirnames:
            for fname in find_files(os.path.join(dirpath, dname)):
                yield fname


def subdict(dct, keys):
    return dict((k, dct[k]) for k in keys if k in dct)


class ProjectFinder(object):

    def find_module(self, path):
        """
        Interpret given file path as a Python module path.

        Return a pair ``(modulepath, rootpath)`` wherer ``modulepath``
        is a dot-separated Python module "path" and ``rootpath`` is a
        system file path where you can find the module named
        ``modulepath``.

        This command tries to import a given file as a module.
        Following methods are applied in order:

        1. If the absolute path of a given file starts with one of the
           path in `sys.path`, the given file is imported as a normal
           module.
        2. If there is ``__init__.py`` is in each sub-directory from
           the current working directory and to the file, the given
           file is imported as a normal module.
        3. If there is `setup.py` in one of the parent directory of
           the given file, the file is imported as a module in a
           package located at the location where `setup.py` is.
        4. If file is a valid python module name, the file is imported
           as a stand alone module.
        5. If none of above matches, the file is imported using
           '%run -n' magic command.

        """
        abspath = os.path.abspath(os.path.expanduser(path))

        for method in [self._method_sys_path,
                       self._method_init,
                       self._method_setup_py,
                       self._method_stand_alone]:
            rootpath = method(abspath)
            if rootpath:
                module = self._construct_modulepath(abspath, rootpath)
                return (module, rootpath)
        return (None, abspath)

    @staticmethod
    def _construct_modulepath(abspath, rootpath):
        submods = os.path.relpath(
            os.path.splitext(abspath)[0], rootpath).split(os.path.sep)
        if submods[-1] == '__init__' and len(submods) > 1:
            submods = submods[:-1]
        return '.'.join(submods)

    _valid_module_re = re.compile(r'^[a-zA-z_][0-9a-zA-Z_]*$')

    @staticmethod
    def _has_init(abspath, rootpath):
        subdirs = os.path.relpath(abspath, rootpath).split(os.path.sep)[:-1]
        while subdirs:
            initpath = os.path.join(
                os.path.join(rootpath, *subdirs), '__init__.py')
            if not os.path.exists(initpath):
                return False
            subdirs.pop()
        return True

    @classmethod
    def _is_valid_module_path(cls, abspath, rootpath):
        test = cls._valid_module_re.match
        subpaths = os.path.splitext(
            os.path.relpath(abspath, rootpath))[0].split(os.path.sep)
        return all(test(p) for p in subpaths)

    @classmethod
    def _is_vaild_root(cls, abspath, rootpath):
        """
        Test if relpath of `abspath` from `rootpath` is a valid module path.
        """
        return (cls._is_valid_module_path(abspath, rootpath) and
                cls._has_init(abspath, rootpath))

    @classmethod
    def _method_sys_path(cls, abspath):
        matches = []
        for p in filter(lambda x: x, sys.path):
            if abspath.startswith(p) and cls._is_vaild_root(abspath, p):
                matches.append(p)
        if matches:
            return sorted(matches)[-1]  # longest match

    @classmethod
    def _method_init(cls, abspath):
        cwd = os.getcwd()
        if not abspath.startswith(cwd):
            return
        if cls._is_vaild_root(abspath, cwd):
            return cwd

    @classmethod
    def _method_setup_py(cls, abspath):
        dirs = abspath.split(os.path.sep)
        matches = []
        while len(dirs) > 1:
            dirs.pop()
            rootpath = os.path.sep.join(dirs)
            if (os.path.exists(os.path.join(rootpath, 'setup.py')) and
                cls._is_vaild_root(abspath, rootpath)):
                matches.append(rootpath)
        if matches:
            # Returning shortest path make sense since some project
            # has "sub" setup.py in its package and the real setup.py
            # in its root directory.
            return sorted(matches)[0]  # shortest match

    @classmethod
    def _method_stand_alone(cls, abspath):
        if cls._valid_module_re.match(
                os.path.splitext(os.path.basename(abspath))[0]):
            return os.path.dirname(abspath)

    def find_package(self, path):
        (module, root) = self.find_module(path)
        if not module or '.' not in module:
            return ([module], root)
        top = module.split('.')[0]
        asmodpath = lambda f: self._construct_modulepath(f, root)
        files = find_files(os.path.join(root, top))
        return ([asmodpath(f) for f in files if f.endswith('.py')], root)


class CodeBrowser(object):

    def __init__(self):
        self.projects = ProjectFinder()

    def readmodule_at(self, path):
        (module, root) = self.projects.find_module(path)
        if module:
            return pyclbr.readmodule_ex(module, [root]).items()
        return []  # FIXME: there should be a way to get some info!

    def readpackage_at(self, path):
        (modules, root) = self.projects.find_package(path)
        for module in modules:
            if not module:
                continue
            for item in pyclbr.readmodule_ex(module, [root]).items():
                yield item

    def get_descriptions(self, path):
        keys = ['module', 'name', 'file', 'lineno']
        for (key, desc) in self.readpackage_at(path):
            if key == '__path__':
                continue
            descdict = subdict(vars(desc), keys)
            descdict.update(fullname='{0}.{1}'.format(desc.module, desc.name))
            yield descdict


def pyclbr_epc_server(address, port):
    from sexpdata import return_as
    import epc.server
    cb = CodeBrowser()
    server = epc.server.EPCServer((address, port))
    server.register_function(return_as(list)(cb.get_descriptions))
    server.print_port()
    server.serve_forever()


def run(mode, address, port, path):
    if mode == 'server':
        pyclbr_epc_server(address, port)
    else:
        cb = CodeBrowser()
        for desc in cb.get_descriptions(path):
            print desc['fullname']


def main(args=None):
    from argparse import ArgumentParser
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        '--address', default='localhost')
    parser.add_argument(
        '--port', default=0, type=int)
    parser.add_argument(
        '--mode', default='server', choices=('server', 'cli'))
    parser.add_argument(
        '--path')
    ns = parser.parse_args(args)
    run(**vars(ns))


if __name__ == '__main__':
    main()
