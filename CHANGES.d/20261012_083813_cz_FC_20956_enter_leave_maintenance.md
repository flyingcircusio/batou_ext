- Deduplicate SymlinkAndCleanup candidates

  It was previously possible to have duplicate entries in the candidates list when appending a "*" to pattern since that would include .etag files in the first glob.glob. The call to extend would then add a second entry while the remove further down only removes one of them, leaving one in the list where each item will be removed.
