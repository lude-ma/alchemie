# -*- coding: utf-8 -*-


import cPickle
from cPickle import PickleError
import glob
import gzip
import os.path
from os import remove
import re
from subprocess import check_output, CalledProcessError, call
import importlib
import warnings

checkpoint_file_re = re.compile("checkpoint-(\d+).pkl.gz")


def idx_from_checkpoint(fn):
    """Given a checkpoint filename, return the index of it.

    Parameters
    ----------

    fn : string
        Of the form ``checkpoint-<somenumberhere>.pkl.gz``.

    Returns
    -------

    idx : int
        Integer of the index file.

    Examples
    --------

    >>> idx_from_checkpoint('checkpoint-12.pkl.gz')
    12
    >>> idx_from_checkpoint('checkpoint-012.pkl.gz')
    12
    >>> idx_from_checkpoint('checkpoint-1.pkl.gz')
    1
    >>> idx_from_checkpoint('checkpoasdhasint-1.pkl.gz')
    Traceback (most recent call last):
        ...
    ValueError: not a valid checkpoint file naming scheme
    """
    r = checkpoint_file_re.search(fn)
    if r is None:
        raise ValueError('not a valid checkpoint file naming scheme')
    return int(r.groups()[0])


def find_checkpoints(dirname):
    cp_files = glob.glob(os.path.join(dirname, 'checkpoint-*.pkl.gz'))
    cp_files.sort(key=idx_from_checkpoint)
    return cp_files


def latest_checkpoint(dirname):
    cps = find_checkpoints(dirname)
    if cps:
        return cps[-1]
    return None


def to_checkpoint(dirname, trainer):
    cp = latest_checkpoint(dirname)

    rm = False
    dumped = False

    if not cp:
        next_cp_idx = 0
        fn = 'checkpoint-0.pkl.gz'
    else:
        next_cp_idx = idx_from_checkpoint(cp) + 1
        fn = 'checkpoint-%i.pkl.gz' % next_cp_idx
        rm = True

    with gzip.open(os.path.join(dirname, fn), 'w') as fp:
        if hasattr(trainer.model, 'data'):
            del trainer.data
        if hasattr(trainer.model, 'assumptions'):
            del trainer.model.assumptions

        try:
            cPickle.dump(trainer, fp, protocol=2)
            dumped = True
        except PickleError:
            raise

        # there is something to be removed and it can be removed because
        # something newer is available
        if rm and dumped:
            remove(os.path.join(dirname, cp))

    return next_cp_idx


def git_log(modules):
    """Given a list of module names, it prints out the version (if
    available), and, if git is available, potential uncommitted changes as
    well as the latest commit and the current branch.

    Parameters
    ----------

    module : list
        List of strings of module names. Note: It will not be checked whether
        such a module exists.

    Returns
    -------

    gitlog : string
        Nicely formatted string holding the information about the packages.
    """

    gitlog = ''

    # check if git works.
    try:
        check_output(["git", "--version"])
        git = True
    except CalledProcessError:
        message = "'git --version' failed. Probably no git available."
        warnings.warn(message)
        gitlog += message
        git = False

    prev_path = os.getcwd()

    for m in modules:
        # add some new lines after last module
        if gitlog:
            gitlog += '\n\n\n\n'

        modinfo = '%s\n-----\n' % m
        mod = importlib.import_module(m)
        modpath = os.path.dirname(mod.__file__)
        os.chdir(modpath)

        if hasattr(mod, '__version__'):
            modinfo += 'Version:\n' + mod.__version__ + '\n\n'

        # return code zero of call indicates that we have a git repository
        is_repo = not bool(call('git rev-parse --is-inside-work-tree',
                           stdout=open(os.devnull, 'w'),
                           stderr=open(os.devnull, 'w')))

        if git and is_repo:
            uncommitted = check_output(['git', 'diff-index', 'HEAD'])
            if uncommitted:
                # delete some unnecessary output
                files = ''
                for line in uncommitted[:-1].split('\n'):
                    f = line.split('\t')[1]
                    files += f + '\n'
                modinfo += 'WARNING: uncommitted changes in module %s\n\n' \
                           'The following files have uncommitted changes:\n' \
                           '%s\n' % (m, files)

            modinfo += 'Latest commit:\n%s\n' % check_output(
                ['git', 'log','-1'])
            modinfo += 'Current branch:\n%s' % check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"]).split('\n')[0]

        gitlog += modinfo

    os.chdir(prev_path)
    return gitlog
