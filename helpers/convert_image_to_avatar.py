import sys


def convert_image_to_avatar(path, to_hex=False):
    with open(path, "rb") as image:
        f = image.read()
    b = bytearray(f)
    if to_hex:
        b = b.hex()
    print(b)
    return b


if __name__ == '__main__':
    args = sys.argv
    if "--help" in args:
        print("Syntax: python convert_image_to_avatar.py [FILE_PATH]\n"
              "Arguments: -h/--hex to convert to hexadecimal value instead of bytes.")
    if "-h" in args or "--hex" in args:
        if "-h" in args:
            args.remove("-h")
        if "--hex" in args:
            args.remove("--hex")
        to_hex = True
    else:
        to_hex = False
    for i, arg in enumerate(args):
        if not i:
            continue
        print(f"Converting '{arg}' to bytes")
        convert_image_to_avatar(arg, to_hex=to_hex)
