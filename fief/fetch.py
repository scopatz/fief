import os
import sys
import urllib

import async

PROTOCOLS = set(['http', 'https', 'git', 'hg', 'ssh', 'file'])

resources = {}

def _url2local(rsrc):
    name = os.path.split(rsrc)[-1]
    h = hash(rsrc) % 0x100000000
    path = os.path.join('oven', 'i', '{0:x}-{1}'.format(h, name))
    return path

def _canonical_resource(rsrc):
    if isinstance(rsrc, basestring):
        if rsrc.startswith('http://'):
            return [('http', rsrc, _url2local(rsrc))]
        elif rsrc.startswith('https://'):
            return [('https', rsrc, _url2local(rsrc))]
        elif rsrc.startswith('git://') or rsrc.startswith('git@') or \
             rsrc.endswith('.git'):
            return [('git', rsrc, rsrc)]
        else:
            return [('file', rsrc, rsrc)]
            #msg = "protocol not inferred for resource {0!r}"
            #raise ValueError(msg.format(rsrc))
    elif 2 == len(rsrc) and rsrc[0] in PROTOCOLS:
        return [rsrc]
    else:
        rtn = []
        for r in rsrc:
            rtn += _canonical_resource(r) 
        return rtn

def _init(repo_pkgs):
    for pkg, (rsrc, _) in resources.items():
        resources[pkg] = _canonical_resource(rsrc)


def retrieve_http(url, filename, tag=None):
    def hook(nblks, bytes_per_blk, fsize):
        totblks = 1 + fsize / bytes_per_blk
        if not (0 == nblks%(totblks/3) or totblks == nblks):
            return 
        msg = '[GET' + ('] ' if tag is None else ': {0}] '.format(tag))
        if nblks == 0:
            msg += 'downloading {0} -> {1}\n'.format(url, filename)
        else:
            msg += '{0:.1%} completed\n'.format(nblks / float(totblks))
        sys.stderr.write(msg)
    
    def retriever():
        try:
            fname, hdrs = urllib.urlretrieve(url, filename, hook)
            got = True
        except urllib.ContentTooShortError:
            got = False
        return got

    return retriever

retrieve_https = retrieve_http

def retrieve_git(url, filename, tag=None):
    raise RuntimeError('git retrieval not yet implemented')

def retrieve_hg(url, filename, tag=None):
    raise RuntimeError('mercurial retrieval not yet implemented')

def retrieve_ssh(url, filename, tag=None):
    raise RuntimeError('secure shell retrieval not yet implemented')

def retrieve_source_a(src, filename=None, pkg=None):
    glbs = globals()
    filename = filename or src
    rsrcs = resources[src]
    got = False
    for proto, url in rsrcs:
        retriever = glbs['retrieve_' + proto]
        got = yield async.WaitFor(retriever(url, filename, pkg))
        if got:
            break
    yield async.Result(got)
