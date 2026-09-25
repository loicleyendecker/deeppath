Rewrite path parsing and traversal: path segments are classified once per
call instead of on every node visited. Wildcard reads are up to 28% faster
and bracket-indexed ``dset`` up to 3x faster.
