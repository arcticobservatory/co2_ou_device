import os

def mkdirs(path):
    pathparts = path.split("/")

    created = []

    for i in range(3, len(pathparts)+1):
        curpath = "/".join(pathparts[0:i])
        try:
            os.mkdir(curpath)
            created += [curpath]
        except OSError as e:
            if "file exists" in str(e): pass
            else: raise e

    return created

def rm_recursive(path):
    try:
        # Try as normal file
        os.remove(path)
        print("Removed file", path)
    except OSError:
        # Try as directory
        try:
            contents = os.listdir(path)
            for c in contents:
                rm_recursive(path+"/"+c)
            os.rmdir(path)
            print("Removed dir ", path)
        except OSError as e:
            print(e)
