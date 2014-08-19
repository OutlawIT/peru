#! /usr/bin/env python3

import os
import sys
import tempfile

import docopt

from .error import PrintableError
from .runtime import Runtime
from . import resolver

__doc__ = """\
Usage:
  peru sync [-fqv]
  peru build [-fqv] [<rules>...]
  peru reup [-qv] [<modules>...]
  peru override [list | add <module> <path> | delete <module>]
  peru copy [-fqv] <target> [<dest>]
  peru clean [-f]
  peru (help | --help | --version)

Commands:
  sync      apply imports to the working copy
  build     run build rules in the working copy
  reup      get updated module fields from remotes
  override  replace a remote module with a local copy
  copy      make a copy of the outputs of a build target
  clean     delete imports from the working copy

Options:
  -f --force    overwrite existing files
  -q --quiet    don't print anything
  -v --verbose  print all the things
  -h --help     show help
"""

__version__ = "peru 0.1"


commands_map = {}


def command(*subcommand_list):
    def decorator(f):
        commands_map[tuple(subcommand_list)] = f
        return f
    return decorator


def find_matching_command(args):
    '''If 'peru override add' matches, 'peru override' will also match. Solve
    this by always choosing the longest match. This also means that a command
    like `peru override list`, which has the same effect as the shorter
    `peru override`, doesn't need to be separately implemented.'''
    matches = [(cmds, f) for cmds, f in commands_map.items() if
               all(args[cmd] for cmd in cmds)]
    if not matches:
        return None
    longest_cmds, longest_f = matches[0]
    for cmds, f in matches[1:]:
        if len(cmds) > len(longest_cmds):
            longest_cmds, longest_f = cmds, f
    return longest_f


class Main:
    def run(self, argv, env):
        self.args = docopt.docopt(__doc__, argv, help=False)

        matching_command = find_matching_command(self.args)
        if matching_command:
            self.runtime = Runtime(self.args, env)
            matching_command(self)
        else:
            if self.args["--version"]:
                print(__version__)
            else:
                # Print the help.
                print(__doc__, end="")

    @command("sync")
    def do_sync(self):
        self.runtime.local_module.apply_imports(self.runtime)

    @command("build")
    def do_build(self):
        rules = resolver.get_rules(self.runtime, self.args["<rules>"])
        self.runtime.local_module.do_build(self.runtime, rules)

    @command('reup')
    def do_reup(self):
        if not self.args['<modules>']:
            modules = resolver.get_all_modules(self.runtime)
        else:
            modules = resolver.get_modules(
                self.runtime, self.args['<modules>'])
        for module in modules:
            module.reup(self.runtime)

    @command("override")
    def do_override(self):
        for module in sorted(self.runtime.overrides):
            print('{}: {}'.format(module, self.runtime.get_override(module)))

    @command("override", "add")
    def do_override_add(self):
        name = self.args['<module>']
        path = self.args['<path>']
        self.runtime.set_override(name, path)

    @command("override", "delete")
    def do_override_delete(self):
        key = self.args['<module>']
        del self.runtime.overrides[key]

    @command('copy')
    def do_copy(self):
        if not self.args['<dest>']:
            dest = tempfile.mkdtemp(prefix='peru_copy_')
        else:
            dest = self.args['<dest>']
        tree = resolver.get_tree(self.runtime, self.args['<target>'])
        self.runtime.cache.export_tree(tree, dest, force=self.runtime.force)
        if not self.args['<dest>']:
            print(dest)

    @command('clean')
    def do_clean(self):
        # Apply empty imports.
        self.runtime.local_module.apply_imports(self.runtime, {})


def print_red(*args, **kwargs):
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[31m")
    print(*args, **kwargs)
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[39m")


def main(argv=None, env=None):
    if argv is None:
        argv = sys.argv[1:]
    if env is None:
        env = os.environ.copy()
    try:
        Main().run(argv, env)
    except PrintableError as e:
        if e.msg:
            print_red(e.msg)
        sys.exit(1)
