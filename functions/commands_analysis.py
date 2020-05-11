def get_number_in_args(args, key, default):
    if key not in args:
        return default
    ind = args.index(key)
    args.pop(ind)
    if len(args) <= ind:
        return default
    return int(args.pop(ind))


def is_key_in_args(args, key):
    if key in args:
        args.remove(key)
        return True
    return False
